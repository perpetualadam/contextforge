"""
Tests for ContextForge Code Viewer tools.

Copyright (c) 2025 ContextForge
"""

import os
import pytest
import tempfile
import shutil
from pathlib import Path

from services.tools.code_viewer import (
    CodeViewer,
    ViewRequest,
    ViewResult,
    ViewResultStatus,
    get_code_viewer
)


@pytest.fixture
def temp_workspace():
    """Create a temporary workspace directory."""
    workspace = tempfile.mkdtemp()
    yield workspace
    shutil.rmtree(workspace, ignore_errors=True)


@pytest.fixture
def viewer(temp_workspace):
    """Create a CodeViewer instance with temp workspace."""
    return CodeViewer(workspace_root=temp_workspace)


@pytest.fixture
def sample_file(temp_workspace):
    """Create a sample file for testing."""
    file_path = Path(temp_workspace) / "sample.py"
    content = '''def hello():
    print("Hello, World!")
    return True

def goodbye():
    print("Goodbye!")
    return False

class MyClass:
    def __init__(self):
        self.value = 42
    
    def get_value(self):
        return self.value
'''
    file_path.write_text(content)
    return file_path


@pytest.fixture
def sample_directory(temp_workspace):
    """Create a sample directory structure."""
    base = Path(temp_workspace)
    
    # Create subdirectories
    (base / "src").mkdir()
    (base / "src" / "utils").mkdir()
    (base / "tests").mkdir()
    
    # Create files
    (base / "src" / "main.py").write_text("# Main file")
    (base / "src" / "utils" / "helpers.py").write_text("# Helpers")
    (base / "tests" / "test_main.py").write_text("# Tests")
    (base / "README.md").write_text("# Project")
    
    return base


class TestViewFile:
    """Tests for file viewing functionality."""
    
    def test_view_file_basic(self, viewer, sample_file):
        """Test basic file viewing."""
        request = ViewRequest(path=str(sample_file))
        
        result = viewer.view_file(request)
        
        assert result.status == ViewResultStatus.SUCCESS
        assert "def hello():" in result.content
        assert result.total_lines > 0
    
    def test_view_file_with_line_numbers(self, viewer, sample_file):
        """Test that line numbers are added."""
        request = ViewRequest(path=str(sample_file))
        
        result = viewer.view_file(request)
        
        # Check line numbers are present
        assert "1\t" in result.content or "     1\t" in result.content
    
    def test_view_file_range(self, viewer, sample_file):
        """Test viewing a specific line range."""
        request = ViewRequest(
            path=str(sample_file),
            view_range=(1, 5)
        )
        
        result = viewer.view_file(request)
        
        assert result.status == ViewResultStatus.SUCCESS
        lines = result.content.strip().split('\n')
        assert len(lines) == 5
    
    def test_view_file_range_to_end(self, viewer, sample_file):
        """Test viewing from a line to end of file."""
        request = ViewRequest(
            path=str(sample_file),
            view_range=(5, -1)
        )
        
        result = viewer.view_file(request)
        
        assert result.status == ViewResultStatus.SUCCESS
        assert "def goodbye():" in result.content
    
    def test_view_file_not_found(self, viewer, temp_workspace):
        """Test viewing a non-existent file."""
        request = ViewRequest(
            path=os.path.join(temp_workspace, "nonexistent.py")
        )
        
        result = viewer.view_file(request)
        
        assert result.status == ViewResultStatus.FILE_NOT_FOUND
    
    def test_view_file_invalid_range(self, viewer, sample_file):
        """Test viewing with invalid line range."""
        request = ViewRequest(
            path=str(sample_file),
            view_range=(1000, 2000)
        )
        
        result = viewer.view_file(request)
        
        assert result.status == ViewResultStatus.INVALID_RANGE


class TestRegexSearch:
    """Tests for regex search functionality."""
    
    def test_regex_search_basic(self, viewer, sample_file):
        """Test basic regex search."""
        request = ViewRequest(
            path=str(sample_file),
            search_query_regex="def [a-z]+\\("
        )
        
        result = viewer.view_file(request)
        
        assert result.status == ViewResultStatus.SUCCESS
        assert "def hello(" in result.content
        assert "def goodbye(" in result.content
    
    def test_regex_search_case_insensitive(self, viewer, sample_file):
        """Test case-insensitive search."""
        request = ViewRequest(
            path=str(sample_file),
            search_query_regex="HELLO",
            case_sensitive=False
        )

        result = viewer.view_file(request)

        assert result.status == ViewResultStatus.SUCCESS
        assert "Hello" in result.content

    def test_regex_search_case_sensitive(self, viewer, sample_file):
        """Test case-sensitive search."""
        request = ViewRequest(
            path=str(sample_file),
            search_query_regex="HELLO",
            case_sensitive=True
        )

        result = viewer.view_file(request)

        # Should not find uppercase HELLO
        assert "No matches" in result.content or result.message

    def test_regex_search_no_matches(self, viewer, sample_file):
        """Test search with no matches."""
        request = ViewRequest(
            path=str(sample_file),
            search_query_regex="nonexistent_pattern_xyz"
        )

        result = viewer.view_file(request)

        assert result.status == ViewResultStatus.SUCCESS
        assert "No matches" in result.content

    def test_regex_search_invalid_pattern(self, viewer, sample_file):
        """Test search with invalid regex pattern."""
        request = ViewRequest(
            path=str(sample_file),
            search_query_regex="[invalid("
        )

        result = viewer.view_file(request)

        assert result.status == ViewResultStatus.REGEX_ERROR

    def test_regex_search_with_context(self, viewer, sample_file):
        """Test search with context lines."""
        request = ViewRequest(
            path=str(sample_file),
            search_query_regex="return True",
            context_lines_before=2,
            context_lines_after=2
        )

        result = viewer.view_file(request)

        assert result.status == ViewResultStatus.SUCCESS
        # Should include context lines
        assert "Hello" in result.content


class TestViewDirectory:
    """Tests for directory viewing functionality."""

    def test_view_directory_basic(self, viewer, sample_directory):
        """Test basic directory viewing."""
        request = ViewRequest(
            path=str(sample_directory),
            view_type="directory"
        )

        result = viewer.view_directory(request)

        assert result.status == ViewResultStatus.SUCCESS
        assert "src" in result.content
        assert "tests" in result.content
        assert "README.md" in result.content

    def test_view_directory_nested(self, viewer, sample_directory):
        """Test viewing nested directory structure."""
        request = ViewRequest(
            path=str(sample_directory),
            view_type="directory",
            max_depth=2
        )

        result = viewer.view_directory(request)

        assert result.status == ViewResultStatus.SUCCESS
        assert "utils" in result.content
        assert "helpers.py" in result.content

    def test_view_directory_not_found(self, viewer, temp_workspace):
        """Test viewing non-existent directory."""
        request = ViewRequest(
            path=os.path.join(temp_workspace, "nonexistent"),
            view_type="directory"
        )

        result = viewer.view_directory(request)

        assert result.status == ViewResultStatus.FILE_NOT_FOUND


class TestMainViewMethod:
    """Tests for the main view() method."""

    def test_view_auto_detect_file(self, viewer, sample_file):
        """Test that view() correctly handles files."""
        request = ViewRequest(path=str(sample_file))

        result = viewer.view(request)

        assert result.status == ViewResultStatus.SUCCESS
        assert "def hello():" in result.content

    def test_view_auto_detect_directory(self, viewer, sample_directory):
        """Test that view() correctly handles directories."""
        request = ViewRequest(
            path=str(sample_directory),
            view_type="directory"
        )

        result = viewer.view(request)

        assert result.status == ViewResultStatus.SUCCESS
        assert "src" in result.content


class TestFactoryFunction:
    """Tests for the get_code_viewer factory function."""

    def test_get_viewer(self, temp_workspace):
        """Test getting a viewer instance."""
        viewer = get_code_viewer(temp_workspace)

        assert isinstance(viewer, CodeViewer)
        assert viewer.workspace_root == Path(temp_workspace)

