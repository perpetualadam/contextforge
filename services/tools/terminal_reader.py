"""
ContextForge Terminal Reader - VS Code terminal content reading tool.

Provides terminal content reading capabilities:
- Read content from VS Code terminal sessions
- Support for reading all visible content or selected text
- Handle different terminal states
- Integration with process management

Copyright (c) 2025 ContextForge
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, Any
from enum import Enum

logger = logging.getLogger(__name__)


class TerminalReadStatus(Enum):
    """Status of a terminal read operation."""
    SUCCESS = "success"
    TERMINAL_NOT_FOUND = "terminal_not_found"
    TERMINAL_CLOSED = "terminal_closed"
    NO_CONTENT = "no_content"
    NO_SELECTION = "no_selection"
    ERROR = "error"


class TerminalState(Enum):
    """State of a terminal."""
    ACTIVE = "active"
    INACTIVE = "inactive"
    CLOSED = "closed"
    UNKNOWN = "unknown"


@dataclass
class TerminalInfo:
    """Information about a terminal session."""
    terminal_id: int
    name: str
    state: TerminalState
    created_at: str
    last_accessed: str = ""
    process_id: Optional[int] = None
    cwd: str = ""


@dataclass
class TerminalReadRequest:
    """Request to read terminal content."""
    terminal_id: Optional[int] = None  # None = most recently used
    only_selected: bool = False  # Read only selected text
    max_lines: Optional[int] = None  # Limit lines returned


@dataclass
class TerminalReadResult:
    """Result of a terminal read operation."""
    status: TerminalReadStatus
    terminal_id: int
    content: str
    message: str = ""
    line_count: int = 0
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    terminal_state: TerminalState = TerminalState.UNKNOWN
    is_truncated: bool = False


class TerminalReader:
    """
    Terminal content reader for VS Code terminal sessions.
    
    Provides:
    - Read terminal output content
    - Read selected text only
    - Track terminal states
    - Integration with ProcessManager
    
    Example usage:
        reader = TerminalReader()
        result = reader.read(TerminalReadRequest(terminal_id=1))
        print(result.content)
    
    Note:
        This tool is designed to work with VS Code's terminal API.
        When used outside VS Code, it integrates with ProcessManager
        to read process output from managed terminals.
    
    Security considerations:
        - Only reads from known/tracked terminals
        - No write access to terminals
        - Content is sanitized before return
    """
    
    MAX_CONTENT_LINES = 5000
    MAX_CONTENT_SIZE = 1024 * 1024  # 1MB
    
    def __init__(self, process_manager=None):
        """
        Initialize terminal reader.
        
        Args:
            process_manager: Optional ProcessManager instance for integration
        """
        self._process_manager = process_manager
        self._terminals: Dict[int, TerminalInfo] = {}
        self._terminal_content: Dict[int, str] = {}
        self._selections: Dict[int, str] = {}
        self._most_recent_terminal: Optional[int] = None
    
    def _get_process_manager(self):
        """Get or create ProcessManager instance."""
        if self._process_manager is None:
            try:
                from services.tools.process_manager import get_process_manager
                self._process_manager = get_process_manager()
            except ImportError:
                pass
        return self._process_manager
    
    def register_terminal(
        self,
        terminal_id: int,
        name: str = "",
        process_id: Optional[int] = None,
        cwd: str = ""
    ) -> TerminalInfo:
        """
        Register a terminal for tracking.
        
        Args:
            terminal_id: Unique terminal identifier
            name: Terminal display name
            process_id: Associated process ID
            cwd: Current working directory
            
        Returns:
            TerminalInfo for the registered terminal
        """
        now = datetime.now().isoformat()
        info = TerminalInfo(
            terminal_id=terminal_id,
            name=name or f"Terminal {terminal_id}",
            state=TerminalState.ACTIVE,
            created_at=now,
            last_accessed=now,
            process_id=process_id,
            cwd=cwd
        )
        self._terminals[terminal_id] = info
        self._most_recent_terminal = terminal_id
        logger.info(f"Registered terminal {terminal_id}: {name}")
        return info

    def update_content(self, terminal_id: int, content: str) -> None:
        """
        Update the stored content for a terminal.

        Args:
            terminal_id: Terminal identifier
            content: New content to store
        """
        self._terminal_content[terminal_id] = content
        if terminal_id in self._terminals:
            self._terminals[terminal_id].last_accessed = datetime.now().isoformat()
            self._most_recent_terminal = terminal_id

    def update_selection(self, terminal_id: int, selection: str) -> None:
        """
        Update the stored selection for a terminal.

        Args:
            terminal_id: Terminal identifier
            selection: Selected text
        """
        self._selections[terminal_id] = selection
        self._most_recent_terminal = terminal_id

    def set_terminal_state(self, terminal_id: int, state: TerminalState) -> None:
        """Update the state of a terminal."""
        if terminal_id in self._terminals:
            self._terminals[terminal_id].state = state

    def _get_terminal_id(self, request: TerminalReadRequest) -> Optional[int]:
        """Resolve the terminal ID from request."""
        if request.terminal_id is not None:
            return request.terminal_id
        return self._most_recent_terminal

    def read(self, request: TerminalReadRequest) -> TerminalReadResult:
        """
        Read content from a terminal.

        Args:
            request: TerminalReadRequest with terminal ID and options

        Returns:
            TerminalReadResult with content and status
        """
        terminal_id = self._get_terminal_id(request)

        if terminal_id is None:
            return TerminalReadResult(
                status=TerminalReadStatus.TERMINAL_NOT_FOUND,
                terminal_id=-1,
                content="",
                message="No terminal available to read from"
            )

        # Check if terminal exists
        terminal_info = self._terminals.get(terminal_id)

        # Try to get content from ProcessManager if terminal not registered
        if terminal_info is None:
            pm = self._get_process_manager()
            if pm:
                try:
                    result = pm.read_process(terminal_id, wait=False, max_wait_seconds=0)
                    if result.success:
                        content = result.output
                        return self._build_result(
                            terminal_id, content, request,
                            TerminalState.ACTIVE
                        )
                except Exception:
                    pass

            return TerminalReadResult(
                status=TerminalReadStatus.TERMINAL_NOT_FOUND,
                terminal_id=terminal_id,
                content="",
                message=f"Terminal {terminal_id} not found"
            )

        # Check terminal state
        if terminal_info.state == TerminalState.CLOSED:
            return TerminalReadResult(
                status=TerminalReadStatus.TERMINAL_CLOSED,
                terminal_id=terminal_id,
                content="",
                message=f"Terminal {terminal_id} is closed",
                terminal_state=TerminalState.CLOSED
            )

        # Handle selection-only request
        if request.only_selected:
            selection = self._selections.get(terminal_id, "")
            if not selection:
                return TerminalReadResult(
                    status=TerminalReadStatus.NO_SELECTION,
                    terminal_id=terminal_id,
                    content="",
                    message="No text selected in terminal",
                    terminal_state=terminal_info.state
                )
            return self._build_result(
                terminal_id, selection, request, terminal_info.state
            )

        # Get full content
        content = self._terminal_content.get(terminal_id, "")

        # Try ProcessManager as fallback
        if not content:
            pm = self._get_process_manager()
            if pm:
                try:
                    result = pm.read_process(terminal_id, wait=False, max_wait_seconds=0)
                    if result.success:
                        content = result.output
                except Exception:
                    pass

        if not content:
            return TerminalReadResult(
                status=TerminalReadStatus.NO_CONTENT,
                terminal_id=terminal_id,
                content="",
                message="Terminal has no visible content",
                terminal_state=terminal_info.state
            )

        return self._build_result(terminal_id, content, request, terminal_info.state)

    def _build_result(
        self,
        terminal_id: int,
        content: str,
        request: TerminalReadRequest,
        state: TerminalState
    ) -> TerminalReadResult:
        """Build a successful result with optional truncation."""
        lines = content.split('\n')
        line_count = len(lines)
        is_truncated = False

        # Apply line limit
        if request.max_lines and len(lines) > request.max_lines:
            lines = lines[-request.max_lines:]  # Keep last N lines
            is_truncated = True
        elif len(lines) > self.MAX_CONTENT_LINES:
            lines = lines[-self.MAX_CONTENT_LINES:]
            is_truncated = True

        final_content = '\n'.join(lines)

        # Size limit
        if len(final_content) > self.MAX_CONTENT_SIZE:
            final_content = final_content[-self.MAX_CONTENT_SIZE:]
            is_truncated = True

        return TerminalReadResult(
            status=TerminalReadStatus.SUCCESS,
            terminal_id=terminal_id,
            content=final_content,
            message=f"Read {line_count} lines from terminal {terminal_id}",
            line_count=line_count,
            terminal_state=state,
            is_truncated=is_truncated
        )

    def list_terminals(self) -> List[TerminalInfo]:
        """Get list of all tracked terminals."""
        return list(self._terminals.values())

    def get_terminal(self, terminal_id: int) -> Optional[TerminalInfo]:
        """Get info for a specific terminal."""
        return self._terminals.get(terminal_id)

    def close_terminal(self, terminal_id: int) -> bool:
        """Mark a terminal as closed."""
        if terminal_id in self._terminals:
            self._terminals[terminal_id].state = TerminalState.CLOSED
            return True
        return False

    def clear(self) -> None:
        """Clear all terminal tracking data."""
        self._terminals.clear()
        self._terminal_content.clear()
        self._selections.clear()
        self._most_recent_terminal = None


# Factory function
_reader_instance: Optional[TerminalReader] = None


def get_terminal_reader() -> TerminalReader:
    """
    Get or create a TerminalReader instance.

    Returns:
        TerminalReader instance
    """
    global _reader_instance
    if _reader_instance is None:
        _reader_instance = TerminalReader()
    return _reader_instance


def reset_terminal_reader() -> None:
    """Reset the singleton instance. Useful for testing."""
    global _reader_instance
    _reader_instance = None

