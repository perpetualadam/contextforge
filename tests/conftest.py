"""
Shared pytest bootstrap for ContextForge tests.

Many service modules are imported as top-level packages (e.g. ``from app import app``,
``from rag import RAGPipeline``). Ensure those service directories are on ``sys.path``
before collection so ``pytest tests/`` works without colliding path hacks.
"""

from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
_API_GATEWAY = _ROOT / "services" / "api_gateway"
_SERVICES = _ROOT / "services"

for path in (_ROOT, _SERVICES, _API_GATEWAY):
    path_str = str(path)
    if path_str not in sys.path:
        sys.path.insert(0, path_str)
