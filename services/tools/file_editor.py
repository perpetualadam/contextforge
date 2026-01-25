"""
ContextForge File Editor - String replacement and file manipulation tools.

Provides precise file editing capabilities:
- str-replace-editor: Exact string replacement in files
- save-file: Create new files with content
- remove-files: Safely delete files

Copyright (c) 2025 ContextForge
"""

import os
import logging
import hashlib
import shutil
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
from enum import Enum

logger = logging.getLogger(__name__)


class EditResultStatus(Enum):
    """Status of an edit operation."""
    SUCCESS = "success"
    ERROR = "error"
    NO_MATCH = "no_match"
    MULTIPLE_MATCHES = "multiple_matches"
    FILE_NOT_FOUND = "file_not_found"
    PERMISSION_DENIED = "permission_denied"
    VALIDATION_ERROR = "validation_error"


@dataclass
class StrReplaceEntry:
    """Single string replacement entry."""
    old_str: str
    new_str: str
    start_line: Optional[int] = None  # 1-based line number
    end_line: Optional[int] = None    # 1-based line number, inclusive


@dataclass
class StrReplaceRequest:
    """Request for string replacement operations."""
    path: str
    replacements: List[StrReplaceEntry]
    create_backup: bool = True


@dataclass
class SaveFileRequest:
    """Request to create/save a new file."""
    path: str
    content: str
    overwrite: bool = False
    create_directories: bool = True
    add_trailing_newline: bool = True
    encoding: str = "utf-8"


@dataclass
class RemoveFilesRequest:
    """
    Request to remove files safely.

    Attributes:
        paths: List of file paths to remove
        allow_directories: Allow removing directories (default: False)
        create_backup: Create backup before deletion (default: True)
        force: Skip safety checks for protected paths (default: False)
        dry_run: Only check what would be deleted without deleting (default: False)
    """
    paths: List[str]
    allow_directories: bool = False
    create_backup: bool = True
    force: bool = False
    dry_run: bool = False


@dataclass
class FileEditResult:
    """Result of a file edit operation."""
    status: EditResultStatus
    path: str
    message: str
    backup_path: Optional[str] = None
    changes_made: int = 0
    snippet: str = ""
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())


class FileEditor:
    """
    File editor for precise string replacements and file operations.

    Provides safe file editing with:
    - Exact string matching for replacements
    - Line number disambiguation for multiple matches
    - Automatic backup creation
    - Directory creation for new files
    - Protected path validation for safe deletion

    Security considerations:
        - Path traversal prevention
        - Protected system paths cannot be deleted without force flag
        - Backups created before destructive operations
    """

    # Protected paths that cannot be deleted without force flag
    PROTECTED_PATTERNS = [
        ".git",
        ".gitignore",
        ".env",
        "node_modules",
        "__pycache__",
        ".venv",
        "venv",
        ".contextforge",
        "package-lock.json",
        "yarn.lock",
        "poetry.lock",
        "Pipfile.lock",
    ]

    # System paths that are never allowed to be deleted
    SYSTEM_PROTECTED_PATHS = [
        "/",
        "/bin",
        "/usr",
        "/etc",
        "/var",
        "/home",
        "/root",
        "C:\\",
        "C:\\Windows",
        "C:\\Program Files",
        "C:\\Program Files (x86)",
        "C:\\Users",
    ]

    def __init__(self, workspace_root: str = None, backup_dir: str = None):
        """
        Initialize file editor.

        Args:
            workspace_root: Root directory for relative paths
            backup_dir: Directory for backup files (default: .contextforge/backups)
        """
        self.workspace_root = Path(workspace_root) if workspace_root else Path.cwd()
        self.backup_dir = Path(backup_dir) if backup_dir else self.workspace_root / ".contextforge" / "backups"

    def _is_protected_path(self, path: Path) -> Tuple[bool, str]:
        """
        Check if a path is protected from deletion.

        Args:
            path: Path to check

        Returns:
            Tuple of (is_protected, reason)
        """
        path_str = str(path.resolve())
        path_name = path.name

        # Check system protected paths
        for sys_path in self.SYSTEM_PROTECTED_PATHS:
            if path_str.lower() == sys_path.lower() or path_str.lower().rstrip("/\\") == sys_path.lower().rstrip("/\\"):
                return True, f"System protected path: {sys_path}"

        # Check protected patterns
        for pattern in self.PROTECTED_PATTERNS:
            if path_name == pattern or pattern in path.parts:
                return True, f"Protected path pattern: {pattern}"

        return False, ""
        
    def _resolve_path(self, path: str) -> Path:
        """Resolve a path relative to workspace root."""
        p = Path(path)
        if p.is_absolute():
            return p
        return self.workspace_root / p
    
    def _validate_path(self, path: Path) -> Tuple[bool, str]:
        """Validate a file path for security."""
        try:
            # Resolve to absolute path
            resolved = path.resolve()
            workspace_resolved = self.workspace_root.resolve()
            
            # Check if within workspace (prevent path traversal)
            if not str(resolved).startswith(str(workspace_resolved)):
                return False, "Path is outside workspace directory"
            
            return True, ""
        except Exception as e:
            return False, f"Path validation failed: {e}"
    
    def _create_backup(self, path: Path) -> Optional[Path]:
        """Create a backup of a file before editing."""
        if not path.exists():
            return None
            
        try:
            self.backup_dir.mkdir(parents=True, exist_ok=True)
            
            # Create unique backup filename
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            content_hash = hashlib.md5(path.read_bytes()).hexdigest()[:8]
            backup_name = f"{path.name}.{timestamp}.{content_hash}.bak"
            backup_path = self.backup_dir / backup_name
            
            shutil.copy2(path, backup_path)
            logger.info(f"Created backup: {backup_path}")
            return backup_path
        except Exception as e:
            logger.warning(f"Failed to create backup: {e}")
            return None
    
    def _find_replacement_location(
        self,
        content: str,
        old_str: str,
        start_line: Optional[int] = None,
        end_line: Optional[int] = None
    ) -> Tuple[int, int, str]:
        """
        Find the location of old_str in content.

        Returns:
            Tuple of (start_index, end_index, error_message)
            If error, returns (-1, -1, error_message)
        """
        lines = content.split('\n')

        # If line numbers provided, search within that range
        if start_line is not None and end_line is not None:
            # Convert to 0-based indices
            start_idx = max(0, start_line - 1)
            end_idx = min(len(lines), end_line)

            # Get the substring for the line range
            line_content = '\n'.join(lines[start_idx:end_idx])

            if old_str not in line_content:
                return -1, -1, f"String not found in lines {start_line}-{end_line}"

            # Calculate the actual position in the full content
            prefix = '\n'.join(lines[:start_idx])
            if prefix:
                prefix += '\n'
            start_pos = len(prefix) + line_content.find(old_str)
            end_pos = start_pos + len(old_str)

            return start_pos, end_pos, ""

        # No line numbers - search entire content
        occurrences = []
        search_start = 0
        while True:
            pos = content.find(old_str, search_start)
            if pos == -1:
                break
            occurrences.append(pos)
            search_start = pos + 1

        if len(occurrences) == 0:
            return -1, -1, "String not found in file"

        if len(occurrences) > 1:
            # Find line numbers for each occurrence
            line_nums = []
            for pos in occurrences:
                line_num = content[:pos].count('\n') + 1
                line_nums.append(line_num)
            return -1, -1, f"Multiple matches found at lines: {line_nums}. Use line numbers to disambiguate."

        return occurrences[0], occurrences[0] + len(old_str), ""

    def str_replace(self, request: StrReplaceRequest) -> FileEditResult:
        """
        Perform string replacement operations on a file.

        Args:
            request: StrReplaceRequest with path and replacements

        Returns:
            FileEditResult with status and details
        """
        path = self._resolve_path(request.path)

        # Validate path
        valid, error = self._validate_path(path)
        if not valid:
            return FileEditResult(
                status=EditResultStatus.VALIDATION_ERROR,
                path=str(path),
                message=error
            )

        # Check file exists
        if not path.exists():
            return FileEditResult(
                status=EditResultStatus.FILE_NOT_FOUND,
                path=str(path),
                message=f"File not found: {path}"
            )

        try:
            # Read current content
            content = path.read_text(encoding='utf-8')
            original_content = content

            # Create backup if requested
            backup_path = None
            if request.create_backup:
                backup_path = self._create_backup(path)

            # Apply replacements
            changes_made = 0
            for entry in request.replacements:
                start_pos, end_pos, error = self._find_replacement_location(
                    content, entry.old_str, entry.start_line, entry.end_line
                )

                if error:
                    return FileEditResult(
                        status=EditResultStatus.NO_MATCH if "not found" in error.lower()
                               else EditResultStatus.MULTIPLE_MATCHES,
                        path=str(path),
                        message=error,
                        backup_path=str(backup_path) if backup_path else None
                    )

                # Perform the replacement
                content = content[:start_pos] + entry.new_str + content[end_pos:]
                changes_made += 1

            # Write the modified content
            path.write_text(content, encoding='utf-8')

            # Generate snippet of the changed area
            snippet = self._generate_snippet(content, request.replacements[0].new_str if request.replacements else "")

            logger.info(f"Successfully edited {path}: {changes_made} replacements")

            return FileEditResult(
                status=EditResultStatus.SUCCESS,
                path=str(path),
                message=f"Successfully made {changes_made} replacement(s)",
                backup_path=str(backup_path) if backup_path else None,
                changes_made=changes_made,
                snippet=snippet
            )

        except PermissionError:
            return FileEditResult(
                status=EditResultStatus.PERMISSION_DENIED,
                path=str(path),
                message=f"Permission denied: {path}"
            )
        except Exception as e:
            logger.error(f"Error editing file: {e}")
            return FileEditResult(
                status=EditResultStatus.ERROR,
                path=str(path),
                message=f"Error: {e}"
            )

    def _generate_snippet(self, content: str, search_str: str, context_lines: int = 3) -> str:
        """Generate a snippet showing the edited area with context."""
        if not search_str:
            return ""

        lines = content.split('\n')

        # Find the line containing the search string
        for i, line in enumerate(lines):
            if search_str in line or (len(search_str) > 50 and search_str[:50] in line):
                start = max(0, i - context_lines)
                end = min(len(lines), i + context_lines + 1)
                snippet_lines = []
                for j in range(start, end):
                    snippet_lines.append(f"{j + 1:4d} | {lines[j]}")
                return '\n'.join(snippet_lines)

        return ""

    def save_file(self, request: SaveFileRequest) -> FileEditResult:
        """
        Create or save a new file.

        Args:
            request: SaveFileRequest with path and content

        Returns:
            FileEditResult with status and details
        """
        path = self._resolve_path(request.path)

        # Validate path
        valid, error = self._validate_path(path)
        if not valid:
            return FileEditResult(
                status=EditResultStatus.VALIDATION_ERROR,
                path=str(path),
                message=error
            )

        # Check if file exists and overwrite not allowed
        if path.exists() and not request.overwrite:
            return FileEditResult(
                status=EditResultStatus.VALIDATION_ERROR,
                path=str(path),
                message="File already exists. Use overwrite=True to replace."
            )

        try:
            # Create directories if needed
            if request.create_directories:
                path.parent.mkdir(parents=True, exist_ok=True)

            # Prepare content
            content = request.content
            if request.add_trailing_newline and not content.endswith('\n'):
                content += '\n'

            # Write file
            path.write_text(content, encoding=request.encoding)

            logger.info(f"Successfully saved file: {path}")

            return FileEditResult(
                status=EditResultStatus.SUCCESS,
                path=str(path),
                message=f"Successfully created file: {path.name}",
                changes_made=1
            )

        except PermissionError:
            return FileEditResult(
                status=EditResultStatus.PERMISSION_DENIED,
                path=str(path),
                message=f"Permission denied: {path}"
            )
        except Exception as e:
            logger.error(f"Error saving file: {e}")
            return FileEditResult(
                status=EditResultStatus.ERROR,
                path=str(path),
                message=f"Error: {e}"
            )

    def remove_files(self, request: RemoveFilesRequest) -> List[FileEditResult]:
        """
        Remove files safely with protection against accidental deletion.

        Safety features:
        - Protected path validation (e.g., .git, node_modules)
        - System path protection (e.g., C:\\Windows, /usr)
        - Optional backup creation before deletion
        - Dry run mode to preview what would be deleted

        Args:
            request: RemoveFilesRequest with paths and options

        Returns:
            List of FileEditResult for each file

        Example:
            editor = get_file_editor()
            result = editor.remove_files(RemoveFilesRequest(
                paths=["temp.txt", "old_file.py"],
                create_backup=True,
                dry_run=False
            ))
        """
        results = []

        for file_path in request.paths:
            path = self._resolve_path(file_path)

            # Validate path security
            valid, error = self._validate_path(path)
            if not valid:
                results.append(FileEditResult(
                    status=EditResultStatus.VALIDATION_ERROR,
                    path=str(path),
                    message=error
                ))
                continue

            # Check if path exists
            if not path.exists():
                results.append(FileEditResult(
                    status=EditResultStatus.FILE_NOT_FOUND,
                    path=str(path),
                    message=f"File not found: {path}"
                ))
                continue

            # Check protected paths unless force is set
            if not request.force:
                is_protected, reason = self._is_protected_path(path)
                if is_protected:
                    results.append(FileEditResult(
                        status=EditResultStatus.VALIDATION_ERROR,
                        path=str(path),
                        message=f"Protected path: {reason}. Use force=True to override."
                    ))
                    continue

            # Check if it's a directory
            if path.is_dir() and not request.allow_directories:
                results.append(FileEditResult(
                    status=EditResultStatus.VALIDATION_ERROR,
                    path=str(path),
                    message="Cannot remove directory. Use allow_directories=True."
                ))
                continue

            # Dry run - just report what would be deleted
            if request.dry_run:
                file_type = "directory" if path.is_dir() else "file"
                results.append(FileEditResult(
                    status=EditResultStatus.SUCCESS,
                    path=str(path),
                    message=f"Would remove {file_type}: {path.name}",
                    changes_made=0
                ))
                continue

            try:
                # Create backup before removal if requested
                backup_path = None
                if request.create_backup:
                    backup_path = self._create_backup(path)

                # Remove file or directory
                if path.is_dir():
                    shutil.rmtree(path)
                else:
                    path.unlink()

                logger.info(f"Successfully removed: {path}")

                results.append(FileEditResult(
                    status=EditResultStatus.SUCCESS,
                    path=str(path),
                    message=f"Successfully removed: {path.name}",
                    backup_path=str(backup_path) if backup_path else None,
                    changes_made=1
                ))

            except PermissionError:
                results.append(FileEditResult(
                    status=EditResultStatus.PERMISSION_DENIED,
                    path=str(path),
                    message=f"Permission denied: {path}"
                ))
            except Exception as e:
                logger.error(f"Error removing file: {e}")
                results.append(FileEditResult(
                    status=EditResultStatus.ERROR,
                    path=str(path),
                    message=f"Error: {e}"
                ))

        return results


# Factory function for easy instantiation
_editor_instance: Optional[FileEditor] = None


def get_file_editor(workspace_root: str = None) -> FileEditor:
    """
    Get or create a FileEditor instance.

    Args:
        workspace_root: Root directory for relative paths

    Returns:
        FileEditor instance
    """
    global _editor_instance
    if _editor_instance is None or workspace_root is not None:
        _editor_instance = FileEditor(workspace_root=workspace_root)
    return _editor_instance

