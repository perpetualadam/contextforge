"""
ContextForge Code Viewer - File and directory viewing with regex search.

Provides file viewing capabilities:
- View files with line numbers
- View directory structure
- Regex search within files
- Line range viewing

Copyright (c) 2025 ContextForge
"""

import os
import re
import logging
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Tuple, Union
from enum import Enum

logger = logging.getLogger(__name__)


class ViewResultStatus(Enum):
    """Status of a view operation."""
    SUCCESS = "success"
    ERROR = "error"
    FILE_NOT_FOUND = "file_not_found"
    PERMISSION_DENIED = "permission_denied"
    INVALID_RANGE = "invalid_range"
    REGEX_ERROR = "regex_error"


@dataclass
class ViewRequest:
    """Request to view a file or directory."""
    path: str
    view_type: str = "file"  # "file" or "directory"
    view_range: Optional[Tuple[int, int]] = None  # (start_line, end_line), 1-based
    search_query_regex: Optional[str] = None
    case_sensitive: bool = False
    context_lines_before: int = 5
    context_lines_after: int = 5
    max_depth: int = 2  # For directory listing


@dataclass
class ViewResult:
    """Result of a view operation."""
    status: ViewResultStatus
    path: str
    content: str
    message: str = ""
    total_lines: int = 0
    is_truncated: bool = False
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())


class CodeViewer:
    """
    Code viewer for files and directories.
    
    Provides:
    - File viewing with line numbers
    - Directory structure listing
    - Regex search with context
    - Line range viewing
    """
    
    MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB
    MAX_OUTPUT_LINES = 1000
    
    def __init__(self, workspace_root: str = None):
        """
        Initialize code viewer.
        
        Args:
            workspace_root: Root directory for relative paths
        """
        self.workspace_root = Path(workspace_root) if workspace_root else Path.cwd()
    
    def _resolve_path(self, path: str) -> Path:
        """Resolve a path relative to workspace root."""
        p = Path(path)
        if p.is_absolute():
            return p
        return self.workspace_root / p
    
    def _validate_path(self, path: Path) -> Tuple[bool, str]:
        """Validate a file path for security."""
        try:
            resolved = path.resolve()
            workspace_resolved = self.workspace_root.resolve()
            
            if not str(resolved).startswith(str(workspace_resolved)):
                return False, "Path is outside workspace directory"
            
            return True, ""
        except Exception as e:
            return False, f"Path validation failed: {e}"
    
    def _add_line_numbers(self, content: str, start_line: int = 1) -> str:
        """Add line numbers to content."""
        lines = content.split('\n')
        numbered_lines = []
        for i, line in enumerate(lines, start=start_line):
            numbered_lines.append(f"{i:6d}\t{line}")
        return '\n'.join(numbered_lines)
    
    def view_file(self, request: ViewRequest) -> ViewResult:
        """
        View a file with optional line range and regex search.
        
        Args:
            request: ViewRequest with path and options
            
        Returns:
            ViewResult with file content
        """
        path = self._resolve_path(request.path)
        
        # Validate path
        valid, error = self._validate_path(path)
        if not valid:
            return ViewResult(
                status=ViewResultStatus.ERROR,
                path=str(path),
                content="",
                message=error
            )
        
        # Check file exists
        if not path.exists():
            return ViewResult(
                status=ViewResultStatus.FILE_NOT_FOUND,
                path=str(path),
                content="",
                message=f"File not found: {path}"
            )
        
        if path.is_dir():
            return self.view_directory(request)
        
        try:
            # Check file size
            file_size = path.stat().st_size
            if file_size > self.MAX_FILE_SIZE:
                return ViewResult(
                    status=ViewResultStatus.ERROR,
                    path=str(path),
                    content="",
                    message=f"File too large: {file_size} bytes (max: {self.MAX_FILE_SIZE})"
                )
            
            # Read file content
            content = path.read_text(encoding='utf-8', errors='replace')
            lines = content.split('\n')
            total_lines = len(lines)
            
            # Apply regex search if specified
            if request.search_query_regex:
                return self._search_file(request, content, lines, path)
            
            # Apply line range if specified
            if request.view_range:
                start, end = request.view_range
                if start < 1:
                    start = 1
                if end == -1:
                    end = total_lines
                if start > total_lines:
                    return ViewResult(
                        status=ViewResultStatus.INVALID_RANGE,
                        path=str(path),
                        content="",
                        message=f"Start line {start} exceeds file length ({total_lines} lines)"
                    )
                
                # Extract range (convert to 0-based)
                selected_lines = lines[start-1:end]
                content = '\n'.join(selected_lines)
                content = self._add_line_numbers(content, start)
            else:
                content = self._add_line_numbers(content)

            # Truncate if too long
            output_lines = content.split('\n')
            is_truncated = len(output_lines) > self.MAX_OUTPUT_LINES
            if is_truncated:
                content = '\n'.join(output_lines[:self.MAX_OUTPUT_LINES])
                content += f"\n\n<response clipped - showing {self.MAX_OUTPUT_LINES} of {len(output_lines)} lines>"

            return ViewResult(
                status=ViewResultStatus.SUCCESS,
                path=str(path),
                content=content,
                total_lines=total_lines,
                is_truncated=is_truncated
            )

        except PermissionError:
            return ViewResult(
                status=ViewResultStatus.PERMISSION_DENIED,
                path=str(path),
                content="",
                message=f"Permission denied: {path}"
            )
        except Exception as e:
            logger.error(f"Error viewing file: {e}")
            return ViewResult(
                status=ViewResultStatus.ERROR,
                path=str(path),
                content="",
                message=f"Error: {e}"
            )

    def _search_file(
        self,
        request: ViewRequest,
        content: str,
        lines: List[str],
        path: Path
    ) -> ViewResult:
        """Search file content with regex and return matches with context."""
        try:
            flags = 0 if request.case_sensitive else re.IGNORECASE
            pattern = re.compile(request.search_query_regex, flags)
        except re.error as e:
            return ViewResult(
                status=ViewResultStatus.REGEX_ERROR,
                path=str(path),
                content="",
                message=f"Invalid regex pattern: {e}"
            )

        # Find matching lines
        matching_indices = set()
        for i, line in enumerate(lines):
            if pattern.search(line):
                matching_indices.add(i)

        if not matching_indices:
            return ViewResult(
                status=ViewResultStatus.SUCCESS,
                path=str(path),
                content="No matches found.",
                total_lines=len(lines),
                message=f"No matches for pattern: {request.search_query_regex}"
            )

        # Build output with context
        output_parts = []
        shown_lines = set()

        for match_idx in sorted(matching_indices):
            start = max(0, match_idx - request.context_lines_before)
            end = min(len(lines), match_idx + request.context_lines_after + 1)

            # Add separator if there's a gap
            if shown_lines and start > max(shown_lines) + 1:
                output_parts.append("...")

            for i in range(start, end):
                if i not in shown_lines:
                    prefix = ">" if i in matching_indices else " "
                    output_parts.append(f"{i+1:6d}{prefix}\t{lines[i]}")
                    shown_lines.add(i)

        return ViewResult(
            status=ViewResultStatus.SUCCESS,
            path=str(path),
            content='\n'.join(output_parts),
            total_lines=len(lines),
            message=f"Found {len(matching_indices)} matches"
        )

    def view_directory(self, request: ViewRequest) -> ViewResult:
        """
        View directory structure.

        Args:
            request: ViewRequest with path

        Returns:
            ViewResult with directory listing
        """
        path = self._resolve_path(request.path)

        # Validate path
        valid, error = self._validate_path(path)
        if not valid:
            return ViewResult(
                status=ViewResultStatus.ERROR,
                path=str(path),
                content="",
                message=error
            )

        if not path.exists():
            return ViewResult(
                status=ViewResultStatus.FILE_NOT_FOUND,
                path=str(path),
                content="",
                message=f"Directory not found: {path}"
            )

        if not path.is_dir():
            return self.view_file(request)

        try:
            output_lines = [f"Directory: {path}", ""]
            self._list_directory(path, output_lines, 0, request.max_depth)

            return ViewResult(
                status=ViewResultStatus.SUCCESS,
                path=str(path),
                content='\n'.join(output_lines)
            )

        except PermissionError:
            return ViewResult(
                status=ViewResultStatus.PERMISSION_DENIED,
                path=str(path),
                content="",
                message=f"Permission denied: {path}"
            )
        except Exception as e:
            logger.error(f"Error viewing directory: {e}")
            return ViewResult(
                status=ViewResultStatus.ERROR,
                path=str(path),
                content="",
                message=f"Error: {e}"
            )

    def _list_directory(
        self,
        path: Path,
        output: List[str],
        depth: int,
        max_depth: int
    ) -> None:
        """Recursively list directory contents."""
        if depth > max_depth:
            return

        indent = "  " * depth

        try:
            entries = sorted(path.iterdir(), key=lambda x: (not x.is_dir(), x.name.lower()))

            for entry in entries:
                # Skip hidden files and common ignore patterns
                if entry.name.startswith('.') or entry.name in ('__pycache__', 'node_modules', 'venv', '.git'):
                    continue

                if entry.is_dir():
                    output.append(f"{indent}📁 {entry.name}/")
                    self._list_directory(entry, output, depth + 1, max_depth)
                else:
                    size = entry.stat().st_size
                    size_str = self._format_size(size)
                    output.append(f"{indent}📄 {entry.name} ({size_str})")
        except PermissionError:
            output.append(f"{indent}⚠️ Permission denied")

    def _format_size(self, size: int) -> str:
        """Format file size in human-readable format."""
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size < 1024:
                return f"{size:.1f}{unit}" if unit != 'B' else f"{size}{unit}"
            size /= 1024
        return f"{size:.1f}TB"

    def view(self, request: ViewRequest) -> ViewResult:
        """
        Main entry point for viewing files or directories.

        Args:
            request: ViewRequest with path and options

        Returns:
            ViewResult with content
        """
        if request.view_type == "directory":
            return self.view_directory(request)
        return self.view_file(request)


# Factory function
_viewer_instance: Optional[CodeViewer] = None


def get_code_viewer(workspace_root: str = None) -> CodeViewer:
    """
    Get or create a CodeViewer instance.

    Args:
        workspace_root: Root directory for relative paths

    Returns:
        CodeViewer instance
    """
    global _viewer_instance
    if _viewer_instance is None or workspace_root is not None:
        _viewer_instance = CodeViewer(workspace_root=workspace_root)
    return _viewer_instance
