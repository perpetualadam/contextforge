"""
Task-scoped retrieval configuration.

Different tasks need different retrieval strategies:
- "find_bugs" should prioritize function bodies and error handling.
- "explain" should include docs, comments, and usage examples.
- "refactor" should include callers and tests.
- "test" should focus on test files and the functions they exercise.
- "general" applies no special boosting or expansion.

Each scope defines:
- preferred_chunk_types: AST chunk types to boost scores for (1.2x).
- boost_content_types: Content-type tags to boost scores for (1.1x).
- graph_expand: Whether to expand results via the code graph.
- graph_edge_types: Which relationship types to follow during expansion.
- graph_depth: How many hops to traverse.
- query_prefix_override: Override the model's query prefix (or None).
"""

from typing import Any, Dict, List, Optional


TASK_SCOPES: Dict[str, Dict[str, Any]] = {
    "find_bugs": {
        "preferred_chunk_types": ["function", "method"],
        "boost_content_types": ["code"],
        "graph_expand": True,
        "graph_edge_types": ["CALLS", "IMPORTS"],
        "graph_depth": 1,
        "query_prefix_override": None,
    },
    "explain": {
        "preferred_chunk_types": ["class", "function", "module"],
        "boost_content_types": ["documentation", "code"],
        "graph_expand": True,
        "graph_edge_types": ["CONTAINS", "INHERITS"],
        "graph_depth": 2,
        "query_prefix_override": None,
    },
    "refactor": {
        "preferred_chunk_types": ["function", "class", "method"],
        "boost_content_types": ["code", "test"],
        "graph_expand": True,
        "graph_edge_types": ["CALLS", "INHERITS", "IMPORTS"],
        "graph_depth": 2,
        "query_prefix_override": None,
    },
    "test": {
        "preferred_chunk_types": ["function", "class"],
        "boost_content_types": ["test", "code"],
        "graph_expand": True,
        "graph_edge_types": ["CALLS", "IMPORTS"],
        "graph_depth": 1,
        "query_prefix_override": None,
    },
    "general": {
        "preferred_chunk_types": None,
        "boost_content_types": None,
        "graph_expand": False,
        "graph_depth": 0,
        "graph_edge_types": None,
        "query_prefix_override": None,
    },
}
