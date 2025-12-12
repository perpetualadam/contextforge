"""
Tests for LLM Adapter functionality.
"""

import pytest
import json
from unittest.mock import Mock, patch, AsyncMock
from datetime import datetime

# Import the modules to test
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'services', 'api_gateway'))

from llm_client import (
    LLMClient,
    OllamaAdapter,
    LMStudioAdapter,
    OpenAIAdapter,
    AnthropicAdapter
)


# Note: MockAdapter was removed in the security update as it was only for testing
# and replaced with production-ready LLM adapters


class TestOllamaAdapter:
    """Test the OllamaAdapter functionality."""

    def setup_method(self):
        """Set up test fixtures."""
        self.adapter = OllamaAdapter("http://localhost:11434/api/generate")

    def test_ollama_adapter_initialization(self):
        """Test OllamaAdapter initializes correctly."""
        assert self.adapter.name == "ollama"
        assert self.adapter.url == "http://localhost:11434/api/generate"
    
    @patch('requests.post')
    def test_ollama_adapter_successful_request(self, mock_post):
        """Test OllamaAdapter handles successful requests."""
        # Mock successful response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "model": "llama2",
            "response": "This is a test response",
            "eval_count": 50
        }
        mock_post.return_value = mock_response
        
        response = self.adapter.generate("test prompt")
        
        assert "text" in response
        assert "meta" in response
        assert response["text"] == "This is a test response"
        assert response["meta"]["backend"] == "ollama"
        assert response["meta"]["tokens"] == 50
    
    @patch('requests.post')
    def test_ollama_adapter_connection_error(self, mock_post):
        """Test OllamaAdapter handles connection errors."""
        # Mock connection error
        mock_post.side_effect = Exception("Connection failed")
        
        with pytest.raises(Exception):
            self.adapter.generate("test prompt")
    
    @patch('requests.post')
    def test_ollama_adapter_http_error(self, mock_post):
        """Test OllamaAdapter handles HTTP errors."""
        # Mock HTTP error response
        mock_response = Mock()
        mock_response.status_code = 500
        mock_response.raise_for_status.side_effect = Exception("HTTP 500 Error")
        mock_post.return_value = mock_response
        
        with pytest.raises(Exception):
            self.adapter.generate("test prompt")


class TestOpenAIAdapter:
    """Test the OpenAIAdapter functionality."""

    def setup_method(self):
        """Set up test fixtures."""
        # OpenAIAdapter reads API key from environment
        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-api-key"}):
            self.adapter = OpenAIAdapter()

    def test_openai_adapter_initialization(self):
        """Test OpenAIAdapter initializes correctly."""
        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-api-key"}):
            adapter = OpenAIAdapter()
            assert adapter.name == "openai"
            assert adapter.api_key == "test-api-key"
    
    @patch('requests.post')
    def test_openai_adapter_successful_request(self, mock_post):
        """Test OpenAIAdapter handles successful requests."""
        # Set up adapter with API key
        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-api-key"}):
            adapter = OpenAIAdapter()

            # Mock successful response
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "model": "gpt-3.5-turbo",
                "choices": [
                    {
                        "message": {
                            "content": "This is a test response from OpenAI"
                        }
                    }
                ],
                "usage": {
                    "completion_tokens": 75,
                    "total_tokens": 100
                }
            }
            mock_post.return_value = mock_response

            response = adapter.generate("test prompt")

            assert "text" in response
            assert "meta" in response
            assert response["text"] == "This is a test response from OpenAI"
            assert response["meta"]["backend"] == "openai"
            assert response["meta"]["tokens"] == 100
    
    @patch('requests.post')
    def test_openai_adapter_api_error(self, mock_post):
        """Test OpenAIAdapter handles API errors."""
        # Mock API error response
        mock_response = Mock()
        mock_response.status_code = 401
        mock_response.raise_for_status.side_effect = Exception("API key invalid")
        mock_post.return_value = mock_response
        
        with pytest.raises(Exception):
            self.adapter.generate("test prompt")


class TestLLMClient:
    """Test the LLMClient functionality."""

    def setup_method(self):
        """Set up test fixtures."""
        self.client = LLMClient()

    def test_llm_client_initialization(self):
        """Test LLMClient initializes correctly."""
        assert hasattr(self.client, 'adapters')
        assert hasattr(self.client, 'priority')
        assert len(self.client.adapters) > 0

    def test_llm_client_has_production_adapters(self):
        """Test LLMClient has production adapters available."""
        # Check that at least one production adapter is available
        production_adapters = ["ollama", "lm_studio", "openai", "anthropic"]
        available_adapters = list(self.client.adapters.keys())
        assert any(adapter in available_adapters for adapter in production_adapters)

    @patch('requests.post')
    def test_llm_client_generate_with_ollama(self, mock_post):
        """Test LLMClient can generate responses using ollama adapter."""
        # Mock successful ollama response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "model": "mistral",
            "response": "This is a test response",
            "eval_count": 50
        }
        mock_post.return_value = mock_response

        # Set priority to ollama only
        self.client.priority = ["ollama"]

        # Mock is_available to return True
        self.client.adapters["ollama"].is_available = Mock(return_value=True)

        response = self.client.generate("test prompt")

        assert "text" in response
        assert "meta" in response
        assert response["meta"]["backend"] == "ollama"
        assert len(response["text"]) > 0

    @patch('requests.post')
    def test_llm_client_fallback_mechanism(self, mock_post):
        """Test LLMClient fallback mechanism."""
        client = LLMClient()

        # Create a failing adapter
        failing_adapter = Mock()
        failing_adapter.name = "failing"
        failing_adapter.is_available = Mock(return_value=True)
        failing_adapter.generate.side_effect = Exception("Adapter failed")

        # Create a working adapter
        working_adapter = Mock()
        working_adapter.name = "working"
        working_adapter.is_available = Mock(return_value=True)
        working_adapter.generate.return_value = {
            "text": "Success from working adapter",
            "meta": {"backend": "working", "latency_ms": 100, "tokens": 10}
        }

        # Set up client with failing first, then working
        client.adapters = {"failing": failing_adapter, "working": working_adapter}
        client.priority = ["failing", "working"]

        # Should fallback to working adapter
        response = client.generate("test prompt")

        assert "text" in response
        assert "meta" in response
        assert response["meta"]["backend"] == "working"

    def test_llm_client_no_adapters_available(self):
        """Test LLMClient behavior when no adapters are available."""
        # Create client with no working adapters
        client = LLMClient()
        client.adapters = {}
        client.priority = []

        with pytest.raises(Exception, match="All LLM adapters failed"):
            client.generate("test prompt")

    def test_llm_client_all_adapters_fail(self):
        """Test LLMClient behavior when all adapters fail."""
        # Create client with only failing adapters
        client = LLMClient()

        failing_adapter = Mock()
        failing_adapter.name = "failing"
        failing_adapter.is_available = Mock(return_value=True)
        failing_adapter.generate.side_effect = Exception("Adapter failed")

        client.adapters = {"failing": failing_adapter}
        client.priority = ["failing"]

        with pytest.raises(Exception, match="All LLM adapters failed"):
            client.generate("test prompt")

    def test_llm_client_list_available_adapters(self):
        """Test LLMClient can list available adapters."""
        available = self.client.list_available_adapters()

        assert isinstance(available, list)

    def test_llm_client_priority_order(self):
        """Test LLMClient has a priority order."""
        assert isinstance(self.client.priority, list)
        assert len(self.client.priority) > 0


class TestLLMAdapterIntegration:
    """Integration tests for LLM adapters."""

    @patch('requests.post')
    def test_adapter_response_format_consistency(self, mock_post):
        """Test adapters return consistent response format."""
        # Mock successful response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "model": "mistral",
            "response": "This is a test response",
            "eval_count": 50
        }
        mock_post.return_value = mock_response

        adapter = OllamaAdapter()
        response = adapter.generate("test prompt")

        # Check required fields
        assert "text" in response
        assert "meta" in response

        # Check text field
        assert isinstance(response["text"], str)
        assert len(response["text"]) > 0

        # Check meta field
        meta = response["meta"]
        assert "backend" in meta
        assert "latency_ms" in meta
        assert isinstance(meta["latency_ms"], (int, float))
        assert meta["latency_ms"] >= 0

    @patch('requests.post')
    def test_adapter_error_handling(self, mock_post):
        """Test adapters handle errors gracefully."""
        # Mock error response
        mock_post.side_effect = Exception("Connection error")

        adapter = OllamaAdapter()

        # Should raise an exception for errors
        with pytest.raises(Exception):
            adapter.generate("test prompt")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
