"""
Tests for the /prompts/enhance API used by the chat composer Enhance control.
"""

import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

import sys
import os

sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'services', 'api_gateway'))

from app import app


class TestPromptEnhanceEndpoint:
    """Ensure enhance-prompt API behavior matches what the chat composer expects."""

    def setup_method(self):
        self.client = TestClient(app)

    @patch('app.LLMClient')
    def test_enhance_prompt_returns_structured_result(self, mock_llm_cls):
        mock_llm = MagicMock()
        mock_llm.generate.return_value = {
            'text': (
                '{"enhanced": "Explain how authentication works in detail, '
                'including token flow and failure modes.",'
                ' "suggestions": ["Add desired output format", "Mention stack"],'
                ' "improvements": ["More specific", "Clearer goal"]}'
            )
        }
        mock_llm_cls.return_value = mock_llm

        response = self.client.post(
            '/prompts/enhance',
            json={'prompt': 'explain auth', 'style': 'professional'},
        )

        assert response.status_code == 200
        data = response.json()
        assert data['original'] == 'explain auth'
        assert 'authentication' in data['enhanced'].lower() or 'auth' in data['enhanced'].lower()
        assert isinstance(data['suggestions'], list)
        assert isinstance(data['improvements'], list)
        assert len(data['suggestions']) >= 1
        mock_llm.generate.assert_called_once()

    @patch('app.LLMClient')
    def test_enhance_prompt_fallback_when_llm_returns_non_json(self, mock_llm_cls):
        mock_llm = MagicMock()
        mock_llm.generate.return_value = {'text': 'not json at all'}
        mock_llm_cls.return_value = mock_llm

        response = self.client.post(
            '/prompts/enhance',
            json={'prompt': 'fix the bug'},
        )

        assert response.status_code == 200
        data = response.json()
        assert data['original'] == 'fix the bug'
        assert data['enhanced']
        assert isinstance(data['suggestions'], list)
        assert len(data['suggestions']) >= 1

    def test_enhance_prompt_requires_prompt_field(self):
        response = self.client.post('/prompts/enhance', json={})
        assert response.status_code == 422

    @patch('app.LLMClient')
    def test_enhance_prompt_accepts_context(self, mock_llm_cls):
        mock_llm = MagicMock()
        mock_llm.generate.return_value = {
            'text': '{"enhanced": "Detailed prompt", "suggestions": [], "improvements": []}'
        }
        mock_llm_cls.return_value = mock_llm

        response = self.client.post(
            '/prompts/enhance',
            json={
                'prompt': 'review this',
                'context': 'src/auth.py',
                'style': 'concise',
            },
        )

        assert response.status_code == 200
        call_kwargs = mock_llm.generate.call_args.kwargs
        assert 'src/auth.py' in call_kwargs.get('prompt', '') or 'src/auth.py' in str(
            mock_llm.generate.call_args
        )

    @patch('app.LLMClient')
    def test_enhance_prompt_surfaces_llm_failures(self, mock_llm_cls):
        mock_llm = MagicMock()
        mock_llm.generate.side_effect = RuntimeError('LLM down')
        mock_llm_cls.return_value = mock_llm

        response = self.client.post(
            '/prompts/enhance',
            json={'prompt': 'hello'},
        )

        assert response.status_code == 500
        assert 'enhance' in response.json()['detail'].lower() or 'failed' in response.json()['detail'].lower()
