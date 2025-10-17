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
    
    def setup_method(self):
        """Set up test fixtures."""
        # Mock the dependencies
        self.mock_vector_client = Mock()
        self.mock_llm_client = Mock()
        self.mock_search_adapter = Mock()
        
        self.pipeline = RAGPipeline(
            vector_client=self.mock_vector_client,
            llm_client=self.mock_llm_client,
            search_adapter=self.mock_search_adapter
        )
    
    def test_rag_pipeline_initialization(self):
        """Test RAGPipeline initializes correctly."""
        assert self.pipeline.vector_client == self.mock_vector_client
        assert self.pipeline.llm_client == self.mock_llm_client
        assert self.pipeline.search_adapter == self.mock_search_adapter
        assert hasattr(self.pipeline, 'answer_question')
    
    def test_retrieve_contexts_success(self):
        """Test successful context retrieval."""
        # Mock vector search results
        mock_contexts = [
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
        
        self.mock_vector_client.post.return_value.json.return_value = mock_contexts
        self.mock_vector_client.post.return_value.status_code = 200
        
        contexts = self.pipeline.retrieve_contexts("authentication", top_k=5)
        
        assert len(contexts) == 2
        assert contexts[0]["text"] == "def authenticate_user(username, password): return True"
        assert contexts[0]["score"] == 0.95
        assert contexts[1]["meta"]["source"] == "models.py"
    
    def test_retrieve_contexts_empty_results(self):
        """Test context retrieval with empty results."""
        self.mock_vector_client.post.return_value.json.return_value = []
        self.mock_vector_client.post.return_value.status_code = 200
        
        contexts = self.pipeline.retrieve_contexts("nonexistent query")
        
        assert len(contexts) == 0
    
    def test_retrieve_contexts_service_error(self):
        """Test context retrieval with service error."""
        self.mock_vector_client.post.return_value.status_code = 500
        self.mock_vector_client.post.return_value.raise_for_status.side_effect = Exception("Service error")
        
        contexts = self.pipeline.retrieve_contexts("test query")
        
        assert len(contexts) == 0
    
    def test_search_web_success(self):
        """Test successful web search."""
        mock_web_results = [
            {
                "title": "Authentication Best Practices",
                "snippet": "Learn about secure authentication methods",
                "url": "https://example.com/auth",
                "source": "serpapi",
                "content": "Detailed content about authentication",
                "fetched_at": "2024-01-01T00:00:00Z"
            }
        ]
        
        self.mock_search_adapter.search.return_value = mock_web_results
        
        web_results = self.pipeline.search_web("authentication best practices", max_results=3)
        
        assert len(web_results) == 1
        assert web_results[0]["title"] == "Authentication Best Practices"
        assert web_results[0]["url"] == "https://example.com/auth"
    
    def test_search_web_disabled(self):
        """Test web search when disabled."""
        web_results = self.pipeline.search_web("test query", enable_web_search=False)
        
        assert len(web_results) == 0
        self.mock_search_adapter.search.assert_not_called()
    
    def test_search_web_error(self):
        """Test web search with error."""
        self.mock_search_adapter.search.side_effect = Exception("Search service error")
        
        web_results = self.pipeline.search_web("test query")
        
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
        
        summary = self.pipeline.summarize_contexts(contexts)
        
        assert isinstance(summary, str)
        assert len(summary) > 0
        assert "authentication" in summary.lower() or "auth" in summary.lower()
    
    def test_summarize_contexts_empty(self):
        """Test context summarization with empty contexts."""
        summary = self.pipeline.summarize_contexts([])
        
        assert summary == "No relevant code contexts found."
    
    def test_format_contexts(self):
        """Test context formatting."""
        contexts = [
            {
                "text": "def hello(): return 'world'",
                "score": 0.95,
                "meta": {"source": "utils.py", "line": 5}
            }
        ]
        
        formatted = self.pipeline.format_contexts(contexts)
        
        assert isinstance(formatted, str)
        assert "utils.py" in formatted
        assert "def hello()" in formatted
        assert "Score:" in formatted
    
    def test_format_contexts_empty(self):
        """Test formatting empty contexts."""
        formatted = self.pipeline.format_contexts([])
        
        assert formatted == "No code contexts available."
    
    def test_compose_prompt(self):
        """Test prompt composition."""
        question = "How does authentication work?"
        contexts = "def authenticate_user(): pass"
        web_results = "Authentication is the process of verifying identity."
        
        prompt = self.pipeline.compose_prompt(question, contexts, web_results)
        
        assert isinstance(prompt, str)
        assert question in prompt
        assert contexts in prompt
        assert web_results in prompt
        assert "SYSTEM:" in prompt or "System:" in prompt
    
    def test_compose_prompt_no_web_results(self):
        """Test prompt composition without web results."""
        question = "How does authentication work?"
        contexts = "def authenticate_user(): pass"
        
        prompt = self.pipeline.compose_prompt(question, contexts, "")
        
        assert isinstance(prompt, str)
        assert question in prompt
        assert contexts in prompt
    
    def test_answer_question_full_pipeline(self):
        """Test complete question answering pipeline."""
        # Mock vector search results
        mock_contexts = [
            {
                "text": "def authenticate_user(username, password): return True",
                "score": 0.95,
                "meta": {"source": "auth.py", "chunk_id": "1"},
                "rank": 1
            }
        ]
        
        # Mock web search results
        mock_web_results = [
            {
                "title": "Auth Guide",
                "snippet": "Authentication guide",
                "url": "https://example.com",
                "source": "web",
                "content": "Authentication content",
                "fetched_at": "2024-01-01T00:00:00Z"
            }
        ]
        
        # Mock LLM response
        mock_llm_response = {
            "text": "Authentication works by validating user credentials against stored data.",
            "meta": {"backend": "mock", "latency_ms": 100, "tokens": 50}
        }
        
        # Set up mocks
        self.mock_vector_client.post.return_value.json.return_value = mock_contexts
        self.mock_vector_client.post.return_value.status_code = 200
        self.mock_search_adapter.search.return_value = mock_web_results
        self.mock_llm_client.generate.return_value = mock_llm_response
        
        # Test the pipeline
        result = self.pipeline.answer_question(
            question="How does authentication work?",
            max_tokens=512,
            top_k=5,
            enable_web_search=True
        )
        
        # Verify result structure
        assert "answer" in result
        assert "contexts" in result
        assert "web_results" in result
        assert "meta" in result
        
        # Verify content
        assert result["answer"] == mock_llm_response["text"]
        assert len(result["contexts"]) == 1
        assert len(result["web_results"]) == 1
        assert result["meta"]["llm_backend"] == "mock"
        assert result["meta"]["total_contexts"] == 1
        assert result["meta"]["total_web_results"] == 1
    
    def test_answer_question_no_contexts(self):
        """Test question answering with no contexts found."""
        # Mock empty vector search
        self.mock_vector_client.post.return_value.json.return_value = []
        self.mock_vector_client.post.return_value.status_code = 200
        
        # Mock LLM response
        mock_llm_response = {
            "text": "I don't have specific information about that in the codebase.",
            "meta": {"backend": "mock", "latency_ms": 100, "tokens": 20}
        }
        self.mock_llm_client.generate.return_value = mock_llm_response
        
        result = self.pipeline.answer_question("unknown topic")
        
        assert result["answer"] == mock_llm_response["text"]
        assert len(result["contexts"]) == 0
        assert result["meta"]["total_contexts"] == 0
    
    def test_answer_question_llm_error(self):
        """Test question answering with LLM error."""
        # Mock contexts
        self.mock_vector_client.post.return_value.json.return_value = []
        self.mock_vector_client.post.return_value.status_code = 200
        
        # Mock LLM error
        self.mock_llm_client.generate.side_effect = Exception("LLM service unavailable")
        
        with pytest.raises(Exception, match="LLM service unavailable"):
            self.pipeline.answer_question("test question")
    
    def test_health_check_all_healthy(self):
        """Test health check when all services are healthy."""
        # Mock healthy responses
        self.mock_vector_client.get.return_value.status_code = 200
        self.mock_vector_client.get.return_value.json.return_value = {"status": "healthy"}
        
        health = self.pipeline.health_check()
        
        assert health["status"] == "healthy"
        assert health["vector_index"] == "healthy"
        assert health["llm_client"] == "healthy"
        assert health["search_adapter"] == "healthy"
    
    def test_health_check_vector_unhealthy(self):
        """Test health check when vector service is unhealthy."""
        # Mock unhealthy vector service
        self.mock_vector_client.get.return_value.status_code = 500
        
        health = self.pipeline.health_check()
        
        assert health["status"] == "degraded"
        assert health["vector_index"] == "unhealthy"
    
    def test_health_check_llm_unhealthy(self):
        """Test health check when LLM service is unhealthy."""
        # Mock healthy vector service
        self.mock_vector_client.get.return_value.status_code = 200
        self.mock_vector_client.get.return_value.json.return_value = {"status": "healthy"}
        
        # Mock unhealthy LLM service
        self.mock_llm_client.get_available_adapters.side_effect = Exception("LLM error")
        
        health = self.pipeline.health_check()
        
        assert health["status"] == "degraded"
        assert health["llm_client"] == "unhealthy"


class TestRAGPipelineIntegration:
    """Integration tests for RAG pipeline."""
    
    def test_rag_template_format(self):
        """Test RAG template formatting."""
        pipeline = RAGPipeline(Mock(), Mock(), Mock())
        
        question = "How does authentication work?"
        contexts = "def authenticate(): pass"
        web_results = "Auth is important for security."
        
        prompt = pipeline.compose_prompt(question, contexts, web_results)
        
        # Check that prompt contains all required sections
        assert "SYSTEM:" in prompt or "System:" in prompt
        assert "QUESTION:" in prompt or "Question:" in prompt
        assert "CODE CONTEXTS:" in prompt or "Code Contexts:" in prompt
        assert "WEB SEARCH RESULTS:" in prompt or "Web Search Results:" in prompt
        
        # Check content is included
        assert question in prompt
        assert contexts in prompt
        assert web_results in prompt
    
    def test_context_ranking_preservation(self):
        """Test that context ranking is preserved through pipeline."""
        pipeline = RAGPipeline(Mock(), Mock(), Mock())
        
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
    
    def test_error_recovery(self):
        """Test pipeline error recovery mechanisms."""
        # Create pipeline with failing dependencies
        failing_vector = Mock()
        failing_vector.post.side_effect = Exception("Vector service down")
        
        failing_search = Mock()
        failing_search.search.side_effect = Exception("Search service down")
        
        working_llm = Mock()
        working_llm.generate.return_value = {
            "text": "I cannot access the codebase right now.",
            "meta": {"backend": "mock", "latency_ms": 50, "tokens": 10}
        }
        
        pipeline = RAGPipeline(failing_vector, working_llm, failing_search)
        
        # Should still be able to answer (with degraded functionality)
        result = pipeline.answer_question("test question")
        
        assert "answer" in result
        assert len(result["contexts"]) == 0  # No contexts due to vector failure
        assert len(result["web_results"]) == 0  # No web results due to search failure
        assert result["answer"] == "I cannot access the codebase right now."
    
    def test_prompt_length_management(self):
        """Test that prompts don't exceed reasonable length limits."""
        pipeline = RAGPipeline(Mock(), Mock(), Mock())
        
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
        prompt = pipeline.compose_prompt("test question", formatted, "web results")
        
        # Should still be a valid string
        assert isinstance(prompt, str)
        assert len(prompt) > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
