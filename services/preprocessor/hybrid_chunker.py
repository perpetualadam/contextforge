"""
Hybrid chunker that uses tree-sitter for incremental and regex for batch.

This module provides a hybrid chunking strategy that automatically selects
the best approach based on context.
"""

import logging
from typing import List, Dict, Any, Optional
from enum import Enum

from services.preprocessor.tree_sitter_parser import TREE_SITTER_AVAILABLE, TreeSitterParser
from services.preprocessor.tree_sitter_chunker import TreeSitterChunker, CodeChunk
from services.preprocessor.lang_chunkers import (
    PythonChunker, JavaScriptChunker, JavaChunker,
    RustChunker, GoChunker, KotlinChunker, CSharpChunker,
    HTMLChunker, CSSChunker, JuliaChunker
)

logger = logging.getLogger(__name__)


class ChunkingMode(Enum):
    """Chunking mode selection."""
    AUTO = "auto"  # Automatically select best mode
    TREE_SITTER = "tree_sitter"  # Use tree-sitter (incremental)
    REGEX = "regex"  # Use regex (batch)


class HybridChunker:
    """
    Hybrid chunker that uses tree-sitter for incremental and regex for batch.
    
    Features:
    - Auto-detect mode based on context (live editing vs batch indexing)
    - Tree-sitter for incremental parsing (live editing)
    - Regex for batch operations (initial indexing)
    - Fallback to regex if tree-sitter fails
    - Consistent output format
    """
    
    # Language to regex chunker mapping
    REGEX_CHUNKERS = {
        'python': PythonChunker,
        'javascript': JavaScriptChunker,
        'typescript': JavaScriptChunker,  # TypeScript uses JavaScript chunker
        'java': JavaChunker,
        'rust': RustChunker,
        'go': GoChunker,
        'kotlin': KotlinChunker,
        'csharp': CSharpChunker,
        'html': HTMLChunker,
        'css': CSSChunker,
        'julia': JuliaChunker,
    }
    
    def __init__(self, language: str, mode: ChunkingMode = ChunkingMode.AUTO):
        """
        Initialize hybrid chunker.
        
        Args:
            language: Programming language
            mode: Chunking mode (AUTO, TREE_SITTER, REGEX)
        """
        self.language = language.lower()
        self.mode = mode
        
        # Initialize tree-sitter chunker if available
        self.tree_sitter_chunker = None
        if TREE_SITTER_AVAILABLE and self.language in TreeSitterParser.LANGUAGE_MAP:
            try:
                self.tree_sitter_chunker = TreeSitterChunker(self.language)
                logger.info(f"Tree-sitter chunker initialized for {language}")
            except Exception as e:
                logger.warning(f"Failed to initialize tree-sitter chunker: {e}")
        
        # Initialize regex chunker
        self.regex_chunker = None
        if self.language in self.REGEX_CHUNKERS:
            self.regex_chunker = self.REGEX_CHUNKERS[self.language]()
            logger.info(f"Regex chunker initialized for {language}")
        
        if not self.tree_sitter_chunker and not self.regex_chunker:
            raise ValueError(f"No chunker available for language: {language}")
    
    def chunk(self, content: str, file_path: str, is_incremental: bool = False) -> List[Dict[str, Any]]:
        """
        Chunk code using hybrid strategy.
        
        Args:
            content: Source code to chunk
            file_path: Path to file
            is_incremental: Whether this is an incremental update
            
        Returns:
            List of chunk dictionaries (compatible with existing format)
        """
        # Determine which chunker to use
        use_tree_sitter = self._should_use_tree_sitter(is_incremental)
        
        if use_tree_sitter and self.tree_sitter_chunker:
            try:
                # Use tree-sitter chunker
                chunks = self.tree_sitter_chunker.chunk_code(content)
                # Convert to standard format
                return self._convert_tree_sitter_chunks(chunks, file_path)
            except Exception as e:
                logger.warning(f"Tree-sitter chunking failed, falling back to regex: {e}")
                # Fallback to regex
                if self.regex_chunker:
                    return self.regex_chunker.chunk(content, file_path)
                else:
                    raise
        else:
            # Use regex chunker
            if self.regex_chunker:
                return self.regex_chunker.chunk(content, file_path)
            else:
                raise ValueError(f"Regex chunker not available for {self.language}")
    
    def _should_use_tree_sitter(self, is_incremental: bool) -> bool:
        """
        Determine whether to use tree-sitter.
        
        Args:
            is_incremental: Whether this is an incremental update
            
        Returns:
            True if tree-sitter should be used
        """
        if self.mode == ChunkingMode.TREE_SITTER:
            return True
        elif self.mode == ChunkingMode.REGEX:
            return False
        else:  # AUTO mode
            # Use tree-sitter for incremental updates, regex for batch
            return is_incremental and self.tree_sitter_chunker is not None
    
    def _convert_tree_sitter_chunks(self, chunks: List[CodeChunk], file_path: str) -> List[Dict[str, Any]]:
        """
        Convert tree-sitter chunks to standard format.
        
        Args:
            chunks: List of CodeChunk objects
            file_path: Path to file
            
        Returns:
            List of chunk dictionaries
        """
        result = []
        for chunk in chunks:
            result.append({
                "text": chunk.content.strip(),
                "meta": {
                    "file_path": file_path,
                    "start_line": chunk.start_line,
                    "end_line": chunk.end_line,
                    "chunk_type": chunk.chunk_type,
                    "language": chunk.language,
                    "name": chunk.name,
                    **(chunk.metadata or {})
                }
            })
        return result

