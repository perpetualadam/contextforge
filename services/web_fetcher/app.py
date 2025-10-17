"""
Web Fetcher Service - FastAPI application for web content fetching with rate limiting.
"""

import os
import time
import hashlib
import logging
import urllib.robotparser
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from urllib.parse import urlparse, urljoin
from pathlib import Path

from fastapi import FastAPI, HTTPException, BackgroundTasks
from pydantic import BaseModel
import requests
from bs4 import BeautifulSoup
import structlog

# Configure structured logging
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        structlog.processors.JSONRenderer()
    ],
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    wrapper_class=structlog.stdlib.BoundLogger,
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger()

# Initialize FastAPI app
app = FastAPI(
    title="ContextForge Web Fetcher Service",
    description="Web content fetching with rate limiting and robots.txt compliance",
    version="1.0.0"
)

# Configuration
CACHE_DIR = os.getenv("CACHE_DIR", "/app/cache")
REQUEST_TIMEOUT = int(os.getenv("REQUEST_TIMEOUT", "10"))
RATE_LIMIT_DELAY = float(os.getenv("RATE_LIMIT_DELAY", "1.0"))  # seconds between requests
MAX_CONTENT_LENGTH = int(os.getenv("MAX_CONTENT_LENGTH", "1048576"))  # 1MB
USER_AGENT = os.getenv("USER_AGENT", "ContextForge/1.0 (Educational Research Tool)")

# Rate limiting storage (in production, use Redis or similar)
rate_limit_store = {}


# Pydantic models
class FetchRequest(BaseModel):
    url: str
    respect_robots: bool = True
    use_cache: bool = True
    max_content_length: int = MAX_CONTENT_LENGTH


class FetchBatchRequest(BaseModel):
    urls: List[str]
    respect_robots: bool = True
    use_cache: bool = True
    max_content_length: int = MAX_CONTENT_LENGTH


class CachedContent(BaseModel):
    url: str
    content: str
    title: str
    fetched_at: str
    content_type: str
    status_code: int


# Initialize cache directory
Path(CACHE_DIR).mkdir(parents=True, exist_ok=True)


# Health check
@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "service": "web_fetcher",
        "cache_dir": CACHE_DIR,
        "timestamp": datetime.now().isoformat()
    }


# Main fetch endpoint
@app.post("/fetch")
async def fetch_url(request: FetchRequest):
    """Fetch content from a single URL."""
    try:
        logger.info("Fetching URL", url=request.url)
        
        # Check cache first
        if request.use_cache:
            cached_content = _get_cached_content(request.url)
            if cached_content:
                logger.info("Returning cached content", url=request.url)
                return cached_content
        
        # Check robots.txt
        if request.respect_robots and not _can_fetch_url(request.url):
            raise HTTPException(status_code=403, 
                              detail=f"Robots.txt disallows fetching {request.url}")
        
        # Rate limiting
        _apply_rate_limit(request.url)
        
        # Fetch content
        content_data = _fetch_url_content(request.url, request.max_content_length)
        
        # Cache the result
        if request.use_cache:
            _cache_content(request.url, content_data)
        
        logger.info("URL fetched successfully", 
                   url=request.url,
                   content_length=len(content_data["content"]))
        
        return content_data
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("URL fetch failed", url=request.url, error=str(e))
        raise HTTPException(status_code=500, detail=f"Fetch failed: {e}")


# Batch fetch endpoint
@app.post("/fetch-batch")
async def fetch_batch(request: FetchBatchRequest, background_tasks: BackgroundTasks):
    """Fetch content from multiple URLs."""
    try:
        logger.info("Fetching batch URLs", num_urls=len(request.urls))
        
        results = []
        errors = []
        
        for url in request.urls:
            try:
                # Check cache first
                if request.use_cache:
                    cached_content = _get_cached_content(url)
                    if cached_content:
                        results.append(cached_content)
                        continue
                
                # Check robots.txt
                if request.respect_robots and not _can_fetch_url(url):
                    errors.append(f"Robots.txt disallows fetching {url}")
                    continue
                
                # Rate limiting
                _apply_rate_limit(url)
                
                # Fetch content
                content_data = _fetch_url_content(url, request.max_content_length)
                results.append(content_data)
                
                # Cache the result
                if request.use_cache:
                    background_tasks.add_task(_cache_content, url, content_data)
                
            except Exception as e:
                error_msg = f"Error fetching {url}: {str(e)}"
                logger.error("Batch fetch error", url=url, error=str(e))
                errors.append(error_msg)
        
        logger.info("Batch fetch completed", 
                   successful=len(results),
                   errors=len(errors))
        
        return {
            "results": results,
            "errors": errors,
            "stats": {
                "total_requested": len(request.urls),
                "successful": len(results),
                "failed": len(errors)
            },
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error("Batch fetch failed", error=str(e))
        raise HTTPException(status_code=500, detail=f"Batch fetch failed: {e}")


# Cache management endpoints
@app.get("/cache/stats")
async def get_cache_stats():
    """Get cache statistics."""
    try:
        cache_path = Path(CACHE_DIR)
        cache_files = list(cache_path.glob("*.json"))
        
        total_size = sum(f.stat().st_size for f in cache_files)
        
        return {
            "cache_dir": CACHE_DIR,
            "cached_items": len(cache_files),
            "total_size_bytes": total_size,
            "total_size_mb": round(total_size / (1024 * 1024), 2)
        }
    except Exception as e:
        logger.error("Failed to get cache stats", error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to get cache stats: {e}")


@app.delete("/cache/clear")
async def clear_cache():
    """Clear the entire cache."""
    try:
        cache_path = Path(CACHE_DIR)
        cache_files = list(cache_path.glob("*.json"))
        
        for cache_file in cache_files:
            cache_file.unlink()
        
        logger.info("Cache cleared", files_deleted=len(cache_files))
        
        return {
            "message": "Cache cleared successfully",
            "files_deleted": len(cache_files)
        }
    except Exception as e:
        logger.error("Failed to clear cache", error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to clear cache: {e}")


@app.delete("/cache/url")
async def delete_cached_url(url: str):
    """Delete a specific URL from cache."""
    try:
        cache_key = _get_cache_key(url)
        cache_file = Path(CACHE_DIR) / f"{cache_key}.json"
        
        if cache_file.exists():
            cache_file.unlink()
            return {"message": f"Cached content for {url} deleted"}
        else:
            return {"message": f"No cached content found for {url}"}
            
    except Exception as e:
        logger.error("Failed to delete cached URL", url=url, error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to delete cached URL: {e}")


# Configuration endpoint
@app.get("/config")
async def get_config():
    """Get current web fetcher configuration."""
    return {
        "cache_dir": CACHE_DIR,
        "request_timeout": REQUEST_TIMEOUT,
        "rate_limit_delay": RATE_LIMIT_DELAY,
        "max_content_length": MAX_CONTENT_LENGTH,
        "user_agent": USER_AGENT
    }


# Utility functions
def _get_cache_key(url: str) -> str:
    """Generate cache key for URL."""
    return hashlib.md5(url.encode('utf-8')).hexdigest()


def _get_cached_content(url: str) -> Optional[Dict[str, Any]]:
    """Get cached content for URL."""
    try:
        cache_key = _get_cache_key(url)
        cache_file = Path(CACHE_DIR) / f"{cache_key}.json"
        
        if cache_file.exists():
            import json
            with open(cache_file, 'r', encoding='utf-8') as f:
                cached_data = json.load(f)
            
            # Check if cache is still valid (24 hours)
            fetched_at = datetime.fromisoformat(cached_data["fetched_at"])
            if datetime.now() - fetched_at < timedelta(hours=24):
                return cached_data
            else:
                # Cache expired, delete it
                cache_file.unlink()
                
    except Exception as e:
        logger.error("Error reading cache", url=url, error=str(e))
    
    return None


def _cache_content(url: str, content_data: Dict[str, Any]):
    """Cache content for URL."""
    try:
        cache_key = _get_cache_key(url)
        cache_file = Path(CACHE_DIR) / f"{cache_key}.json"
        
        import json
        with open(cache_file, 'w', encoding='utf-8') as f:
            json.dump(content_data, f, ensure_ascii=False, indent=2)
            
    except Exception as e:
        logger.error("Error caching content", url=url, error=str(e))


def _can_fetch_url(url: str) -> bool:
    """Check if URL can be fetched according to robots.txt."""
    try:
        parsed_url = urlparse(url)
        robots_url = f"{parsed_url.scheme}://{parsed_url.netloc}/robots.txt"
        
        rp = urllib.robotparser.RobotFileParser()
        rp.set_url(robots_url)
        rp.read()
        
        return rp.can_fetch(USER_AGENT, url)
    except Exception:
        # If we can't check robots.txt, be conservative and allow
        return True


def _apply_rate_limit(url: str):
    """Apply rate limiting per domain."""
    parsed_url = urlparse(url)
    domain = parsed_url.netloc
    
    current_time = time.time()
    
    if domain in rate_limit_store:
        last_request_time = rate_limit_store[domain]
        time_since_last = current_time - last_request_time
        
        if time_since_last < RATE_LIMIT_DELAY:
            sleep_time = RATE_LIMIT_DELAY - time_since_last
            time.sleep(sleep_time)
    
    rate_limit_store[domain] = time.time()


def _fetch_url_content(url: str, max_content_length: int) -> Dict[str, Any]:
    """Fetch and parse content from URL."""
    session = requests.Session()
    session.headers.update({
        "User-Agent": USER_AGENT
    })
    
    try:
        response = session.get(url, timeout=REQUEST_TIMEOUT, stream=True)
        response.raise_for_status()
        
        # Check content length
        content_length = response.headers.get('content-length')
        if content_length and int(content_length) > max_content_length:
            raise ValueError(f"Content too large: {content_length} bytes")
        
        # Read content with size limit
        content = b""
        for chunk in response.iter_content(chunk_size=8192):
            content += chunk
            if len(content) > max_content_length:
                raise ValueError(f"Content too large: {len(content)} bytes")
        
        # Parse content
        soup = BeautifulSoup(content, 'html.parser')
        
        # Remove script and style elements
        for script in soup(["script", "style"]):
            script.decompose()
        
        # Extract title
        title = ""
        title_tag = soup.find('title')
        if title_tag:
            title = title_tag.get_text(strip=True)
        
        # Extract text content
        text_content = soup.get_text()
        
        # Clean up whitespace
        lines = (line.strip() for line in text_content.splitlines())
        chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
        clean_text = ' '.join(chunk for chunk in chunks if chunk)
        
        return {
            "url": url,
            "content": clean_text,
            "title": title,
            "fetched_at": datetime.now().isoformat(),
            "content_type": response.headers.get('content-type', 'unknown'),
            "status_code": response.status_code,
            "content_length": len(clean_text)
        }
        
    except Exception as e:
        logger.error("Error fetching URL content", url=url, error=str(e))
        raise


if __name__ == "__main__":
    import uvicorn
    
    port = int(os.getenv("PORT", "8004"))
    log_level = os.getenv("LOG_LEVEL", "INFO").lower()
    
    uvicorn.run(
        "app:app",
        host="0.0.0.0",
        port=port,
        log_level=log_level,
        reload=False
    )
