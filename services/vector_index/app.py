"""
Vector Index Service - FastAPI application for vector indexing and search.
"""

import os
import logging
from typing import Dict, List, Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import structlog

from .index import VectorIndex

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
    title="ContextForge Vector Index Service",
    description="Vector indexing and similarity search service",
    version="1.0.0"
)

# Initialize vector index
vector_index = VectorIndex()


# Pydantic models
class InsertRequest(BaseModel):
    chunks: List[Dict[str, Any]]


class SearchRequest(BaseModel):
    query: str
    top_k: int = 10


class EmbeddingRequest(BaseModel):
    texts: List[str]


# Health check
@app.get("/health")
async def health_check():
    """Health check endpoint."""
    try:
        stats = vector_index.stats()
        return {
            "status": "healthy",
            "service": "vector_index",
            "stats": stats,
            "timestamp": "2024-01-01T00:00:00"  # Will be updated by actual timestamp
        }
    except Exception as e:
        logger.error("Health check failed", error=str(e))
        return {
            "status": "unhealthy",
            "service": "vector_index",
            "error": str(e)
        }


# Index management endpoints
@app.post("/index/insert")
async def insert_chunks(request: InsertRequest):
    """Insert text chunks into the vector index."""
    try:
        logger.info("Inserting chunks", num_chunks=len(request.chunks))
        result = vector_index.insert(request.chunks)
        logger.info("Chunks inserted successfully", indexed_count=result["indexed_count"])
        return result
    except Exception as e:
        logger.error("Failed to insert chunks", error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to insert chunks: {e}")


@app.post("/search")
async def search_index(request: SearchRequest):
    """Search the vector index for similar content."""
    try:
        logger.info("Searching index", query=request.query, top_k=request.top_k)
        result = vector_index.search(request.query, request.top_k)
        logger.info("Search completed", num_results=result["total_results"])
        return result
    except Exception as e:
        logger.error("Search failed", error=str(e))
        raise HTTPException(status_code=500, detail=f"Search failed: {e}")


@app.delete("/index/clear")
async def clear_index():
    """Clear the entire vector index."""
    try:
        logger.info("Clearing vector index")
        result = vector_index.clear()
        logger.info("Vector index cleared successfully")
        return result
    except Exception as e:
        logger.error("Failed to clear index", error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to clear index: {e}")


@app.get("/index/stats")
async def get_index_stats():
    """Get vector index statistics."""
    try:
        stats = vector_index.stats()
        return stats
    except Exception as e:
        logger.error("Failed to get index stats", error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to get stats: {e}")


# Embedding endpoints
@app.post("/embeddings/generate")
async def generate_embeddings(request: EmbeddingRequest):
    """Generate embeddings for a list of texts."""
    try:
        logger.info("Generating embeddings", num_texts=len(request.texts))
        embeddings = vector_index.embedding_generator.encode(request.texts)
        
        return {
            "embeddings": embeddings.tolist(),
            "dimension": vector_index.dimension,
            "model": vector_index.embedding_generator.model_name,
            "num_embeddings": len(embeddings)
        }
    except Exception as e:
        logger.error("Failed to generate embeddings", error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to generate embeddings: {e}")


@app.get("/embeddings/model")
async def get_embedding_model_info():
    """Get information about the embedding model."""
    return {
        "model_name": vector_index.embedding_generator.model_name,
        "dimension": vector_index.dimension,
        "backend": "FAISS" if hasattr(vector_index.index, 'index') else "In-Memory"
    }


# Index backup and restore
@app.post("/index/save")
async def save_index():
    """Manually save the index to disk."""
    try:
        vector_index.save()
        return {"message": "Index saved successfully"}
    except Exception as e:
        logger.error("Failed to save index", error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to save index: {e}")


@app.post("/index/load")
async def load_index():
    """Manually load the index from disk."""
    try:
        success = vector_index.load()
        if success:
            return {"message": "Index loaded successfully"}
        else:
            return {"message": "No existing index found"}
    except Exception as e:
        logger.error("Failed to load index", error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to load index: {e}")


if __name__ == "__main__":
    import uvicorn
    
    port = int(os.getenv("PORT", "8001"))
    log_level = os.getenv("LOG_LEVEL", "INFO").lower()
    
    uvicorn.run(
        "app:app",
        host="0.0.0.0",
        port=port,
        log_level=log_level,
        reload=False
    )
