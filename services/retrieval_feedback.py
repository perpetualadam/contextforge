"""
Append-only feedback and lightweight A/B logging (self-hosted, local files).
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_DATA = Path(os.getenv("FEEDBACK_DATA_DIR", "data/feedback"))
_LOCK = Lock()


def _jsonl_path() -> Path:
    _DATA.mkdir(parents=True, exist_ok=True)
    return _DATA / "query_feedback.jsonl"


def append_feedback(entry: Dict[str, Any]) -> None:
    """Append one JSON object per line."""
    line = {
        "ts": datetime.now(timezone.utc).isoformat(),
        **entry,
    }
    with _LOCK:
        with open(_jsonl_path(), "a", encoding="utf-8") as f:
            f.write(json.dumps(line, ensure_ascii=False) + "\n")


def read_recent_feedback(limit: int = 500) -> List[Dict[str, Any]]:
    p = _jsonl_path()
    if not p.is_file():
        return []
    lines = p.read_text(encoding="utf-8").strip().splitlines()
    out: List[Dict[str, Any]] = []
    for ln in lines[-limit:]:
        try:
            out.append(json.loads(ln))
        except json.JSONDecodeError:
            continue
    return out


def aggregate_insights() -> Dict[str, Any]:
    """Simple aggregates for GET /retrieval/insights (no secrets)."""
    rows = read_recent_feedback(2000)
    if not rows:
        return {"count": 0, "note": "no_feedback_yet"}

    ratings = [r.get("rating") for r in rows if r.get("rating") is not None]
    thumbs_up = sum(1 for x in ratings if x == 1)
    thumbs_down = sum(1 for x in ratings if x == -1)
    latencies = [float(r["latency_ms"]) for r in rows if r.get("latency_ms") is not None]
    recalls = [float(r["recall_at_k"]) for r in rows if r.get("recall_at_k") is not None]

    lat_sorted = sorted(latencies) if latencies else []
    p95 = lat_sorted[int(len(lat_sorted) * 0.95)] if len(lat_sorted) > 1 else (lat_sorted[0] if lat_sorted else None)

    return {
        "count": len(rows),
        "thumbs_up": thumbs_up,
        "thumbs_down": thumbs_down,
        "mean_latency_ms": sum(latencies) / len(latencies) if latencies else None,
        "p95_latency_ms": p95,
        "mean_recall_at_k": sum(recalls) / len(recalls) if recalls else None,
    }
