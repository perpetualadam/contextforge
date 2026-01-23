"""
Live indexer that integrates FileWatcher with IncrementalIndexer.

This module provides real-time indexing of code changes using file watching
and incremental parsing.
"""

import logging
from typing import Dict, Optional, Callable
from pathlib import Path

from services.tools.file_watcher import FileWatcher, WatchConfig, FileEvent, FileEventType
from services.indexing.incremental_indexer import IncrementalIndexer
from services.preprocessor.tree_sitter_parser import TREE_SITTER_AVAILABLE

logger = logging.getLogger(__name__)


class LiveIndexer:
    """
    Live indexer that watches files and incrementally updates the index.
    
    Features:
    - Real-time file watching
    - Incremental indexing on file changes
    - Language detection
    - Event callbacks for index updates
    """
    
    # Language detection by extension
    EXTENSION_TO_LANGUAGE = {
        '.py': 'python',
        '.js': 'javascript',
        '.jsx': 'javascript',
        '.ts': 'typescript',
        '.tsx': 'typescript',
        '.java': 'java',
        '.rs': 'rust',
        '.go': 'go',
        '.cpp': 'cpp',
        '.cc': 'cpp',
        '.cxx': 'cpp',
        '.c': 'c',
        '.cs': 'csharp',
        '.rb': 'ruby',
        '.php': 'php',
        '.kt': 'kotlin',
        '.jl': 'julia',
        '.html': 'html',
        '.css': 'css',
    }
    
    def __init__(self, workspace_root: str = None):
        """
        Initialize live indexer.
        
        Args:
            workspace_root: Root directory for file watching
        """
        if not TREE_SITTER_AVAILABLE:
            raise ImportError("tree-sitter is not installed")
        
        self.workspace_root = workspace_root or str(Path.cwd())
        self.file_watcher = FileWatcher(workspace_root=self.workspace_root)
        self.incremental_indexer = IncrementalIndexer()
        self.watch_id: Optional[int] = None
        self.update_callback: Optional[Callable] = None
        logger.info(f"Initialized LiveIndexer for {self.workspace_root}")
    
    def start(self, patterns: list = None, update_callback: Callable = None):
        """
        Start live indexing.
        
        Args:
            patterns: File patterns to watch (default: code files)
            update_callback: Callback function called on index updates
        """
        if patterns is None:
            patterns = list(self.EXTENSION_TO_LANGUAGE.keys())
        
        self.update_callback = update_callback
        
        # Start file watcher
        config = WatchConfig(
            path=self.workspace_root,
            recursive=True,
            patterns=[f"*{ext}" for ext in patterns],
            debounce_seconds=0.5
        )
        
        self.watch_id = self.file_watcher.start_watch(config)
        logger.info(f"Started live indexing with watch ID {self.watch_id}")
    
    def process_events(self):
        """
        Process pending file events and update index.
        
        Returns:
            Number of events processed
        """
        if self.watch_id is None:
            return 0
        
        events = self.file_watcher.get_events(self.watch_id)
        processed = 0
        
        for event in events:
            try:
                self._handle_event(event)
                processed += 1
            except Exception as e:
                logger.error(f"Error processing event {event}: {e}")
        
        return processed
    
    def _handle_event(self, event: FileEvent):
        """
        Handle a single file event.
        
        Args:
            event: File event to handle
        """
        file_path = event.path
        language = self._detect_language(file_path)
        
        if not language:
            logger.debug(f"Skipping unsupported file: {file_path}")
            return
        
        if event.event_type == FileEventType.CREATED or event.event_type == FileEventType.MODIFIED:
            # Read file content
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                # Index file
                chunks = self.incremental_indexer.index_file(file_path, content, language)
                
                # Call update callback
                if self.update_callback:
                    self.update_callback({
                        'event_type': event.event_type.value,
                        'file_path': file_path,
                        'language': language,
                        'chunks': chunks
                    })
                
                logger.info(f"Indexed {file_path}: {len(chunks)} chunks")
            except Exception as e:
                logger.error(f"Error indexing {file_path}: {e}")
        
        elif event.event_type == FileEventType.DELETED:
            # Remove file from index
            self.incremental_indexer.remove_file(file_path)
            
            # Call update callback
            if self.update_callback:
                self.update_callback({
                    'event_type': event.event_type.value,
                    'file_path': file_path,
                    'language': language,
                    'chunks': []
                })
            
            logger.info(f"Removed {file_path} from index")
    
    def _detect_language(self, file_path: str) -> Optional[str]:
        """
        Detect programming language from file extension.
        
        Args:
            file_path: Path to file
            
        Returns:
            Language name or None
        """
        ext = Path(file_path).suffix.lower()
        return self.EXTENSION_TO_LANGUAGE.get(ext)
    
    def stop(self):
        """Stop live indexing."""
        if self.watch_id is not None:
            self.file_watcher.stop_watch(self.watch_id)
            self.watch_id = None
            logger.info("Stopped live indexing")
    
    def get_stats(self) -> Dict:
        """Get indexing statistics."""
        return {
            'total_files': len(self.incremental_indexer.file_states),
            'watch_active': self.watch_id is not None,
            'workspace_root': self.workspace_root
        }

