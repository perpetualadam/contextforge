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
    AnthropicAdapter, 
    MockAdapter
)


class TestMockAdapter:
    """Test the MockAdapter functionality."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.adapter = MockAdapter()
    
    def test_mock_adapter_initialization(self):
        """Test MockAdapter initializes correctly."""
        assert self.adapter.name == "mock"
        assert hasattr(self.adapter, 'generate')
    
    def test_mock_adapter_code_response(self):
        """Test MockAdapter returns code-related responses for code prompts."""
        code_prompts = [
            "Write a Python function",
            "Implement a class",
            "Create a script",
            "Show me some code"
        ]
        
        for prompt in code_prompts:
            response = self.adapter.generate(prompt)
            assert "text" in response
            assert "meta" in response
            assert response["meta"]["backend"] == "mock"
            assert len(response["text"]) > 0
            # Code responses should contain code-related keywords
            text_lower = response["text"].lower()
            assert any(keyword in text_lower for keyword in ["function", "class", "def", "import", "return"])
    
    def test_mock_adapter_explanation_response(self):
        """Test MockAdapter returns explanatory responses for explanation prompts."""
        explanation_prompts = [
            "Explain how this works",
            "What is machine learning?",
            "Describe the process",
            "Tell me about authentication"
        ]
        
        for prompt in explanation_prompts:
            response = self.adapter.generate(prompt)
            assert "text" in response
            assert "meta" in response
            assert response["meta"]["backend"] == "mock"
            assert len(response["text"]) > 0
    
    def test_mock_adapter_general_response(self):
        """Test MockAdapter returns general responses for other prompts."""
        general_prompts = [
            "Hello there",
            "Random question",
            "Something else entirely"
        ]
        
        for prompt in general_prompts:
            response = self.adapter.generate(prompt)
            assert "text" in response
            assert "meta" in response
            assert response["meta"]["backend"] == "mock"
            assert len(response["text"]) > 0
    
    def test_mock_adapter_metadata(self):
        """Test MockAdapter returns proper metadata."""
        response = self.adapter.generate("test prompt")
        
        meta = response["meta"]
        assert meta["backend"] == "mock"
        assert "latency_ms" in meta
        assert isinstance(meta["latency_ms"], (int, float))
        assert meta["latency_ms"] >= 0
        assert "tokens" in meta
        assert isinstance(meta["tokens"], int)
        assert meta["tokens"] > 0


class TestOllamaAdapter:
    """Test the OllamaAdapter functionality."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.adapter = OllamaAdapter("http://localhost:11434")
    
    def test_ollama_adapter_initialization(self):
        """Test OllamaAdapter initializes correctly."""
        assert self.adapter.name == "ollama"
        assert self.adapter.base_url == "http://localhost:11434"
    
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
        self.adapter = OpenAIAdapter("test-api-key")
    
    def test_openai_adapter_initialization(self):
        """Test OpenAIAdapter initializes correctly."""
        assert self.adapter.name == "openai"
        assert self.adapter.api_key == "test-api-key"
    
    @patch('requests.post')
    def test_openai_adapter_successful_request(self, mock_post):
        """Test OpenAIAdapter handles successful requests."""
        # Mock successful response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "choices": [
                {
                    "message": {
                        "content": "This is a test response from OpenAI"
                    }
                }
            ],
            "usage": {
                "completion_tokens": 75
            }
        }
        mock_post.return_value = mock_response
        
        response = self.adapter.generate("test prompt")
        
        assert "text" in response
        assert "meta" in response
        assert response["text"] == "This is a test response from OpenAI"
        assert response["meta"]["backend"] == "openai"
        assert response["meta"]["tokens"] == 75
    
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
    
    def test_llm_client_mock_adapter_available(self):
        """Test LLMClient has mock adapter available."""
        assert "mock" in self.client.adapters
        assert isinstance(self.client.adapters["mock"], MockAdapter)
    
    def test_llm_client_generate_with_mock(self):
        """Test LLMClient can generate responses using mock adapter."""
        # Set priority to mock only
        self.client.priority = ["mock"]
        
        response = self.client.generate("test prompt")
        
        assert "text" in response
        assert "meta" in response
        assert response["meta"]["backend"] == "mock"
        assert len(response["text"]) > 0
    
    def test_llm_client_fallback_mechanism(self):
        """Test LLMClient fallback mechanism."""
        # Create a client with mock adapters that fail
        client = LLMClient()
        
        # Mock a failing adapter
        failing_adapter = Mock()
        failing_adapter.name = "failing"
        failing_adapter.generate.side_effect = Exception("Adapter failed")
        
        # Add failing adapter to the beginning of priority
        client.adapters["failing"] = failing_adapter
        client.priority = ["failing", "mock"]
        
        # Should fallback to mock adapter
        response = client.generate("test prompt")
        
        assert "text" in response
        assert "meta" in response
        assert response["meta"]["backend"] == "mock"
    
    def test_llm_client_no_adapters_available(self):
        """Test LLMClient behavior when no adapters are available."""
        # Create client with no working adapters
        client = LLMClient()
        client.adapters = {}
        client.priority = []
        
        with pytest.raises(Exception, match="No LLM adapters available"):
            client.generate("test prompt")
    
    def test_llm_client_all_adapters_fail(self):
        """Test LLMClient behavior when all adapters fail."""
        # Create client with only failing adapters
        client = LLMClient()
        
        failing_adapter = Mock()
        failing_adapter.name = "failing"
        failing_adapter.generate.side_effect = Exception("Adapter failed")
        
        client.adapters = {"failing": failing_adapter}
        client.priority = ["failing"]
        
        with pytest.raises(Exception, match="All LLM adapters failed"):
            client.generate("test prompt")
    
    def test_llm_client_get_available_adapters(self):
        """Test LLMClient can list available adapters."""
        available = self.client.get_available_adapters()
        
        assert isinstance(available, list)
        assert "mock" in available
        assert len(available) > 0
    
    def test_llm_client_get_priority_order(self):
        """Test LLMClient can return priority order."""
        priority = self.client.get_priority_order()
        
        assert isinstance(priority, list)
        assert len(priority) > 0
    
    def test_llm_client_custom_priority(self):
        """Test LLMClient respects custom priority order."""
        # Set custom priority
        custom_priority = ["mock"]
        client = LLMClient(priority=custom_priority)
        
        assert client.priority == custom_priority
        
        response = client.generate("test prompt")
        assert response["meta"]["backend"] == "mock"


class TestLLMAdapterIntegration:
    """Integration tests for LLM adapters."""
    
    def test_adapter_response_format_consistency(self):
        """Test all adapters return consistent response format."""
        adapters = [
            MockAdapter(),
        ]
        
        for adapter in adapters:
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
    
    def test_adapter_error_handling(self):
        """Test adapters handle errors gracefully."""
        # Test with mock adapter (should not raise errors)
        adapter = MockAdapter()
        
        # Test with various inputs
        test_inputs = [
            "",  # Empty string
            "a" * 10000,  # Very long string
            "Special chars: !@#$%^&*()",  # Special characters
            "Unicode: 你好世界 🌍",  # Unicode characters
        ]
        
        for test_input in test_inputs:
            response = adapter.generate(test_input)
            assert "text" in response
            assert "meta" in response


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
