"""
Minimal audit trail for sensitive endpoints (append-only JSON lines).
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from typing import Any, Dict, Optional

_LOCK = Lock()
_DIR = Path(os.getenv("AUDIT_LOG_DIR", "data/audit"))


def audit_event(
    action: str,
    path: str,
    client_id: Optional[str] = None,
    trace_id: Optional[str] = None,
    extra: Optional[Dict[str, Any]] = None,
) -> None:
    if os.getenv("AUDIT_LOG_ENABLED", "false").lower() not in ("true", "1", "yes"):
        return
    _DIR.mkdir(parents=True, exist_ok=True)
    entry = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "action": action,
        "path": path,
        "client_id": client_id,
        "trace_id": trace_id,
        **(extra or {}),
    }
    log_file = _DIR / "audit.jsonl"
    with _LOCK:
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
