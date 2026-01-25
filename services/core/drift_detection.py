"""
Drift Detection and Scoped Re-Grounding.

Detects when files have changed externally (human edits, other tools, CI)
and triggers scoped re-grounding to maintain consistency.

Copyright (c) 2025 ContextForge
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Set
from enum import Enum

from .fingerprint import FileFingerprint, capture_fingerprint

logger = logging.getLogger(__name__)


class DriftSeverity(Enum):
    """Severity of detected drift."""
    NONE = "none"
    MINOR = "minor"  # Timestamp changed but content same
    MODERATE = "moderate"  # Content changed, symbols intact
    MAJOR = "major"  # Symbols changed or file deleted


@dataclass
class DriftEvent:
    """Record of a drift detection event."""
    
    file_path: str
    severity: DriftSeverity
    expected_hash: str
    actual_hash: Optional[str]
    expected_symbols: Set[str]
    actual_symbols: Set[str]
    detected_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    
    def get_changed_symbols(self) -> tuple[Set[str], Set[str]]:
        """Return (added_symbols, removed_symbols)."""
        added = self.actual_symbols - self.expected_symbols
        removed = self.expected_symbols - self.actual_symbols
        return added, removed
    
    def to_dict(self) -> dict:
        """Serialize to dictionary."""
        return {
            "file_path": self.file_path,
            "severity": self.severity.value,
            "expected_hash": self.expected_hash,
            "actual_hash": self.actual_hash,
            "expected_symbols": list(self.expected_symbols),
            "actual_symbols": list(self.actual_symbols),
            "detected_at": self.detected_at.isoformat(),
        }


@dataclass
class DriftDetectionResult:
    """Result of drift detection across multiple files."""
    
    drifted_files: List[DriftEvent] = field(default_factory=list)
    stable_files: List[str] = field(default_factory=list)
    missing_files: List[str] = field(default_factory=list)
    
    @property
    def has_drift(self) -> bool:
        """Check if any drift was detected."""
        return len(self.drifted_files) > 0 or len(self.missing_files) > 0
    
    @property
    def max_severity(self) -> DriftSeverity:
        """Get maximum severity across all drifted files."""
        if self.missing_files:
            return DriftSeverity.MAJOR
        if not self.drifted_files:
            return DriftSeverity.NONE
        
        severities = [event.severity for event in self.drifted_files]
        if DriftSeverity.MAJOR in severities:
            return DriftSeverity.MAJOR
        if DriftSeverity.MODERATE in severities:
            return DriftSeverity.MODERATE
        return DriftSeverity.MINOR
    
    def get_affected_files(self) -> Set[str]:
        """Get all files affected by drift."""
        affected = set(self.missing_files)
        affected.update(event.file_path for event in self.drifted_files)
        return affected


class DriftDetector:
    """Detects drift between expected and actual file states."""
    
    def __init__(self):
        self.fingerprints: Dict[str, FileFingerprint] = {}
        self.drift_history: List[DriftEvent] = []
    
    def register_fingerprint(self, fingerprint: FileFingerprint) -> None:
        """Register a file fingerprint for tracking."""
        self.fingerprints[fingerprint.path] = fingerprint
        logger.debug(f"Registered fingerprint for {fingerprint.path}")
    
    def register_file(self, file_path: str, language: Optional[str] = None) -> bool:
        """Capture and register fingerprint for a file."""
        fingerprint = capture_fingerprint(file_path, language)
        if fingerprint:
            self.register_fingerprint(fingerprint)
            return True
        return False
    
    def detect_drift(self, file_paths: Optional[List[str]] = None) -> DriftDetectionResult:
        """
        Detect drift for specified files or all tracked files.
        
        Args:
            file_paths: Specific files to check, or None for all tracked files
        
        Returns:
            DriftDetectionResult with details of any drift detected
        """
        result = DriftDetectionResult()
        
        # Determine which files to check
        paths_to_check = file_paths if file_paths else list(self.fingerprints.keys())
        
        for file_path in paths_to_check:
            expected = self.fingerprints.get(file_path)
            if not expected:
                logger.warning(f"No fingerprint registered for {file_path}")
                continue
            
            # Check if file exists
            if not Path(file_path).exists():
                result.missing_files.append(file_path)
                logger.warning(f"File missing: {file_path}")
                continue
            
            # Capture current state
            actual = capture_fingerprint(file_path)
            if not actual:
                result.missing_files.append(file_path)
                continue
            
            # Compare fingerprints
            if expected.content_hash == actual.content_hash:
                result.stable_files.append(file_path)
                continue
            
            # Drift detected - determine severity
            severity = self._assess_severity(expected, actual)
            
            event = DriftEvent(
                file_path=file_path,
                severity=severity,
                expected_hash=expected.content_hash,
                actual_hash=actual.content_hash,
                expected_symbols=expected.symbols,
                actual_symbols=actual.symbols,
            )
            
            result.drifted_files.append(event)
            self.drift_history.append(event)
            
            logger.info(f"Drift detected in {file_path}: {severity.value}")
        
        return result
    
    def _assess_severity(self, expected: FileFingerprint, actual: FileFingerprint) -> DriftSeverity:
        """Assess severity of drift between two fingerprints."""
        # Check if symbols changed
        if expected.symbols != actual.symbols:
            return DriftSeverity.MAJOR
        
        # Content changed but symbols intact
        return DriftSeverity.MODERATE
    
    def update_fingerprint(self, file_path: str, language: Optional[str] = None) -> bool:
        """Update fingerprint after successful operation."""
        fingerprint = capture_fingerprint(file_path, language)
        if fingerprint:
            self.fingerprints[file_path] = fingerprint
            logger.debug(f"Updated fingerprint for {file_path}")
            return True
        return False
    
    def clear_fingerprints(self, file_paths: Optional[List[str]] = None) -> None:
        """Clear fingerprints for specified files or all files."""
        if file_paths:
            for path in file_paths:
                self.fingerprints.pop(path, None)
        else:
            self.fingerprints.clear()

