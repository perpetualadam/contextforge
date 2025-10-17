"""
Tests for auto-terminal execution functionality.
"""

import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

from services.api_gateway.app import app, extract_commands_from_response, is_command_whitelisted


@pytest.fixture
def client():
    """Create test client."""
    return TestClient(app)


class TestCommandExtraction:
    """Test command extraction from LLM responses."""
    
    def test_extract_bash_code_blocks(self):
        """Test extracting commands from bash code blocks."""
        response_text = """
        To install dependencies, run:
        
        ```bash
        npm install
        npm run build
        ```
        
        Then check the status:
        ```shell
        git status
        ```
        """
        
        commands = extract_commands_from_response(response_text)
        expected = ["npm install", "npm run build", "git status"]
        assert commands == expected
    
    def test_extract_inline_commands(self):
        """Test extracting inline commands."""
        response_text = """
        You can run `npm test` to execute tests or use `python -m pytest` for Python tests.
        Also try `git status` to check your repository status.
        """
        
        commands = extract_commands_from_response(response_text)
        expected = ["npm test", "python -m pytest", "git status"]
        assert commands == expected
    
    def test_extract_run_execute_patterns(self):
        """Test extracting Run: and Execute: patterns."""
        response_text = """
        Run: npm install
        Execute: python setup.py install
        Command: git status
        """
        
        commands = extract_commands_from_response(response_text)
        expected = ["npm install", "python setup.py install", "git status"]
        assert commands == expected
    
    def test_extract_dollar_prefixed_commands(self):
        """Test extracting $ prefixed commands."""
        response_text = """
        $ npm install
        $ git status
        $ python --version
        """
        
        commands = extract_commands_from_response(response_text)
        expected = ["npm install", "git status", "python --version"]
        assert commands == expected
    
    def test_ignore_comments_and_empty_lines(self):
        """Test that comments and empty lines are ignored."""
        response_text = """
        ```bash
        # This is a comment
        npm install
        
        # Another comment
        git status
        ```
        """
        
        commands = extract_commands_from_response(response_text)
        expected = ["npm install", "git status"]
        assert commands == expected
    
    def test_remove_duplicates(self):
        """Test that duplicate commands are removed."""
        response_text = """
        ```bash
        npm install
        git status
        ```
        
        Also run `npm install` and `git status` again.
        """
        
        commands = extract_commands_from_response(response_text)
        expected = ["npm install", "git status"]
        assert commands == expected
    
    def test_mixed_patterns(self):
        """Test extracting from mixed patterns."""
        response_text = """
        First, install dependencies:
        ```bash
        npm install
        ```
        
        Then run `npm test` and Execute: git status
        
        Finally: $ python --version
        """
        
        commands = extract_commands_from_response(response_text)
        expected = ["npm install", "npm test", "git status", "python --version"]
        assert commands == expected


class TestWhitelistValidation:
    """Test command whitelist validation."""
    
    def test_exact_match(self):
        """Test exact command matching."""
        whitelist = ["git status", "npm test", "python --version"]
        
        assert is_command_whitelisted("git status", whitelist) == True
        assert is_command_whitelisted("npm test", whitelist) == True
        assert is_command_whitelisted("python --version", whitelist) == True
        assert is_command_whitelisted("rm -rf /", whitelist) == False
    
    def test_prefix_matching(self):
        """Test prefix matching for commands."""
        whitelist = ["git", "npm", "python"]
        
        assert is_command_whitelisted("git status", whitelist) == True
        assert is_command_whitelisted("git log", whitelist) == True
        assert is_command_whitelisted("npm install", whitelist) == True
        assert is_command_whitelisted("python script.py", whitelist) == True
        assert is_command_whitelisted("sudo rm", whitelist) == False
    
    def test_npm_variations(self):
        """Test npm command variations."""
        whitelist = ["npm test", "npm run test"]
        
        assert is_command_whitelisted("npm test", whitelist) == True
        assert is_command_whitelisted("npm run test", whitelist) == True
        # Should not match different npm commands
        assert is_command_whitelisted("npm install", whitelist) == False
    
    def test_python_variations(self):
        """Test python command variations."""
        whitelist = ["python -m pytest"]
        
        assert is_command_whitelisted("python -m pytest", whitelist) == True
        assert is_command_whitelisted("python3 -m pytest", whitelist) == True
        assert is_command_whitelisted("python script.py", whitelist) == False
    
    def test_empty_whitelist(self):
        """Test behavior with empty whitelist."""
        whitelist = []
        
        assert is_command_whitelisted("git status", whitelist) == False
        assert is_command_whitelisted("npm test", whitelist) == False
    
    def test_none_whitelist(self):
        """Test behavior with None whitelist."""
        whitelist = None
        
        assert is_command_whitelisted("git status", whitelist) == False


class TestAutoTerminalAPI:
    """Test auto-terminal API integration."""
    
    @patch('services.api_gateway.app.rag_pipeline')
    @patch('services.api_gateway.app.requests.post')
    def test_auto_terminal_disabled(self, mock_requests, mock_rag, client):
        """Test query with auto-terminal disabled."""
        # Mock RAG pipeline response
        mock_rag.answer_question.return_value = {
            "question": "test question",
            "answer": "Run `git status` to check status",
            "contexts": [],
            "web_results": [],
            "meta": {
                "backend": "mock",
                "total_latency_ms": 100,
                "num_contexts": 0,
                "num_web_results": 0
            }
        }
        
        response = client.post("/query", json={
            "query": "test question",
            "auto_terminal_mode": False
        })
        
        assert response.status_code == 200
        data = response.json()
        assert "auto_terminal_results" not in data
        assert "auto_commands_executed" not in data["meta"]
    
    @patch('services.api_gateway.app.rag_pipeline')
    @patch('services.api_gateway.app.requests.post')
    def test_auto_terminal_enabled_success(self, mock_requests, mock_rag, client):
        """Test query with auto-terminal enabled and successful execution."""
        # Mock RAG pipeline response
        mock_rag.answer_question.return_value = {
            "question": "test question",
            "answer": "Run `git status` to check status",
            "contexts": [],
            "web_results": [],
            "meta": {
                "backend": "mock",
                "total_latency_ms": 100,
                "num_contexts": 0,
                "num_web_results": 0
            }
        }
        
        # Mock terminal executor response
        mock_terminal_response = MagicMock()
        mock_terminal_response.raise_for_status.return_value = None
        mock_terminal_response.json.return_value = {
            "command": "git status",
            "exit_code": 0,
            "stdout": "On branch main\nnothing to commit, working tree clean",
            "stderr": "",
            "execution_time": 0.5
        }
        mock_requests.return_value = mock_terminal_response
        
        response = client.post("/query", json={
            "query": "test question",
            "auto_terminal_mode": True,
            "auto_terminal_whitelist": ["git status"]
        })
        
        assert response.status_code == 200
        data = response.json()
        assert "auto_terminal_results" in data
        assert len(data["auto_terminal_results"]) == 1
        assert data["auto_terminal_results"][0]["command"] == "git status"
        assert data["auto_terminal_results"][0]["exit_code"] == 0
        assert data["auto_terminal_results"][0]["matched_whitelist"] == True
        assert data["meta"]["auto_commands_executed"] == 1
    
    @patch('services.api_gateway.app.rag_pipeline')
    def test_auto_terminal_command_not_whitelisted(self, mock_rag, client):
        """Test auto-terminal with command not in whitelist."""
        # Mock RAG pipeline response
        mock_rag.answer_question.return_value = {
            "question": "test question",
            "answer": "Run `npm install dangerous-package` to install it",
            "contexts": [],
            "web_results": [],
            "meta": {
                "backend": "mock",
                "total_latency_ms": 100,
                "num_contexts": 0,
                "num_web_results": 0
            }
        }

        response = client.post("/query", json={
            "query": "test question",
            "auto_terminal_mode": True,
            "auto_terminal_whitelist": ["git status", "npm test"]
        })

        assert response.status_code == 200
        data = response.json()
        assert "auto_terminal_results" in data
        assert len(data["auto_terminal_results"]) == 1
        assert data["auto_terminal_results"][0]["command"] == "npm install dangerous-package"
        assert data["auto_terminal_results"][0]["exit_code"] == -1
        assert data["auto_terminal_results"][0]["matched_whitelist"] == False
        assert "not in whitelist" in data["auto_terminal_results"][0]["stderr"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
