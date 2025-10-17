"""
Vector index implementation with FAISS backend and in-memory fallback.
Handles embedding generation and similarity search.
"""

import os
import json
import pickle
import logging
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime
import numpy as np

try:
    import faiss
    FAISS_AVAILABLE = True
except ImportError:
    FAISS_AVAILABLE = False
    logging.warning("FAISS not available, using in-memory fallback")

from sentence_transformers import SentenceTransformer

logger = logging.getLogger(__name__)

# Configuration
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "all-MiniLM-L6-v2")
DATA_DIR = os.getenv("DATA_DIR", "/app/data")
INDEX_FILE = os.path.join(DATA_DIR, "faiss_index.bin")
METADATA_FILE = os.path.join(DATA_DIR, "metadata.json")


class EmbeddingGenerator:
    """Handles text embedding generation."""
    
    def __init__(self, model_name: str = EMBEDDING_MODEL):
        self.model_name = model_name
        self.model = None
        self._load_model()
    
    def _load_model(self):
        """Load the sentence transformer model."""
        try:
            logger.info(f"Loading embedding model: {self.model_name}")
            self.model = SentenceTransformer(self.model_name)
            logger.info("Embedding model loaded successfully")
        except Exception as e:
            logger.error(f"Failed to load embedding model: {e}")
            raise
    
    def encode(self, texts: List[str]) -> np.ndarray:
        """Generate embeddings for a list of texts."""
        if not self.model:
            raise RuntimeError("Embedding model not loaded")
        
        try:
            embeddings = self.model.encode(texts, convert_to_numpy=True)
            return embeddings
        except Exception as e:
            logger.error(f"Failed to generate embeddings: {e}")
            raise
    
    def encode_single(self, text: str) -> np.ndarray:
        """Generate embedding for a single text."""
        return self.encode([text])[0]
    
    @property
    def dimension(self) -> int:
        """Get the embedding dimension."""
        if not self.model:
            return 384  # Default for all-MiniLM-L6-v2
        return self.model.get_sentence_embedding_dimension()


class FAISSIndex:
    """FAISS-based vector index implementation."""
    
    def __init__(self, dimension: int):
        self.dimension = dimension
        self.index = faiss.IndexFlatIP(dimension)  # Inner product (cosine similarity)
        self.metadata = []
        self.id_counter = 0
    
    def add(self, embeddings: np.ndarray, metadata: List[Dict[str, Any]]) -> List[int]:
        """Add embeddings and metadata to the index."""
        # Normalize embeddings for cosine similarity
        faiss.normalize_L2(embeddings)
        
        # Add to FAISS index
        self.index.add(embeddings)
        
        # Store metadata
        ids = []
        for meta in metadata:
            meta["id"] = self.id_counter
            meta["added_at"] = datetime.now().isoformat()
            self.metadata.append(meta)
            ids.append(self.id_counter)
            self.id_counter += 1
        
        return ids
    
    def search(self, query_embedding: np.ndarray, top_k: int = 10) -> List[Dict[str, Any]]:
        """Search for similar embeddings."""
        # Normalize query embedding
        query_embedding = query_embedding.reshape(1, -1)
        faiss.normalize_L2(query_embedding)
        
        # Search
        scores, indices = self.index.search(query_embedding, top_k)
        
        # Prepare results
        results = []
        for i, (score, idx) in enumerate(zip(scores[0], indices[0])):
            if idx == -1:  # No more results
                break
            
            result = {
                "id": idx,
                "score": float(score),
                "metadata": self.metadata[idx] if idx < len(self.metadata) else {},
                "rank": i + 1
            }
            results.append(result)
        
        return results
    
    def save(self, index_path: str, metadata_path: str):
        """Save index and metadata to disk."""
        try:
            faiss.write_index(self.index, index_path)
            with open(metadata_path, 'w') as f:
                json.dump({
                    "metadata": self.metadata,
                    "id_counter": self.id_counter,
                    "dimension": self.dimension
                }, f, indent=2)
            logger.info(f"Index saved to {index_path}")
        except Exception as e:
            logger.error(f"Failed to save index: {e}")
            raise
    
    def load(self, index_path: str, metadata_path: str):
        """Load index and metadata from disk."""
        try:
            if os.path.exists(index_path) and os.path.exists(metadata_path):
                self.index = faiss.read_index(index_path)
                with open(metadata_path, 'r') as f:
                    data = json.load(f)
                    self.metadata = data["metadata"]
                    self.id_counter = data["id_counter"]
                    self.dimension = data["dimension"]
                logger.info(f"Index loaded from {index_path}")
                return True
        except Exception as e:
            logger.error(f"Failed to load index: {e}")
        return False
    
    def clear(self):
        """Clear the index and metadata."""
        self.index = faiss.IndexFlatIP(self.dimension)
        self.metadata = []
        self.id_counter = 0
    
    def stats(self) -> Dict[str, Any]:
        """Get index statistics."""
        return {
            "total_vectors": self.index.ntotal,
            "dimension": self.dimension,
            "metadata_count": len(self.metadata),
            "index_type": "FAISS IndexFlatIP"
        }


class SimpleInMemoryIndex:
    """Simple in-memory fallback index when FAISS is not available."""
    
    def __init__(self, dimension: int):
        self.dimension = dimension
        self.embeddings = []
        self.metadata = []
        self.id_counter = 0
    
    def add(self, embeddings: np.ndarray, metadata: List[Dict[str, Any]]) -> List[int]:
        """Add embeddings and metadata to the index."""
        ids = []
        for i, (embedding, meta) in enumerate(zip(embeddings, metadata)):
            # Normalize embedding
            norm = np.linalg.norm(embedding)
            if norm > 0:
                embedding = embedding / norm
            
            self.embeddings.append(embedding)
            
            meta["id"] = self.id_counter
            meta["added_at"] = datetime.now().isoformat()
            self.metadata.append(meta)
            ids.append(self.id_counter)
            self.id_counter += 1
        
        return ids
    
    def search(self, query_embedding: np.ndarray, top_k: int = 10) -> List[Dict[str, Any]]:
        """Search for similar embeddings using cosine similarity."""
        if not self.embeddings:
            return []
        
        # Normalize query
        norm = np.linalg.norm(query_embedding)
        if norm > 0:
            query_embedding = query_embedding / norm
        
        # Calculate similarities
        similarities = []
        for i, embedding in enumerate(self.embeddings):
            similarity = np.dot(query_embedding, embedding)
            similarities.append((similarity, i))
        
        # Sort by similarity (descending)
        similarities.sort(key=lambda x: x[0], reverse=True)
        
        # Prepare results
        results = []
        for rank, (score, idx) in enumerate(similarities[:top_k]):
            result = {
                "id": idx,
                "score": float(score),
                "metadata": self.metadata[idx],
                "rank": rank + 1
            }
            results.append(result)
        
        return results
    
    def save(self, index_path: str, metadata_path: str):
        """Save index and metadata to disk."""
        try:
            # Save embeddings as numpy array
            embeddings_array = np.array(self.embeddings) if self.embeddings else np.array([])
            np.save(index_path.replace('.bin', '_embeddings.npy'), embeddings_array)
            
            # Save metadata
            with open(metadata_path, 'w') as f:
                json.dump({
                    "metadata": self.metadata,
                    "id_counter": self.id_counter,
                    "dimension": self.dimension
                }, f, indent=2)
            logger.info(f"In-memory index saved to {index_path}")
        except Exception as e:
            logger.error(f"Failed to save in-memory index: {e}")
            raise
    
    def load(self, index_path: str, metadata_path: str):
        """Load index and metadata from disk."""
        try:
            embeddings_path = index_path.replace('.bin', '_embeddings.npy')
            if os.path.exists(embeddings_path) and os.path.exists(metadata_path):
                # Load embeddings
                embeddings_array = np.load(embeddings_path)
                self.embeddings = embeddings_array.tolist() if embeddings_array.size > 0 else []
                
                # Load metadata
                with open(metadata_path, 'r') as f:
                    data = json.load(f)
                    self.metadata = data["metadata"]
                    self.id_counter = data["id_counter"]
                    self.dimension = data["dimension"]
                logger.info(f"In-memory index loaded from {index_path}")
                return True
        except Exception as e:
            logger.error(f"Failed to load in-memory index: {e}")
        return False
    
    def clear(self):
        """Clear the index and metadata."""
        self.embeddings = []
        self.metadata = []
        self.id_counter = 0
    
    def stats(self) -> Dict[str, Any]:
        """Get index statistics."""
        return {
            "total_vectors": len(self.embeddings),
            "dimension": self.dimension,
            "metadata_count": len(self.metadata),
            "index_type": "Simple In-Memory"
        }


class VectorIndex:
    """Main vector index class with automatic backend selection."""
    
    def __init__(self):
        self.embedding_generator = EmbeddingGenerator()
        self.dimension = self.embedding_generator.dimension
        
        # Choose backend
        if FAISS_AVAILABLE:
            self.index = FAISSIndex(self.dimension)
            logger.info("Using FAISS backend")
        else:
            self.index = SimpleInMemoryIndex(self.dimension)
            logger.info("Using in-memory fallback backend")
        
        # Ensure data directory exists
        os.makedirs(DATA_DIR, exist_ok=True)
        
        # Try to load existing index
        self.load()
    
    def insert(self, chunks: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Insert text chunks into the index."""
        if not chunks:
            return {"indexed_count": 0, "message": "No chunks to index"}
        
        try:
            # Extract texts and metadata
            texts = []
            metadata = []
            
            for chunk in chunks:
                text = chunk.get("text", "")
                if not text.strip():
                    continue
                
                texts.append(text)
                
                # Prepare metadata
                meta = {
                    "text": text,
                    "meta": chunk.get("meta", {}),
                    "chunk_id": chunk.get("chunk_id"),
                    "source": chunk.get("source", "unknown")
                }
                metadata.append(meta)
            
            if not texts:
                return {"indexed_count": 0, "message": "No valid texts to index"}
            
            # Generate embeddings
            logger.info(f"Generating embeddings for {len(texts)} texts")
            embeddings = self.embedding_generator.encode(texts)
            
            # Add to index
            ids = self.index.add(embeddings, metadata)
            
            # Save index
            self.save()
            
            logger.info(f"Successfully indexed {len(ids)} chunks")
            return {
                "indexed_count": len(ids),
                "message": "Chunks indexed successfully",
                "ids": ids
            }
            
        except Exception as e:
            logger.error(f"Failed to insert chunks: {e}")
            raise
    
    def search(self, query: str, top_k: int = 10) -> Dict[str, Any]:
        """Search the index for similar content."""
        try:
            # Generate query embedding
            query_embedding = self.embedding_generator.encode_single(query)
            
            # Search index
            results = self.index.search(query_embedding, top_k)
            
            # Format results
            formatted_results = []
            for result in results:
                formatted_result = {
                    "text": result["metadata"].get("text", ""),
                    "score": result["score"],
                    "meta": result["metadata"].get("meta", {}),
                    "source": result["metadata"].get("source", "unknown"),
                    "rank": result["rank"]
                }
                formatted_results.append(formatted_result)
            
            return {
                "query": query,
                "results": formatted_results,
                "total_results": len(formatted_results),
                "timestamp": datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Search failed: {e}")
            raise
    
    def save(self):
        """Save the index to disk."""
        self.index.save(INDEX_FILE, METADATA_FILE)
    
    def load(self):
        """Load the index from disk."""
        return self.index.load(INDEX_FILE, METADATA_FILE)
    
    def clear(self):
        """Clear the entire index."""
        self.index.clear()
        self.save()
        return {"message": "Index cleared successfully"}
    
    def stats(self) -> Dict[str, Any]:
        """Get index statistics."""
        base_stats = self.index.stats()
        base_stats.update({
            "embedding_model": self.embedding_generator.model_name,
            "backend": "FAISS" if FAISS_AVAILABLE else "In-Memory",
            "data_directory": DATA_DIR
        })
        return base_stats
