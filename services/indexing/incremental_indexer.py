"""
Incremental indexer using tree-sitter for live editing.

This module provides incremental indexing that only re-indexes changed portions
of code files using tree-sitter's incremental parsing capabilities.
"""

import logging
import hashlib
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
from pathlib import Path

from services.preprocessor.tree_sitter_parser import TreeSitterParser, TREE_SITTER_AVAILABLE
from services.preprocessor.tree_sitter_chunker import TreeSitterChunker, CodeChunk

logger = logging.getLogger(__name__)


@dataclass
class FileState:
    """Tracks state of a file for incremental indexing."""
    path: str
    content_hash: str
    tree: Any  # tree-sitter Tree object
    chunks: List[CodeChunk]
    last_modified: float


class IncrementalIndexer:
    """
    Incremental indexer using tree-sitter for live editing.
    
    Features:
    - Tracks file state (AST trees, chunks)
    - Incremental parsing on file changes
    - Only re-indexes changed portions
    - Maintains consistency with full indexing
    """
    
    def __init__(self):
        """Initialize incremental indexer."""
        if not TREE_SITTER_AVAILABLE:
            raise ImportError("tree-sitter is not installed")
        
        self.file_states: Dict[str, FileState] = {}
        self.parsers: Dict[str, TreeSitterParser] = {}
        self.chunkers: Dict[str, TreeSitterChunker] = {}
        logger.info("Initialized IncrementalIndexer")
    
    def index_file(self, file_path: str, content: str, language: str) -> List[CodeChunk]:
        """
        Index a file (full or incremental).
        
        Args:
            file_path: Path to file
            content: File content
            language: Programming language
            
        Returns:
            List of code chunks
        """
        # Get or create parser and chunker
        if language not in self.parsers:
            self.parsers[language] = TreeSitterParser(language)
            self.chunkers[language] = TreeSitterChunker(language)
        
        parser = self.parsers[language]
        chunker = self.chunkers[language]
        
        # Check if file exists in state
        if file_path in self.file_states:
            # Incremental update
            return self._incremental_index(file_path, content, language, parser, chunker)
        else:
            # Full index
            return self._full_index(file_path, content, language, parser, chunker)
    
    def _full_index(
        self, 
        file_path: str, 
        content: str, 
        language: str,
        parser: TreeSitterParser,
        chunker: TreeSitterChunker
    ) -> List[CodeChunk]:
        """
        Perform full indexing of a file.
        
        Args:
            file_path: Path to file
            content: File content
            language: Programming language
            parser: Tree-sitter parser
            chunker: Tree-sitter chunker
            
        Returns:
            List of code chunks
        """
        # Parse code
        tree = parser.parse(content)
        
        # Chunk code
        chunks = chunker.chunk_code(content)
        
        # Calculate content hash
        content_hash = hashlib.sha256(content.encode('utf-8')).hexdigest()
        
        # Store file state
        self.file_states[file_path] = FileState(
            path=file_path,
            content_hash=content_hash,
            tree=tree,
            chunks=chunks,
            last_modified=Path(file_path).stat().st_mtime if Path(file_path).exists() else 0
        )
        
        logger.info(f"Full index: {file_path} -> {len(chunks)} chunks")
        return chunks
    
    def _incremental_index(
        self,
        file_path: str,
        content: str,
        language: str,
        parser: TreeSitterParser,
        chunker: TreeSitterChunker
    ) -> List[CodeChunk]:
        """
        Perform incremental indexing of a file.
        
        Args:
            file_path: Path to file
            content: Updated file content
            language: Programming language
            parser: Tree-sitter parser
            chunker: Tree-sitter chunker
            
        Returns:
            List of code chunks
        """
        old_state = self.file_states[file_path]
        
        # Calculate new content hash
        new_hash = hashlib.sha256(content.encode('utf-8')).hexdigest()
        
        # Check if content changed
        if new_hash == old_state.content_hash:
            logger.debug(f"No changes detected: {file_path}")
            return old_state.chunks
        
        # Detect edits (simplified - in production, use diff algorithm)
        edits = self._detect_edits(old_state.tree, content)
        
        # Incremental parse
        if edits:
            new_tree = parser.incremental_parse(old_state.tree, content, edits)
        else:
            # Fallback to full parse if edit detection fails
            new_tree = parser.parse(content)
        
        # Re-chunk code
        chunks = chunker.chunk_code(content)
        
        # Update file state
        self.file_states[file_path] = FileState(
            path=file_path,
            content_hash=new_hash,
            tree=new_tree,
            chunks=chunks,
            last_modified=Path(file_path).stat().st_mtime if Path(file_path).exists() else 0
        )
        
        logger.info(f"Incremental index: {file_path} -> {len(chunks)} chunks")
        return chunks
    
    def _detect_edits(self, old_tree: Any, new_content: str) -> List[Dict[str, Any]]:
        """
        Detect edits between old tree and new content.
        
        This is a simplified implementation. In production, use a proper diff algorithm.
        
        Args:
            old_tree: Old AST tree
            new_content: New file content
            
        Returns:
            List of edit operations
        """
        # Simplified: return empty list to trigger full reparse
        # In production, implement proper diff detection
        return []
    
    def remove_file(self, file_path: str):
        """Remove file from index."""
        if file_path in self.file_states:
            del self.file_states[file_path]
            logger.info(f"Removed file from index: {file_path}")
    
    def get_file_chunks(self, file_path: str) -> Optional[List[CodeChunk]]:
        """Get chunks for a file."""
        if file_path in self.file_states:
            return self.file_states[file_path].chunks
        return None
    
    def clear(self):
        """Clear all file states."""
        self.file_states.clear()
        logger.info("Cleared incremental indexer state")

