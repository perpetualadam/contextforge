"""
Tests for ContextForge Terminal Reader tool.

Copyright (c) 2025 ContextForge
"""

import pytest
from unittest.mock import MagicMock

from services.tools.terminal_reader import (
    TerminalReader,
    TerminalReadRequest,
    TerminalReadResult,
    TerminalReadStatus,
    TerminalInfo,
    TerminalState,
    get_terminal_reader,
    reset_terminal_reader
)


@pytest.fixture
def reader():
    """Create a TerminalReader instance."""
    return TerminalReader()


@pytest.fixture(autouse=True)
def reset_singleton():
    """Reset singleton before each test."""
    reset_terminal_reader()
    yield
    reset_terminal_reader()


class TestTerminalRegistration:
    """Tests for terminal registration."""
    
    def test_register_terminal(self, reader):
        """Test registering a new terminal."""
        info = reader.register_terminal(
            terminal_id=1,
            name="Test Terminal",
            cwd="/home/user"
        )
        
        assert info.terminal_id == 1
        assert info.name == "Test Terminal"
        assert info.state == TerminalState.ACTIVE
        assert info.cwd == "/home/user"
    
    def test_register_sets_most_recent(self, reader):
        """Test registration sets most recent terminal."""
        reader.register_terminal(terminal_id=1, name="First")
        reader.register_terminal(terminal_id=2, name="Second")
        
        assert reader._most_recent_terminal == 2
    
    def test_list_terminals(self, reader):
        """Test listing all terminals."""
        reader.register_terminal(terminal_id=1, name="First")
        reader.register_terminal(terminal_id=2, name="Second")
        
        terminals = reader.list_terminals()
        assert len(terminals) == 2


class TestContentManagement:
    """Tests for content management."""
    
    def test_update_content(self, reader):
        """Test updating terminal content."""
        reader.register_terminal(terminal_id=1, name="Test")
        reader.update_content(1, "Hello\nWorld")
        
        assert reader._terminal_content[1] == "Hello\nWorld"
    
    def test_update_selection(self, reader):
        """Test updating terminal selection."""
        reader.register_terminal(terminal_id=1, name="Test")
        reader.update_selection(1, "selected text")
        
        assert reader._selections[1] == "selected text"


class TestTerminalReading:
    """Tests for reading terminal content."""
    
    def test_read_content(self, reader):
        """Test reading terminal content."""
        reader.register_terminal(terminal_id=1, name="Test")
        reader.update_content(1, "Line 1\nLine 2\nLine 3")
        
        request = TerminalReadRequest(terminal_id=1)
        result = reader.read(request)
        
        assert result.status == TerminalReadStatus.SUCCESS
        assert "Line 1" in result.content
        assert result.line_count == 3
    
    def test_read_most_recent(self, reader):
        """Test reading from most recent terminal."""
        reader.register_terminal(terminal_id=1, name="First")
        reader.register_terminal(terminal_id=2, name="Second")
        reader.update_content(2, "Second terminal content")
        
        request = TerminalReadRequest()  # No terminal_id
        result = reader.read(request)
        
        assert result.status == TerminalReadStatus.SUCCESS
        assert result.terminal_id == 2
    
    def test_read_selection_only(self, reader):
        """Test reading only selected text."""
        reader.register_terminal(terminal_id=1, name="Test")
        reader.update_content(1, "Full content here")
        reader.update_selection(1, "selected portion")
        
        request = TerminalReadRequest(terminal_id=1, only_selected=True)
        result = reader.read(request)
        
        assert result.status == TerminalReadStatus.SUCCESS
        assert result.content == "selected portion"
    
    def test_read_no_selection(self, reader):
        """Test reading selection when none exists."""
        reader.register_terminal(terminal_id=1, name="Test")
        reader.update_content(1, "Full content")
        
        request = TerminalReadRequest(terminal_id=1, only_selected=True)
        result = reader.read(request)
        
        assert result.status == TerminalReadStatus.NO_SELECTION
    
    def test_read_nonexistent_terminal(self, reader):
        """Test reading from nonexistent terminal."""
        request = TerminalReadRequest(terminal_id=999)
        result = reader.read(request)
        
        assert result.status == TerminalReadStatus.TERMINAL_NOT_FOUND
    
    def test_read_closed_terminal(self, reader):
        """Test reading from closed terminal."""
        reader.register_terminal(terminal_id=1, name="Test")
        reader.close_terminal(1)
        
        request = TerminalReadRequest(terminal_id=1)
        result = reader.read(request)
        
        assert result.status == TerminalReadStatus.TERMINAL_CLOSED
    
    def test_read_with_max_lines(self, reader):
        """Test reading with line limit."""
        reader.register_terminal(terminal_id=1, name="Test")
        content = "\n".join([f"Line {i}" for i in range(100)])
        reader.update_content(1, content)
        
        request = TerminalReadRequest(terminal_id=1, max_lines=10)
        result = reader.read(request)
        
        assert result.status == TerminalReadStatus.SUCCESS
        assert result.is_truncated is True
        assert len(result.content.split('\n')) == 10


class TestTerminalState:
    """Tests for terminal state management."""
    
    def test_close_terminal(self, reader):
        """Test closing a terminal."""
        reader.register_terminal(terminal_id=1, name="Test")
        result = reader.close_terminal(1)
        
        assert result is True
        assert reader._terminals[1].state == TerminalState.CLOSED
    
    def test_close_nonexistent(self, reader):
        """Test closing nonexistent terminal."""
        result = reader.close_terminal(999)
        assert result is False
    
    def test_clear_all(self, reader):
        """Test clearing all terminals."""
        reader.register_terminal(terminal_id=1, name="First")
        reader.register_terminal(terminal_id=2, name="Second")
        reader.clear()
        
        assert len(reader._terminals) == 0
        assert reader._most_recent_terminal is None

