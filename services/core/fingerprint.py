"""
File Fingerprint Tracking for Drift Detection.

Tracks file hashes, timestamps, and symbols to detect external changes
and prevent stale edits in multi-agent/multi-tool environments.

Copyright (c) 2025 ContextForge
"""

import hashlib
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Set
import os
import re

logger = logging.getLogger(__name__)


@dataclass
class FileFingerprint:
    """Fingerprint of a file at a specific point in time."""
    
    path: str
    content_hash: str  # SHA256 of file content
    mtime: float  # Last modified timestamp
    size: int  # File size in bytes
    symbols: Set[str] = field(default_factory=set)  # Functions, classes, etc.
    captured_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    
    def matches_filesystem(self, tolerance_seconds: float = 0.1) -> bool:
        """Check if fingerprint matches current filesystem state."""
        try:
            path_obj = Path(self.path)
            if not path_obj.exists():
                return False
            
            stat = path_obj.stat()
            
            # Check size first (fast)
            if stat.st_size != self.size:
                return False
            
            # Check mtime with tolerance for filesystem precision
            if abs(stat.st_mtime - self.mtime) > tolerance_seconds:
                return False
            
            # Check content hash (slower but definitive)
            current_hash = compute_file_hash(self.path)
            return current_hash == self.content_hash
            
        except Exception as e:
            logger.error(f"Error checking fingerprint for {self.path}: {e}")
            return False
    
    def to_dict(self) -> dict:
        """Serialize to dictionary."""
        return {
            "path": self.path,
            "content_hash": self.content_hash,
            "mtime": self.mtime,
            "size": self.size,
            "symbols": list(self.symbols),
            "captured_at": self.captured_at.isoformat(),
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "FileFingerprint":
        """Deserialize from dictionary."""
        return cls(
            path=data["path"],
            content_hash=data["content_hash"],
            mtime=data["mtime"],
            size=data["size"],
            symbols=set(data.get("symbols", [])),
            captured_at=datetime.fromisoformat(data["captured_at"]),
        )


def compute_file_hash(file_path: str) -> str:
    """Compute SHA256 hash of file content."""
    hasher = hashlib.sha256()
    try:
        with open(file_path, 'rb') as f:
            for chunk in iter(lambda: f.read(8192), b''):
                hasher.update(chunk)
        return hasher.hexdigest()
    except Exception as e:
        logger.error(f"Error hashing file {file_path}: {e}")
        return ""


def extract_symbols(file_path: str, language: Optional[str] = None) -> Set[str]:
    """Extract function/class names from source file."""
    symbols = set()
    
    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
        
        # Python symbols
        if file_path.endswith('.py') or language == 'python':
            # Classes
            symbols.update(re.findall(r'^class\s+(\w+)', content, re.MULTILINE))
            # Functions
            symbols.update(re.findall(r'^def\s+(\w+)', content, re.MULTILINE))
            symbols.update(re.findall(r'^\s+def\s+(\w+)', content, re.MULTILINE))
        
        # JavaScript/TypeScript symbols
        elif file_path.endswith(('.js', '.ts', '.jsx', '.tsx')) or language in ('javascript', 'typescript'):
            symbols.update(re.findall(r'class\s+(\w+)', content))
            symbols.update(re.findall(r'function\s+(\w+)', content))
            symbols.update(re.findall(r'const\s+(\w+)\s*=\s*(?:async\s+)?(?:function|\()', content))
        
        # Java symbols
        elif file_path.endswith('.java') or language == 'java':
            symbols.update(re.findall(r'class\s+(\w+)', content))
            symbols.update(re.findall(r'interface\s+(\w+)', content))
            symbols.update(re.findall(r'(?:public|private|protected)\s+\w+\s+(\w+)\s*\(', content))
        
        # C/C++ symbols
        elif file_path.endswith(('.c', '.cpp', '.h', '.hpp')) or language in ('c', 'cpp'):
            symbols.update(re.findall(r'class\s+(\w+)', content))
            symbols.update(re.findall(r'struct\s+(\w+)', content))
            symbols.update(re.findall(r'\w+\s+(\w+)\s*\([^)]*\)\s*{', content))
        
    except Exception as e:
        logger.warning(f"Error extracting symbols from {file_path}: {e}")
    
    return symbols


def capture_fingerprint(file_path: str, language: Optional[str] = None) -> Optional[FileFingerprint]:
    """Capture current fingerprint of a file."""
    try:
        path_obj = Path(file_path)
        if not path_obj.exists():
            return None
        
        stat = path_obj.stat()
        content_hash = compute_file_hash(file_path)
        symbols = extract_symbols(file_path, language)
        
        return FileFingerprint(
            path=file_path,
            content_hash=content_hash,
            mtime=stat.st_mtime,
            size=stat.st_size,
            symbols=symbols,
        )
    except Exception as e:
        logger.error(f"Error capturing fingerprint for {file_path}: {e}")
        return None

