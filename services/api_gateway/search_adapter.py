"""
Web search adapter with pluggable providers and fallback support.
Supports SerpAPI, Bing, Google Custom Search, and DOM scraping fallback.
"""

import os
import time
import logging
import urllib.robotparser
from typing import Dict, List, Optional, Any
from urllib.parse import urljoin, urlparse
from datetime import datetime

import requests
from bs4 import BeautifulSoup
from tenacity import retry, stop_after_attempt, wait_exponential

logger = logging.getLogger(__name__)

DEFAULT_SEARCH_TIMEOUT = int(os.getenv("SEARCH_TIMEOUT", "10"))
DEFAULT_NUM_RESULTS = int(os.getenv("WEB_SEARCH_RESULTS", "5"))


class SearchError(Exception):
    """Base exception for search-related errors."""
    pass


class BaseSearchProvider:
    """Base class for search providers."""
    
    def __init__(self, name: str):
        self.name = name
        self.timeout = DEFAULT_SEARCH_TIMEOUT
    
    def search(self, query: str, num_results: int = DEFAULT_NUM_RESULTS) -> List[Dict[str, Any]]:
        """Search for query and return normalized results."""
        raise NotImplementedError
    
    def is_available(self) -> bool:
        """Check if this provider is available/configured."""
        return True


class SerpAPIProvider(BaseSearchProvider):
    """SerpAPI Google Search provider."""
    
    def __init__(self):
        super().__init__("serpapi")
        self.api_key = os.getenv("SERPAPI_KEY")
        self.base_url = "https://serpapi.com/search"
    
    def is_available(self) -> bool:
        return bool(self.api_key)
    
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=8))
    def search(self, query: str, num_results: int = DEFAULT_NUM_RESULTS) -> List[Dict[str, Any]]:
        if not self.api_key:
            raise SearchError("SerpAPI key not configured")
        
        params = {
            "q": query,
            "api_key": self.api_key,
            "engine": "google",
            "num": num_results,
            "format": "json"
        }
        
        try:
            response = requests.get(self.base_url, params=params, timeout=self.timeout)
            response.raise_for_status()
            
            data = response.json()
            results = []
            
            for item in data.get("organic_results", []):
                results.append({
                    "title": item.get("title", ""),
                    "snippet": item.get("snippet", ""),
                    "url": item.get("link", ""),
                    "source": self.name,
                    "content": "",  # Will be fetched separately if needed
                    "fetched_at": datetime.now().isoformat()
                })
            
            return results
            
        except Exception as e:
            logger.error(f"SerpAPI search failed: {e}")
            raise SearchError(f"SerpAPI search failed: {e}")


class BingSearchProvider(BaseSearchProvider):
    """Bing Web Search API provider."""
    
    def __init__(self):
        super().__init__("bing")
        self.api_key = os.getenv("BING_SUBSCRIPTION_KEY")
        self.base_url = "https://api.bing.microsoft.com/v7.0/search"
    
    def is_available(self) -> bool:
        return bool(self.api_key)
    
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=8))
    def search(self, query: str, num_results: int = DEFAULT_NUM_RESULTS) -> List[Dict[str, Any]]:
        if not self.api_key:
            raise SearchError("Bing API key not configured")
        
        headers = {
            "Ocp-Apim-Subscription-Key": self.api_key
        }
        
        params = {
            "q": query,
            "count": num_results,
            "responseFilter": "Webpages"
        }
        
        try:
            response = requests.get(self.base_url, headers=headers, params=params, 
                                  timeout=self.timeout)
            response.raise_for_status()
            
            data = response.json()
            results = []
            
            for item in data.get("webPages", {}).get("value", []):
                results.append({
                    "title": item.get("name", ""),
                    "snippet": item.get("snippet", ""),
                    "url": item.get("url", ""),
                    "source": self.name,
                    "content": "",
                    "fetched_at": datetime.now().isoformat()
                })
            
            return results
            
        except Exception as e:
            logger.error(f"Bing search failed: {e}")
            raise SearchError(f"Bing search failed: {e}")


class GoogleCSEProvider(BaseSearchProvider):
    """Google Custom Search Engine provider."""
    
    def __init__(self):
        super().__init__("google_cse")
        self.api_key = os.getenv("GOOGLE_CSE_KEY")
        self.cse_id = os.getenv("GOOGLE_CSE_ID")
        self.base_url = "https://www.googleapis.com/customsearch/v1"
    
    def is_available(self) -> bool:
        return bool(self.api_key and self.cse_id)
    
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=8))
    def search(self, query: str, num_results: int = DEFAULT_NUM_RESULTS) -> List[Dict[str, Any]]:
        if not (self.api_key and self.cse_id):
            raise SearchError("Google CSE key or ID not configured")
        
        params = {
            "key": self.api_key,
            "cx": self.cse_id,
            "q": query,
            "num": min(num_results, 10)  # Google CSE max is 10
        }
        
        try:
            response = requests.get(self.base_url, params=params, timeout=self.timeout)
            response.raise_for_status()
            
            data = response.json()
            results = []
            
            for item in data.get("items", []):
                results.append({
                    "title": item.get("title", ""),
                    "snippet": item.get("snippet", ""),
                    "url": item.get("link", ""),
                    "source": self.name,
                    "content": "",
                    "fetched_at": datetime.now().isoformat()
                })
            
            return results
            
        except Exception as e:
            logger.error(f"Google CSE search failed: {e}")
            raise SearchError(f"Google CSE search failed: {e}")


class ScrapeFallbackProvider(BaseSearchProvider):
    """Fallback provider that scrapes search engines directly."""
    
    def __init__(self):
        super().__init__("scrape_fallback")
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        })
    
    def search(self, query: str, num_results: int = DEFAULT_NUM_RESULTS) -> List[Dict[str, Any]]:
        """Scrape DuckDuckGo as a fallback search engine."""
        try:
            # Use DuckDuckGo as it's more scraping-friendly
            url = "https://duckduckgo.com/html/"
            params = {"q": query}
            
            response = self.session.get(url, params=params, timeout=self.timeout)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            results = []
            
            # Parse DuckDuckGo results
            for result_div in soup.find_all('div', class_='result')[:num_results]:
                title_elem = result_div.find('a', class_='result__a')
                snippet_elem = result_div.find('a', class_='result__snippet')
                
                if title_elem:
                    results.append({
                        "title": title_elem.get_text(strip=True),
                        "snippet": snippet_elem.get_text(strip=True) if snippet_elem else "",
                        "url": title_elem.get('href', ''),
                        "source": self.name,
                        "content": "",
                        "fetched_at": datetime.now().isoformat()
                    })
            
            return results
            
        except Exception as e:
            logger.error(f"Scrape fallback search failed: {e}")
            raise SearchError(f"Scrape fallback search failed: {e}")


class ContentFetcher:
    """Utility class for fetching and parsing web page content."""
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "ContextForge/1.0 (Educational Research Tool)"
        })
    
    def can_fetch(self, url: str) -> bool:
        """Check robots.txt to see if we can fetch this URL."""
        try:
            parsed_url = urlparse(url)
            robots_url = f"{parsed_url.scheme}://{parsed_url.netloc}/robots.txt"
            
            rp = urllib.robotparser.RobotFileParser()
            rp.set_url(robots_url)
            rp.read()
            
            return rp.can_fetch("*", url)
        except Exception:
            # If we can't check robots.txt, be conservative and allow
            return True
    
    def fetch_content(self, url: str, max_length: int = 5000) -> str:
        """Fetch and extract text content from a web page."""
        if not self.can_fetch(url):
            logger.warning(f"Robots.txt disallows fetching {url}")
            return ""
        
        try:
            response = self.session.get(url, timeout=10)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Remove script and style elements
            for script in soup(["script", "style"]):
                script.decompose()
            
            # Get text content
            text = soup.get_text()
            
            # Clean up whitespace
            lines = (line.strip() for line in text.splitlines())
            chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
            text = ' '.join(chunk for chunk in chunks if chunk)
            
            # Truncate if too long
            if len(text) > max_length:
                text = text[:max_length] + "..."
            
            return text
            
        except Exception as e:
            logger.error(f"Failed to fetch content from {url}: {e}")
            return ""


class SearchAdapter:
    """Main search adapter with provider priority and fallback support."""
    
    def __init__(self):
        self.providers = {}
        self.content_fetcher = ContentFetcher()
        self._initialize_providers()
    
    def _initialize_providers(self):
        """Initialize all available search providers."""
        provider_classes = {
            "serpapi": SerpAPIProvider,
            "bing": BingSearchProvider,
            "google_cse": GoogleCSEProvider,
            "scrape_fallback": ScrapeFallbackProvider
        }
        
        for name, provider_class in provider_classes.items():
            try:
                self.providers[name] = provider_class()
                logger.info(f"Initialized {name} search provider")
            except Exception as e:
                logger.warning(f"Failed to initialize {name} provider: {e}")
    
    def search(self, query: str, provider: Optional[str] = None, 
              num_results: int = DEFAULT_NUM_RESULTS, 
              fetch_content: bool = False) -> Dict[str, Any]:
        """Search using specified provider or try all available providers."""
        
        if provider and provider in self.providers:
            providers_to_try = [provider]
        else:
            # Try providers in order of preference
            providers_to_try = ["serpapi", "bing", "google_cse", "scrape_fallback"]
        
        last_error = None
        
        for provider_name in providers_to_try:
            if provider_name not in self.providers:
                continue
            
            provider_obj = self.providers[provider_name]
            
            if not provider_obj.is_available():
                logger.info(f"Provider {provider_name} not available, trying next")
                continue
            
            try:
                logger.info(f"Searching with {provider_name}")
                results = provider_obj.search(query, num_results)
                
                # Optionally fetch full content for each result
                if fetch_content:
                    for result in results:
                        if result["url"]:
                            content = self.content_fetcher.fetch_content(result["url"])
                            result["content"] = content
                
                return {
                    "query": query,
                    "provider": provider_name,
                    "num_results": len(results),
                    "results": results,
                    "timestamp": datetime.now().isoformat()
                }
                
            except Exception as e:
                last_error = e
                logger.warning(f"Provider {provider_name} failed: {e}")
                continue
        
        # If all providers failed
        raise SearchError(f"All search providers failed. Last error: {last_error}")
    
    def list_available_providers(self) -> List[str]:
        """List currently available search providers."""
        return [name for name, provider in self.providers.items() 
                if provider.is_available()]
