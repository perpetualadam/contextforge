"""
Tree-sitter-based code chunker for semantic chunking.

This module provides semantic code chunking using tree-sitter AST parsing.
"""

import logging
from typing import List, Dict, Any, Optional
from dataclasses import dataclass

from services.preprocessor.tree_sitter_parser import (
    TreeSitterParser, ParsedNode, NodeType, TREE_SITTER_AVAILABLE
)

logger = logging.getLogger(__name__)


@dataclass
class CodeChunk:
    """Represents a semantic code chunk."""
    content: str
    chunk_type: str  # 'function', 'class', 'method', etc.
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
    - Function and class extraction
    - Context preservation (imports, docstrings)
    - Multi-language support
    """
    
    def __init__(self, language: str):
        """
        Initialize tree-sitter chunker.
        
        Args:
            language: Programming language
        """
        if not TREE_SITTER_AVAILABLE:
            raise ImportError("tree-sitter is not installed")
        
        self.language = language
        self.parser = TreeSitterParser(language)
        logger.info(f"Initialized TreeSitterChunker for {language}")
    
    def chunk_code(self, code: str, max_chunk_size: int = 1000) -> List[CodeChunk]:
        """
        Chunk code into semantic units.
        
        Args:
            code: Source code to chunk
            max_chunk_size: Maximum chunk size in characters
            
        Returns:
            List of CodeChunk objects
        """
        # Parse code
        tree = self.parser.parse(code)
        
        # Extract semantic nodes
        nodes = self.parser.extract_nodes(tree, code)
        
        # Convert nodes to chunks
        chunks = []
        for node in nodes:
            chunk = self._node_to_chunk(node, code)
            if chunk:
                # Split large chunks
                if len(chunk.content) > max_chunk_size:
                    sub_chunks = self._split_chunk(chunk, max_chunk_size)
                    chunks.extend(sub_chunks)
                else:
                    chunks.append(chunk)
        
        logger.info(f"Chunked code into {len(chunks)} chunks")
        return chunks
    
    def _node_to_chunk(self, node: ParsedNode, code: str) -> Optional[CodeChunk]:
        """
        Convert ParsedNode to CodeChunk.
        
        Args:
            node: Parsed AST node
            code: Source code
            
        Returns:
            CodeChunk or None
        """
        # Calculate line numbers
        lines = code[:node.start_byte].count('\n')
        start_line = lines + 1
        end_line = start_line + node.text.count('\n')
        
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
            }
        )
    
    def _split_chunk(self, chunk: CodeChunk, max_size: int) -> List[CodeChunk]:
        """
        Split large chunk into smaller chunks.
        
        Args:
            chunk: Large chunk to split
            max_size: Maximum chunk size
            
        Returns:
            List of smaller chunks
        """
        chunks = []
        lines = chunk.content.split('\n')
        current_chunk = []
        current_size = 0
        current_line = chunk.start_line
        
        for line in lines:
            line_size = len(line) + 1  # +1 for newline
            
            if current_size + line_size > max_size and current_chunk:
                # Create chunk from accumulated lines
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
                
                current_chunk = []
                current_size = 0
                current_line += len(current_chunk)
            
            current_chunk.append(line)
            current_size += line_size
        
        # Add remaining lines
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

