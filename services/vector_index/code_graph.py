"""
Code Graph — lightweight relationship graph stored alongside the FAISS index.

Tracks structural code relationships (imports, calls, inheritance, containment)
between indexed chunks so that retrieval can follow graph edges rather than
relying solely on embedding similarity.

Persistence: ``data/code_graph.json``
"""

import json
import logging
import os
from collections import defaultdict
from typing import Dict, List, Optional, Set, Any

logger = logging.getLogger(__name__)


class CodeGraph:
    """Lightweight directed graph of code relationships.

    Nodes are chunk IDs (strings) produced by the preprocessor.
    Edges have a type (IMPORTS, CALLS, INHERITS, CONTAINS) and connect
    a source chunk to a target *symbol name*.  During search expansion
    we resolve symbol names to chunk IDs via a symbol→chunk_id index
    that is built during insertion.
    """

    # Supported edge types
    EDGE_TYPES = {"IMPORTS", "CALLS", "INHERITS", "CONTAINS"}

    def __init__(self, storage_path: Optional[str] = None):
        self.storage_path = storage_path

        # chunk_id  →  list of {type, target}
        self._edges: Dict[str, List[Dict[str, str]]] = defaultdict(list)

        # symbol_name  →  set of chunk_ids that *define* that symbol
        self._symbol_to_chunks: Dict[str, Set[str]] = defaultdict(set)

        # chunk_id  →  symbol_name (what symbol does this chunk define?)
        self._chunk_to_symbol: Dict[str, str] = {}

        # Reverse index: chunk_id → set of chunk_ids that reference it
        self._reverse_edges: Dict[str, Set[str]] = defaultdict(set)

    # ------------------------------------------------------------------
    # Insertion
    # ------------------------------------------------------------------

    def add_chunk(
        self,
        chunk_id: str,
        symbol_name: str = "",
        relationships: Optional[List[Dict[str, str]]] = None,
    ) -> None:
        """Register a chunk and its outgoing relationships.

        Args:
            chunk_id: Unique chunk identifier.
            symbol_name: The symbol this chunk defines (e.g. function name).
            relationships: List of dicts ``{"type": "CALLS", "target": "foo"}``.
        """
        if symbol_name:
            self._symbol_to_chunks[symbol_name].add(chunk_id)
            self._chunk_to_symbol[chunk_id] = symbol_name

        if relationships:
            for rel in relationships:
                rel_type = rel.get("type", "")
                target = rel.get("target", "")
                if rel_type in self.EDGE_TYPES and target:
                    self._edges[chunk_id].append({"type": rel_type, "target": target})

    def rebuild_reverse_index(self) -> None:
        """Rebuild the reverse edge index after bulk insertion."""
        self._reverse_edges.clear()
        for src_id, edges in self._edges.items():
            for edge in edges:
                target_name = edge["target"]
                for target_chunk_id in self._symbol_to_chunks.get(target_name, set()):
                    self._reverse_edges[target_chunk_id].add(src_id)

    # ------------------------------------------------------------------
    # Query
    # ------------------------------------------------------------------

    def get_related(
        self,
        chunk_id: str,
        depth: int = 1,
        edge_types: Optional[List[str]] = None,
    ) -> List[str]:
        """Get chunk IDs related to the given chunk within ``depth`` hops.

        Follows both outgoing edges (what this chunk references) and
        incoming edges (what references this chunk).

        Args:
            chunk_id: Starting chunk ID.
            depth: Number of hops to traverse.
            edge_types: Filter to specific edge types (None = all).

        Returns:
            Deduplicated list of related chunk IDs (not including the input).
        """
        visited: Set[str] = {chunk_id}
        frontier: Set[str] = {chunk_id}
        filter_types = set(edge_types) if edge_types else None

        for _ in range(depth):
            next_frontier: Set[str] = set()
            for cid in frontier:
                # Outgoing edges
                for edge in self._edges.get(cid, []):
                    if filter_types and edge["type"] not in filter_types:
                        continue
                    target_name = edge["target"]
                    for target_cid in self._symbol_to_chunks.get(target_name, set()):
                        if target_cid not in visited:
                            next_frontier.add(target_cid)

                # Incoming edges (reverse)
                for source_cid in self._reverse_edges.get(cid, set()):
                    if source_cid not in visited:
                        # Check edge type filter on the incoming edge
                        if filter_types:
                            src_edges = self._edges.get(source_cid, [])
                            symbol = self._chunk_to_symbol.get(cid, "")
                            if not any(
                                e["target"] == symbol and e["type"] in filter_types
                                for e in src_edges
                            ):
                                continue
                        next_frontier.add(source_cid)

            visited.update(next_frontier)
            frontier = next_frontier
            if not frontier:
                break

        visited.discard(chunk_id)
        return list(visited)

    def expand_results(
        self,
        results: List[Dict[str, Any]],
        depth: int = 1,
        edge_types: Optional[List[str]] = None,
        metadata_lookup: Optional[Dict[int, Dict]] = None,
    ) -> List[Dict[str, Any]]:
        """Enrich a list of search results with graph-related chunks.

        For each result that has a ``chunk_id`` in its metadata, find
        graph neighbours and append them to the results (deduplicated,
        with a ``graph_expanded: True`` flag and reduced score).

        Args:
            results: Search result dicts (must contain ``meta.chunk_id`` or
                     be keyed by internal doc id).
            depth: Graph traversal depth.
            edge_types: Filter to specific relationship types.
            metadata_lookup: Optional mapping of internal_id → metadata
                             for looking up chunk text of expanded nodes.

        Returns:
            Original results + expanded results, deduplicated.
        """
        if depth <= 0:
            return results

        seen_chunk_ids: Set[str] = set()
        for r in results:
            cid = (r.get("meta") or {}).get("chunk_id") or r.get("chunk_id", "")
            if cid:
                seen_chunk_ids.add(cid)

        expanded = []
        for r in results:
            cid = (r.get("meta") or {}).get("chunk_id") or r.get("chunk_id", "")
            if not cid:
                continue
            neighbours = self.get_related(cid, depth=depth, edge_types=edge_types)
            for neighbour_id in neighbours:
                if neighbour_id in seen_chunk_ids:
                    continue
                seen_chunk_ids.add(neighbour_id)

                # Build a lightweight result entry for the expanded node
                exp_result = {
                    "text": "",
                    "score": r.get("score", 0) * 0.6,  # Reduced score
                    "dense_score": 0,
                    "lexical_score": 0,
                    "recency_boost": 0,
                    "meta": {"chunk_id": neighbour_id},
                    "source": "graph_expansion",
                    "content_type": "code",
                    "rank": 0,
                    "graph_expanded": True,
                    "expanded_from": cid,
                }

                # Try to fill text from metadata lookup
                if metadata_lookup:
                    for _doc_id, meta in metadata_lookup.items():
                        if meta.get("chunk_id") == neighbour_id:
                            exp_result["text"] = meta.get("text", "")
                            exp_result["meta"] = meta.get("meta", {})
                            exp_result["content_type"] = meta.get("content_type", "code")
                            break

                expanded.append(exp_result)

        return results + expanded

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def save(self, path: Optional[str] = None) -> None:
        """Save graph to JSON file."""
        path = path or self.storage_path
        if not path:
            return

        data = {
            "edges": dict(self._edges),
            "symbol_to_chunks": {k: list(v) for k, v in self._symbol_to_chunks.items()},
            "chunk_to_symbol": self._chunk_to_symbol,
        }

        try:
            os.makedirs(os.path.dirname(path) if os.path.dirname(path) else ".", exist_ok=True)
            with open(path, "w") as f:
                json.dump(data, f)
            logger.info(f"Code graph saved: {len(self._edges)} nodes, "
                        f"{sum(len(v) for v in self._edges.values())} edges")
        except Exception as e:
            logger.error(f"Failed to save code graph: {e}")

    def load(self, path: Optional[str] = None) -> bool:
        """Load graph from JSON file."""
        path = path or self.storage_path
        if not path or not os.path.exists(path):
            return False

        try:
            with open(path, "r") as f:
                data = json.load(f)

            self._edges = defaultdict(list, data.get("edges", {}))
            self._symbol_to_chunks = defaultdict(
                set,
                {k: set(v) for k, v in data.get("symbol_to_chunks", {}).items()}
            )
            self._chunk_to_symbol = data.get("chunk_to_symbol", {})
            self.rebuild_reverse_index()

            logger.info(f"Code graph loaded: {len(self._edges)} nodes, "
                        f"{sum(len(v) for v in self._edges.values())} edges")
            return True
        except Exception as e:
            logger.error(f"Failed to load code graph: {e}")
            return False

    def clear(self) -> None:
        """Clear all graph data."""
        self._edges.clear()
        self._symbol_to_chunks.clear()
        self._chunk_to_symbol.clear()
        self._reverse_edges.clear()

    def stats(self) -> Dict[str, Any]:
        """Get graph statistics."""
        total_edges = sum(len(v) for v in self._edges.values())
        edge_type_counts: Dict[str, int] = defaultdict(int)
        for edges in self._edges.values():
            for e in edges:
                edge_type_counts[e["type"]] += 1

        return {
            "nodes": len(self._edges),
            "total_edges": total_edges,
            "symbols_indexed": len(self._symbol_to_chunks),
            "edge_types": dict(edge_type_counts),
        }
