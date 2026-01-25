"""
Diff-Based Edit Engine.

Operates on file diffs rather than full content to prevent overwriting
unrelated code and improve token efficiency.

Copyright (c) 2025 ContextForge
"""

import difflib
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from enum import Enum

logger = logging.getLogger(__name__)


class DiffType(Enum):
    """Type of diff operation."""
    ADD = "add"
    REMOVE = "remove"
    MODIFY = "modify"


@dataclass
class LineDiff:
    """Represents a single line change."""
    
    line_number: int
    diff_type: DiffType
    old_content: Optional[str] = None
    new_content: Optional[str] = None
    context_before: List[str] = field(default_factory=list)
    context_after: List[str] = field(default_factory=list)


@dataclass
class FileDiff:
    """Represents all changes to a file."""
    
    file_path: str
    old_hash: Optional[str] = None
    new_hash: Optional[str] = None
    line_diffs: List[LineDiff] = field(default_factory=list)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    
    @property
    def total_additions(self) -> int:
        """Count total lines added."""
        return sum(1 for d in self.line_diffs if d.diff_type == DiffType.ADD)
    
    @property
    def total_deletions(self) -> int:
        """Count total lines removed."""
        return sum(1 for d in self.line_diffs if d.diff_type == DiffType.REMOVE)
    
    @property
    def total_modifications(self) -> int:
        """Count total lines modified."""
        return sum(1 for d in self.line_diffs if d.diff_type == DiffType.MODIFY)
    
    def to_unified_diff(self) -> str:
        """Convert to unified diff format."""
        lines = [f"--- {self.file_path}\n", f"+++ {self.file_path}\n"]
        
        for diff in self.line_diffs:
            if diff.diff_type == DiffType.ADD:
                lines.append(f"+{diff.new_content}\n")
            elif diff.diff_type == DiffType.REMOVE:
                lines.append(f"-{diff.old_content}\n")
            elif diff.diff_type == DiffType.MODIFY:
                lines.append(f"-{diff.old_content}\n")
                lines.append(f"+{diff.new_content}\n")
        
        return "".join(lines)


class DiffEngine:
    """Engine for computing and applying diffs."""
    
    def __init__(self, context_lines: int = 3):
        self.context_lines = context_lines
    
    def compute_diff(self, file_path: str, new_content: str) -> Optional[FileDiff]:
        """
        Compute diff between current file and new content.
        
        Args:
            file_path: Path to file
            new_content: Proposed new content
        
        Returns:
            FileDiff object or None if file doesn't exist
        """
        try:
            path_obj = Path(file_path)
            
            # Read current content
            if path_obj.exists():
                with open(file_path, 'r', encoding='utf-8') as f:
                    old_content = f.read()
            else:
                old_content = ""
            
            # Split into lines
            old_lines = old_content.splitlines(keepends=True)
            new_lines = new_content.splitlines(keepends=True)
            
            # Compute unified diff
            diff = difflib.unified_diff(
                old_lines,
                new_lines,
                fromfile=file_path,
                tofile=file_path,
                lineterm='',
            )
            
            # Parse diff into structured format
            file_diff = FileDiff(file_path=file_path)
            
            for line in diff:
                if line.startswith('---') or line.startswith('+++'):
                    continue
                elif line.startswith('@@'):
                    continue
                elif line.startswith('+'):
                    file_diff.line_diffs.append(LineDiff(
                        line_number=-1,  # Will be computed during application
                        diff_type=DiffType.ADD,
                        new_content=line[1:],
                    ))
                elif line.startswith('-'):
                    file_diff.line_diffs.append(LineDiff(
                        line_number=-1,
                        diff_type=DiffType.REMOVE,
                        old_content=line[1:],
                    ))
            
            return file_diff
            
        except Exception as e:
            logger.error(f"Error computing diff for {file_path}: {e}")
            return None
    
    def apply_diff(self, file_diff: FileDiff, dry_run: bool = False) -> bool:
        """
        Apply a diff to a file.
        
        Args:
            file_diff: Diff to apply
            dry_run: If True, validate but don't write
        
        Returns:
            True if successful, False otherwise
        """
        try:
            path_obj = Path(file_diff.file_path)
            
            # Read current content
            if path_obj.exists():
                with open(file_diff.file_path, 'r', encoding='utf-8') as f:
                    lines = f.readlines()
            else:
                lines = []
            
            # Apply diffs
            for diff in file_diff.line_diffs:
                if diff.diff_type == DiffType.ADD and diff.new_content:
                    lines.append(diff.new_content)
                elif diff.diff_type == DiffType.REMOVE and diff.old_content:
                    if diff.old_content in lines:
                        lines.remove(diff.old_content)
            
            if not dry_run:
                # Write updated content
                path_obj.parent.mkdir(parents=True, exist_ok=True)
                with open(file_diff.file_path, 'w', encoding='utf-8') as f:
                    f.writelines(lines)
                
                logger.info(f"Applied diff to {file_diff.file_path}: "
                           f"+{file_diff.total_additions} -{file_diff.total_deletions}")
            
            return True
            
        except Exception as e:
            logger.error(f"Error applying diff to {file_diff.file_path}: {e}")
            return False
    
    def get_context_around_line(self, file_path: str, line_number: int) -> Tuple[List[str], List[str]]:
        """Get context lines before and after a specific line."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
            
            start = max(0, line_number - self.context_lines)
            end = min(len(lines), line_number + self.context_lines + 1)
            
            before = lines[start:line_number]
            after = lines[line_number + 1:end]
            
            return before, after
            
        except Exception as e:
            logger.error(f"Error getting context for {file_path}:{line_number}: {e}")
            return [], []

