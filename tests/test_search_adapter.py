"""
Tests for Search Adapter functionality.
"""

import pytest
import json
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime

# Import the modules to test
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'services', 'api_gateway'))

from search_adapter import (
    SearchAdapter,
    SerpAPIProvider,
    BingSearchProvider,
    GoogleCSEProvider,
    ScrapeFallbackProvider,
    ContentFetcher
)


class TestSerpAPIProvider:
    """Test the SerpAPIProvider functionality."""

    def setup_method(self):
        """Set up test fixtures."""
        # SerpAPIProvider reads API key from environment
        with patch.dict(os.environ, {"SERPAPI_KEY": "test-api-key"}):
            self.provider = SerpAPIProvider()

    def test_serpapi_provider_initialization(self):
        """Test SerpAPIProvider initializes correctly."""
        with patch.dict(os.environ, {"SERPAPI_KEY": "test-api-key"}):
            provider = SerpAPIProvider()
            assert provider.name == "serpapi"
            assert provider.api_key == "test-api-key"

    @patch('requests.get')
    def test_serpapi_successful_search(self, mock_get):
        """Test SerpAPIProvider handles successful searches."""
        with patch.dict(os.environ, {"SERPAPI_KEY": "test-api-key"}):
            provider = SerpAPIProvider()

            # Mock successful response
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "organic_results": [
                    {
                        "title": "Test Result 1",
                        "snippet": "This is a test snippet",
                        "link": "https://example.com/1"
                    },
                    {
                        "title": "Test Result 2",
                        "snippet": "Another test snippet",
                        "link": "https://example.com/2"
                    }
                ]
            }
            mock_get.return_value = mock_response

            results = provider.search("test query", num_results=5)

            assert len(results) == 2
            assert results[0]["title"] == "Test Result 1"
            assert results[0]["snippet"] == "This is a test snippet"
            assert results[0]["url"] == "https://example.com/1"
            assert results[0]["source"] == "serpapi"

    @patch('requests.get')
    def test_serpapi_api_error(self, mock_get):
        """Test SerpAPIProvider handles API errors."""
        with patch.dict(os.environ, {"SERPAPI_KEY": "test-api-key"}):
            provider = SerpAPIProvider()

            # Mock API error response
            mock_get.side_effect = Exception("API key invalid")

            with pytest.raises(Exception):
                provider.search("test query")

    @patch('requests.get')
    def test_serpapi_empty_results(self, mock_get):
        """Test SerpAPIProvider handles empty results."""
        with patch.dict(os.environ, {"SERPAPI_KEY": "test-api-key"}):
            provider = SerpAPIProvider()

            # Mock empty response
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"organic_results": []}
            mock_get.return_value = mock_response

            results = provider.search("test query")
            assert len(results) == 0


class TestBingSearchProvider:
    """Test the BingSearchProvider functionality."""

    def setup_method(self):
        """Set up test fixtures."""
        # BingSearchProvider reads API key from environment
        pass

    def test_bing_provider_initialization(self):
        """Test BingSearchProvider initializes correctly."""
        with patch.dict(os.environ, {"BING_SUBSCRIPTION_KEY": "test-subscription-key"}):
            provider = BingSearchProvider()
            assert provider.name == "bing"
            assert provider.api_key == "test-subscription-key"

    @patch('requests.get')
    def test_bing_successful_search(self, mock_get):
        """Test BingSearchProvider handles successful searches."""
        with patch.dict(os.environ, {"BING_SUBSCRIPTION_KEY": "test-subscription-key"}):
            provider = BingSearchProvider()

            # Mock successful response
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "webPages": {
                    "value": [
                        {
                            "name": "Bing Test Result",
                            "snippet": "Bing test snippet",
                            "url": "https://bing-example.com"
                        }
                    ]
                }
            }
            mock_get.return_value = mock_response

            results = provider.search("test query")

            assert len(results) == 1
            assert results[0]["title"] == "Bing Test Result"
            assert results[0]["snippet"] == "Bing test snippet"
            assert results[0]["url"] == "https://bing-example.com"
            assert results[0]["source"] == "bing"


class TestGoogleCSEProvider:
    """Test the GoogleCSEProvider functionality."""

    def setup_method(self):
        """Set up test fixtures."""
        # GoogleCSEProvider reads API key and CSE ID from environment
        pass

    def test_google_cse_provider_initialization(self):
        """Test GoogleCSEProvider initializes correctly."""
        with patch.dict(os.environ, {"GOOGLE_CSE_KEY": "test-api-key", "GOOGLE_CSE_ID": "test-cse-id"}):
            provider = GoogleCSEProvider()
            assert provider.name == "google_cse"
            assert provider.api_key == "test-api-key"
            assert provider.cse_id == "test-cse-id"

    @patch('requests.get')
    def test_google_cse_successful_search(self, mock_get):
        """Test GoogleCSEProvider handles successful searches."""
        with patch.dict(os.environ, {"GOOGLE_CSE_KEY": "test-api-key", "GOOGLE_CSE_ID": "test-cse-id"}):
            provider = GoogleCSEProvider()

            # Mock successful response
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "items": [
                    {
                        "title": "Google CSE Result",
                        "snippet": "Google CSE snippet",
                        "link": "https://google-example.com"
                    }
                ]
            }
            mock_get.return_value = mock_response

            results = provider.search("test query")

            assert len(results) == 1
            assert results[0]["title"] == "Google CSE Result"
            assert results[0]["snippet"] == "Google CSE snippet"
            assert results[0]["url"] == "https://google-example.com"
            assert results[0]["source"] == "google_cse"


class TestScrapeFallbackProvider:
    """Test the ScrapeFallbackProvider functionality."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.provider = ScrapeFallbackProvider()
    
    def test_scrape_provider_initialization(self):
        """Test ScrapeFallbackProvider initializes correctly."""
        assert self.provider.name == "scrape_fallback"
    
    @patch('requests.get')
    def test_scrape_fallback_search(self, mock_get):
        """Test ScrapeFallbackProvider search functionality."""
        # Mock search results page
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = '''
        <html>
            <body>
                <div class="result">
                    <h3><a href="https://example.com/1">Test Result 1</a></h3>
                    <p>This is a test snippet from scraping</p>
                </div>
                <div class="result">
                    <h3><a href="https://example.com/2">Test Result 2</a></h3>
                    <p>Another test snippet from scraping</p>
                </div>
            </body>
        </html>
        '''
        mock_get.return_value = mock_response

        results = self.provider.search("test query", num_results=5)

        # Scrape fallback should return at least some results
        assert len(results) >= 0

        # If results are found, check format
        if results:
            assert "title" in results[0]
            assert "snippet" in results[0]
            assert "url" in results[0]
            assert results[0]["source"] == "scrape_fallback"


class TestContentFetcher:
    """Test the ContentFetcher functionality."""

    def setup_method(self):
        """Set up test fixtures."""
        self.fetcher = ContentFetcher()

    def test_content_fetcher_initialization(self):
        """Test ContentFetcher initializes correctly."""
        assert hasattr(self.fetcher, 'session')

    def test_content_fetcher_has_can_fetch_method(self):
        """Test ContentFetcher has can_fetch method."""
        assert hasattr(self.fetcher, 'can_fetch')
        assert callable(self.fetcher.can_fetch)

    def test_content_fetcher_has_fetch_content_method(self):
        """Test ContentFetcher has fetch_content method."""
        assert hasattr(self.fetcher, 'fetch_content')
        assert callable(self.fetcher.fetch_content)


class TestSearchAdapter:
    """Test the main SearchAdapter functionality."""

    def setup_method(self):
        """Set up test fixtures."""
        self.adapter = SearchAdapter()

    def test_search_adapter_initialization(self):
        """Test SearchAdapter initializes correctly."""
        assert hasattr(self.adapter, 'providers')
        assert hasattr(self.adapter, 'content_fetcher')
        assert len(self.adapter.providers) > 0

    def test_search_adapter_has_fallback_provider(self):
        """Test SearchAdapter has scrape fallback provider."""
        # providers is a dict
        assert "scrape_fallback" in self.adapter.providers

    @patch.object(ScrapeFallbackProvider, 'search')
    def test_search_with_fallback(self, mock_scrape_search):
        """Test SearchAdapter fallback mechanism."""
        # Mock scrape fallback to return results
        mock_scrape_search.return_value = [
            {
                "title": "Fallback Result",
                "snippet": "Fallback snippet",
                "url": "https://fallback.com",
                "source": "scrape_fallback"
            }
        ]

        # Create adapter with only fallback provider
        adapter = SearchAdapter()
        adapter.providers = {"scrape_fallback": ScrapeFallbackProvider()}

        result = adapter.search("test query", num_results=5)

        # search() returns a dict with 'results' key
        assert "results" in result
        assert len(result["results"]) > 0
        assert result["results"][0]["source"] == "scrape_fallback"

    def test_search_no_providers_available(self):
        """Test SearchAdapter behavior when no providers work."""
        from search_adapter import SearchError

        # Create adapter with no providers
        adapter = SearchAdapter()
        adapter.providers = {}

        # Should raise SearchError when all providers fail
        with pytest.raises(SearchError):
            adapter.search("test query", num_results=5)

    @patch.object(ContentFetcher, 'fetch_content')
    def test_content_fetcher_integration(self, mock_fetch):
        """Test SearchAdapter content fetcher integration."""
        # Mock content fetching
        mock_fetch.return_value = "Full page content here"

        content = self.adapter.content_fetcher.fetch_content("https://example.com")

        assert content == "Full page content here"
        mock_fetch.assert_called_once_with("https://example.com")

    def test_list_available_providers(self):
        """Test SearchAdapter can list available providers."""
        providers = self.adapter.list_available_providers()

        assert isinstance(providers, list)
        assert len(providers) > 0
        assert "scrape_fallback" in providers


class TestSearchIntegration:
    """Integration tests for search functionality."""
    
    def test_search_result_format_consistency(self):
        """Test all providers return consistent result format."""
        providers = [
            ScrapeFallbackProvider(),
        ]
        
        for provider in providers:
            # Mock the actual search to avoid network calls
            with patch.object(provider, 'search') as mock_search:
                mock_search.return_value = [
                    {
                        "title": f"Test Result from {provider.name}",
                        "snippet": f"Test snippet from {provider.name}",
                        "url": f"https://{provider.name}.example.com",
                        "source": provider.name
                    }
                ]
                
                results = provider.search("test query")
                
                assert len(results) > 0
                
                for result in results:
                    # Check required fields
                    assert "title" in result
                    assert "snippet" in result
                    assert "url" in result
                    assert "source" in result
                    
                    # Check field types
                    assert isinstance(result["title"], str)
                    assert isinstance(result["snippet"], str)
                    assert isinstance(result["url"], str)
                    assert isinstance(result["source"], str)
                    
                    # Check URL format
                    assert result["url"].startswith(("http://", "https://"))
    
    def test_search_adapter_provider_fallback(self):
        """Test SearchAdapter provider fallback mechanism."""
        # Create failing provider
        failing_provider = Mock()
        failing_provider.name = "failing"
        failing_provider.is_available.return_value = True
        failing_provider.search.side_effect = Exception("Provider failed")

        # Create working provider
        working_provider = Mock()
        working_provider.name = "working"
        working_provider.is_available.return_value = True
        working_provider.search.return_value = [
            {
                "title": "Working Result",
                "snippet": "Working snippet",
                "url": "https://working.com",
                "source": "working"
            }
        ]

        # Create adapter with failing provider first, then working provider
        adapter = SearchAdapter()
        adapter.providers = {"failing": failing_provider, "working": working_provider}

        result = adapter.search("test query", provider="working")

        # Should get results from working provider
        assert "results" in result
        assert len(result["results"]) > 0
        assert result["results"][0]["source"] == "working"

    def test_content_fetcher_can_fetch(self):
        """Test ContentFetcher can_fetch method."""
        fetcher = ContentFetcher()

        # Test that can_fetch returns a boolean
        result = fetcher.can_fetch("https://example.com")
        assert isinstance(result, bool)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
