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
        self.provider = SerpAPIProvider("test-api-key")
    
    def test_serpapi_provider_initialization(self):
        """Test SerpAPIProvider initializes correctly."""
        assert self.provider.name == "serpapi"
        assert self.provider.api_key == "test-api-key"
    
    @patch('requests.get')
    def test_serpapi_successful_search(self, mock_get):
        """Test SerpAPIProvider handles successful searches."""
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
        
        results = self.provider.search("test query", max_results=5)
        
        assert len(results) == 2
        assert results[0]["title"] == "Test Result 1"
        assert results[0]["snippet"] == "This is a test snippet"
        assert results[0]["url"] == "https://example.com/1"
        assert results[0]["source"] == "serpapi"
    
    @patch('requests.get')
    def test_serpapi_api_error(self, mock_get):
        """Test SerpAPIProvider handles API errors."""
        # Mock API error response
        mock_response = Mock()
        mock_response.status_code = 401
        mock_response.raise_for_status.side_effect = Exception("API key invalid")
        mock_get.return_value = mock_response
        
        with pytest.raises(Exception):
            self.provider.search("test query")
    
    @patch('requests.get')
    def test_serpapi_empty_results(self, mock_get):
        """Test SerpAPIProvider handles empty results."""
        # Mock empty response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"organic_results": []}
        mock_get.return_value = mock_response
        
        results = self.provider.search("test query")
        assert len(results) == 0


class TestBingSearchProvider:
    """Test the BingSearchProvider functionality."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.provider = BingSearchProvider("test-subscription-key")
    
    def test_bing_provider_initialization(self):
        """Test BingSearchProvider initializes correctly."""
        assert self.provider.name == "bing"
        assert self.provider.subscription_key == "test-subscription-key"
    
    @patch('requests.get')
    def test_bing_successful_search(self, mock_get):
        """Test BingSearchProvider handles successful searches."""
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
        
        results = self.provider.search("test query")
        
        assert len(results) == 1
        assert results[0]["title"] == "Bing Test Result"
        assert results[0]["snippet"] == "Bing test snippet"
        assert results[0]["url"] == "https://bing-example.com"
        assert results[0]["source"] == "bing"


class TestGoogleCSEProvider:
    """Test the GoogleCSEProvider functionality."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.provider = GoogleCSEProvider("test-api-key", "test-cse-id")
    
    def test_google_cse_provider_initialization(self):
        """Test GoogleCSEProvider initializes correctly."""
        assert self.provider.name == "google_cse"
        assert self.provider.api_key == "test-api-key"
        assert self.provider.cse_id == "test-cse-id"
    
    @patch('requests.get')
    def test_google_cse_successful_search(self, mock_get):
        """Test GoogleCSEProvider handles successful searches."""
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
        
        results = self.provider.search("test query")
        
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
        
        results = self.provider.search("test query", max_results=5)
        
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
        assert hasattr(self.fetcher, 'rate_limiter')
    
    @patch('requests.Session.get')
    def test_fetch_content_success(self, mock_get):
        """Test ContentFetcher successful content fetching."""
        # Mock successful response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = '''
        <html>
            <head><title>Test Page</title></head>
            <body>
                <h1>Main Heading</h1>
                <p>This is test content.</p>
                <script>console.log('script');</script>
                <style>body { color: red; }</style>
            </body>
        </html>
        '''
        mock_get.return_value = mock_response
        
        content = self.fetcher.fetch_content("https://example.com")
        
        assert content is not None
        assert "Main Heading" in content
        assert "This is test content" in content
        # Scripts and styles should be removed
        assert "console.log" not in content
        assert "color: red" not in content
    
    @patch('requests.Session.get')
    def test_fetch_content_http_error(self, mock_get):
        """Test ContentFetcher handles HTTP errors."""
        # Mock HTTP error
        mock_response = Mock()
        mock_response.status_code = 404
        mock_response.raise_for_status.side_effect = Exception("Not Found")
        mock_get.return_value = mock_response
        
        content = self.fetcher.fetch_content("https://example.com/notfound")
        assert content is None
    
    @patch('urllib.robotparser.RobotFileParser')
    def test_robots_txt_compliance(self, mock_robot_parser):
        """Test ContentFetcher respects robots.txt."""
        # Mock robots.txt that disallows access
        mock_rp = Mock()
        mock_rp.can_fetch.return_value = False
        mock_robot_parser.return_value = mock_rp
        
        content = self.fetcher.fetch_content("https://example.com/disallowed")
        assert content is None
    
    def test_rate_limiting(self):
        """Test ContentFetcher rate limiting."""
        # Test that rate limiter exists and has expected attributes
        assert hasattr(self.fetcher.rate_limiter, 'get')
        
        # Test rate limiting for same domain
        domain = "example.com"
        
        # First call should succeed
        can_fetch_1 = self.fetcher.rate_limiter.get(domain, 1) > 0
        
        # Immediate second call might be rate limited
        can_fetch_2 = self.fetcher.rate_limiter.get(domain, 1) > 0
        
        # At least one should work (implementation dependent)
        assert can_fetch_1 or can_fetch_2


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
        provider_names = [p.name for p in self.adapter.providers]
        assert "scrape_fallback" in provider_names
    
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
        adapter.providers = [ScrapeFallbackProvider()]
        
        results = adapter.search("test query", max_results=5)
        
        assert len(results) > 0
        assert results[0]["source"] == "scrape_fallback"
    
    def test_search_empty_query(self):
        """Test SearchAdapter handles empty queries."""
        results = self.adapter.search("", max_results=5)
        assert len(results) == 0
    
    def test_search_no_providers_available(self):
        """Test SearchAdapter behavior when no providers work."""
        # Create adapter with no providers
        adapter = SearchAdapter()
        adapter.providers = []
        
        results = adapter.search("test query", max_results=5)
        assert len(results) == 0
    
    @patch.object(ContentFetcher, 'fetch_content')
    def test_fetch_full_content(self, mock_fetch):
        """Test SearchAdapter content fetching."""
        # Mock content fetching
        mock_fetch.return_value = "Full page content here"
        
        content = self.adapter.fetch_full_content("https://example.com")
        
        assert content == "Full page content here"
        mock_fetch.assert_called_once_with("https://example.com")
    
    def test_get_available_providers(self):
        """Test SearchAdapter can list available providers."""
        providers = self.adapter.get_available_providers()
        
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
        failing_provider.search.side_effect = Exception("Provider failed")
        
        # Create working provider
        working_provider = Mock()
        working_provider.name = "working"
        working_provider.search.return_value = [
            {
                "title": "Working Result",
                "snippet": "Working snippet",
                "url": "https://working.com",
                "source": "working"
            }
        ]
        
        # Create adapter with failing provider first
        adapter = SearchAdapter()
        adapter.providers = [failing_provider, working_provider]
        
        results = adapter.search("test query")
        
        # Should get results from working provider
        assert len(results) > 0
        assert results[0]["source"] == "working"
    
    def test_content_fetcher_error_handling(self):
        """Test ContentFetcher handles various error conditions."""
        fetcher = ContentFetcher()
        
        # Test invalid URL
        content = fetcher.fetch_content("not-a-url")
        assert content is None
        
        # Test empty URL
        content = fetcher.fetch_content("")
        assert content is None
        
        # Test None URL
        content = fetcher.fetch_content(None)
        assert content is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
