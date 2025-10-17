"""
Connector Service - FastAPI application for filesystem repository ingestion.
"""

import os
import logging
import fnmatch
from typing import Dict, List, Optional, Any
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
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
    title="ContextForge Connector Service",
    description="Filesystem connector for repository ingestion",
    version="1.0.0"
)

# Default patterns
DEFAULT_INCLUDE_PATTERNS = [
    "*.py", "*.js", "*.jsx", "*.ts", "*.tsx", "*.md", "*.markdown",
    "*.txt", "*.json", "*.yaml", "*.yml", "*.toml", "*.cfg", "*.ini"
]

DEFAULT_EXCLUDE_PATTERNS = [
    "*.pyc", "*.pyo", "*.pyd", "__pycache__/*", "*.so", "*.dylib", "*.dll",
    ".git/*", ".svn/*", ".hg/*", ".bzr/*",
    "node_modules/*", "venv/*", "env/*", ".env/*", "virtualenv/*",
    "*.log", "*.tmp", "*.temp", "*.cache",
    ".DS_Store", "Thumbs.db",
    "*.min.js", "*.min.css",
    "dist/*", "build/*", "target/*", "out/*",
    "*.env*", "*.key", "*.pem", "*secret*", "*password*",
    "*.zip", "*.tar", "*.gz", "*.rar", "*.7z",
    "*.jpg", "*.jpeg", "*.png", "*.gif", "*.bmp", "*.svg", "*.ico",
    "*.mp3", "*.mp4", "*.avi", "*.mov", "*.wmv", "*.flv",
    "*.pdf", "*.doc", "*.docx", "*.xls", "*.xlsx", "*.ppt", "*.pptx"
]

# Configuration
MAX_FILE_SIZE = int(os.getenv("MAX_FILE_SIZE", "1048576"))  # 1MB default
MAX_FILES = int(os.getenv("MAX_FILES", "10000"))


# Pydantic models
class ConnectRequest(BaseModel):
    path: str
    recursive: bool = True
    file_patterns: Optional[List[str]] = None
    exclude_patterns: Optional[List[str]] = None
    max_file_size: int = MAX_FILE_SIZE
    max_files: int = MAX_FILES


class FileInfo(BaseModel):
    path: str
    content: str
    size: int
    modified_time: str
    encoding: str = "utf-8"


# Health check
@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "service": "connector",
        "timestamp": datetime.now().isoformat()
    }


# Main connection endpoint
@app.post("/connect")
async def connect_repository(request: ConnectRequest):
    """Connect to a filesystem repository and extract file contents."""
    try:
        logger.info("Connecting to repository", path=request.path)
        
        # Validate path
        repo_path = Path(request.path)
        if not repo_path.exists():
            raise HTTPException(status_code=404, detail=f"Path not found: {request.path}")
        
        if not repo_path.is_dir():
            raise HTTPException(status_code=400, detail=f"Path is not a directory: {request.path}")
        
        # Set up patterns
        include_patterns = request.file_patterns or DEFAULT_INCLUDE_PATTERNS
        exclude_patterns = request.exclude_patterns or DEFAULT_EXCLUDE_PATTERNS
        
        # Scan files
        files = []
        stats = {
            "total_files_found": 0,
            "files_processed": 0,
            "files_skipped": 0,
            "total_size": 0,
            "errors": []
        }
        
        for file_path in _scan_directory(repo_path, request.recursive):
            stats["total_files_found"] += 1
            
            # Check if we've hit the file limit
            if len(files) >= request.max_files:
                logger.warning("File limit reached", max_files=request.max_files)
                break
            
            try:
                # Check patterns
                relative_path = str(file_path.relative_to(repo_path))
                
                if not _matches_patterns(relative_path, include_patterns):
                    stats["files_skipped"] += 1
                    continue
                
                if _matches_patterns(relative_path, exclude_patterns):
                    stats["files_skipped"] += 1
                    continue
                
                # Check file size
                file_size = file_path.stat().st_size
                if file_size > request.max_file_size:
                    logger.warning("File too large", 
                                 file_path=str(file_path), 
                                 size=file_size,
                                 max_size=request.max_file_size)
                    stats["files_skipped"] += 1
                    continue
                
                # Read file content
                content, encoding = _read_file_content(file_path)
                if content is None:
                    stats["files_skipped"] += 1
                    continue
                
                # Create file info
                file_info = FileInfo(
                    path=str(file_path.relative_to(repo_path)),
                    content=content,
                    size=file_size,
                    modified_time=datetime.fromtimestamp(file_path.stat().st_mtime).isoformat(),
                    encoding=encoding
                )
                
                files.append(file_info.dict())
                stats["files_processed"] += 1
                stats["total_size"] += file_size
                
                logger.debug("File processed", 
                           file_path=relative_path,
                           size=file_size,
                           encoding=encoding)
                
            except Exception as e:
                error_msg = f"Error processing {file_path}: {str(e)}"
                logger.error("File processing error", 
                           file_path=str(file_path), 
                           error=str(e))
                stats["errors"].append(error_msg)
                stats["files_skipped"] += 1
        
        logger.info("Repository connection completed",
                   files_processed=stats["files_processed"],
                   files_skipped=stats["files_skipped"],
                   total_size=stats["total_size"])
        
        return {
            "repository_path": str(repo_path),
            "files": files,
            "stats": stats,
            "timestamp": datetime.now().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Repository connection failed", error=str(e))
        raise HTTPException(status_code=500, detail=f"Connection failed: {e}")


# File listing endpoint
@app.post("/list-files")
async def list_files(request: ConnectRequest):
    """List files in a repository without reading content."""
    try:
        logger.info("Listing files in repository", path=request.path)
        
        # Validate path
        repo_path = Path(request.path)
        if not repo_path.exists():
            raise HTTPException(status_code=404, detail=f"Path not found: {request.path}")
        
        if not repo_path.is_dir():
            raise HTTPException(status_code=400, detail=f"Path is not a directory: {request.path}")
        
        # Set up patterns
        include_patterns = request.file_patterns or DEFAULT_INCLUDE_PATTERNS
        exclude_patterns = request.exclude_patterns or DEFAULT_EXCLUDE_PATTERNS
        
        # Scan files
        file_list = []
        stats = {
            "total_files_found": 0,
            "files_matched": 0,
            "files_skipped": 0,
            "total_size": 0
        }
        
        for file_path in _scan_directory(repo_path, request.recursive):
            stats["total_files_found"] += 1
            
            try:
                relative_path = str(file_path.relative_to(repo_path))
                file_size = file_path.stat().st_size
                
                # Check patterns
                if not _matches_patterns(relative_path, include_patterns):
                    stats["files_skipped"] += 1
                    continue
                
                if _matches_patterns(relative_path, exclude_patterns):
                    stats["files_skipped"] += 1
                    continue
                
                # Check file size
                if file_size > request.max_file_size:
                    stats["files_skipped"] += 1
                    continue
                
                file_info = {
                    "path": relative_path,
                    "size": file_size,
                    "modified_time": datetime.fromtimestamp(file_path.stat().st_mtime).isoformat(),
                    "extension": file_path.suffix
                }
                
                file_list.append(file_info)
                stats["files_matched"] += 1
                stats["total_size"] += file_size
                
            except Exception as e:
                logger.error("Error processing file info", 
                           file_path=str(file_path), 
                           error=str(e))
                stats["files_skipped"] += 1
        
        return {
            "repository_path": str(repo_path),
            "files": file_list,
            "stats": stats,
            "timestamp": datetime.now().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("File listing failed", error=str(e))
        raise HTTPException(status_code=500, detail=f"File listing failed: {e}")


# Configuration endpoints
@app.get("/config")
async def get_config():
    """Get current connector configuration."""
    return {
        "max_file_size": MAX_FILE_SIZE,
        "max_files": MAX_FILES,
        "default_include_patterns": DEFAULT_INCLUDE_PATTERNS,
        "default_exclude_patterns": DEFAULT_EXCLUDE_PATTERNS
    }


@app.get("/patterns")
async def get_patterns():
    """Get default file patterns."""
    return {
        "include_patterns": DEFAULT_INCLUDE_PATTERNS,
        "exclude_patterns": DEFAULT_EXCLUDE_PATTERNS
    }


# Utility functions
def _scan_directory(path: Path, recursive: bool = True):
    """Scan directory for files."""
    if recursive:
        return path.rglob("*")
    else:
        return path.glob("*")


def _matches_patterns(file_path: str, patterns: List[str]) -> bool:
    """Check if file path matches any of the patterns."""
    for pattern in patterns:
        if fnmatch.fnmatch(file_path, pattern) or fnmatch.fnmatch(file_path.lower(), pattern.lower()):
            return True
    return False


def _read_file_content(file_path: Path) -> tuple[Optional[str], str]:
    """Read file content with encoding detection."""
    encodings = ['utf-8', 'utf-16', 'latin-1', 'cp1252']
    
    for encoding in encodings:
        try:
            with open(file_path, 'r', encoding=encoding) as f:
                content = f.read()
                return content, encoding
        except (UnicodeDecodeError, UnicodeError):
            continue
        except Exception as e:
            logger.error("Error reading file", 
                       file_path=str(file_path), 
                       encoding=encoding,
                       error=str(e))
            return None, encoding
    
    # If all encodings fail, try binary mode and decode as best effort
    try:
        with open(file_path, 'rb') as f:
            raw_content = f.read()
            content = raw_content.decode('utf-8', errors='replace')
            return content, 'utf-8-with-errors'
    except Exception as e:
        logger.error("Failed to read file in binary mode", 
                   file_path=str(file_path), 
                   error=str(e))
        return None, 'failed'


if __name__ == "__main__":
    import uvicorn
    
    port = int(os.getenv("PORT", "8002"))
    log_level = os.getenv("LOG_LEVEL", "INFO").lower()
    
    uvicorn.run(
        "app:app",
        host="0.0.0.0",
        port=port,
        log_level=log_level,
        reload=False
    )
