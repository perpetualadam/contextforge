"""
Multi-query expansion and task-aware routing hints for retrieval.
Disabled by default (QUERY_PLANNER_ENABLED=false).
"""

from __future__ import annotations

import os
import re
from typing import List, Optional, Set

QUERY_PLANNER_ENABLED = os.getenv("QUERY_PLANNER_ENABLED", "false").lower() in ("true", "1", "yes")
MAX_SUBQUERIES = int(os.getenv("QUERY_PLANNER_MAX_SUBQUERIES", "5"))


def _unique_preserve(seq: List[str]) -> List[str]:
    seen: Set[str] = set()
    out: List[str] = []
    for s in seq:
        k = s.strip()
        if len(k) < 2 or k in seen:
            continue
        seen.add(k)
        out.append(k)
    return out[:MAX_SUBQUERIES]


def plan_queries(query: str, task_scope: Optional[str] = None) -> List[str]:
    """
    Return ordered sub-queries: always starts with the original query, then variants.
    """
    base = query.strip()
    if not base:
        return []

    if not QUERY_PLANNER_ENABLED:
        return [base]

    variants: List[str] = [base]

    # Identifier-style queries: add tokenized pieces for lexical recall
    idents = re.findall(r"[A-Za-z_][A-Za-z0-9_.]*", base)
    if len(idents) >= 2:
        variants.append(" ".join(idents[:8]))

    ts = (task_scope or "general").lower()
    if ts == "find_bugs":
        variants.append(f"{base} error exception traceback bug failure")
    elif ts == "explain":
        variants.append(f"{base} overview architecture how it works")
    elif ts == "refactor":
        variants.append(f"{base} duplicate coupling dependency interface")
    elif ts == "test":
        variants.append(f"{base} test spec assert mock coverage")

    return _unique_preserve(variants)
