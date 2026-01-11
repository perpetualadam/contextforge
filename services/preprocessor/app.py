"""
Preprocessor Service - FastAPI application for language-aware text chunking.

Enhanced features:
- Smart chunking with 512-1024 token range (optimal for embeddings)
- 50-100 token overlap for context preservation
- Rich metadata: function names, class names, module context
- Content type tagging: tests, configs, documentation
- Token-aware chunking for better embedding quality
"""

import os
import sys
import logging
import hashlib
import re
from typing import Dict, List, Any, Optional
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
import structlog

# Add parent directory to path for services imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from .lang_chunkers import ChunkerFactory

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
    title="ContextForge Preprocessor Service",
    description="Language-aware text chunking and preprocessing service with smart chunking",
    version="2.0.0"
)

# Try to use unified config, fallback to env vars
try:
    from services.config import get_config
    _config = get_config()
    CONFIG_AVAILABLE = True

    # Configuration from unified config
    MIN_CHUNK_SIZE = _config.indexing.min_chunk_size
    MAX_CHUNK_SIZE = _config.indexing.max_chunk_size
    DEFAULT_CHUNK_SIZE = _config.indexing.chunk_size
    CHUNK_OVERLAP = _config.indexing.chunk_overlap
    MAX_OVERLAP = CHUNK_OVERLAP * 2  # Derived
except ImportError:
    CONFIG_AVAILABLE = False
    _config = None

    # Fallback to environment variables
    MIN_CHUNK_SIZE = int(os.getenv("MIN_CHUNK_SIZE", "512"))  # ~128 tokens minimum
    MAX_CHUNK_SIZE = int(os.getenv("MAX_CHUNK_SIZE", "4096"))  # ~1024 tokens maximum
    DEFAULT_CHUNK_SIZE = int(os.getenv("DEFAULT_CHUNK_SIZE", "2048"))  # ~512 tokens default
    CHUNK_OVERLAP = int(os.getenv("CHUNK_OVERLAP", "200"))  # ~50 tokens overlap
    MAX_OVERLAP = int(os.getenv("MAX_OVERLAP", "400"))  # ~100 tokens max overlap

# Content type patterns for tagging
TEST_PATTERNS = ['test_', '_test.', 'tests/', 'test/', 'spec/', '_spec.', '.spec.', '.test.']
CONFIG_PATTERNS = ['config', '.json', '.yaml', '.yml', '.toml', '.ini', '.env', 'settings']
DOC_PATTERNS = ['.md', '.rst', '.txt', 'readme', 'changelog', 'license', 'contributing', 'docs/']


# Pydantic models
class FileData(BaseModel):
    path: str
    content: str
    size: int
    modified_time: str
    git_commit: Optional[str] = None  # Optional: last commit hash
    git_author: Optional[str] = None  # Optional: last author


class ProcessRequest(BaseModel):
    files: List[FileData]
    max_chunk_size: int = Field(default=DEFAULT_CHUNK_SIZE, ge=MIN_CHUNK_SIZE, le=MAX_CHUNK_SIZE)
    overlap: int = Field(default=CHUNK_OVERLAP, ge=0, le=MAX_OVERLAP)
    include_module_context: bool = True  # Include module/file-level context
    extract_symbols: bool = True  # Extract function/class names as metadata
    tag_content_type: bool = True  # Tag chunks as test/config/doc/code


class ChunkRequest(BaseModel):
    content: str
    file_path: str
    max_chunk_size: int = Field(default=DEFAULT_CHUNK_SIZE, ge=MIN_CHUNK_SIZE, le=MAX_CHUNK_SIZE)
    overlap: int = Field(default=CHUNK_OVERLAP, ge=0, le=MAX_OVERLAP)
    include_module_context: bool = True
    extract_symbols: bool = True
    tag_content_type: bool = True


class SmartChunkConfig(BaseModel):
    """Configuration for smart chunking."""
    min_chunk_size: int = Field(default=MIN_CHUNK_SIZE, description="Minimum chunk size in characters")
    max_chunk_size: int = Field(default=MAX_CHUNK_SIZE, description="Maximum chunk size in characters")
    default_chunk_size: int = Field(default=DEFAULT_CHUNK_SIZE, description="Default target chunk size")
    overlap: int = Field(default=CHUNK_OVERLAP, description="Overlap between chunks")
    semantic_boundaries: bool = Field(default=True, description="Respect semantic boundaries (functions, classes)")
    include_imports: bool = Field(default=True, description="Include import statements in context")


# Health check
@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "service": "preprocessor",
        "supported_extensions": ChunkerFactory.supported_extensions(),
        "timestamp": datetime.now().isoformat()
    }


# Utility functions for content classification
def _detect_content_type(file_path: str) -> str:
    """Detect content type based on file path patterns."""
    path_lower = file_path.lower()

    # Check for test files
    if any(pattern in path_lower for pattern in TEST_PATTERNS):
        return "test"

    # Check for config files
    if any(pattern in path_lower for pattern in CONFIG_PATTERNS):
        return "config"

    # Check for documentation
    if any(pattern in path_lower for pattern in DOC_PATTERNS):
        return "documentation"

    return "code"


def _extract_module_context(file_path: str, content: str) -> Dict[str, Any]:
    """Extract module-level context from file."""
    context = {
        "file_name": Path(file_path).name,
        "directory": str(Path(file_path).parent),
        "extension": Path(file_path).suffix,
        "module_name": Path(file_path).stem,
    }

    # Try to extract module docstring (Python)
    if file_path.endswith('.py'):
        docstring_match = re.match(r'^["\'][\'"]{2}(.*?)["\'][\'"]{2}', content, re.DOTALL)
        if docstring_match:
            context["module_docstring"] = docstring_match.group(1).strip()[:500]

    # Extract package info
    if '/' in file_path or '\\' in file_path:
        parts = Path(file_path).parts
        if len(parts) > 1:
            context["package"] = '.'.join(parts[:-1])

    return context


def _enrich_chunk_metadata(chunk: Dict, file_data: FileData,
                           content_type: str, module_context: Dict,
                           request: ProcessRequest) -> Dict:
    """Enrich chunk metadata with additional context."""
    meta = chunk.get("meta", {})

    # Add content type tag
    if request.tag_content_type:
        meta["content_type"] = content_type

    # Add module context
    if request.include_module_context:
        meta["module_context"] = module_context

    # Add git info if available
    if file_data.git_commit:
        meta["git_commit"] = file_data.git_commit
    if file_data.git_author:
        meta["git_author"] = file_data.git_author

    # Extract and add symbol information
    if request.extract_symbols:
        symbols = _extract_symbols_from_chunk(chunk)
        if symbols:
            meta["symbols"] = symbols

    chunk["meta"] = meta
    return chunk


def _extract_symbols_from_chunk(chunk: Dict) -> Dict[str, List[str]]:
    """Extract symbol names from chunk metadata."""
    symbols = {}
    meta = chunk.get("meta", {})

    # Get function name
    if meta.get("function_name"):
        symbols["functions"] = [meta["function_name"]]

    # Get class name
    if meta.get("class_name"):
        symbols["classes"] = [meta["class_name"]]

    # Get method names from class
    if meta.get("methods"):
        symbols["methods"] = meta["methods"]

    # Get import modules
    if meta.get("modules"):
        symbols["imports"] = meta["modules"]

    return symbols


# Main processing endpoint
@app.post("/process")
async def process_files(request: ProcessRequest):
    """Process multiple files and return chunks with enhanced metadata."""
    try:
        logger.info("Processing files",
                   num_files=len(request.files),
                   chunk_size=request.max_chunk_size,
                   overlap=request.overlap)

        all_chunks = []
        stats = {
            "files_processed": 0,
            "total_chunks": 0,
            "files_by_language": {},
            "chunks_by_language": {},
            "chunks_by_content_type": {},
            "processing_errors": [],
            "config": {
                "max_chunk_size": request.max_chunk_size,
                "overlap": request.overlap,
                "include_module_context": request.include_module_context,
                "extract_symbols": request.extract_symbols,
                "tag_content_type": request.tag_content_type
            }
        }

        for file_data in request.files:
            try:
                # Detect content type
                content_type = _detect_content_type(file_data.path)

                # Extract module-level context
                module_context = _extract_module_context(file_data.path, file_data.content)

                # Get appropriate chunker
                chunker = ChunkerFactory.get_chunker(
                    file_data.path,
                    max_chunk_size=request.max_chunk_size,
                    overlap=request.overlap
                )

                # Process file
                chunks = chunker.chunk(file_data.content, file_data.path)

                # Enrich each chunk with metadata
                for i, chunk in enumerate(chunks):
                    chunk_id = _generate_chunk_id(file_data.path, i, chunk["text"])
                    chunk["chunk_id"] = chunk_id
                    chunk["source"] = "file"
                    chunk["file_size"] = file_data.size
                    chunk["file_modified"] = file_data.modified_time

                    # Enrich with additional metadata
                    chunk = _enrich_chunk_metadata(
                        chunk, file_data, content_type, module_context, request
                    )

                all_chunks.extend(chunks)

                # Update stats
                language = chunker.get_language()
                stats["files_by_language"][language] = stats["files_by_language"].get(language, 0) + 1
                stats["chunks_by_language"][language] = stats["chunks_by_language"].get(language, 0) + len(chunks)
                stats["chunks_by_content_type"][content_type] = stats["chunks_by_content_type"].get(content_type, 0) + len(chunks)
                stats["files_processed"] += 1

                logger.info("File processed",
                           file_path=file_data.path,
                           language=language,
                           content_type=content_type,
                           num_chunks=len(chunks))

            except Exception as e:
                error_msg = f"Error processing {file_data.path}: {str(e)}"
                logger.error("File processing error",
                           file_path=file_data.path,
                           error=str(e))
                stats["processing_errors"].append(error_msg)
        
        stats["total_chunks"] = len(all_chunks)
        
        logger.info("Processing completed", 
                   files_processed=stats["files_processed"],
                   total_chunks=stats["total_chunks"])
        
        return {
            "chunks": all_chunks,
            "stats": stats,
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error("Processing failed", error=str(e))
        raise HTTPException(status_code=500, detail=f"Processing failed: {e}")


# Single file processing endpoint
@app.post("/chunk")
async def chunk_single_file(request: ChunkRequest):
    """Process a single file and return chunks with enhanced metadata."""
    try:
        logger.info("Chunking single file", file_path=request.file_path)

        # Detect content type
        content_type = _detect_content_type(request.file_path)

        # Extract module-level context
        module_context = _extract_module_context(request.file_path, request.content)

        # Get appropriate chunker
        chunker = ChunkerFactory.get_chunker(
            request.file_path,
            max_chunk_size=request.max_chunk_size,
            overlap=request.overlap
        )

        # Process content
        chunks = chunker.chunk(request.content, request.file_path)

        # Create a mock FileData for enrichment
        class MockFileData:
            path = request.file_path
            git_commit = None
            git_author = None

        mock_file = MockFileData()

        # Add chunk IDs and enrich metadata
        for i, chunk in enumerate(chunks):
            chunk_id = _generate_chunk_id(request.file_path, i, chunk["text"])
            chunk["chunk_id"] = chunk_id
            chunk["source"] = "content"

            # Enrich with additional metadata
            if request.tag_content_type or request.include_module_context or request.extract_symbols:
                meta = chunk.get("meta", {})
                if request.tag_content_type:
                    meta["content_type"] = content_type
                if request.include_module_context:
                    meta["module_context"] = module_context
                if request.extract_symbols:
                    symbols = _extract_symbols_from_chunk(chunk)
                    if symbols:
                        meta["symbols"] = symbols
                chunk["meta"] = meta

        logger.info("Chunking completed",
                   file_path=request.file_path,
                   language=chunker.get_language(),
                   content_type=content_type,
                   num_chunks=len(chunks))

        return {
            "chunks": chunks,
            "language": chunker.get_language(),
            "content_type": content_type,
            "num_chunks": len(chunks),
            "timestamp": datetime.now().isoformat()
        }

    except Exception as e:
        logger.error("Chunking failed", file_path=request.file_path, error=str(e))
        raise HTTPException(status_code=500, detail=f"Chunking failed: {e}")


# Language detection endpoint
@app.post("/detect-language")
async def detect_language(file_path: str):
    """Detect the language/chunker for a file path."""
    try:
        chunker = ChunkerFactory.get_chunker(file_path)
        return {
            "file_path": file_path,
            "language": chunker.get_language(),
            "chunker_class": chunker.__class__.__name__
        }
    except Exception as e:
        logger.error("Language detection failed", file_path=file_path, error=str(e))
        raise HTTPException(status_code=500, detail=f"Language detection failed: {e}")


# Supported extensions endpoint
@app.get("/supported-extensions")
async def get_supported_extensions():
    """Get list of supported file extensions."""
    return {
        "supported_extensions": ChunkerFactory.supported_extensions(),
        "chunker_types": {
            "python": [".py"],
            "javascript": [".js", ".jsx", ".ts", ".tsx"],
            "markdown": [".md", ".markdown"]
        }
    }


# Configuration endpoint
@app.get("/config")
async def get_config():
    """Get current preprocessor configuration with smart chunking settings."""
    return {
        "min_chunk_size": MIN_CHUNK_SIZE,
        "max_chunk_size": MAX_CHUNK_SIZE,
        "default_chunk_size": DEFAULT_CHUNK_SIZE,
        "chunk_overlap": CHUNK_OVERLAP,
        "max_overlap": MAX_OVERLAP,
        "supported_extensions": ChunkerFactory.supported_extensions(),
        "content_type_patterns": {
            "test": TEST_PATTERNS,
            "config": CONFIG_PATTERNS,
            "documentation": DOC_PATTERNS
        },
        "features": {
            "smart_chunking": True,
            "module_context": True,
            "symbol_extraction": True,
            "content_type_tagging": True
        }
    }


# Utility functions
def _generate_chunk_id(file_path: str, chunk_index: int, content: str) -> str:
    """Generate a unique ID for a chunk."""
    # Create a hash based on file path, chunk index, and content
    content_hash = hashlib.md5(content.encode('utf-8')).hexdigest()[:8]
    return f"{file_path}#{chunk_index}#{content_hash}"


# Statistics endpoint
@app.get("/stats")
async def get_stats():
    """Get preprocessor statistics with enhanced configuration info."""
    return {
        "service": "preprocessor",
        "version": "2.0.0",
        "supported_languages": len(ChunkerFactory.supported_extensions()),
        "supported_extensions": ChunkerFactory.supported_extensions(),
        "default_config": {
            "min_chunk_size": MIN_CHUNK_SIZE,
            "max_chunk_size": MAX_CHUNK_SIZE,
            "default_chunk_size": DEFAULT_CHUNK_SIZE,
            "chunk_overlap": CHUNK_OVERLAP,
            "max_overlap": MAX_OVERLAP
        },
        "features": {
            "smart_chunking": "512-1024 token range",
            "module_context_extraction": True,
            "symbol_extraction": True,
            "content_type_tagging": True,
            "semantic_boundaries": True
        }
    }


if __name__ == "__main__":
    import uvicorn
    
    port = int(os.getenv("PORT", "8003"))
    log_level = os.getenv("LOG_LEVEL", "INFO").lower()
    
    uvicorn.run(
        "app:app",
        host="0.0.0.0",
        port=port,
        log_level=log_level,
        reload=False
    )
