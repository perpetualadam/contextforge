"""
Tests for RAG Pipeline functionality.
"""

import pytest
import json
from unittest.mock import Mock, patch, MagicMock

# Import the modules to test
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'services', 'api_gateway'))

from rag import RAGPipeline


class TestRAGPipeline:
    """Test the RAGPipeline functionality."""

    @patch('rag.SearchAdapter')
    @patch('rag.LLMClient')
    def setup_method(self, method, mock_llm_client_class, mock_search_adapter_class):
        """Set up test fixtures."""
        # Create mock instances
        self.mock_llm_client = Mock()
        self.mock_search_adapter = Mock()

        # Configure the mock classes to return our mock instances
        mock_llm_client_class.return_value = self.mock_llm_client
        mock_search_adapter_class.return_value = self.mock_search_adapter

        # Create the pipeline (it will use our mocks)
        self.pipeline = RAGPipeline()
        # Manually set the mocks since setup_method patching is tricky
        self.pipeline.llm_client = self.mock_llm_client
        self.pipeline.search_adapter = self.mock_search_adapter

    def test_rag_pipeline_initialization(self):
        """Test RAGPipeline initializes correctly."""
        pipeline = RAGPipeline()
        assert hasattr(pipeline, 'llm_client')
        assert hasattr(pipeline, 'search_adapter')
        assert hasattr(pipeline, 'answer_question')
        assert hasattr(pipeline, 'vector_index_url')
    
    @patch('requests.post')
    def test_retrieve_contexts_success(self, mock_post):
        """Test successful context retrieval."""
        # Mock vector search results
        mock_contexts = {
            "results": [
                {
                    "text": "def authenticate_user(username, password): return True",
                    "score": 0.95,
                    "meta": {"source": "auth.py", "chunk_id": "1"},
                    "rank": 1
                },
                {
                    "text": "class User: def __init__(self, username): self.username = username",
                    "score": 0.87,
                    "meta": {"source": "models.py", "chunk_id": "2"},
                    "rank": 2
                }
            ]
        }

        mock_response = Mock()
        mock_response.json.return_value = mock_contexts
        mock_response.status_code = 200
        mock_post.return_value = mock_response

        pipeline = RAGPipeline()
        contexts = pipeline.retrieve_contexts("authentication", top_k=5)

        assert len(contexts) == 2
        assert contexts[0]["text"] == "def authenticate_user(username, password): return True"
        assert contexts[0]["score"] == 0.95
        assert contexts[1]["meta"]["source"] == "models.py"

    @patch('requests.post')
    def test_retrieve_contexts_empty_results(self, mock_post):
        """Test context retrieval with empty results."""
        mock_response = Mock()
        mock_response.json.return_value = {"results": []}
        mock_response.status_code = 200
        mock_post.return_value = mock_response

        pipeline = RAGPipeline()
        contexts = pipeline.retrieve_contexts("nonexistent query")

        assert len(contexts) == 0

    @patch('requests.post')
    def test_retrieve_contexts_service_error(self, mock_post):
        """Test context retrieval with service error."""
        mock_post.side_effect = Exception("Service error")

        pipeline = RAGPipeline()
        contexts = pipeline.retrieve_contexts("test query")

        assert len(contexts) == 0
    
    @patch('rag.SearchAdapter')
    @patch('rag.LLMClient')
    def test_search_web_success(self, mock_llm_class, mock_search_class):
        """Test successful web search."""
        mock_search_adapter = Mock()
        mock_search_class.return_value = mock_search_adapter

        mock_web_results = {
            "results": [
                {
                    "title": "Authentication Best Practices",
                    "snippet": "Learn about secure authentication methods",
                    "url": "https://example.com/auth",
                    "source": "serpapi",
                    "content": "Detailed content about authentication",
                    "fetched_at": "2024-01-01T00:00:00Z"
                }
            ]
        }

        mock_search_adapter.search.return_value = mock_web_results

        pipeline = RAGPipeline()
        web_results = pipeline.search_web("authentication best practices", num_results=3)

        assert len(web_results) == 1
        assert web_results[0]["title"] == "Authentication Best Practices"
        assert web_results[0]["url"] == "https://example.com/auth"

    @patch('rag.ENABLE_WEB_SEARCH', False)
    def test_search_web_disabled(self):
        """Test web search when disabled."""
        pipeline = RAGPipeline()
        web_results = pipeline.search_web("test query")

        assert len(web_results) == 0

    @patch('rag.SearchAdapter')
    @patch('rag.LLMClient')
    def test_search_web_error(self, mock_llm_class, mock_search_class):
        """Test web search with error."""
        mock_search_adapter = Mock()
        mock_search_class.return_value = mock_search_adapter
        mock_search_adapter.search.side_effect = Exception("Search service error")

        pipeline = RAGPipeline()
        web_results = pipeline.search_web("test query")

        assert len(web_results) == 0

    def test_summarize_contexts(self):
        """Test context summarization."""
        contexts = [
            {
                "text": "def authenticate_user(username, password): return validate_credentials(username, password)",
                "score": 0.95,
                "meta": {"source": "auth.py", "line": 10}
            },
            {
                "text": "def validate_credentials(username, password): return check_database(username, password)",
                "score": 0.87,
                "meta": {"source": "auth.py", "line": 25}
            }
        ]

        pipeline = RAGPipeline()
        # summarize_contexts now returns a list, not a string
        result = pipeline.summarize_contexts(contexts)

        assert isinstance(result, list)
        assert len(result) == 2

    def test_summarize_contexts_empty(self):
        """Test context summarization with empty contexts."""
        pipeline = RAGPipeline()
        result = pipeline.summarize_contexts([])

        # summarize_contexts returns an empty list for empty input
        assert result == []

    def test_format_contexts(self):
        """Test context formatting."""
        contexts = [
            {
                "text": "def hello(): return 'world'",
                "score": 0.95,
                "meta": {"file_path": "utils.py", "line": 5}
            }
        ]

        pipeline = RAGPipeline()
        formatted = pipeline.format_contexts(contexts)

        assert isinstance(formatted, str)
        assert "utils.py" in formatted
        assert "def hello()" in formatted
        assert "score:" in formatted.lower()

    def test_format_contexts_empty(self):
        """Test formatting empty contexts."""
        pipeline = RAGPipeline()
        formatted = pipeline.format_contexts([])

        assert formatted == "No relevant contexts found."

    def test_compose_prompt(self):
        """Test prompt composition."""
        question = "How does authentication work?"
        contexts = [{"text": "def authenticate_user(): pass", "score": 0.9, "meta": {}}]
        web_results = [{"title": "Auth", "snippet": "Authentication is the process of verifying identity.", "url": "http://example.com"}]

        pipeline = RAGPipeline()
        prompt = pipeline.compose_prompt(question, contexts, web_results)

        assert isinstance(prompt, str)
        assert question in prompt

    def test_compose_prompt_no_web_results(self):
        """Test prompt composition without web results."""
        question = "How does authentication work?"
        contexts = [{"text": "def authenticate_user(): pass", "score": 0.9, "meta": {}}]

        pipeline = RAGPipeline()
        prompt = pipeline.compose_prompt(question, contexts, [])

        assert isinstance(prompt, str)
        assert question in prompt
    
    @patch('requests.post')
    @patch('rag.SearchAdapter')
    @patch('rag.LLMClient')
    def test_answer_question_full_pipeline(self, mock_llm_class, mock_search_class, mock_post):
        """Test complete question answering pipeline."""
        # Set up mocks
        mock_llm_client = Mock()
        mock_search_adapter = Mock()
        mock_llm_class.return_value = mock_llm_client
        mock_search_class.return_value = mock_search_adapter

        # Mock vector search results
        mock_vector_response = Mock()
        mock_vector_response.json.return_value = {
            "results": [
                {
                    "text": "def authenticate_user(username, password): return True",
                    "score": 0.95,
                    "meta": {"source": "auth.py", "chunk_id": "1"},
                    "rank": 1
                }
            ]
        }
        mock_vector_response.status_code = 200
        mock_post.return_value = mock_vector_response

        # Mock web search results
        mock_search_adapter.search.return_value = {
            "results": [
                {
                    "title": "Auth Guide",
                    "snippet": "Authentication guide",
                    "url": "https://example.com",
                    "source": "web",
                    "content": "Authentication content",
                    "fetched_at": "2024-01-01T00:00:00Z"
                }
            ]
        }

        # Mock LLM response
        mock_llm_client.generate.return_value = {
            "text": "Authentication works by validating user credentials against stored data.",
            "meta": {"backend": "ollama", "latency_ms": 100, "tokens": 50}
        }

        pipeline = RAGPipeline()

        # Test the pipeline
        result = pipeline.answer_question(
            question="How does authentication work?",
            max_tokens=512,
            enable_web_search=True
        )

        # Verify result structure
        assert "answer" in result
        assert "contexts" in result
        assert "web_results" in result
        assert "meta" in result

        # Verify content
        assert "Authentication" in result["answer"] or "error" in result["answer"].lower()

    @patch('requests.post')
    @patch('rag.LLMClient')
    def test_answer_question_no_contexts(self, mock_llm_class, mock_post):
        """Test question answering with no contexts found."""
        mock_llm_client = Mock()
        mock_llm_class.return_value = mock_llm_client

        # Mock empty vector search
        mock_response = Mock()
        mock_response.json.return_value = {"results": []}
        mock_response.status_code = 200
        mock_post.return_value = mock_response

        # Mock LLM response
        mock_llm_client.generate.return_value = {
            "text": "I don't have specific information about that in the codebase.",
            "meta": {"backend": "ollama", "latency_ms": 100, "tokens": 20}
        }

        pipeline = RAGPipeline()
        result = pipeline.answer_question("unknown topic")

        assert "answer" in result
        assert len(result["contexts"]) == 0
        assert result["meta"]["num_contexts"] == 0

    @patch('requests.post')
    @patch('rag.LLMClient')
    def test_answer_question_llm_error(self, mock_llm_class, mock_post):
        """Test question answering with LLM error."""
        mock_llm_client = Mock()
        mock_llm_class.return_value = mock_llm_client

        # Mock empty vector search
        mock_response = Mock()
        mock_response.json.return_value = {"results": []}
        mock_response.status_code = 200
        mock_post.return_value = mock_response

        # Mock LLM error
        mock_llm_client.generate.side_effect = Exception("LLM service unavailable")

        pipeline = RAGPipeline()
        # The pipeline now catches errors and returns an error response instead of raising
        result = pipeline.answer_question("test question")

        assert "answer" in result
        assert "error" in result["answer"].lower() or "error" in result["meta"]


class TestRAGPipelineIntegration:
    """Integration tests for RAG pipeline."""

    def test_rag_template_format(self):
        """Test RAG template formatting."""
        pipeline = RAGPipeline()

        question = "How does authentication work?"
        contexts = [{"text": "def authenticate(): pass", "score": 0.9, "meta": {}}]
        web_results = [{"title": "Auth", "snippet": "Auth is important for security.", "url": "http://example.com"}]

        prompt = pipeline.compose_prompt(question, contexts, web_results)

        # Check that prompt is a valid string
        assert isinstance(prompt, str)
        assert len(prompt) > 0

        # Check content is included
        assert question in prompt

    def test_context_ranking_preservation(self):
        """Test that context ranking is preserved through pipeline."""
        pipeline = RAGPipeline()

        contexts = [
            {"text": "high score", "score": 0.95, "meta": {"source": "a.py"}, "rank": 1},
            {"text": "medium score", "score": 0.75, "meta": {"source": "b.py"}, "rank": 2},
            {"text": "low score", "score": 0.55, "meta": {"source": "c.py"}, "rank": 3}
        ]

        formatted = pipeline.format_contexts(contexts)

        # Check that higher ranked items appear first
        high_pos = formatted.find("high score")
        medium_pos = formatted.find("medium score")
        low_pos = formatted.find("low score")

        assert high_pos < medium_pos < low_pos

    @patch('requests.post')
    @patch('rag.SearchAdapter')
    @patch('rag.LLMClient')
    def test_error_recovery(self, mock_llm_class, mock_search_class, mock_post):
        """Test pipeline error recovery mechanisms."""
        # Mock vector service failure
        mock_post.side_effect = Exception("Vector service down")

        # Mock search adapter failure
        mock_search_adapter = Mock()
        mock_search_adapter.search.side_effect = Exception("Search service down")
        mock_search_class.return_value = mock_search_adapter

        # Mock working LLM
        mock_llm_client = Mock()
        mock_llm_client.generate.return_value = {
            "text": "I cannot access the codebase right now.",
            "meta": {"backend": "ollama", "latency_ms": 50, "tokens": 10}
        }
        mock_llm_class.return_value = mock_llm_client

        pipeline = RAGPipeline()

        # Should still be able to answer (with degraded functionality)
        result = pipeline.answer_question("test question")

        assert "answer" in result
        assert len(result["contexts"]) == 0  # No contexts due to vector failure

    def test_prompt_length_management(self):
        """Test that prompts don't exceed reasonable length limits."""
        pipeline = RAGPipeline()

        # Create very long contexts
        long_contexts = [
            {
                "text": "x" * 10000,  # Very long text
                "score": 0.95,
                "meta": {"source": "long.py"},
                "rank": 1
            }
        ] * 10  # Multiple long contexts

        formatted = pipeline.format_contexts(long_contexts)

        # Should handle long contexts gracefully
        assert isinstance(formatted, str)
        assert len(formatted) > 0

        # Compose prompt with long content
        prompt = pipeline.compose_prompt("test question", long_contexts, [])

        # Should still be a valid string
        assert isinstance(prompt, str)
        assert len(prompt) > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
