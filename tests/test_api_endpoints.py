"""
Tests for API Gateway endpoints.
"""

import pytest
import json
from unittest.mock import Mock, patch, MagicMock
from fastapi.testclient import TestClient

# Import the modules to test
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'services', 'api_gateway'))

from app import app


class TestAPIGatewayEndpoints:
    """Test the API Gateway endpoints."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.client = TestClient(app)
    
    def test_health_endpoint(self):
        """Test health check endpoint."""
        response = self.client.get("/health")
        
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert "timestamp" in data
        assert "version" in data
    
    def test_config_endpoint(self):
        """Test configuration endpoint."""
        response = self.client.get("/config")
        
        assert response.status_code == 200
        data = response.json()
        assert "privacy_mode" in data
        assert "enable_web_search" in data
        assert "llm_priority" in data
    
    @patch('app.rag_pipeline')
    def test_query_endpoint_success(self, mock_rag):
        """Test successful query endpoint."""
        # Mock RAG pipeline response
        mock_response = {
            "answer": "Authentication works by validating credentials.",
            "contexts": [
                {
                    "text": "def authenticate_user(): pass",
                    "score": 0.95,
                    "meta": {"source": "auth.py"}
                }
            ],
            "web_results": [],
            "meta": {
                "llm_backend": "mock",
                "total_contexts": 1,
                "total_web_results": 0,
                "latency_ms": 150
            }
        }
        mock_rag.answer_question.return_value = mock_response
        
        # Test query
        query_data = {
            "query": "How does authentication work?",
            "max_tokens": 512,
            "top_k": 5,
            "enable_web_search": False
        }
        
        response = self.client.post("/query", json=query_data)
        
        assert response.status_code == 200
        data = response.json()
        assert data["answer"] == "Authentication works by validating credentials."
        assert len(data["contexts"]) == 1
        assert data["meta"]["llm_backend"] == "mock"
    
    def test_query_endpoint_missing_query(self):
        """Test query endpoint with missing query parameter."""
        response = self.client.post("/query", json={})
        
        assert response.status_code == 422  # Validation error
    
    def test_query_endpoint_empty_query(self):
        """Test query endpoint with empty query."""
        query_data = {"query": ""}
        
        response = self.client.post("/query", json=query_data)
        
        assert response.status_code == 400
        data = response.json()
        assert "error" in data
        assert "empty" in data["error"].lower()
    
    @patch('app.rag_pipeline')
    def test_query_endpoint_rag_error(self, mock_rag):
        """Test query endpoint with RAG pipeline error."""
        mock_rag.answer_question.side_effect = Exception("RAG pipeline error")
        
        query_data = {"query": "test question"}
        
        response = self.client.post("/query", json=query_data)
        
        assert response.status_code == 500
        data = response.json()
        assert "error" in data
    
    @patch('requests.post')
    def test_ingest_endpoint_success(self, mock_post):
        """Test successful ingestion endpoint."""
        # Mock service responses
        mock_connector_response = Mock()
        mock_connector_response.status_code = 200
        mock_connector_response.json.return_value = {
            "files_processed": 5,
            "total_size": 12345,
            "files": ["file1.py", "file2.js"]
        }
        
        mock_preprocessor_response = Mock()
        mock_preprocessor_response.status_code = 200
        mock_preprocessor_response.json.return_value = {
            "chunks_created": 15,
            "total_chunks": 15
        }
        
        mock_vector_response = Mock()
        mock_vector_response.status_code = 200
        mock_vector_response.json.return_value = {
            "chunks_processed": 15,
            "chunks_indexed": 15
        }
        
        mock_post.side_effect = [
            mock_connector_response,
            mock_preprocessor_response,
            mock_vector_response
        ]
        
        # Test ingestion
        ingest_data = {
            "path": "/test/repo",
            "recursive": True,
            "file_patterns": ["*.py", "*.js"],
            "exclude_patterns": ["*.pyc"]
        }
        
        response = self.client.post("/ingest", json=ingest_data)
        
        assert response.status_code == 200
        data = response.json()
        assert "files_processed" in data
        assert "chunks_created" in data
        assert "chunks_indexed" in data
        assert data["files_processed"] == 5
        assert data["chunks_indexed"] == 15
    
    def test_ingest_endpoint_missing_path(self):
        """Test ingestion endpoint with missing path."""
        response = self.client.post("/ingest", json={})
        
        assert response.status_code == 422  # Validation error
    
    @patch('requests.post')
    def test_ingest_endpoint_connector_error(self, mock_post):
        """Test ingestion endpoint with connector service error."""
        mock_response = Mock()
        mock_response.status_code = 500
        mock_response.raise_for_status.side_effect = Exception("Connector error")
        mock_post.return_value = mock_response
        
        ingest_data = {"path": "/test/repo"}
        
        response = self.client.post("/ingest", json=ingest_data)
        
        assert response.status_code == 500
        data = response.json()
        assert "error" in data
    
    @patch('requests.post')
    def test_vector_search_endpoint(self, mock_post):
        """Test vector search endpoint."""
        # Mock vector service response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = [
            {
                "text": "def test_function(): pass",
                "score": 0.95,
                "meta": {"source": "test.py"},
                "rank": 1
            }
        ]
        mock_post.return_value = mock_response
        
        search_data = {
            "query": "test function",
            "top_k": 5
        }
        
        response = self.client.post("/search/vector", json=search_data)
        
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["text"] == "def test_function(): pass"
    
    @patch('app.search_adapter')
    def test_web_search_endpoint(self, mock_search):
        """Test web search endpoint."""
        # Mock search adapter response
        mock_search.search.return_value = [
            {
                "title": "Test Result",
                "snippet": "Test snippet",
                "url": "https://example.com",
                "source": "serpapi"
            }
        ]
        
        search_data = {
            "query": "test search",
            "max_results": 5
        }
        
        response = self.client.post("/search/web", json=search_data)
        
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["title"] == "Test Result"
    
    @patch('app.llm_client')
    def test_llm_generate_endpoint(self, mock_llm):
        """Test LLM generation endpoint."""
        # Mock LLM response
        mock_llm.generate.return_value = {
            "text": "This is a generated response.",
            "meta": {"backend": "mock", "latency_ms": 100, "tokens": 25}
        }
        
        generate_data = {
            "prompt": "Generate a response",
            "max_tokens": 100
        }
        
        response = self.client.post("/llm/generate", json=generate_data)
        
        assert response.status_code == 200
        data = response.json()
        assert data["text"] == "This is a generated response."
        assert data["meta"]["backend"] == "mock"
    
    @patch('app.llm_client')
    def test_llm_adapters_endpoint(self, mock_llm):
        """Test LLM adapters listing endpoint."""
        # Mock available adapters
        mock_llm.get_available_adapters.return_value = ["mock", "ollama"]
        mock_llm.get_priority_order.return_value = ["ollama", "mock"]
        
        response = self.client.get("/llm/adapters")
        
        assert response.status_code == 200
        data = response.json()
        assert "available" in data
        assert "priority" in data
        assert "mock" in data["available"]
        assert "ollama" in data["available"]
    
    @patch('requests.get')
    def test_index_stats_endpoint(self, mock_get):
        """Test index statistics endpoint."""
        # Mock vector service response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "total_vectors": 150,
            "dimension": 384,
            "backend": "faiss"
        }
        mock_get.return_value = mock_response
        
        response = self.client.get("/index/stats")
        
        assert response.status_code == 200
        data = response.json()
        assert data["total_vectors"] == 150
        assert data["dimension"] == 384
        assert data["backend"] == "faiss"
    
    @patch('requests.delete')
    def test_index_clear_endpoint(self, mock_delete):
        """Test index clearing endpoint."""
        # Mock vector service response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"status": "cleared"}
        mock_delete.return_value = mock_response
        
        response = self.client.delete("/index/clear")
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "cleared"
    
    def test_cors_headers(self):
        """Test CORS headers are present."""
        response = self.client.options("/health")
        
        # Should have CORS headers
        assert "access-control-allow-origin" in response.headers
    
    def test_invalid_endpoint(self):
        """Test invalid endpoint returns 404."""
        response = self.client.get("/invalid/endpoint")
        
        assert response.status_code == 404
    
    def test_method_not_allowed(self):
        """Test method not allowed returns 405."""
        response = self.client.put("/health")  # Health only supports GET
        
        assert response.status_code == 405


class TestAPIValidation:
    """Test API request validation."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.client = TestClient(app)
    
    def test_query_validation_max_tokens(self):
        """Test query validation for max_tokens parameter."""
        # Test negative max_tokens
        response = self.client.post("/query", json={
            "query": "test",
            "max_tokens": -1
        })
        assert response.status_code == 422
        
        # Test zero max_tokens
        response = self.client.post("/query", json={
            "query": "test",
            "max_tokens": 0
        })
        assert response.status_code == 422
        
        # Test very large max_tokens
        response = self.client.post("/query", json={
            "query": "test",
            "max_tokens": 100000
        })
        assert response.status_code == 422
    
    def test_query_validation_top_k(self):
        """Test query validation for top_k parameter."""
        # Test negative top_k
        response = self.client.post("/query", json={
            "query": "test",
            "top_k": -1
        })
        assert response.status_code == 422
        
        # Test zero top_k
        response = self.client.post("/query", json={
            "query": "test",
            "top_k": 0
        })
        assert response.status_code == 422
    
    def test_ingest_validation_path(self):
        """Test ingestion validation for path parameter."""
        # Test empty path
        response = self.client.post("/ingest", json={
            "path": ""
        })
        assert response.status_code == 400
        
        # Test path with null bytes
        response = self.client.post("/ingest", json={
            "path": "/test\x00/path"
        })
        assert response.status_code == 400
    
    def test_vector_search_validation(self):
        """Test vector search validation."""
        # Test empty query
        response = self.client.post("/search/vector", json={
            "query": ""
        })
        assert response.status_code == 400
        
        # Test invalid top_k
        response = self.client.post("/search/vector", json={
            "query": "test",
            "top_k": -1
        })
        assert response.status_code == 422
    
    def test_web_search_validation(self):
        """Test web search validation."""
        # Test empty query
        response = self.client.post("/search/web", json={
            "query": ""
        })
        assert response.status_code == 400
        
        # Test invalid max_results
        response = self.client.post("/search/web", json={
            "query": "test",
            "max_results": 0
        })
        assert response.status_code == 422
    
    def test_llm_generate_validation(self):
        """Test LLM generation validation."""
        # Test empty prompt
        response = self.client.post("/llm/generate", json={
            "prompt": ""
        })
        assert response.status_code == 400
        
        # Test invalid max_tokens
        response = self.client.post("/llm/generate", json={
            "prompt": "test",
            "max_tokens": -1
        })
        assert response.status_code == 422


class TestAPIErrorHandling:
    """Test API error handling."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.client = TestClient(app)
    
    def test_json_decode_error(self):
        """Test handling of invalid JSON."""
        response = self.client.post(
            "/query",
            data="invalid json",
            headers={"Content-Type": "application/json"}
        )
        
        assert response.status_code == 422
    
    def test_content_type_error(self):
        """Test handling of wrong content type."""
        response = self.client.post(
            "/query",
            data="query=test",
            headers={"Content-Type": "application/x-www-form-urlencoded"}
        )
        
        # Should still work with form data for simple cases
        assert response.status_code in [400, 422]
    
    @patch('app.rag_pipeline')
    def test_internal_server_error(self, mock_rag):
        """Test handling of internal server errors."""
        mock_rag.answer_question.side_effect = Exception("Internal error")
        
        response = self.client.post("/query", json={"query": "test"})
        
        assert response.status_code == 500
        data = response.json()
        assert "error" in data
        assert "Internal error" in data["error"]
    
    def test_request_timeout_simulation(self):
        """Test request timeout handling (simulated)."""
        # This would require actual timeout simulation
        # For now, just test that the endpoint exists and responds
        response = self.client.get("/health")
        assert response.status_code == 200


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
