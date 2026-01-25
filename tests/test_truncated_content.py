"""
Tests for ContextForge Truncated Content tools.

Copyright (c) 2025 ContextForge
"""

import pytest
from datetime import datetime, timedelta

from services.tools.truncated_content import (
    TruncatedContentManager,
    ContentReference,
    ViewRangeRequest,
    ViewRangeResult,
    SearchRequest,
    SearchResult,
    SearchMatch,
    TruncatedContentStatus,
    get_truncated_content_manager,
    reset_truncated_content_manager
)


@pytest.fixture
def manager():
    """Create a TruncatedContentManager instance."""
    return TruncatedContentManager(expiry_hours=1)


@pytest.fixture(autouse=True)
def reset_singleton():
    """Reset singleton before each test."""
    reset_truncated_content_manager()
    yield
    reset_truncated_content_manager()


@pytest.fixture
def sample_content():
    """Create sample content for testing."""
    return "\n".join([f"Line {i}: This is line number {i}" for i in range(1, 101)])


class TestContentStorage:
    """Tests for content storage."""
    
    def test_store_content(self, manager, sample_content):
        """Test storing content returns reference ID."""
        ref_id = manager.store_content(sample_content, "test.py")
        
        assert ref_id is not None
        assert len(ref_id) == 8  # Short UUID
    
    def test_get_reference(self, manager, sample_content):
        """Test retrieving stored reference."""
        ref_id = manager.store_content(sample_content, "test.py")
        ref = manager.get_reference(ref_id)
        
        assert ref is not None
        assert ref.content == sample_content
        assert ref.source == "test.py"
        assert ref.total_lines == 100
    
    def test_get_nonexistent_reference(self, manager):
        """Test getting nonexistent reference."""
        ref = manager.get_reference("nonexistent")
        assert ref is None
    
    def test_list_references(self, manager):
        """Test listing all references."""
        manager.store_content("Content 1", "file1.py")
        manager.store_content("Content 2", "file2.py")
        
        refs = manager.list_references()
        assert len(refs) == 2


class TestViewRange:
    """Tests for view range functionality."""
    
    def test_view_range_success(self, manager, sample_content):
        """Test viewing a line range."""
        ref_id = manager.store_content(sample_content, "test.py")
        
        request = ViewRangeRequest(
            reference_id=ref_id,
            start_line=10,
            end_line=15
        )
        result = manager.view_range(request)
        
        assert result.status == TruncatedContentStatus.SUCCESS
        assert result.start_line == 10
        assert result.end_line == 15
        assert "Line 10" in result.content
        assert "Line 15" in result.content
    
    def test_view_range_with_line_numbers(self, manager, sample_content):
        """Test that output includes line numbers."""
        ref_id = manager.store_content(sample_content, "test.py")
        
        request = ViewRangeRequest(
            reference_id=ref_id,
            start_line=1,
            end_line=3
        )
        result = manager.view_range(request)
        
        lines = result.content.split('\n')
        assert lines[0].strip().startswith("1")
    
    def test_view_range_invalid_reference(self, manager):
        """Test viewing with invalid reference."""
        request = ViewRangeRequest(
            reference_id="invalid",
            start_line=1,
            end_line=10
        )
        result = manager.view_range(request)
        
        assert result.status == TruncatedContentStatus.REFERENCE_NOT_FOUND
    
    def test_view_range_invalid_start(self, manager, sample_content):
        """Test viewing with invalid start line."""
        ref_id = manager.store_content(sample_content, "test.py")
        
        request = ViewRangeRequest(
            reference_id=ref_id,
            start_line=0,
            end_line=10
        )
        result = manager.view_range(request)
        
        assert result.status == TruncatedContentStatus.INVALID_RANGE
    
    def test_view_range_start_greater_than_end(self, manager, sample_content):
        """Test viewing with start > end."""
        ref_id = manager.store_content(sample_content, "test.py")
        
        request = ViewRangeRequest(
            reference_id=ref_id,
            start_line=20,
            end_line=10
        )
        result = manager.view_range(request)
        
        assert result.status == TruncatedContentStatus.INVALID_RANGE
    
    def test_view_range_exceeds_total(self, manager, sample_content):
        """Test viewing range that exceeds total lines."""
        ref_id = manager.store_content(sample_content, "test.py")

        request = ViewRangeRequest(
            reference_id=ref_id,
            start_line=95,
            end_line=150
        )
        result = manager.view_range(request)

        assert result.status == TruncatedContentStatus.SUCCESS
        assert result.end_line == 100  # Adjusted to actual end


class TestSearch:
    """Tests for search functionality."""

    def test_search_plain_text(self, manager, sample_content):
        """Test plain text search."""
        ref_id = manager.store_content(sample_content, "test.py")

        request = SearchRequest(
            reference_id=ref_id,
            search_term="Line 50"
        )
        result = manager.search(request)

        assert result.status == TruncatedContentStatus.SUCCESS
        assert result.total_matches >= 1
        assert any(m.line_number == 50 for m in result.matches)

    def test_search_regex(self, manager, sample_content):
        """Test regex search."""
        ref_id = manager.store_content(sample_content, "test.py")

        request = SearchRequest(
            reference_id=ref_id,
            search_term=r"Line \d{2}:",
            use_regex=True
        )
        result = manager.search(request)

        assert result.status == TruncatedContentStatus.SUCCESS
        assert result.total_matches > 0

    def test_search_case_insensitive(self, manager):
        """Test case-insensitive search."""
        content = "Hello World\nhello world\nHELLO WORLD"
        ref_id = manager.store_content(content, "test.txt")

        request = SearchRequest(
            reference_id=ref_id,
            search_term="hello",
            case_sensitive=False
        )
        result = manager.search(request)

        assert result.status == TruncatedContentStatus.SUCCESS
        assert result.total_matches == 3

    def test_search_case_sensitive(self, manager):
        """Test case-sensitive search."""
        content = "Hello World\nhello world\nHELLO WORLD"
        ref_id = manager.store_content(content, "test.txt")

        request = SearchRequest(
            reference_id=ref_id,
            search_term="hello",
            case_sensitive=True
        )
        result = manager.search(request)

        assert result.status == TruncatedContentStatus.SUCCESS
        assert result.total_matches == 1

    def test_search_with_context(self, manager, sample_content):
        """Test search includes context lines."""
        ref_id = manager.store_content(sample_content, "test.py")

        request = SearchRequest(
            reference_id=ref_id,
            search_term="Line 50",
            context_lines=3
        )
        result = manager.search(request)

        assert result.status == TruncatedContentStatus.SUCCESS
        match = result.matches[0]
        assert len(match.context_before) == 3
        assert len(match.context_after) == 3

    def test_search_no_matches(self, manager, sample_content):
        """Test search with no matches."""
        ref_id = manager.store_content(sample_content, "test.py")

        request = SearchRequest(
            reference_id=ref_id,
            search_term="NONEXISTENT_STRING"
        )
        result = manager.search(request)

        assert result.status == TruncatedContentStatus.NO_MATCHES

    def test_search_invalid_regex(self, manager, sample_content):
        """Test search with invalid regex."""
        ref_id = manager.store_content(sample_content, "test.py")

        request = SearchRequest(
            reference_id=ref_id,
            search_term="[invalid",
            use_regex=True
        )
        result = manager.search(request)

        assert result.status == TruncatedContentStatus.REGEX_ERROR

    def test_search_invalid_reference(self, manager):
        """Test search with invalid reference."""
        request = SearchRequest(
            reference_id="invalid",
            search_term="test"
        )
        result = manager.search(request)

        assert result.status == TruncatedContentStatus.REFERENCE_NOT_FOUND


class TestFormatting:
    """Tests for result formatting."""

    def test_format_search_results(self, manager, sample_content):
        """Test formatting search results."""
        ref_id = manager.store_content(sample_content, "test.py")

        request = SearchRequest(
            reference_id=ref_id,
            search_term="Line 50",
            context_lines=1
        )
        result = manager.search(request)
        formatted = manager.format_search_results(result)

        assert ">>>" in formatted  # Match highlight
        assert "<<<" in formatted
        assert "..." in formatted  # Separator


class TestExpiration:
    """Tests for content expiration."""

    def test_clear_all(self, manager, sample_content):
        """Test clearing all references."""
        manager.store_content(sample_content, "test1.py")
        manager.store_content(sample_content, "test2.py")

        manager.clear()

        assert len(manager.list_references()) == 0


class TestSingleton:
    """Tests for singleton pattern."""

    def test_get_singleton(self):
        """Test getting singleton instance."""
        manager1 = get_truncated_content_manager()
        manager2 = get_truncated_content_manager()

        assert manager1 is manager2

    def test_reset_singleton(self):
        """Test resetting singleton."""
        manager1 = get_truncated_content_manager()
        reset_truncated_content_manager()
        manager2 = get_truncated_content_manager()

        assert manager1 is not manager2

