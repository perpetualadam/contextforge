"""
ContextForge Feature Routes - New feature endpoints.

Implements API endpoints for:
- #1  Inline code completion (POST /completion)
- #2  Inline editing (POST /inline-edit)
- #3  Multi-file agent mode (POST /agent/execute)
- #7  Project rules support (accepted in existing endpoints)
- #8  Documentation indexing (POST /docs/index, POST /docs/search)
- #9  Image/attachment passthrough (accepted in /chat)
- #10 Smart apply (POST /smart-apply)
- #14 Symbol lookup (POST /symbols/lookup)
- #15 Multi-cursor edit (POST /multi-cursor-edit)
- #20 Composer (POST /composer/start, GET /composer/status/{id})
"""

import os
import sys
import re
import json
import uuid
import logging
import difflib
import threading
from typing import Dict, List, Optional, Any
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

logger = logging.getLogger(__name__)

# Service URLs
VECTOR_INDEX_URL = os.getenv("VECTOR_INDEX_URL", "http://vector-index:8001")
PREPROCESSOR_URL = os.getenv("PREPROCESSOR_URL", "http://preprocessor:8003")
LLM_REQUEST_TIMEOUT = int(os.getenv("LLM_REQUEST_TIMEOUT", "300"))

router = APIRouter()

# ─── Lazy-loaded shared resources ───
_llm_client = None
_rag_pipeline = None

def _get_llm():
    global _llm_client
    if _llm_client is None:
        from llm_client import LLMClient
        _llm_client = LLMClient()
    return _llm_client

def _get_rag():
    global _rag_pipeline
    if _rag_pipeline is None:
        from rag import RAGPipeline
        _rag_pipeline = RAGPipeline()
    return _rag_pipeline


# ═══════════════════════════════════════════════════════════════════════
# #1 Inline Code Completion
# ═══════════════════════════════════════════════════════════════════════

class CompletionRequest(BaseModel):
    prefix: str = Field(..., max_length=50000)
    suffix: str = Field(default="", max_length=20000)
    language: str = Field(default="plaintext")
    file_path: Optional[str] = None
    max_tokens: int = Field(default=128, le=1024)
    privacy_mode: bool = False

class CompletionResponse(BaseModel):
    completion: str
    model: str = "unknown"
    latency_ms: int = 0

@router.post("/completion", response_model=CompletionResponse)
async def inline_completion(req: CompletionRequest):
    """Generate inline code completion given prefix/suffix context."""
    start = datetime.now()
    prompt = f"""Complete the following {req.language} code. Only output the completion text, nothing else.

```{req.language}
{req.prefix}"""

    if req.suffix.strip():
        prompt += f"\n[CURSOR_POSITION]\n{req.suffix}\n```\nComplete at [CURSOR_POSITION]:"
    else:
        prompt += "\n```\nContinue the code:"

    try:
        llm = _get_llm()
        resp = llm.generate(prompt, max_tokens=req.max_tokens)
        completion = resp.get("text", "").strip()
        # Clean up: remove markdown fences if the model wrapped it
        completion = re.sub(r'^```\w*\n?', '', completion)
        completion = re.sub(r'\n?```$', '', completion)

        latency = int((datetime.now() - start).total_seconds() * 1000)
        return CompletionResponse(
            completion=completion,
            model=resp.get("meta", {}).get("backend", "unknown"),
            latency_ms=latency,
        )
    except Exception as e:
        logger.error(f"Completion failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ═══════════════════════════════════════════════════════════════════════
# #2 Inline Editing
# ═══════════════════════════════════════════════════════════════════════

class InlineEditRequest(BaseModel):
    code: str = Field(..., max_length=100000)
    instruction: str = Field(..., max_length=10000)
    language: str = Field(default="plaintext")
    file_path: Optional[str] = None
    context_before: str = Field(default="", max_length=10000)
    context_after: str = Field(default="", max_length=10000)
    project_rules: Optional[str] = None
    privacy_mode: bool = False

class InlineEditResponse(BaseModel):
    edited_code: str
    explanation: str = ""
    model: str = "unknown"

@router.post("/inline-edit", response_model=InlineEditResponse)
async def inline_edit(req: InlineEditRequest):
    """Edit selected code based on a natural language instruction."""
    rules_block = f"\nPROJECT RULES:\n{req.project_rules}\n" if req.project_rules else ""
    prompt = f"""You are a code editor. Apply the following instruction to the code below.
Output ONLY the modified code, no explanations or markdown fences.
{rules_block}
INSTRUCTION: {req.instruction}

CONTEXT BEFORE:
{req.context_before}

CODE TO EDIT:
{req.code}

CONTEXT AFTER:
{req.context_after}

EDITED CODE:"""

    try:
        llm = _get_llm()
        resp = llm.generate(prompt, max_tokens=min(len(req.code) * 3, 8192))
        edited = resp.get("text", "").strip()
        edited = re.sub(r'^```\w*\n?', '', edited)
        edited = re.sub(r'\n?```$', '', edited)

        return InlineEditResponse(
            edited_code=edited,
            model=resp.get("meta", {}).get("backend", "unknown"),
        )
    except Exception as e:
        logger.error(f"Inline edit failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ═══════════════════════════════════════════════════════════════════════
# #3 Multi-file Agent Mode
# ═══════════════════════════════════════════════════════════════════════

class AgentExecuteRequest(BaseModel):
    task: str = Field(..., max_length=50000)
    repo_path: str
    mode: str = Field(default="auto")
    project_rules: Optional[str] = None
    privacy_mode: bool = False
    dry_run: bool = True

class FileChange(BaseModel):
    path: str
    diff: str = ""
    newContent: str = ""
    action: str = "modify"

class AgentExecuteResponse(BaseModel):
    changes: List[FileChange] = []
    plan: str = ""
    status: str = "completed"

@router.post("/agent/execute", response_model=AgentExecuteResponse)
async def agent_execute(req: AgentExecuteRequest):
    """Execute a multi-file agent task with planning and diff generation."""
    import requests as http_requests

    rules_block = f"\nPROJECT RULES:\n{req.project_rules}\n" if req.project_rules else ""

    # Step 1: Get relevant context via RAG
    rag = _get_rag()
    contexts = rag.retrieve_contexts(req.task, top_k=15)
    context_text = rag.format_contexts(contexts)

    # Step 2: Plan the changes
    plan_prompt = f"""You are a code architect. Given the task and codebase context, output a JSON plan.
{rules_block}
TASK: {req.task}

CODEBASE CONTEXT:
{context_text}

Output a JSON object with:
- "plan": a brief description of the approach
- "files": an array of objects, each with:
  - "path": relative file path
  - "action": "modify" | "create" | "delete"
  - "description": what to change

Output ONLY valid JSON:"""

    try:
        llm = _get_llm()
        plan_resp = llm.generate(plan_prompt, max_tokens=4096)
        plan_text = plan_resp.get("text", "").strip()
        # Extract JSON from response
        json_match = re.search(r'\{[\s\S]*\}', plan_text)
        if not json_match:
            return AgentExecuteResponse(plan=plan_text, status="no_changes")
        plan = json.loads(json_match.group())
    except Exception as e:
        logger.error(f"Agent planning failed: {e}")
        raise HTTPException(status_code=500, detail=f"Planning failed: {e}")

    # Step 3: Generate changes for each file
    changes: List[FileChange] = []
    for file_info in plan.get("files", []):
        file_path = file_info.get("path", "")
        action = file_info.get("action", "modify")
        description = file_info.get("description", "")

        full_path = os.path.join(req.repo_path, file_path) if not os.path.isabs(file_path) else file_path

        if action == "delete":
            changes.append(FileChange(path=file_path, action="delete", diff="File deleted"))
            continue

        existing_content = ""
        if os.path.exists(full_path) and action == "modify":
            try:
                with open(full_path, 'r', encoding='utf-8', errors='replace') as f:
                    existing_content = f.read()
            except Exception:
                pass

        edit_prompt = f"""You are a code editor. {'Modify the following file' if existing_content else 'Create the following file'} according to the instruction.
Output ONLY the complete file content, no explanations or markdown fences.

INSTRUCTION: {description}

{'CURRENT FILE CONTENT:' if existing_content else 'Create this new file:'}
{existing_content[:20000] if existing_content else f'(new file: {file_path})'}

COMPLETE NEW FILE CONTENT:"""

        try:
            edit_resp = llm.generate(edit_prompt, max_tokens=8192)
            new_content = edit_resp.get("text", "").strip()
            new_content = re.sub(r'^```\w*\n?', '', new_content)
            new_content = re.sub(r'\n?```$', '', new_content)

            diff_text = ""
            if existing_content:
                diff_lines = list(difflib.unified_diff(
                    existing_content.splitlines(keepends=True),
                    new_content.splitlines(keepends=True),
                    fromfile=file_path, tofile=file_path,
                ))
                diff_text = "".join(diff_lines)

            changes.append(FileChange(
                path=file_path, action=action,
                diff=diff_text, newContent=new_content,
            ))
        except Exception as e:
            logger.error(f"Agent edit failed for {file_path}: {e}")

    return AgentExecuteResponse(
        changes=changes,
        plan=plan.get("plan", ""),
        status="completed",
    )


# ═══════════════════════════════════════════════════════════════════════
# #8 Documentation Indexing
# ═══════════════════════════════════════════════════════════════════════

class DocsIndexRequest(BaseModel):
    url: str
    label: str = ""
    recursive: bool = True
    max_pages: int = Field(default=50, le=200)

class DocsSearchRequest(BaseModel):
    query: str
    top_k: int = Field(default=5, le=20)
    label: Optional[str] = None

_docs_store: Dict[str, List[Dict[str, Any]]] = {}

@router.post("/docs/index")
async def index_docs(req: DocsIndexRequest):
    """Fetch and index external documentation from a URL."""
    import requests as http_requests

    label = req.label or req.url
    pages_indexed = 0

    try:
        # Fetch the page
        resp = http_requests.get(req.url, timeout=30, headers={
            'User-Agent': 'ContextForge/1.0 DocIndexer'
        })
        resp.raise_for_status()
        content = resp.text

        # Simple HTML-to-text extraction
        text = re.sub(r'<script[^>]*>[\s\S]*?</script>', '', content)
        text = re.sub(r'<style[^>]*>[\s\S]*?</style>', '', text)
        text = re.sub(r'<[^>]+>', ' ', text)
        text = re.sub(r'\s+', ' ', text).strip()

        if not text:
            raise HTTPException(status_code=422, detail="No text content found at URL")

        # Chunk the text
        chunks = []
        chunk_size = 1000
        for i in range(0, len(text), chunk_size):
            chunk_text = text[i:i + chunk_size]
            chunks.append({
                "text": chunk_text,
                "meta": {
                    "source": "docs",
                    "url": req.url,
                    "label": label,
                    "chunk_type": "documentation",
                },
                "chunk_id": f"doc_{label}_{i}",
                "source": "docs",
            })

        # Index in vector store
        if chunks:
            http_requests.post(
                f"{VECTOR_INDEX_URL}/index/insert",
                json={"chunks": chunks},
                timeout=60,
            )
            pages_indexed = 1

        # Store in local docs registry
        if label not in _docs_store:
            _docs_store[label] = []
        _docs_store[label].extend(chunks)

        return {"status": "ok", "pages_indexed": pages_indexed, "chunks": len(chunks), "label": label}

    except http_requests.RequestException as e:
        raise HTTPException(status_code=502, detail=f"Failed to fetch URL: {e}")

@router.post("/docs/search")
async def search_docs(req: DocsSearchRequest):
    """Search indexed documentation."""
    import requests as http_requests

    try:
        payload: Dict[str, Any] = {"query": req.query, "top_k": req.top_k * 2}
        resp = http_requests.post(
            f"{VECTOR_INDEX_URL}/search",
            json=payload,
            timeout=30,
        )
        resp.raise_for_status()
        results = resp.json().get("results", [])
        # Filter to docs-only results
        doc_results = [r for r in results if r.get("source") == "docs" or
                       (r.get("meta", {}).get("source") == "docs")]
        if req.label:
            doc_results = [r for r in doc_results if r.get("meta", {}).get("label") == req.label]
        return {"results": doc_results[:req.top_k]}
    except Exception as e:
        logger.error(f"Docs search failed: {e}")
        return {"results": []}


# ═══════════════════════════════════════════════════════════════════════
# #10 Smart Apply
# ═══════════════════════════════════════════════════════════════════════

class SmartApplyRequest(BaseModel):
    file_path: str
    file_content: str = Field(..., max_length=500000)
    code_block: str = Field(..., max_length=100000)
    language: str = Field(default="plaintext")

class SmartApplyResponse(BaseModel):
    start_line: int
    end_line: int
    replacement: str
    new_content: str
    confidence: float = 0.0

@router.post("/smart-apply", response_model=SmartApplyResponse)
async def smart_apply(req: SmartApplyRequest):
    """Intelligently determine where in a file to apply a code block."""
    prompt = f"""You are a code editor assistant. Given a file and a code block, determine WHERE in the file the code block should be inserted or replace existing code.

FILE ({req.language}):
{req.file_content[:30000]}

CODE BLOCK TO APPLY:
{req.code_block}

Output a JSON object with:
- "start_line": 1-based line number where the code should start
- "end_line": 1-based line number where replacement ends (same as start_line for pure insertion)
- "action": "replace" or "insert"
- "confidence": 0.0 to 1.0

Output ONLY valid JSON:"""

    try:
        llm = _get_llm()
        resp = llm.generate(prompt, max_tokens=512)
        text = resp.get("text", "").strip()
        json_match = re.search(r'\{[\s\S]*?\}', text)
        if not json_match:
            raise HTTPException(status_code=422, detail="Could not determine insertion point")

        result = json.loads(json_match.group())
        start = max(1, result.get("start_line", 1))
        end = max(start, result.get("end_line", start))
        confidence = result.get("confidence", 0.5)

        lines = req.file_content.splitlines(keepends=True)
        if result.get("action") == "insert":
            new_lines = lines[:start - 1] + [req.code_block + "\n"] + lines[start - 1:]
        else:
            new_lines = lines[:start - 1] + [req.code_block + "\n"] + lines[end:]

        return SmartApplyResponse(
            start_line=start, end_line=end,
            replacement=req.code_block,
            new_content="".join(new_lines),
            confidence=confidence,
        )
    except json.JSONDecodeError:
        raise HTTPException(status_code=422, detail="Failed to parse LLM response as JSON")
    except Exception as e:
        logger.error(f"Smart apply failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ═══════════════════════════════════════════════════════════════════════
# #14 Symbol Lookup
# ═══════════════════════════════════════════════════════════════════════

class SymbolLookupRequest(BaseModel):
    symbol: str = Field(..., max_length=500)
    file_path: Optional[str] = None
    line: Optional[int] = None
    kind: str = Field(default="definition")  # "definition" or "references"

class SymbolLocation(BaseModel):
    file_path: str
    line: int
    column: int = 0
    content: str = ""

class SymbolLookupResponse(BaseModel):
    location: Optional[SymbolLocation] = None
    references: List[SymbolLocation] = []
    content: str = ""

@router.post("/symbols/lookup", response_model=SymbolLookupResponse)
async def symbol_lookup(req: SymbolLookupRequest):
    """Look up symbol definitions or references using the code graph and vector index."""
    import requests as http_requests

    try:
        # Search for the symbol in the vector index
        search_resp = http_requests.post(
            f"{VECTOR_INDEX_URL}/search",
            json={
                "query": f"{req.symbol} definition",
                "top_k": 20,
                "expand_graph": True,
                "graph_depth": 2,
            },
            timeout=15,
        )
        search_resp.raise_for_status()
        results = search_resp.json().get("results", [])

        if req.kind == "definition":
            # Find the chunk that most likely contains the definition
            for r in results:
                meta = r.get("meta", {})
                text = r.get("text", "")
                chunk_type = meta.get("chunk_type", "")
                symbol_name = meta.get("symbol_name", "") or meta.get("function_name", "") or meta.get("class_name", "")

                if symbol_name == req.symbol or req.symbol in text[:200]:
                    if chunk_type in ("function", "class", "method") or f"def {req.symbol}" in text or f"class {req.symbol}" in text:
                        return SymbolLookupResponse(
                            location=SymbolLocation(
                                file_path=meta.get("file_path", ""),
                                line=meta.get("start_line", 1),
                                content=text[:500],
                            ),
                            content=text[:2000],
                        )
            # Fallback: return the top result
            if results:
                meta = results[0].get("meta", {})
                return SymbolLookupResponse(
                    location=SymbolLocation(
                        file_path=meta.get("file_path", ""),
                        line=meta.get("start_line", 1),
                        content=results[0].get("text", "")[:500],
                    ),
                    content=results[0].get("text", "")[:2000],
                )
        else:
            # Find all references
            refs = []
            seen = set()
            for r in results:
                meta = r.get("meta", {})
                text = r.get("text", "")
                fp = meta.get("file_path", "")
                sl = meta.get("start_line", 1)
                key = f"{fp}:{sl}"
                if key in seen:
                    continue
                seen.add(key)
                if req.symbol in text:
                    refs.append(SymbolLocation(
                        file_path=fp, line=sl,
                        content=text[:200],
                    ))
            return SymbolLookupResponse(references=refs)

    except Exception as e:
        logger.error(f"Symbol lookup failed: {e}")

    return SymbolLookupResponse()


# ═══════════════════════════════════════════════════════════════════════
# #15 Multi-Cursor Edit
# ═══════════════════════════════════════════════════════════════════════

class MultiCursorEditRequest(BaseModel):
    file_content: str = Field(..., max_length=500000)
    instruction: str = Field(..., max_length=10000)
    language: str = Field(default="plaintext")
    file_path: Optional[str] = None

class EditLocation(BaseModel):
    start_line: int
    start_col: int
    end_line: int
    end_col: int
    new_text: str

class MultiCursorEditResponse(BaseModel):
    edits: List[EditLocation] = []

@router.post("/multi-cursor-edit", response_model=MultiCursorEditResponse)
async def multi_cursor_edit(req: MultiCursorEditRequest):
    """Generate multiple simultaneous edits across a file."""
    prompt = f"""You are a code editor. Apply the instruction to ALL matching locations in the file.
Output a JSON array of edit objects, each with:
- "start_line": 1-based line number
- "start_col": 0-based column
- "end_line": 1-based line number
- "end_col": 0-based column
- "new_text": replacement text

INSTRUCTION: {req.instruction}

FILE ({req.language}):
{req.file_content[:30000]}

Output ONLY a valid JSON array:"""

    try:
        llm = _get_llm()
        resp = llm.generate(prompt, max_tokens=4096)
        text = resp.get("text", "").strip()
        json_match = re.search(r'\[[\s\S]*\]', text)
        if not json_match:
            return MultiCursorEditResponse(edits=[])

        edits_raw = json.loads(json_match.group())
        edits = [EditLocation(**e) for e in edits_raw if isinstance(e, dict)]
        # Sort edits bottom-to-top so line numbers don't shift
        edits.sort(key=lambda e: (e.start_line, e.start_col), reverse=True)
        return MultiCursorEditResponse(edits=edits)
    except Exception as e:
        logger.error(f"Multi-cursor edit failed: {e}")
        return MultiCursorEditResponse(edits=[])


# ═══════════════════════════════════════════════════════════════════════
# #20 Composer (Long-Running Agent)
# ═══════════════════════════════════════════════════════════════════════

class ComposerStartRequest(BaseModel):
    task: str = Field(..., max_length=50000)
    repo_path: str
    project_rules: Optional[str] = None
    privacy_mode: bool = False

class ComposerStatusResponse(BaseModel):
    session_id: str
    state: str  # "running", "completed", "failed"
    progress: float = 0.0
    current_step: str = ""
    changes: List[FileChange] = []
    error: Optional[str] = None
    log: List[str] = []

_composer_sessions: Dict[str, Dict[str, Any]] = {}

def _run_composer(session_id: str, task: str, repo_path: str,
                  project_rules: Optional[str], privacy_mode: bool):
    """Run the composer agent in a background thread."""
    session = _composer_sessions[session_id]
    try:
        session["state"] = "running"
        session["log"].append(f"Starting composer for: {task[:100]}")
        session["current_step"] = "Planning"
        session["progress"] = 0.1

        llm = _get_llm()
        rag = _get_rag()

        # Step 1: Plan
        contexts = rag.retrieve_contexts(task, top_k=15)
        context_text = rag.format_contexts(contexts)
        rules = f"\nPROJECT RULES:\n{project_rules}\n" if project_rules else ""

        plan_prompt = f"""You are a software architect planning a multi-step coding task.
{rules}
TASK: {task}

CODEBASE CONTEXT:
{context_text[:10000]}

Create a step-by-step plan as JSON:
{{"steps": [{{"description": "...", "files": ["..."], "action": "modify|create|delete"}}], "summary": "..."}}

Output ONLY valid JSON:"""

        plan_resp = llm.generate(plan_prompt, max_tokens=4096)
        plan_text = plan_resp.get("text", "").strip()
        json_match = re.search(r'\{[\s\S]*\}', plan_text)
        if not json_match:
            session["state"] = "failed"
            session["error"] = "Failed to generate plan"
            return

        plan = json.loads(json_match.group())
        steps = plan.get("steps", [])
        session["log"].append(f"Plan: {plan.get('summary', 'N/A')}")
        session["log"].append(f"Steps: {len(steps)}")

        # Step 2: Execute each step
        changes = []
        for i, step in enumerate(steps):
            session["current_step"] = step.get("description", f"Step {i+1}")
            session["progress"] = 0.1 + 0.8 * (i / max(len(steps), 1))
            session["log"].append(f"Step {i+1}: {step.get('description', '')}")

            for file_path in step.get("files", []):
                full_path = os.path.join(repo_path, file_path) if not os.path.isabs(file_path) else file_path
                existing = ""
                if os.path.exists(full_path):
                    try:
                        with open(full_path, 'r', encoding='utf-8', errors='replace') as f:
                            existing = f.read()
                    except Exception:
                        pass

                edit_prompt = f"""Apply this change to the file. Output ONLY the complete new file content.
{rules}
STEP: {step.get('description', '')}
OVERALL TASK: {task}

FILE ({file_path}):
{existing[:20000] if existing else '(new file)'}

COMPLETE NEW FILE CONTENT:"""

                try:
                    edit_resp = llm.generate(edit_prompt, max_tokens=8192)
                    new_content = edit_resp.get("text", "").strip()
                    new_content = re.sub(r'^```\w*\n?', '', new_content)
                    new_content = re.sub(r'\n?```$', '', new_content)

                    changes.append({
                        "path": file_path,
                        "action": step.get("action", "modify"),
                        "newContent": new_content,
                        "diff": "",
                    })
                except Exception as e:
                    session["log"].append(f"Error editing {file_path}: {e}")

        session["changes"] = changes
        session["state"] = "completed"
        session["progress"] = 1.0
        session["current_step"] = "Done"
        session["log"].append(f"Completed with {len(changes)} file change(s)")

    except Exception as e:
        session["state"] = "failed"
        session["error"] = str(e)
        session["log"].append(f"Error: {e}")

@router.post("/composer/start")
async def composer_start(req: ComposerStartRequest):
    """Start a long-running composer agent session."""
    session_id = str(uuid.uuid4())[:8]
    _composer_sessions[session_id] = {
        "session_id": session_id,
        "state": "starting",
        "progress": 0.0,
        "current_step": "Initializing",
        "changes": [],
        "error": None,
        "log": [],
        "task": req.task,
    }

    thread = threading.Thread(
        target=_run_composer,
        args=(session_id, req.task, req.repo_path, req.project_rules, req.privacy_mode),
        daemon=True,
    )
    thread.start()

    return {"session_id": session_id, "state": "starting"}

@router.get("/composer/status/{session_id}")
async def composer_status(session_id: str):
    """Get the status of a running composer session."""
    session = _composer_sessions.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return session
