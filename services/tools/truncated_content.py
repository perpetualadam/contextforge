"""
ContextForge Truncated Content Tools - View and search within truncated content.

Provides tools for working with truncated content:
- View specific line ranges from truncated content
- Search within truncated content with context
- Manage content references for retrieval

Copyright (c) 2025 ContextForge
"""

import re
import uuid
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from enum import Enum

logger = logging.getLogger(__name__)


class TruncatedContentStatus(Enum):
    """Status of a truncated content operation."""
    SUCCESS = "success"
    REFERENCE_NOT_FOUND = "reference_not_found"
    REFERENCE_EXPIRED = "reference_expired"
    INVALID_RANGE = "invalid_range"
    NO_MATCHES = "no_matches"
    REGEX_ERROR = "regex_error"
    ERROR = "error"


@dataclass
class ContentReference:
    """Reference to stored truncated content."""
    reference_id: str
    content: str
    source: str  # e.g., file path, command output
    total_lines: int
    created_at: str
    expires_at: Optional[str] = None
    metadata: Dict = field(default_factory=dict)


@dataclass
class ViewRangeRequest:
    """Request to view a range of lines from truncated content."""
    reference_id: str
    start_line: int  # 1-based, inclusive
    end_line: int  # 1-based, inclusive


@dataclass
class ViewRangeResult:
    """Result of viewing a range from truncated content."""
    status: TruncatedContentStatus
    reference_id: str
    content: str
    message: str = ""
    start_line: int = 0
    end_line: int = 0
    total_lines: int = 0
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())


@dataclass
class SearchMatch:
    """A single search match with context."""
    line_number: int
    line_content: str
    match_start: int  # Character position in line
    match_end: int
    context_before: List[str] = field(default_factory=list)
    context_after: List[str] = field(default_factory=list)


@dataclass
class SearchRequest:
    """Request to search within truncated content."""
    reference_id: str
    search_term: str
    use_regex: bool = False
    case_sensitive: bool = False
    context_lines: int = 2  # Lines before and after match


@dataclass
class SearchResult:
    """Result of searching truncated content."""
    status: TruncatedContentStatus
    reference_id: str
    matches: List[SearchMatch] = field(default_factory=list)
    message: str = ""
    total_matches: int = 0
    total_lines: int = 0
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())


class TruncatedContentManager:
    """
    Manager for truncated content viewing and searching.
    
    When content is truncated during viewing, it can be stored with a reference ID
    for later retrieval via view_range or search operations.
    
    Provides:
    - Store truncated content with reference IDs
    - View specific line ranges
    - Search with regex or plain text
    - Context lines around matches
    - Automatic expiration of old references
    
    Example usage:
        manager = TruncatedContentManager()
        
        # Store content
        ref_id = manager.store_content(large_content, "file.py")
        
        # View specific range
        result = manager.view_range(ViewRangeRequest(
            reference_id=ref_id,
            start_line=100,
            end_line=150
        ))
        
        # Search content
        result = manager.search(SearchRequest(
            reference_id=ref_id,
            search_term="def.*function",
            use_regex=True
        ))
    
    Security considerations:
        - Reference IDs are UUIDs to prevent guessing
        - Content expires after configurable time
        - Maximum storage limits enforced
    """
    
    DEFAULT_EXPIRY_HOURS = 1
    MAX_STORED_REFERENCES = 100
    MAX_CONTENT_SIZE = 50 * 1024 * 1024  # 50MB total
    MAX_SEARCH_RESULTS = 100
    
    def __init__(self, expiry_hours: int = None):
        """
        Initialize truncated content manager.

        Args:
            expiry_hours: Hours until content references expire
        """
        self._expiry_hours = expiry_hours or self.DEFAULT_EXPIRY_HOURS
        self._references: Dict[str, ContentReference] = {}
        self._total_size = 0

    def _generate_reference_id(self) -> str:
        """Generate a unique reference ID."""
        return str(uuid.uuid4())[:8]  # Short ID for usability

    def _cleanup_expired(self) -> None:
        """Remove expired references."""
        now = datetime.now()
        expired = []

        for ref_id, ref in self._references.items():
            if ref.expires_at:
                expires = datetime.fromisoformat(ref.expires_at)
                if now > expires:
                    expired.append(ref_id)

        for ref_id in expired:
            self._remove_reference(ref_id)
            logger.debug(f"Removed expired reference: {ref_id}")

    def _remove_reference(self, reference_id: str) -> None:
        """Remove a reference and update size tracking."""
        if reference_id in self._references:
            ref = self._references[reference_id]
            self._total_size -= len(ref.content)
            del self._references[reference_id]

    def _enforce_limits(self) -> None:
        """Enforce storage limits by removing oldest references."""
        # Remove expired first
        self._cleanup_expired()

        # Remove oldest if over count limit
        while len(self._references) >= self.MAX_STORED_REFERENCES:
            oldest_id = min(
                self._references.keys(),
                key=lambda k: self._references[k].created_at
            )
            self._remove_reference(oldest_id)
            logger.debug(f"Removed oldest reference due to limit: {oldest_id}")

    def store_content(
        self,
        content: str,
        source: str = "",
        metadata: Dict = None
    ) -> str:
        """
        Store content and return a reference ID.

        Args:
            content: The content to store
            source: Source description (e.g., file path)
            metadata: Optional metadata dict

        Returns:
            Reference ID for later retrieval
        """
        self._enforce_limits()

        reference_id = self._generate_reference_id()
        now = datetime.now()
        expires = now + timedelta(hours=self._expiry_hours)

        lines = content.split('\n')
        ref = ContentReference(
            reference_id=reference_id,
            content=content,
            source=source,
            total_lines=len(lines),
            created_at=now.isoformat(),
            expires_at=expires.isoformat(),
            metadata=metadata or {}
        )

        self._references[reference_id] = ref
        self._total_size += len(content)

        logger.info(f"Stored content reference {reference_id}: {len(lines)} lines from {source}")
        return reference_id

    def get_reference(self, reference_id: str) -> Optional[ContentReference]:
        """Get a content reference by ID."""
        self._cleanup_expired()
        return self._references.get(reference_id)

    def view_range(self, request: ViewRangeRequest) -> ViewRangeResult:
        """
        View a specific line range from stored content.

        Args:
            request: ViewRangeRequest with reference ID and line range

        Returns:
            ViewRangeResult with requested content
        """
        ref = self.get_reference(request.reference_id)

        if ref is None:
            return ViewRangeResult(
                status=TruncatedContentStatus.REFERENCE_NOT_FOUND,
                reference_id=request.reference_id,
                content="",
                message=f"Reference '{request.reference_id}' not found or expired"
            )

        lines = ref.content.split('\n')
        total_lines = len(lines)

        # Validate range
        start = request.start_line
        end = request.end_line

        if start < 1 or end < 1:
            return ViewRangeResult(
                status=TruncatedContentStatus.INVALID_RANGE,
                reference_id=request.reference_id,
                content="",
                message="Line numbers must be >= 1"
            )

        if start > end:
            return ViewRangeResult(
                status=TruncatedContentStatus.INVALID_RANGE,
                reference_id=request.reference_id,
                content="",
                message=f"Start line ({start}) cannot be greater than end line ({end})"
            )

        if start > total_lines:
            return ViewRangeResult(
                status=TruncatedContentStatus.INVALID_RANGE,
                reference_id=request.reference_id,
                content="",
                message=f"Start line ({start}) exceeds total lines ({total_lines})"
            )

        # Adjust end if needed
        end = min(end, total_lines)

        # Extract lines (convert to 0-based indexing)
        selected_lines = lines[start - 1:end]

        # Format with line numbers
        formatted = []
        for i, line in enumerate(selected_lines, start=start):
            formatted.append(f"{i:6d}\t{line}")

        return ViewRangeResult(
            status=TruncatedContentStatus.SUCCESS,
            reference_id=request.reference_id,
            content='\n'.join(formatted),
            message=f"Lines {start}-{end} of {total_lines}",
            start_line=start,
            end_line=end,
            total_lines=total_lines
        )

    def search(self, request: SearchRequest) -> SearchResult:
        """
        Search within stored content.

        Args:
            request: SearchRequest with reference ID, search term, and options

        Returns:
            SearchResult with matches and context
        """
        ref = self.get_reference(request.reference_id)

        if ref is None:
            return SearchResult(
                status=TruncatedContentStatus.REFERENCE_NOT_FOUND,
                reference_id=request.reference_id,
                message=f"Reference '{request.reference_id}' not found or expired"
            )

        lines = ref.content.split('\n')
        total_lines = len(lines)

        # Compile pattern
        try:
            if request.use_regex:
                flags = 0 if request.case_sensitive else re.IGNORECASE
                pattern = re.compile(request.search_term, flags)
            else:
                # Escape for literal matching
                escaped = re.escape(request.search_term)
                flags = 0 if request.case_sensitive else re.IGNORECASE
                pattern = re.compile(escaped, flags)
        except re.error as e:
            return SearchResult(
                status=TruncatedContentStatus.REGEX_ERROR,
                reference_id=request.reference_id,
                message=f"Invalid regex pattern: {e}",
                total_lines=total_lines
            )

        # Search for matches
        matches = []
        context = request.context_lines

        for line_num, line in enumerate(lines, start=1):
            for match in pattern.finditer(line):
                if len(matches) >= self.MAX_SEARCH_RESULTS:
                    break

                # Get context lines
                ctx_before = []
                ctx_after = []

                for i in range(max(0, line_num - 1 - context), line_num - 1):
                    ctx_before.append(f"{i + 1:6d}\t{lines[i]}")

                for i in range(line_num, min(total_lines, line_num + context)):
                    ctx_after.append(f"{i + 1:6d}\t{lines[i]}")

                matches.append(SearchMatch(
                    line_number=line_num,
                    line_content=line,
                    match_start=match.start(),
                    match_end=match.end(),
                    context_before=ctx_before,
                    context_after=ctx_after
                ))

            if len(matches) >= self.MAX_SEARCH_RESULTS:
                break

        if not matches:
            return SearchResult(
                status=TruncatedContentStatus.NO_MATCHES,
                reference_id=request.reference_id,
                message=f"No matches found for '{request.search_term}'",
                total_lines=total_lines
            )

        return SearchResult(
            status=TruncatedContentStatus.SUCCESS,
            reference_id=request.reference_id,
            matches=matches,
            message=f"Found {len(matches)} matches",
            total_matches=len(matches),
            total_lines=total_lines
        )

    def format_search_results(self, result: SearchResult) -> str:
        """
        Format search results for display.

        Args:
            result: SearchResult to format

        Returns:
            Formatted string with matches and context
        """
        if result.status != TruncatedContentStatus.SUCCESS:
            return result.message

        output = []
        for match in result.matches:
            # Context before
            for ctx_line in match.context_before:
                output.append(ctx_line)

            # The matching line with highlight markers
            line_prefix = f"{match.line_number:6d}\t"
            highlighted = (
                match.line_content[:match.match_start] +
                ">>>" + match.line_content[match.match_start:match.match_end] + "<<<" +
                match.line_content[match.match_end:]
            )
            output.append(f"{line_prefix}{highlighted}")

            # Context after
            for ctx_line in match.context_after:
                output.append(ctx_line)

            output.append("...")  # Separator between matches

        return '\n'.join(output)

    def list_references(self) -> List[ContentReference]:
        """Get list of all active references."""
        self._cleanup_expired()
        return list(self._references.values())

    def clear(self) -> None:
        """Clear all stored references."""
        self._references.clear()
        self._total_size = 0


# Factory function
_content_manager_instance: Optional[TruncatedContentManager] = None


def get_truncated_content_manager() -> TruncatedContentManager:
    """
    Get or create a TruncatedContentManager instance.

    Returns:
        TruncatedContentManager instance
    """
    global _content_manager_instance
    if _content_manager_instance is None:
        _content_manager_instance = TruncatedContentManager()
    return _content_manager_instance


def reset_truncated_content_manager() -> None:
    """Reset the singleton instance. Useful for testing."""
    global _content_manager_instance
    _content_manager_instance = None

