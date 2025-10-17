"""
ContextForge API Gateway - Main FastAPI application.
Provides unified API for ingestion, querying, and management.
"""

import os
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime

from fastapi import FastAPI, HTTPException, BackgroundTasks, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import requests
import structlog
import base64
import io
from pathlib import Path
import PyPDF2
from docx import Document
from PIL import Image
import uuid

from rag import RAGPipeline
from llm_client import LLMClient
from search_adapter import SearchAdapter

# Configure structured logging
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        structlog.processors.JSONRenderer()
    ],
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    wrapper_class=structlog.stdlib.BoundLogger,
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger()

# Service URLs
VECTOR_INDEX_URL = os.getenv("VECTOR_INDEX_URL", "http://vector-index:8001")
PREPROCESSOR_URL = os.getenv("PREPROCESSOR_URL", "http://preprocessor:8003")
CONNECTOR_URL = os.getenv("CONNECTOR_URL", "http://connector:8002")
WEB_FETCHER_URL = os.getenv("WEB_FETCHER_URL", "http://web-fetcher:8004")
TERMINAL_EXECUTOR_URL = os.getenv("TERMINAL_EXECUTOR_URL", "http://terminal-executor:8006")

# Initialize FastAPI app
app = FastAPI(
    title="ContextForge API Gateway",
    description="Local-first context engine and augment/assistant pipeline",
    version="1.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize RAG pipeline
rag_pipeline = RAGPipeline()


# Pydantic models
class IngestRequest(BaseModel):
    path: str
    recursive: bool = True
    file_patterns: Optional[List[str]] = None
    exclude_patterns: Optional[List[str]] = None


class QueryRequest(BaseModel):
    query: str
    max_tokens: int = 512
    enable_web_search: Optional[bool] = None
    top_k: int = 10
    auto_terminal_mode: bool = False
    auto_terminal_timeout: int = 30
    auto_terminal_whitelist: Optional[List[str]] = None


class SearchRequest(BaseModel):
    query: str
    provider: Optional[str] = None
    num_results: int = 5
    fetch_content: bool = False


class LLMRequest(BaseModel):
    prompt: str
    model: Optional[str] = None
    max_tokens: int = 512
    temperature: float = 0.7


class TerminalRequest(BaseModel):
    command: str
    working_directory: Optional[str] = None
    timeout: int = 30
    environment: Optional[Dict[str, str]] = None
    stream: bool = False


class CommandSuggestionRequest(BaseModel):
    task_description: str
    context: Optional[str] = None
    working_directory: Optional[str] = None


class ChatMessage(BaseModel):
    role: str  # 'user' or 'assistant'
    content: str


class ChatRequest(BaseModel):
    messages: List[ChatMessage]
    max_tokens: int = 1024
    enable_web_search: bool = False
    enable_context: bool = True

class CommitMessageRequest(BaseModel):
    diff: str
    staged_files: List[str]
    branch: str
    recent_commits: List[str]

class CommitMessageResponse(BaseModel):
    message: str
    description: Optional[str] = None
    confidence: float

class FileUploadResponse(BaseModel):
    id: str
    name: str
    type: str
    size: int
    data: str  # base64 encoded
    extractedText: Optional[str] = None
    analysisResult: Optional[str] = None

class FileAnalysisRequest(BaseModel):
    fileId: str
    fileName: str
    fileType: str
    data: str  # base64 encoded


class PromptEnhancementRequest(BaseModel):
    prompt: str
    context: Optional[str] = None
    style: str = "professional"


class PromptEnhancementResponse(BaseModel):
    original: str
    enhanced: str
    suggestions: List[str]
    improvements: List[str]


# Health check endpoint
@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return rag_pipeline.health_check()


# Ingestion endpoints
@app.post("/ingest")
async def ingest_repository(request: IngestRequest, background_tasks: BackgroundTasks):
    """Ingest a repository or directory for indexing."""
    try:
        logger.info("Starting repository ingestion", path=request.path)
        
        # Step 1: Connect to repository
        connector_response = requests.post(
            f"{CONNECTOR_URL}/connect",
            json={
                "path": request.path,
                "recursive": request.recursive,
                "file_patterns": request.file_patterns,
                "exclude_patterns": request.exclude_patterns
            },
            timeout=30
        )
        connector_response.raise_for_status()
        files_data = connector_response.json()
        
        logger.info("Repository connected", num_files=len(files_data.get("files", [])))
        
        # Step 2: Preprocess files
        preprocessor_response = requests.post(
            f"{PREPROCESSOR_URL}/process",
            json={"files": files_data["files"]},
            timeout=60
        )
        preprocessor_response.raise_for_status()
        chunks_data = preprocessor_response.json()
        
        logger.info("Files preprocessed", num_chunks=len(chunks_data.get("chunks", [])))
        
        # Step 3: Index chunks
        index_response = requests.post(
            f"{VECTOR_INDEX_URL}/index/insert",
            json={"chunks": chunks_data["chunks"]},
            timeout=120
        )
        index_response.raise_for_status()
        index_data = index_response.json()
        
        logger.info("Chunks indexed", indexed_count=index_data.get("indexed_count", 0))
        
        return {
            "status": "success",
            "message": "Repository ingested successfully",
            "stats": {
                "files_processed": len(files_data.get("files", [])),
                "chunks_created": len(chunks_data.get("chunks", [])),
                "chunks_indexed": index_data.get("indexed_count", 0)
            },
            "timestamp": datetime.now().isoformat()
        }
        
    except requests.RequestException as e:
        logger.error("Service request failed during ingestion", error=str(e))
        raise HTTPException(status_code=503, detail=f"Service unavailable: {e}")
    except Exception as e:
        logger.error("Ingestion failed", error=str(e))
        raise HTTPException(status_code=500, detail=f"Ingestion failed: {e}")


@app.get("/ingest/status")
async def get_ingestion_status():
    """Get status of ingested repositories."""
    try:
        response = requests.get(f"{VECTOR_INDEX_URL}/index/stats", timeout=10)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        logger.error("Failed to get ingestion status", error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to get status: {e}")


# Query endpoints
@app.post("/query")
async def query_context(request: QueryRequest):
    """Query the context engine for an answer."""
    try:
        logger.info("Processing query", query=request.query, auto_terminal_mode=request.auto_terminal_mode)

        response = rag_pipeline.answer_question(
            question=request.query,
            enable_web_search=request.enable_web_search,
            max_tokens=request.max_tokens
        )

        # Auto-terminal execution if enabled
        auto_terminal_results = []
        if request.auto_terminal_mode:
            logger.info("Auto-terminal mode enabled, extracting commands from response")

            # Extract commands from LLM response
            commands = extract_commands_from_response(response["answer"])

            # Filter commands against whitelist
            whitelist = request.auto_terminal_whitelist or []
            for command in commands:
                if is_command_whitelisted(command, whitelist):
                    logger.info("Executing auto-terminal command", command=command)
                    try:
                        # Execute command via terminal executor
                        exec_response = requests.post(
                            f"{TERMINAL_EXECUTOR_URL}/execute",
                            json={
                                "command": command,
                                "timeout": request.auto_terminal_timeout,
                                "stream": False
                            },
                            timeout=request.auto_terminal_timeout + 10
                        )
                        exec_response.raise_for_status()
                        exec_result = exec_response.json()

                        auto_terminal_results.append({
                            "command": command,
                            "exit_code": exec_result["exit_code"],
                            "stdout": exec_result["stdout"],
                            "stderr": exec_result["stderr"],
                            "execution_time": exec_result["execution_time"],
                            "matched_whitelist": True
                        })

                        logger.info("Auto-terminal command executed",
                                   command=command,
                                   exit_code=exec_result["exit_code"])

                    except Exception as e:
                        logger.error("Auto-terminal command failed", command=command, error=str(e))
                        auto_terminal_results.append({
                            "command": command,
                            "exit_code": -1,
                            "stdout": "",
                            "stderr": f"Execution failed: {str(e)}",
                            "execution_time": 0,
                            "matched_whitelist": True
                        })
                else:
                    logger.warning("Command not in whitelist, skipping", command=command)
                    auto_terminal_results.append({
                        "command": command,
                        "exit_code": -1,
                        "stdout": "",
                        "stderr": "Command not in whitelist",
                        "execution_time": 0,
                        "matched_whitelist": False
                    })

        # Add auto-terminal results to response
        if auto_terminal_results:
            response["auto_terminal_results"] = auto_terminal_results
            response["meta"]["auto_commands_executed"] = len(auto_terminal_results)

        logger.info("Query processed successfully",
                   backend=response["meta"].get("backend"),
                   latency=response["meta"].get("total_latency_ms"),
                   auto_commands=len(auto_terminal_results))

        return response

    except Exception as e:
        logger.error("Query processing failed", error=str(e))
        raise HTTPException(status_code=500, detail=f"Query failed: {e}")


@app.post("/search/vector")
async def search_vector_index(query: str, top_k: int = 10):
    """Search the vector index directly."""
    try:
        response = requests.post(
            f"{VECTOR_INDEX_URL}/search",
            json={"query": query, "top_k": top_k},
            timeout=10
        )
        response.raise_for_status()
        return response.json()
    except Exception as e:
        logger.error("Vector search failed", error=str(e))
        raise HTTPException(status_code=500, detail=f"Vector search failed: {e}")


@app.post("/search/web")
async def search_web(request: SearchRequest):
    """Search the web for additional context."""
    try:
        search_adapter = SearchAdapter()
        result = search_adapter.search(
            query=request.query,
            provider=request.provider,
            num_results=request.num_results,
            fetch_content=request.fetch_content
        )
        return result
    except Exception as e:
        logger.error("Web search failed", error=str(e))
        raise HTTPException(status_code=500, detail=f"Web search failed: {e}")


# LLM endpoints
@app.post("/llm/generate")
async def generate_text(request: LLMRequest):
    """Generate text using the LLM client."""
    try:
        llm_client = LLMClient()
        response = llm_client.generate(
            prompt=request.prompt,
            model=request.model,
            max_tokens=request.max_tokens,
            temperature=request.temperature
        )
        return response
    except Exception as e:
        logger.error("LLM generation failed", error=str(e))
        raise HTTPException(status_code=500, detail=f"LLM generation failed: {e}")


@app.get("/llm/adapters")
async def list_llm_adapters():
    """List available LLM adapters."""
    try:
        llm_client = LLMClient()
        return {
            "available_adapters": llm_client.list_available_adapters(),
            "priority": os.getenv("LLM_PRIORITY", "ollama,mock").split(",")
        }
    except Exception as e:
        logger.error("Failed to list LLM adapters", error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to list adapters: {e}")


# Chat endpoints
@app.post("/chat")
async def chat_conversation(request: ChatRequest):
    """Handle multi-turn chat conversation with context awareness."""
    try:
        logger.info("Processing chat request", messages_count=len(request.messages))

        # Get the latest user message
        if not request.messages or request.messages[-1].role != 'user':
            raise HTTPException(status_code=400, detail="Last message must be from user")

        latest_message = request.messages[-1].content

        # Build conversation context from previous messages
        conversation_context = ""
        if len(request.messages) > 1:
            conversation_context = "Previous conversation:\n"
            for msg in request.messages[:-1]:  # Exclude the latest message
                role_label = "User" if msg.role == "user" else "Assistant"
                conversation_context += f"{role_label}: {msg.content}\n"
            conversation_context += "\nCurrent question: "

        # Combine conversation context with the latest message
        enhanced_query = conversation_context + latest_message

        # Use RAG pipeline for context-aware response if enabled
        if request.enable_context:
            response = rag_pipeline.answer_question(
                question=enhanced_query,
                enable_web_search=request.enable_web_search,
                max_tokens=request.max_tokens
            )

            return {
                "response": response["answer"],
                "context_used": len(response.get("contexts", [])),
                "web_results_used": len(response.get("web_results", [])),
                "meta": response.get("meta", {})
            }
        else:
            # Direct LLM generation without RAG context
            llm_client = LLMClient()

            # Format messages for LLM
            prompt = ""
            for msg in request.messages:
                role_label = "Human" if msg.role == "user" else "Assistant"
                prompt += f"{role_label}: {msg.content}\n"
            prompt += "Assistant: "

            llm_response = llm_client.generate(
                prompt=prompt,
                max_tokens=request.max_tokens,
                temperature=0.7
            )

            return {
                "response": llm_response["text"],
                "context_used": 0,
                "web_results_used": 0,
                "meta": llm_response.get("meta", {})
            }

    except Exception as e:
        logger.error("Chat conversation failed", error=str(e))
        raise HTTPException(status_code=500, detail=f"Chat failed: {e}")


# Git Integration endpoints
@app.post("/git/commit-message")
async def generate_commit_message(request: CommitMessageRequest):
    """Generate AI-powered commit message based on diff and context."""
    try:
        logger.info("Generating commit message",
                   staged_files=len(request.staged_files),
                   branch=request.branch,
                   diff_length=len(request.diff))

        # Analyze the diff to understand the changes
        diff_lines = request.diff.split('\n')
        added_lines = [line for line in diff_lines if line.startswith('+') and not line.startswith('+++')]
        removed_lines = [line for line in diff_lines if line.startswith('-') and not line.startswith('---')]

        # Extract file types and patterns
        file_extensions = set()
        for file_path in request.staged_files:
            if '.' in file_path:
                ext = file_path.split('.')[-1].lower()
                file_extensions.add(ext)

        # Build context for LLM
        context_parts = []
        context_parts.append(f"Branch: {request.branch}")
        context_parts.append(f"Files changed: {', '.join(request.staged_files)}")
        context_parts.append(f"File types: {', '.join(file_extensions) if file_extensions else 'mixed'}")
        context_parts.append(f"Lines added: {len(added_lines)}")
        context_parts.append(f"Lines removed: {len(removed_lines)}")

        if request.recent_commits:
            context_parts.append(f"Recent commits: {'; '.join(request.recent_commits[:3])}")

        # Create prompt for commit message generation
        prompt = f"""Generate a concise, conventional commit message for the following changes:

Context:
{chr(10).join(context_parts)}

Diff (first 2000 characters):
{request.diff[:2000]}

Requirements:
1. Use conventional commit format: type(scope): description
2. Types: feat, fix, docs, style, refactor, test, chore
3. Keep the first line under 50 characters
4. Be specific about what changed
5. Use imperative mood (e.g., "add", "fix", "update")

Generate only the commit message, no explanation."""

        # Generate commit message using LLM
        llm_client = LLMClient()
        llm_response = llm_client.generate(
            prompt=prompt,
            max_tokens=200
        )

        commit_message = llm_response["text"].strip()

        # Parse commit message to separate title and description
        lines = commit_message.split('\n')
        title = lines[0].strip()
        description = '\n'.join(lines[1:]).strip() if len(lines) > 1 else None

        # Calculate confidence based on various factors
        confidence = 0.8  # Base confidence

        # Adjust confidence based on diff quality
        if len(request.diff) < 100:
            confidence -= 0.1  # Very small changes are harder to understand
        elif len(request.diff) > 5000:
            confidence -= 0.1  # Very large changes are complex

        # Adjust confidence based on file types
        if len(file_extensions) == 1:
            confidence += 0.1  # Single file type is clearer
        elif len(file_extensions) > 5:
            confidence -= 0.1  # Many file types are complex

        # Adjust confidence based on conventional commit format
        conventional_types = ['feat', 'fix', 'docs', 'style', 'refactor', 'test', 'chore']
        if any(title.lower().startswith(t) for t in conventional_types):
            confidence += 0.1

        # Ensure confidence is within bounds
        confidence = max(0.1, min(1.0, confidence))

        logger.info("Generated commit message",
                   message=title,
                   confidence=confidence,
                   backend=llm_response["meta"]["backend"])

        return CommitMessageResponse(
            message=title,
            description=description,
            confidence=confidence
        )

    except Exception as e:
        logger.error("Commit message generation failed", error=str(e))
        raise HTTPException(status_code=500, detail=f"Commit message generation failed: {e}")


# File Upload and Processing endpoints
@app.post("/prompts/enhance")
async def enhance_prompt(request: PromptEnhancementRequest):
    """Enhance a user prompt with AI suggestions."""
    try:
        # Build enhancement prompt
        enhancement_prompt = f"""You are an expert prompt engineer. Enhance the following user prompt to make it more effective, clear, and specific.

Original prompt:
{request.prompt}

{f'Context: {request.context}' if request.context else ''}

Style: {request.style}

Please provide:
1. An enhanced version of the prompt that is more specific and effective
2. 2-3 specific suggestions for improvement
3. 2-3 key improvements made

Format your response as JSON with keys: enhanced, suggestions, improvements"""

        # Call LLM
        llm_client = LLMClient()
        response = llm_client.generate(
            prompt=enhancement_prompt,
            max_tokens=500,
            temperature=0.7
        )

        # Parse response
        try:
            import json
            response_text = response.get('text', '')

            # Try to extract JSON from response
            json_start = response_text.find('{')
            json_end = response_text.rfind('}') + 1

            if json_start >= 0 and json_end > json_start:
                json_str = response_text[json_start:json_end]
                parsed = json.loads(json_str)

                return PromptEnhancementResponse(
                    original=request.prompt,
                    enhanced=parsed.get('enhanced', request.prompt),
                    suggestions=parsed.get('suggestions', []),
                    improvements=parsed.get('improvements', [])
                )
        except Exception as parse_error:
            logger.warning(f"Failed to parse LLM response: {parse_error}")

        # Fallback: return basic enhancement
        return PromptEnhancementResponse(
            original=request.prompt,
            enhanced=f"{request.prompt}\n\n[Enhanced with additional context and specificity]",
            suggestions=[
                "Add specific examples or use cases",
                "Include desired output format",
                "Specify any constraints or requirements"
            ],
            improvements=[
                "Made prompt more specific",
                "Added context for better understanding",
                "Included output format guidance"
            ]
        )

    except Exception as e:
        logger.error(f"Prompt enhancement failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Prompt enhancement failed: {str(e)}")


@app.post("/files/upload")
async def upload_file(file: UploadFile = File(...)):
    """Upload and process a file for chat context."""
    try:
        logger.info("File upload started", filename=file.filename, content_type=file.content_type)

        # Read file content
        content = await file.read()

        # Validate file size (10MB max)
        max_size = 10 * 1024 * 1024
        if len(content) > max_size:
            raise HTTPException(status_code=413, detail=f"File size exceeds {max_size / 1024 / 1024}MB limit")

        # Encode to base64
        file_data = base64.b64encode(content).decode('utf-8')

        # Extract text based on file type
        extracted_text = None
        analysis_result = None

        if file.content_type == 'application/pdf':
            extracted_text = extract_text_from_pdf(content)
        elif file.content_type in ['application/vnd.openxmlformats-officedocument.wordprocessingml.document', 'application/msword']:
            extracted_text = extract_text_from_docx(content)
        elif file.content_type.startswith('text/'):
            extracted_text = content.decode('utf-8', errors='ignore')
        elif file.content_type.startswith('image/'):
            analysis_result = analyze_image(content)

        # Generate file ID
        file_id = f"file_{str(uuid.uuid4())[:8]}"

        logger.info("File processed successfully",
                   file_id=file_id,
                   filename=file.filename,
                   extracted_text_length=len(extracted_text) if extracted_text else 0)

        return FileUploadResponse(
            id=file_id,
            name=file.filename,
            type=file.content_type,
            size=len(content),
            data=file_data,
            extractedText=extracted_text,
            analysisResult=analysis_result
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error("File upload failed", error=str(e), filename=file.filename)
        raise HTTPException(status_code=500, detail=f"File upload failed: {e}")


def extract_text_from_pdf(content: bytes) -> str:
    """Extract text from PDF file."""
    try:
        pdf_reader = PyPDF2.PdfReader(io.BytesIO(content))
        text = ""
        for page in pdf_reader.pages:
            text += page.extract_text() + "\n"
        return text.strip()
    except Exception as e:
        logger.error("PDF extraction failed", error=str(e))
        return ""


def extract_text_from_docx(content: bytes) -> str:
    """Extract text from DOCX file."""
    try:
        doc = Document(io.BytesIO(content))
        text = ""
        for paragraph in doc.paragraphs:
            text += paragraph.text + "\n"
        return text.strip()
    except Exception as e:
        logger.error("DOCX extraction failed", error=str(e))
        return ""


# Vision model cache for performance
_vision_model_cache = {}

def analyze_image(content: bytes) -> str:
    """
    Analyze image using tiered vision model strategy.

    Priority order (cost-effective to feature-rich):
    1. CLIP (free, fast, good for general understanding)
    2. BLIP (free, better captions, slightly slower)
    3. Google ViT (free, good classification)
    4. Basic image properties (always available)
    """
    try:
        image = Image.open(io.BytesIO(content))
        # Get image properties
        width, height = image.size
        format_type = image.format
        mode = image.mode

        # Basic image info
        basic_info = f"{format_type} image ({width}x{height}), Color mode: {mode}"

        # Convert PIL image to RGB if needed
        if image.mode != 'RGB':
            image = image.convert('RGB')

        # Try CLIP first (fastest, good results)
        analysis = _try_clip_analysis(image, basic_info)
        if analysis:
            return analysis

        # Try BLIP if CLIP fails (better captions)
        analysis = _try_blip_analysis(image, basic_info)
        if analysis:
            return analysis

        # Try Google ViT if BLIP fails
        analysis = _try_vit_analysis(image, basic_info)
        if analysis:
            return analysis

        # Fallback to basic analysis
        logger.warning("All vision models failed, using basic analysis")
        return f"Image Analysis: {basic_info}"

    except Exception as e:
        logger.error("Image analysis failed", error=str(e))
        return "Image analysis unavailable"


def _try_clip_analysis(image, basic_info: str) -> str:
    """Try CLIP model for image analysis (fastest, free)."""
    try:
        import clip
        import torch

        # Load model from cache or download
        if 'clip' not in _vision_model_cache:
            device = "cuda" if torch.cuda.is_available() else "cpu"
            model, preprocess = clip.load("ViT-B/32", device=device)
            _vision_model_cache['clip'] = (model, preprocess, device)
        else:
            model, preprocess, device = _vision_model_cache['clip']

        # Preprocess image
        image_input = preprocess(image).unsqueeze(0).to(device)

        # Define candidate labels
        candidate_labels = [
            "a photo of a person",
            "a photo of a document",
            "a photo of code",
            "a screenshot",
            "a diagram",
            "a chart",
            "a graph",
            "a table",
            "a photo of nature",
            "a photo of an object",
            "a photo of text",
            "a photo of a building",
            "a photo of a landscape"
        ]

        text_inputs = clip.tokenize(candidate_labels).to(device)

        with torch.no_grad():
            image_features = model.encode_image(image_input)
            text_features = model.encode_text(text_inputs)

            # Normalize features
            image_features /= image_features.norm(dim=-1, keepdim=True)
            text_features /= text_features.norm(dim=-1, keepdim=True)

            # Calculate similarity
            similarity = (100.0 * image_features @ text_features.T).softmax(dim=-1)
            values, indices = similarity[0].topk(3)

        # Format results
        top_labels = [candidate_labels[idx] for idx in indices]
        scores = [f"{v:.1%}" for v in values]
        labels = ", ".join([f"{label} ({score})" for label, score in zip(top_labels, scores)])

        analysis = f"Image Analysis: {basic_info}\nContent: {labels}"
        logger.info("Image analysis completed with CLIP model")
        return analysis

    except Exception as e:
        logger.debug(f"CLIP analysis failed: {str(e)}")
        return None


def _try_blip_analysis(image, basic_info: str) -> str:
    """Try BLIP model for image captioning (better descriptions)."""
    try:
        from transformers import BlipProcessor, BlipForConditionalGeneration

        # Load model from cache or download
        if 'blip' not in _vision_model_cache:
            processor = BlipProcessor.from_pretrained("Salesforce/blip-image-captioning-base")
            model = BlipForConditionalGeneration.from_pretrained("Salesforce/blip-image-captioning-base")
            _vision_model_cache['blip'] = (processor, model)
        else:
            processor, model = _vision_model_cache['blip']

        # Generate caption
        inputs = processor(image, return_tensors="pt")
        out = model.generate(**inputs, max_length=50)
        caption = processor.decode(out[0], skip_special_tokens=True)

        analysis = f"Image Analysis: {basic_info}\nCaption: {caption}"
        logger.info("Image analysis completed with BLIP model")
        return analysis

    except Exception as e:
        logger.debug(f"BLIP analysis failed: {str(e)}")
        return None


def _try_vit_analysis(image, basic_info: str) -> str:
    """Try Google ViT model for image classification (fallback)."""
    try:
        from transformers import pipeline

        # Load model from cache or download
        if 'vit' not in _vision_model_cache:
            classifier = pipeline("image-classification", model="google/vit-base-patch16-224")
            _vision_model_cache['vit'] = classifier
        else:
            classifier = _vision_model_cache['vit']

        # Get predictions
        predictions = classifier(image)
        top_predictions = predictions[:3]
        labels = ", ".join([f"{p['label']} ({p['score']:.1%})" for p in top_predictions])

        analysis = f"Image Analysis: {basic_info}\nClassification: {labels}"
        logger.info("Image analysis completed with ViT model")
        return analysis

    except Exception as e:
        logger.debug(f"ViT analysis failed: {str(e)}")
        return None


# Management endpoints
@app.delete("/index/clear")
async def clear_index():
    """Clear the vector index."""
    try:
        response = requests.delete(f"{VECTOR_INDEX_URL}/index/clear", timeout=30)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        logger.error("Failed to clear index", error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to clear index: {e}")


@app.get("/index/stats")
async def get_index_stats():
    """Get vector index statistics."""
    try:
        response = requests.get(f"{VECTOR_INDEX_URL}/index/stats", timeout=10)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        logger.error("Failed to get index stats", error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to get stats: {e}")


# Configuration endpoints
@app.get("/config")
async def get_configuration():
    """Get current configuration."""
    return {
        "llm_priority": os.getenv("LLM_PRIORITY", "ollama,mock").split(","),
        "enable_web_search": os.getenv("ENABLE_WEB_SEARCH", "True").lower() == "true",
        "vector_top_k": int(os.getenv("VECTOR_TOP_K", "10")),
        "web_search_results": int(os.getenv("WEB_SEARCH_RESULTS", "5")),
        "privacy_mode": os.getenv("PRIVACY_MODE", "local"),
        "services": {
            "vector_index": VECTOR_INDEX_URL,
            "preprocessor": PREPROCESSOR_URL,
            "connector": CONNECTOR_URL,
            "web_fetcher": WEB_FETCHER_URL,
            "terminal_executor": TERMINAL_EXECUTOR_URL
        }
    }


# Terminal execution endpoints
@app.post("/terminal/execute")
async def execute_terminal_command(request: TerminalRequest):
    """Execute a terminal command safely."""
    try:
        logger.info("Executing terminal command", command=request.command)

        response = requests.post(
            f"{TERMINAL_EXECUTOR_URL}/execute",
            json={
                "command": request.command,
                "working_directory": request.working_directory,
                "timeout": request.timeout,
                "environment": request.environment,
                "stream": request.stream
            },
            timeout=request.timeout + 10  # Add buffer for network overhead
        )
        response.raise_for_status()
        return response.json()

    except requests.exceptions.Timeout:
        logger.error("Terminal command timed out", command=request.command)
        raise HTTPException(status_code=408, detail="Command execution timed out")
    except requests.exceptions.RequestException as e:
        logger.error("Terminal command failed", command=request.command, error=str(e))
        raise HTTPException(status_code=500, detail=f"Command execution failed: {e}")


@app.post("/terminal/execute-stream")
async def execute_terminal_command_stream(request: TerminalRequest):
    """Execute a terminal command with streaming output."""
    try:
        logger.info("Streaming terminal command", command=request.command)

        # Forward the streaming request to terminal executor
        response = requests.post(
            f"{TERMINAL_EXECUTOR_URL}/execute-stream",
            json={
                "command": request.command,
                "working_directory": request.working_directory,
                "timeout": request.timeout,
                "environment": request.environment,
                "stream": True
            },
            stream=True,
            timeout=request.timeout + 10
        )
        response.raise_for_status()

        # Stream the response back to client
        from fastapi.responses import StreamingResponse

        def stream_generator():
            for chunk in response.iter_content(chunk_size=1024):
                if chunk:
                    yield chunk

        return StreamingResponse(
            stream_generator(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
            }
        )

    except requests.exceptions.RequestException as e:
        logger.error("Streaming command failed", command=request.command, error=str(e))
        raise HTTPException(status_code=500, detail=f"Streaming execution failed: {e}")


@app.post("/terminal/suggest")
async def suggest_command(request: CommandSuggestionRequest):
    """Suggest terminal commands based on task description using LLM."""
    try:
        logger.info("Generating command suggestions", task=request.task_description)

        # Create a prompt for command suggestion
        context_info = f"\nWorking directory: {request.working_directory}" if request.working_directory else ""
        additional_context = f"\nAdditional context: {request.context}" if request.context else ""

        prompt = f"""You are a helpful assistant that suggests safe terminal commands for development tasks.

Task: {request.task_description}{context_info}{additional_context}

Please suggest 1-3 safe terminal commands that would accomplish this task.
Focus on common development tools like npm, python, git, docker, etc.
Avoid any dangerous commands that could harm the system.
Format your response as a JSON array of command objects with 'command' and 'description' fields.

Example format:
[
  {{"command": "npm install", "description": "Install project dependencies"}},
  {{"command": "npm run build", "description": "Build the project"}}
]"""

        # Use the LLM to generate suggestions
        llm_response = await rag_pipeline.llm_client.generate(
            prompt=prompt,
            max_tokens=512,
            temperature=0.3
        )

        # Try to parse the JSON response
        import json
        try:
            suggestions = json.loads(llm_response["text"])
            if not isinstance(suggestions, list):
                suggestions = [{"command": llm_response["text"], "description": "Generated suggestion"}]
        except json.JSONDecodeError:
            # Fallback if JSON parsing fails
            suggestions = [{"command": llm_response["text"], "description": "Generated suggestion"}]

        return {
            "task": request.task_description,
            "suggestions": suggestions,
            "llm_backend": llm_response.get("meta", {}).get("backend", "unknown")
        }

    except Exception as e:
        logger.error("Command suggestion failed", task=request.task_description, error=str(e))
        raise HTTPException(status_code=500, detail=f"Command suggestion failed: {e}")


@app.get("/terminal/allowed-commands")
async def get_allowed_commands():
    """Get list of allowed terminal commands."""
    try:
        response = requests.get(f"{TERMINAL_EXECUTOR_URL}/allowed-commands", timeout=10)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        logger.error("Failed to get allowed commands", error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to get allowed commands: {e}")


@app.get("/terminal/processes")
async def get_active_processes():
    """Get list of active terminal processes."""
    try:
        response = requests.get(f"{TERMINAL_EXECUTOR_URL}/processes", timeout=10)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        logger.error("Failed to get active processes", error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to get processes: {e}")


@app.delete("/terminal/processes/{process_id}")
async def kill_process(process_id: int):
    """Kill an active terminal process."""
    try:
        response = requests.delete(f"{TERMINAL_EXECUTOR_URL}/processes/{process_id}", timeout=10)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        logger.error("Failed to kill process", process_id=process_id, error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to kill process: {e}")


if __name__ == "__main__":
    import uvicorn
    
    port = int(os.getenv("PORT", "8080"))
    log_level = os.getenv("LOG_LEVEL", "INFO").lower()
    
    uvicorn.run(
        "app:app",
        host="0.0.0.0",
        port=port,
        log_level=log_level,
        reload=False
    )


# Auto-terminal helper functions
def extract_commands_from_response(response_text: str) -> List[str]:
    """Extract terminal commands from LLM response text."""
    import re

    commands = []

    # First, remove code blocks from text to avoid conflicts with inline patterns
    text_without_blocks = re.sub(r'```(?:bash|shell|terminal|sh).*?```', '', response_text, flags=re.DOTALL | re.IGNORECASE)

    # Pattern 1: Code blocks with bash/shell/terminal
    code_block_pattern = r'```(?:bash|shell|terminal|sh)\s*\n(.*?)\n\s*```'
    code_blocks = re.findall(code_block_pattern, response_text, re.DOTALL | re.IGNORECASE)
    for block in code_blocks:
        # Split by lines and filter out comments and empty lines
        lines = [line.strip() for line in block.split('\n')]
        for line in lines:
            if line and not line.startswith('#') and not line.startswith('//'):
                commands.append(line)

    # Pattern 2: Inline code commands (single backticks) - only from text without code blocks
    inline_pattern = r'`([^`\n]+)`'
    inline_matches = re.findall(inline_pattern, text_without_blocks)
    for match in inline_matches:
        # Only include if it looks like a command (starts with common command words)
        command_starters = ['npm', 'python', 'pip', 'git', 'docker', 'ls', 'cd', 'pwd', 'cat', 'grep', 'find']
        if any(match.strip().startswith(starter) for starter in command_starters):
            commands.append(match.strip())

    # Pattern 3: "Run:" or "Execute:" patterns - exclude code block markers
    run_pattern = r'(?:Run|Execute|Command):\s*`?([^`\n]+)`?'
    run_matches = re.findall(run_pattern, text_without_blocks, re.IGNORECASE)
    for match in run_matches:
        clean_match = match.strip()
        # Only include if it looks like a command (starts with common command words)
        command_starters = ['npm', 'python', 'pip', 'git', 'docker', 'ls', 'cd', 'pwd', 'cat', 'grep', 'find']
        if any(clean_match.startswith(starter) for starter in command_starters):
            commands.append(clean_match)

    # Pattern 4: $ prefixed commands
    dollar_pattern = r'\$\s+([^\n]+)'
    dollar_matches = re.findall(dollar_pattern, response_text)
    for match in dollar_matches:
        commands.append(match.strip())

    # Remove duplicates while preserving order
    unique_commands = []
    seen = set()
    for cmd in commands:
        if cmd not in seen:
            unique_commands.append(cmd)
            seen.add(cmd)

    return unique_commands


def is_command_whitelisted(command: str, whitelist: List[str]) -> bool:
    """Check if a command matches the whitelist patterns."""
    if not whitelist:
        return False

    command = command.strip()

    # Exact match
    if command in whitelist:
        return True

    # Pattern matching - check if command starts with any whitelisted pattern
    for pattern in whitelist:
        # Simple prefix matching
        if command.startswith(pattern):
            return True

        # Allow for common variations (e.g., "npm test" matches "npm run test")
        if pattern.startswith('npm ') and command.startswith('npm '):
            # Extract npm command
            pattern_cmd = pattern.split()[1] if len(pattern.split()) > 1 else ''
            command_cmd = command.split()[1] if len(command.split()) > 1 else ''
            if pattern_cmd == command_cmd:
                return True

        # Allow for python variations
        if pattern.startswith('python ') and command.startswith(('python ', 'python3 ')):
            pattern_args = ' '.join(pattern.split()[1:])
            command_args = ' '.join(command.split()[1:])
            if pattern_args == command_args:
                return True

    return False
