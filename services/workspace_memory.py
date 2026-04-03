"""
Explicit, privacy-preserving workspace memories (local JSON files).
Optional; keyed by workspace_id (caller-supplied hash or slug).
"""

from __future__ import annotations

import json
import logging
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

DATA_ROOT = Path(os.getenv("WORKSPACE_MEMORY_DIR", "data/workspace_memories"))
_MAX_MEMORIES = int(os.getenv("WORKSPACE_MEMORY_MAX_ITEMS", "50"))
_MAX_CHARS = int(os.getenv("WORKSPACE_MEMORY_MAX_CHARS", "32000"))


def _sanitize_id(workspace_id: str) -> str:
    w = re.sub(r"[^a-zA-Z0-9_.-]", "_", workspace_id.strip())[:128]
    return w or "default"


def _path(workspace_id: str) -> Path:
    DATA_ROOT.mkdir(parents=True, exist_ok=True)
    return DATA_ROOT / f"{_sanitize_id(workspace_id)}.json"


def load_memories(workspace_id: Optional[str]) -> str:
    """Return concatenated memory lines for RAG system prompt, or empty string."""
    if not workspace_id:
        return ""
    p = _path(workspace_id)
    if not p.is_file():
        return ""
    try:
        raw = json.loads(p.read_text(encoding="utf-8"))
        items = raw.get("memories", [])
        if not isinstance(items, list):
            return ""
        lines = []
        for it in items[:_MAX_MEMORIES]:
            if isinstance(it, str) and it.strip():
                lines.append(it.strip())
            elif isinstance(it, dict):
                t = (it.get("text") or it.get("content") or "").strip()
                if t:
                    lines.append(t)
        text = "\n".join(f"- {ln}" for ln in lines)
        if len(text) > _MAX_CHARS:
            text = text[: _MAX_CHARS] + "\n... (truncated)"
        return text
    except Exception as e:
        logger.warning("workspace_memory load failed: %s", e)
        return ""


def list_memories(workspace_id: str) -> List[Dict[str, Any]]:
    p = _path(workspace_id)
    if not p.is_file():
        return []
    try:
        raw = json.loads(p.read_text(encoding="utf-8"))
        return list(raw.get("memories", []))
    except Exception:
        return []


def save_memories(workspace_id: str, memories: List[Any]) -> None:
    p = _path(workspace_id)
    payload = {"memories": memories[:_MAX_MEMORIES]}
    p.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def append_memory(workspace_id: str, text: str) -> Dict[str, Any]:
    cur = list_memories(workspace_id)
    cur.append({"text": text.strip()})
    save_memories(workspace_id, cur)
    return {"status": "ok", "count": len(cur)}


def clear_memories(workspace_id: str) -> None:
    p = _path(workspace_id)
    if p.is_file():
        p.unlink()
