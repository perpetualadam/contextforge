"""
Preprocessor Service - FastAPI application for language-aware text chunking.
"""

import os
import logging
import hashlib
from typing import Dict, List, Any
from datetime import datetime

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import structlog

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
    description="Language-aware text chunking and preprocessing service",
    version="1.0.0"
)

# Configuration
MAX_CHUNK_SIZE = int(os.getenv("MAX_CHUNK_SIZE", "1000"))
CHUNK_OVERLAP = int(os.getenv("CHUNK_OVERLAP", "100"))


# Pydantic models
class FileData(BaseModel):
    path: str
    content: str
    size: int
    modified_time: str


class ProcessRequest(BaseModel):
    files: List[FileData]
    max_chunk_size: int = MAX_CHUNK_SIZE
    overlap: int = CHUNK_OVERLAP


class ChunkRequest(BaseModel):
    content: str
    file_path: str
    max_chunk_size: int = MAX_CHUNK_SIZE
    overlap: int = CHUNK_OVERLAP


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


# Main processing endpoint
@app.post("/process")
async def process_files(request: ProcessRequest):
    """Process multiple files and return chunks."""
    try:
        logger.info("Processing files", num_files=len(request.files))
        
        all_chunks = []
        stats = {
            "files_processed": 0,
            "total_chunks": 0,
            "files_by_language": {},
            "chunks_by_language": {},
            "processing_errors": []
        }
        
        for file_data in request.files:
            try:
                # Get appropriate chunker
                chunker = ChunkerFactory.get_chunker(
                    file_data.path,
                    max_chunk_size=request.max_chunk_size,
                    overlap=request.overlap
                )
                
                # Process file
                chunks = chunker.chunk(file_data.content, file_data.path)
                
                # Add chunk IDs and source info
                for i, chunk in enumerate(chunks):
                    chunk_id = _generate_chunk_id(file_data.path, i, chunk["text"])
                    chunk["chunk_id"] = chunk_id
                    chunk["source"] = "file"
                    chunk["file_size"] = file_data.size
                    chunk["file_modified"] = file_data.modified_time
                
                all_chunks.extend(chunks)
                
                # Update stats
                language = chunker.get_language()
                stats["files_by_language"][language] = stats["files_by_language"].get(language, 0) + 1
                stats["chunks_by_language"][language] = stats["chunks_by_language"].get(language, 0) + len(chunks)
                stats["files_processed"] += 1
                
                logger.info("File processed", 
                           file_path=file_data.path, 
                           language=language, 
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
    """Process a single file and return chunks."""
    try:
        logger.info("Chunking single file", file_path=request.file_path)
        
        # Get appropriate chunker
        chunker = ChunkerFactory.get_chunker(
            request.file_path,
            max_chunk_size=request.max_chunk_size,
            overlap=request.overlap
        )
        
        # Process content
        chunks = chunker.chunk(request.content, request.file_path)
        
        # Add chunk IDs
        for i, chunk in enumerate(chunks):
            chunk_id = _generate_chunk_id(request.file_path, i, chunk["text"])
            chunk["chunk_id"] = chunk_id
            chunk["source"] = "content"
        
        logger.info("Chunking completed", 
                   file_path=request.file_path,
                   language=chunker.get_language(),
                   num_chunks=len(chunks))
        
        return {
            "chunks": chunks,
            "language": chunker.get_language(),
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
    """Get current preprocessor configuration."""
    return {
        "max_chunk_size": MAX_CHUNK_SIZE,
        "chunk_overlap": CHUNK_OVERLAP,
        "supported_extensions": ChunkerFactory.supported_extensions()
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
    """Get preprocessor statistics."""
    return {
        "service": "preprocessor",
        "version": "1.0.0",
        "supported_languages": len(ChunkerFactory.supported_extensions()),
        "supported_extensions": ChunkerFactory.supported_extensions(),
        "default_config": {
            "max_chunk_size": MAX_CHUNK_SIZE,
            "chunk_overlap": CHUNK_OVERLAP
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
