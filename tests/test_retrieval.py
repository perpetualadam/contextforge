"""
Tests for the ContextForge hierarchical retrieval service.

Copyright (c) 2025 ContextForge
"""

import pytest
from unittest.mock import patch, MagicMock


class TestContextLevel:
    """Test ContextLevel enum."""
    
    def test_context_levels(self):
        """Test context level values."""
        from services.retrieval import ContextLevel
        
        assert ContextLevel.MODULE.value == "module"
        assert ContextLevel.FILE.value == "file"
        assert ContextLevel.FUNCTION.value == "function"
        assert ContextLevel.CHUNK.value == "chunk"


class TestContextResult:
    """Test ContextResult dataclass."""
    
    def test_context_result_creation(self):
        """Test creating a ContextResult."""
        from services.retrieval import ContextResult, ContextLevel
        
        result = ContextResult(
            content="def test():",
            level=ContextLevel.FUNCTION,
            score=0.95,
            file_path="test.py",
            function_name="test"
        )
        
        assert result.content == "def test():"
        assert result.level == ContextLevel.FUNCTION
        assert result.score == 0.95
        assert result.function_name == "test"


class TestRetrievalRequest:
    """Test RetrievalRequest dataclass."""
    
    def test_default_request(self):
        """Test default retrieval request values."""
        from services.retrieval import RetrievalRequest, ContextLevel
        
        request = RetrievalRequest(query="test query")
        
        assert request.query == "test query"
        assert request.top_k == 10
        assert ContextLevel.MODULE in request.levels
        assert ContextLevel.FILE in request.levels
        assert ContextLevel.FUNCTION in request.levels
    
    def test_custom_request(self):
        """Test custom retrieval request."""
        from services.retrieval import RetrievalRequest, ContextLevel
        
        request = RetrievalRequest(
            query="find function",
            top_k=20,
            levels=[ContextLevel.FUNCTION],
            include_tests=True,
            include_git_history=True
        )
        
        assert request.top_k == 20
        assert len(request.levels) == 1
        assert request.include_tests == True
        assert request.include_git_history == True


class TestHierarchicalRetriever:
    """Test HierarchicalRetriever class."""
    
    def test_retriever_creation(self):
        """Test creating a retriever."""
        from services.retrieval import HierarchicalRetriever
        
        with patch('services.config.get_config'):
            retriever = HierarchicalRetriever()
            
            assert retriever._vector_index is None  # Lazy loaded
            assert retriever._cache is None  # Lazy loaded
    
    def test_retriever_with_mock_index(self):
        """Test retrieval with mocked vector index."""
        from services.retrieval import HierarchicalRetriever, RetrievalRequest
        
        with patch('services.config.get_config'):
            retriever = HierarchicalRetriever()
            
            # Mock the vector index
            mock_index = MagicMock()
            mock_index.search.return_value = [
                {
                    "content": "def test():",
                    "score": 0.9,
                    "metadata": {
                        "file_path": "test.py",
                        "module_name": "tests",
                        "function_name": "test"
                    }
                }
            ]
            retriever._vector_index = mock_index
            
            # Mock the cache
            mock_cache = MagicMock()
            mock_cache.get_results.return_value = None
            retriever._cache = mock_cache
            
            request = RetrievalRequest(query="test function")
            results = retriever.retrieve(request)
            
            assert len(results) > 0


class TestSemanticSearch:
    """Test semantic_search convenience function."""
    
    def test_semantic_search(self):
        """Test semantic search function."""
        from services.retrieval import semantic_search
        
        with patch('services.retrieval.HierarchicalRetriever') as MockRetriever:
            mock_retriever = MagicMock()
            mock_retriever.retrieve.return_value = []
            MockRetriever.return_value = mock_retriever
            
            results = semantic_search("test query", top_k=5)
            
            assert isinstance(results, list)


class TestLexicalFilter:
    """Test lexical_filter function."""
    
    def test_lexical_filter_boosts_matches(self):
        """Test that lexical filter boosts matching results."""
        from services.retrieval import lexical_filter
        
        results = [
            {"content": "def test_function():", "score": 0.8},
            {"content": "class Something:", "score": 0.9},
        ]
        
        filtered = lexical_filter(results, "test function")
        
        # Result with matching terms should be boosted
        assert filtered[0]["content"] == "def test_function():"
    
    def test_lexical_filter_adds_scores(self):
        """Test that lexical filter adds lexical and combined scores."""
        from services.retrieval import lexical_filter
        
        results = [{"content": "test content", "score": 0.8}]
        
        filtered = lexical_filter(results, "test")
        
        assert "lexical_score" in filtered[0]
        assert "combined_score" in filtered[0]


class TestRetrieverSingleton:
    """Test retriever singleton pattern."""
    
    def test_get_retriever(self):
        """Test getting singleton retriever."""
        from services.retrieval import get_retriever, HierarchicalRetriever
        import services.retrieval as ret_module
        
        # Reset singleton
        ret_module._retriever = None
        
        with patch('services.config.get_config'):
            r1 = get_retriever()
            r2 = get_retriever()
            
            assert r1 is r2

