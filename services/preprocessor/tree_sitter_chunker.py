"""
Tree-sitter-based code chunker for semantic chunking.

This module provides semantic code chunking using tree-sitter AST parsing.
It produces chunks that respect language grammar boundaries (functions, classes,
imports) rather than splitting at arbitrary character positions.

Output format matches the standard chunk dict format used by the preprocessor
pipeline: {"text": ..., "meta": {...}}.
"""

import logging
from typing import List, Dict, Any, Optional
from dataclasses import dataclass

from .tree_sitter_parser import (
    TreeSitterParser, ParsedNode, NodeType, TREE_SITTER_AVAILABLE
)

logger = logging.getLogger(__name__)


@dataclass
class CodeChunk:
    """Represents a semantic code chunk."""
    content: str
    chunk_type: str  # 'function', 'class', 'method', 'import', etc.
    name: str
    start_line: int
    end_line: int
    language: str
    metadata: Dict[str, Any] = None

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


class TreeSitterChunker:
    """
    Tree-sitter-based code chunker for semantic chunking.

    Features:
    - Semantic boundary detection using AST
    - Function, class, method, and import extraction
    - Relationship extraction (calls, imports, inheritance, containment)
    - Context preservation (imports, docstrings)
    - Multi-language support (14 languages)
    - Output compatible with preprocessor pipeline dict format
    """

    def __init__(self, language: str, max_chunk_size: int = 1000, overlap: int = 100):
        """
        Initialize tree-sitter chunker.

        Args:
            language: Programming language
            max_chunk_size: Maximum chunk size in characters
            overlap: Overlap between chunks (unused for AST chunking but kept for interface compat)
        """
        if not TREE_SITTER_AVAILABLE:
            raise ImportError("tree-sitter is not installed")

        self.language = language
        self.max_chunk_size = max_chunk_size
        self.overlap = overlap
        self.parser = TreeSitterParser(language)
        logger.info(f"Initialized TreeSitterChunker for {language}")

    def get_language(self) -> str:
        """Get the language identifier."""
        return self.language

    def chunk(self, content: str, file_path: str) -> List[Dict[str, Any]]:
        """
        Chunk code into semantic units matching the preprocessor dict format.

        This is the primary interface called by ChunkerFactory, matching the
        BaseChunker.chunk() signature.

        Args:
            content: Source code to chunk
            file_path: File path for metadata

        Returns:
            List of chunk dicts with 'text' and 'meta' keys
        """
        return self.chunk_to_dicts(content, file_path)

    def chunk_to_dicts(self, content: str, file_path: str) -> List[Dict[str, Any]]:
        """
        Chunk code and return standard preprocessor dict format.

        Each chunk dict contains:
        - text: The chunk content
        - meta: Metadata including file_path, start_line, end_line, chunk_type,
                language, AST info, and relationships

        Args:
            content: Source code
            file_path: File path

        Returns:
            List of chunk dicts
        """
        code_chunks = self.chunk_code(content, self.max_chunk_size)

        dicts = []
        for chunk in code_chunks:
            relationships = chunk.metadata.get('relationships', [])
            meta = {
                "file_path": file_path,
                "start_line": chunk.start_line,
                "end_line": chunk.end_line,
                "chunk_type": chunk.chunk_type,
                "language": chunk.language,
                "symbol_name": chunk.name,
                "parent_name": chunk.metadata.get('parent_name', ''),
                # AST positional info
                "start_byte": chunk.metadata.get('start_byte'),
                "end_byte": chunk.metadata.get('end_byte'),
                "start_point": chunk.metadata.get('start_point'),
                "end_point": chunk.metadata.get('end_point'),
                # Relationships for code graph
                "relationships": relationships,
            }

            # Add convenient symbol lists for backward compat
            if chunk.chunk_type == "function" or chunk.chunk_type == "method":
                meta["function_name"] = chunk.name
            elif chunk.chunk_type == "class":
                meta["class_name"] = chunk.name
                methods = [
                    r['target'] for r in relationships
                    if r.get('type') == 'CONTAINS' and r.get('context') != 'member_of'
                ]
                if methods:
                    meta["methods"] = methods
                bases = [r['target'] for r in relationships if r.get('type') == 'INHERITS']
                if bases:
                    meta["base_classes"] = bases
            elif chunk.chunk_type == "import":
                meta["modules"] = [
                    r['target'] for r in relationships
                    if r.get('type') == 'IMPORTS'
                ]

            dicts.append({
                "text": chunk.content.strip(),
                "meta": meta,
            })

        return dicts

    def chunk_code(self, code: str, max_chunk_size: int = None) -> List[CodeChunk]:
        """
        Chunk code into semantic CodeChunk objects.

        Args:
            code: Source code to chunk
            max_chunk_size: Maximum chunk size in characters (overrides init value)

        Returns:
            List of CodeChunk objects
        """
        if max_chunk_size is None:
            max_chunk_size = self.max_chunk_size

        # Parse code
        tree = self.parser.parse(code)

        # Extract semantic nodes with relationships
        nodes = self.parser.extract_nodes(tree, code, extract_relationships=True)

        # If no AST nodes found, fall back to whole-file chunk
        if not nodes:
            return [CodeChunk(
                content=code,
                chunk_type="block",
                name="module",
                start_line=1,
                end_line=code.count('\n') + 1,
                language=self.language,
                metadata={},
            )]

        # Group adjacent import nodes into a single chunk
        chunks = []
        import_group = []

        for node in nodes:
            if node.node_type == NodeType.IMPORT:
                import_group.append(node)
            else:
                # Flush any pending import group
                if import_group:
                    chunks.append(self._imports_to_chunk(import_group, code))
                    import_group = []
                chunk = self._node_to_chunk(node, code)
                if chunk:
                    if len(chunk.content) > max_chunk_size:
                        sub_chunks = self._split_chunk(chunk, max_chunk_size)
                        chunks.extend(sub_chunks)
                    else:
                        chunks.append(chunk)

        # Flush trailing import group
        if import_group:
            chunks.append(self._imports_to_chunk(import_group, code))

        logger.info(f"Chunked code into {len(chunks)} semantic chunks")
        return chunks

    def _imports_to_chunk(self, import_nodes: List[ParsedNode], code: str) -> CodeChunk:
        """Merge a group of adjacent import nodes into a single chunk."""
        text = '\n'.join(n.text for n in import_nodes)
        first = import_nodes[0]
        last = import_nodes[-1]
        start_line = code[:first.start_byte].count('\n') + 1
        end_line = code[:last.end_byte].count('\n') + 1

        # Collect all import relationships
        all_rels = []
        for n in import_nodes:
            all_rels.extend([r.to_dict() for r in n.relationships])

        return CodeChunk(
            content=text,
            chunk_type="import",
            name="imports",
            start_line=start_line,
            end_line=end_line,
            language=self.language,
            metadata={
                'start_byte': first.start_byte,
                'end_byte': last.end_byte,
                'start_point': first.start_point,
                'end_point': last.end_point,
                'relationships': all_rels,
            }
        )

    def _node_to_chunk(self, node: ParsedNode, code: str) -> Optional[CodeChunk]:
        """Convert ParsedNode to CodeChunk."""
        start_line = code[:node.start_byte].count('\n') + 1
        end_line = start_line + node.text.count('\n')

        relationships = [r.to_dict() for r in node.relationships]

        return CodeChunk(
            content=node.text,
            chunk_type=node.node_type.value,
            name=node.name,
            start_line=start_line,
            end_line=end_line,
            language=self.language,
            metadata={
                'start_byte': node.start_byte,
                'end_byte': node.end_byte,
                'start_point': node.start_point,
                'end_point': node.end_point,
                'parent_name': node.parent_name,
                'relationships': relationships,
            }
        )

    def _split_chunk(self, chunk: CodeChunk, max_size: int) -> List[CodeChunk]:
        """Split large chunk into smaller chunks preserving metadata."""
        chunks = []
        lines = chunk.content.split('\n')
        current_chunk = []
        current_size = 0
        current_line = chunk.start_line

        for line in lines:
            line_size = len(line) + 1

            if current_size + line_size > max_size and current_chunk:
                chunk_content = '\n'.join(current_chunk)
                chunks.append(CodeChunk(
                    content=chunk_content,
                    chunk_type=chunk.chunk_type,
                    name=f"{chunk.name}_part{len(chunks)+1}",
                    start_line=current_line,
                    end_line=current_line + len(current_chunk) - 1,
                    language=chunk.language,
                    metadata=chunk.metadata.copy()
                ))

                current_line = current_line + len(current_chunk)
                current_chunk = []
                current_size = 0

            current_chunk.append(line)
            current_size += line_size

        if current_chunk:
            chunk_content = '\n'.join(current_chunk)
            chunks.append(CodeChunk(
                content=chunk_content,
                chunk_type=chunk.chunk_type,
                name=f"{chunk.name}_part{len(chunks)+1}" if len(chunks) > 0 else chunk.name,
                start_line=current_line,
                end_line=current_line + len(current_chunk) - 1,
                language=chunk.language,
                metadata=chunk.metadata.copy()
            ))

        return chunks
