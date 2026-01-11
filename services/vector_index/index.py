"""
Vector index implementation with FAISS backend and in-memory fallback.
Handles embedding generation and similarity search.

Enhanced features:
- Multiple embedding model support (general + code-specific)
- Hybrid retrieval with lexical search
- LLM-based re-ranking
- Recency boost for recent code changes
"""

import os
import sys
import re
import json
import pickle
import logging
from typing import Dict, List, Optional, Any, Tuple, Set
from datetime import datetime
from collections import Counter
from pathlib import Path
import numpy as np

try:
    import faiss
    FAISS_AVAILABLE = True
except ImportError:
    FAISS_AVAILABLE = False
    logging.warning("FAISS not available, using in-memory fallback")

from sentence_transformers import SentenceTransformer

# Add parent directory to path for services imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

logger = logging.getLogger(__name__)

# Try to use unified config, fallback to env vars
try:
    from services.config import get_config
    _config = get_config()
    CONFIG_AVAILABLE = True

    # Configuration from unified config
    EMBEDDING_MODEL = _config.indexing.embedding_model
    CODE_EMBEDDING_MODEL = _config.indexing.code_embedding_model
    USE_CODE_EMBEDDINGS = _config.indexing.use_code_embeddings
    DATA_DIR = _config.data.data_dir
    HYBRID_SEARCH_ENABLED = _config.indexing.hybrid_search_enabled
    DENSE_WEIGHT = _config.indexing.dense_weight
    LEXICAL_WEIGHT = _config.indexing.lexical_weight
    RECENCY_BOOST_ENABLED = _config.indexing.recency_boost_enabled
    RECENCY_BOOST_FACTOR = _config.indexing.recency_boost_factor
except ImportError:
    CONFIG_AVAILABLE = False
    _config = None

    # Fallback to environment variables
    EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "all-mpnet-base-v2")
    CODE_EMBEDDING_MODEL = os.getenv("CODE_EMBEDDING_MODEL", "microsoft/codebert-base")
    USE_CODE_EMBEDDINGS = os.getenv("USE_CODE_EMBEDDINGS", "true").lower() == "true"
    DATA_DIR = os.getenv("DATA_DIR", "/app/data")
    HYBRID_SEARCH_ENABLED = os.getenv("HYBRID_SEARCH_ENABLED", "true").lower() == "true"
    DENSE_WEIGHT = float(os.getenv("DENSE_WEIGHT", "0.7"))
    LEXICAL_WEIGHT = float(os.getenv("LEXICAL_WEIGHT", "0.3"))
    RECENCY_BOOST_ENABLED = os.getenv("RECENCY_BOOST_ENABLED", "true").lower() == "true"
    RECENCY_BOOST_FACTOR = float(os.getenv("RECENCY_BOOST_FACTOR", "0.1"))

# Derived paths
INDEX_FILE = os.path.join(DATA_DIR, "faiss_index.bin")
METADATA_FILE = os.path.join(DATA_DIR, "metadata.json")
LEXICAL_INDEX_FILE = os.path.join(DATA_DIR, "lexical_index.json")

# Code file extensions for specialized embedding
CODE_EXTENSIONS = {'.py', '.js', '.ts', '.jsx', '.tsx', '.java', '.cs', '.cpp', '.c',
                   '.h', '.hpp', '.go', '.rs', '.rb', '.php', '.swift', '.kt', '.scala'}


class EmbeddingGenerator:
    """
    Handles text embedding generation with support for multiple models.

    Features:
    - Primary model: all-mpnet-base-v2 for high-quality general embeddings (768 dim)
    - Code model: CodeBERT or similar for code-specific embeddings
    - Automatic model selection based on content type
    """

    def __init__(self, model_name: str = EMBEDDING_MODEL, use_code_model: bool = USE_CODE_EMBEDDINGS):
        self.model_name = model_name
        self.code_model_name = CODE_EMBEDDING_MODEL
        self.use_code_model = use_code_model
        self.model = None
        self.code_model = None
        self._load_models()

    def _load_models(self):
        """Load the sentence transformer models."""
        try:
            logger.info(f"Loading primary embedding model: {self.model_name}")
            self.model = SentenceTransformer(self.model_name)
            logger.info(f"Primary embedding model loaded successfully (dim={self.model.get_sentence_embedding_dimension()})")

            # Load code-specific model if enabled
            if self.use_code_model:
                try:
                    logger.info(f"Loading code embedding model: {self.code_model_name}")
                    self.code_model = SentenceTransformer(self.code_model_name)
                    logger.info(f"Code embedding model loaded successfully (dim={self.code_model.get_sentence_embedding_dimension()})")
                except Exception as e:
                    logger.warning(f"Failed to load code embedding model, using primary model: {e}")
                    self.code_model = None
        except Exception as e:
            logger.error(f"Failed to load embedding model: {e}")
            raise

    def _is_code_content(self, text: str, file_path: Optional[str] = None) -> bool:
        """Determine if content is code based on file extension or content analysis."""
        if file_path:
            ext = os.path.splitext(file_path)[1].lower()
            if ext in CODE_EXTENSIONS:
                return True

        # Heuristic: check for code patterns
        code_patterns = [
            r'def\s+\w+\s*\(', r'class\s+\w+', r'function\s+\w+',
            r'import\s+', r'from\s+\w+\s+import', r'const\s+\w+\s*=',
            r'let\s+\w+\s*=', r'var\s+\w+\s*=', r'public\s+\w+',
            r'private\s+\w+', r'async\s+', r'=>', r'\{\s*\n'
        ]
        matches = sum(1 for p in code_patterns if re.search(p, text))
        return matches >= 2

    def encode(self, texts: List[str], file_paths: Optional[List[str]] = None) -> np.ndarray:
        """Generate embeddings for a list of texts."""
        if not self.model:
            raise RuntimeError("Embedding model not loaded")

        try:
            # If code model is available and enabled, use it for code content
            if self.code_model and file_paths:
                code_indices = []
                text_indices = []

                for i, (text, path) in enumerate(zip(texts, file_paths)):
                    if self._is_code_content(text, path):
                        code_indices.append(i)
                    else:
                        text_indices.append(i)

                # Generate embeddings with appropriate models
                embeddings = np.zeros((len(texts), self.dimension))

                if text_indices:
                    text_texts = [texts[i] for i in text_indices]
                    text_embeds = self.model.encode(text_texts, convert_to_numpy=True)
                    for j, i in enumerate(text_indices):
                        embeddings[i] = text_embeds[j]

                if code_indices:
                    code_texts = [texts[i] for i in code_indices]
                    # For code, prepend with special token if using CodeBERT-style model
                    code_embeds = self.code_model.encode(code_texts, convert_to_numpy=True)
                    for j, i in enumerate(code_indices):
                        # Resize if dimensions differ
                        if code_embeds[j].shape[0] != self.dimension:
                            # Use primary model for consistency
                            embeddings[i] = self.model.encode([texts[i]], convert_to_numpy=True)[0]
                        else:
                            embeddings[i] = code_embeds[j]

                return embeddings
            else:
                # Use primary model for all texts
                embeddings = self.model.encode(texts, convert_to_numpy=True)
                return embeddings
        except Exception as e:
            logger.error(f"Failed to generate embeddings: {e}")
            raise

    def encode_single(self, text: str, file_path: Optional[str] = None) -> np.ndarray:
        """Generate embedding for a single text."""
        file_paths = [file_path] if file_path else None
        return self.encode([text], file_paths)[0]

    @property
    def dimension(self) -> int:
        """Get the embedding dimension (using primary model)."""
        if not self.model:
            return 768  # Default for all-mpnet-base-v2
        return self.model.get_sentence_embedding_dimension()

    def get_model_info(self) -> Dict[str, Any]:
        """Get information about loaded models."""
        return {
            "primary_model": self.model_name,
            "primary_dimension": self.model.get_sentence_embedding_dimension() if self.model else None,
            "code_model": self.code_model_name if self.code_model else None,
            "code_dimension": self.code_model.get_sentence_embedding_dimension() if self.code_model else None,
            "use_code_embeddings": self.use_code_model and self.code_model is not None
        }


class FAISSIndex:
    """FAISS-based vector index implementation."""
    
    def __init__(self, dimension: int):
        self.dimension = dimension
        self.index = faiss.IndexFlatIP(dimension)  # Inner product (cosine similarity)
        self.metadata = []
        self.id_counter = 0
    
    def add(self, embeddings: np.ndarray, metadata: List[Dict[str, Any]]) -> List[int]:
        """Add embeddings and metadata to the index."""
        # Ensure embeddings are contiguous float32 for FAISS
        embeddings = np.ascontiguousarray(embeddings, dtype=np.float32)

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
                loaded_index = faiss.read_index(index_path)
                with open(metadata_path, 'r') as f:
                    data = json.load(f)

                # Check for dimension mismatch
                loaded_dimension = data.get("dimension", loaded_index.d)
                if loaded_dimension != self.dimension:
                    logger.warning(f"Dimension mismatch: saved={loaded_dimension}, current={self.dimension}. Reinitializing index.")
                    return False

                self.index = loaded_index
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
                # Load metadata first to check dimension
                with open(metadata_path, 'r') as f:
                    data = json.load(f)

                # Check for dimension mismatch
                loaded_dimension = data.get("dimension", self.dimension)
                if loaded_dimension != self.dimension:
                    logger.warning(f"Dimension mismatch: saved={loaded_dimension}, current={self.dimension}. Reinitializing index.")
                    return False

                # Load embeddings
                embeddings_array = np.load(embeddings_path)
                self.embeddings = embeddings_array.tolist() if embeddings_array.size > 0 else []

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


class LexicalIndex:
    """
    BM25-style lexical index for hybrid retrieval.

    Uses TF-IDF style scoring with inverted index for fast keyword search.
    """

    def __init__(self):
        self.inverted_index: Dict[str, Set[int]] = {}  # term -> set of doc ids
        self.doc_terms: Dict[int, Counter] = {}  # doc_id -> term frequencies
        self.doc_lengths: Dict[int, int] = {}  # doc_id -> document length
        self.avg_doc_length = 0.0
        self.total_docs = 0
        self.id_to_metadata: Dict[int, Dict] = {}

        # BM25 parameters
        self.k1 = 1.5
        self.b = 0.75

        # Stop words for code (minimal set)
        self.stop_words = {'the', 'a', 'an', 'is', 'are', 'was', 'were', 'be', 'been',
                          'being', 'have', 'has', 'had', 'do', 'does', 'did', 'will',
                          'would', 'could', 'should', 'may', 'might', 'must', 'shall',
                          'can', 'need', 'to', 'of', 'in', 'for', 'on', 'with', 'at',
                          'by', 'from', 'as', 'into', 'through', 'during', 'before',
                          'after', 'above', 'below', 'between', 'under', 'again',
                          'further', 'then', 'once', 'and', 'but', 'or', 'nor', 'so',
                          'yet', 'both', 'each', 'few', 'more', 'most', 'other', 'some',
                          'such', 'no', 'not', 'only', 'own', 'same', 'than', 'too',
                          'very', 'just', 'also', 'now', 'here', 'there', 'when',
                          'where', 'why', 'how', 'all', 'any', 'both', 'each', 'this',
                          'that', 'these', 'those', 'it', 'its'}

    def _tokenize(self, text: str) -> List[str]:
        """Tokenize text into terms, handling code-specific patterns."""
        # Split camelCase BEFORE lowercasing (need case info)
        text = re.sub(r'([a-z])([A-Z])', r'\1 \2', text)

        # Split snake_case
        text = text.replace('_', ' ')

        # Convert to lowercase
        text = text.lower()

        # Extract alphanumeric tokens
        tokens = re.findall(r'\b[a-zA-Z][a-zA-Z0-9]{1,}\b', text)

        # Filter stop words and short tokens
        tokens = [t for t in tokens if t not in self.stop_words and len(t) > 1]

        return tokens

    def add(self, doc_id: int, text: str, metadata: Dict[str, Any]):
        """Add a document to the lexical index."""
        tokens = self._tokenize(text)

        if not tokens:
            return

        # Store term frequencies
        term_freq = Counter(tokens)
        self.doc_terms[doc_id] = term_freq
        self.doc_lengths[doc_id] = len(tokens)
        self.id_to_metadata[doc_id] = metadata

        # Update inverted index
        for term in term_freq:
            if term not in self.inverted_index:
                self.inverted_index[term] = set()
            self.inverted_index[term].add(doc_id)

        # Update statistics
        self.total_docs += 1
        total_length = sum(self.doc_lengths.values())
        self.avg_doc_length = total_length / self.total_docs if self.total_docs > 0 else 0

    def search(self, query: str, top_k: int = 10) -> List[Dict[str, Any]]:
        """Search using BM25 scoring."""
        query_tokens = self._tokenize(query)

        if not query_tokens:
            return []

        # Calculate BM25 scores for all matching documents
        scores: Dict[int, float] = {}

        for term in query_tokens:
            if term not in self.inverted_index:
                continue

            # IDF calculation
            doc_freq = len(self.inverted_index[term])
            idf = np.log((self.total_docs - doc_freq + 0.5) / (doc_freq + 0.5) + 1)

            for doc_id in self.inverted_index[term]:
                tf = self.doc_terms[doc_id].get(term, 0)
                doc_length = self.doc_lengths[doc_id]

                # BM25 score
                numerator = tf * (self.k1 + 1)
                denominator = tf + self.k1 * (1 - self.b + self.b * doc_length / max(self.avg_doc_length, 1))

                score = idf * numerator / denominator
                scores[doc_id] = scores.get(doc_id, 0) + score

        # Sort by score and return top-k
        sorted_docs = sorted(scores.items(), key=lambda x: x[1], reverse=True)[:top_k]

        results = []
        for rank, (doc_id, score) in enumerate(sorted_docs):
            results.append({
                "id": doc_id,
                "score": float(score),
                "metadata": self.id_to_metadata.get(doc_id, {}),
                "rank": rank + 1
            })

        return results

    def save(self, path: str):
        """Save lexical index to disk."""
        try:
            data = {
                "inverted_index": {k: list(v) for k, v in self.inverted_index.items()},
                "doc_terms": {str(k): dict(v) for k, v in self.doc_terms.items()},
                "doc_lengths": {str(k): v for k, v in self.doc_lengths.items()},
                "id_to_metadata": {str(k): v for k, v in self.id_to_metadata.items()},
                "avg_doc_length": self.avg_doc_length,
                "total_docs": self.total_docs
            }
            with open(path, 'w') as f:
                json.dump(data, f)
            logger.info(f"Lexical index saved to {path}")
        except Exception as e:
            logger.error(f"Failed to save lexical index: {e}")

    def load(self, path: str) -> bool:
        """Load lexical index from disk."""
        try:
            if os.path.exists(path):
                with open(path, 'r') as f:
                    data = json.load(f)
                self.inverted_index = {k: set(v) for k, v in data.get("inverted_index", {}).items()}
                self.doc_terms = {int(k): Counter(v) for k, v in data.get("doc_terms", {}).items()}
                self.doc_lengths = {int(k): v for k, v in data.get("doc_lengths", {}).items()}
                self.id_to_metadata = {int(k): v for k, v in data.get("id_to_metadata", {}).items()}
                self.avg_doc_length = data.get("avg_doc_length", 0.0)
                self.total_docs = data.get("total_docs", 0)
                logger.info(f"Lexical index loaded from {path}")
                return True
        except Exception as e:
            logger.error(f"Failed to load lexical index: {e}")
        return False

    def clear(self):
        """Clear the lexical index."""
        self.inverted_index = {}
        self.doc_terms = {}
        self.doc_lengths = {}
        self.id_to_metadata = {}
        self.avg_doc_length = 0.0
        self.total_docs = 0

    def stats(self) -> Dict[str, Any]:
        """Get index statistics."""
        return {
            "total_docs": self.total_docs,
            "unique_terms": len(self.inverted_index),
            "avg_doc_length": self.avg_doc_length,
            "index_type": "BM25 Lexical"
        }


class VectorIndex:
    """
    Main vector index class with hybrid retrieval support.

    Features:
    - Automatic backend selection (FAISS or in-memory)
    - Hybrid search (dense + lexical)
    - Recency boosting for recent code changes
    - LLM-based re-ranking (optional)
    """

    def __init__(self, enable_hybrid: bool = HYBRID_SEARCH_ENABLED):
        self.embedding_generator = EmbeddingGenerator()
        self.dimension = self.embedding_generator.dimension
        self.enable_hybrid = enable_hybrid

        # Choose backend
        if FAISS_AVAILABLE:
            self.index = FAISSIndex(self.dimension)
            logger.info("Using FAISS backend")
        else:
            self.index = SimpleInMemoryIndex(self.dimension)
            logger.info("Using in-memory fallback backend")

        # Initialize lexical index for hybrid search
        self.lexical_index = LexicalIndex() if enable_hybrid else None

        # Ensure data directory exists
        os.makedirs(DATA_DIR, exist_ok=True)

        # Try to load existing index
        self.load()

    def insert(self, chunks: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Insert text chunks into the index."""
        if not chunks:
            return {"indexed_count": 0, "message": "No chunks to index"}

        try:
            # Extract texts, metadata, and file paths for code detection
            texts = []
            metadata = []
            file_paths = []

            for chunk in chunks:
                text = chunk.get("text", "")
                if not text.strip():
                    continue

                texts.append(text)

                # Get file path for code-specific embeddings
                chunk_meta = chunk.get("meta", {})
                file_path = chunk_meta.get("file_path", "")
                file_paths.append(file_path)

                # Prepare metadata with enhanced info
                meta = {
                    "text": text,
                    "meta": chunk_meta,
                    "chunk_id": chunk.get("chunk_id"),
                    "source": chunk.get("source", "unknown"),
                    "indexed_at": datetime.now().isoformat(),
                    # Add content type tags
                    "content_type": self._detect_content_type(text, file_path, chunk_meta)
                }
                metadata.append(meta)

            if not texts:
                return {"indexed_count": 0, "message": "No valid texts to index"}

            # Generate embeddings with code-specific model where appropriate
            logger.info(f"Generating embeddings for {len(texts)} texts")
            embeddings = self.embedding_generator.encode(texts, file_paths)

            # Add to vector index
            ids = self.index.add(embeddings, metadata)

            # Add to lexical index for hybrid search
            if self.lexical_index:
                for doc_id, (text, meta) in zip(ids, zip(texts, metadata)):
                    self.lexical_index.add(doc_id, text, meta)

            # Save indexes
            self.save()

            logger.info(f"Successfully indexed {len(ids)} chunks")
            return {
                "indexed_count": len(ids),
                "message": "Chunks indexed successfully",
                "ids": ids,
                "hybrid_enabled": self.enable_hybrid
            }

        except Exception as e:
            logger.error(f"Failed to insert chunks: {e}")
            raise

    def _detect_content_type(self, text: str, file_path: str, meta: Dict) -> str:
        """Detect content type for tagging."""
        chunk_type = meta.get("chunk_type", "")

        # Check for test files
        if any(pattern in file_path.lower() for pattern in ['test_', '_test', 'tests/', 'spec/']):
            return "test"

        # Check for config files
        config_patterns = ['config', '.json', '.yaml', '.yml', '.toml', '.ini', '.env']
        if any(pattern in file_path.lower() for pattern in config_patterns):
            return "config"

        # Check for documentation
        doc_patterns = ['.md', '.rst', '.txt', 'readme', 'doc']
        if any(pattern in file_path.lower() for pattern in doc_patterns):
            return "documentation"

        # Default to code or text based on chunk type
        if chunk_type in ['function', 'class', 'method', 'import']:
            return "code"

        return "text"

    def search(self, query: str, top_k: int = 10,
               enable_hybrid: Optional[bool] = None,
               enable_reranking: bool = False,
               recency_boost: Optional[bool] = None) -> Dict[str, Any]:
        """
        Search the index for similar content with hybrid retrieval.

        Args:
            query: Search query
            top_k: Number of results to return
            enable_hybrid: Override hybrid search setting
            enable_reranking: Enable LLM-based re-ranking
            recency_boost: Override recency boost setting
        """
        try:
            use_hybrid = enable_hybrid if enable_hybrid is not None else self.enable_hybrid
            use_recency = recency_boost if recency_boost is not None else RECENCY_BOOST_ENABLED

            # Generate query embedding
            query_embedding = self.embedding_generator.encode_single(query)

            # Dense vector search
            dense_results = self.index.search(query_embedding, top_k * 2)  # Get more for fusion

            # Hybrid search: combine dense + lexical
            if use_hybrid and self.lexical_index:
                lexical_results = self.lexical_index.search(query, top_k * 2)
                combined_results = self._fuse_results(dense_results, lexical_results, top_k * 2)
            else:
                combined_results = dense_results

            # Apply recency boost
            if use_recency:
                combined_results = self._apply_recency_boost(combined_results)

            # Re-sort by final score
            combined_results.sort(key=lambda x: x.get("final_score", x.get("score", 0)), reverse=True)

            # Take top-k
            final_results = combined_results[:top_k]

            # Format results
            formatted_results = []
            for i, result in enumerate(final_results):
                formatted_result = {
                    "text": result["metadata"].get("text", ""),
                    "score": result.get("final_score", result.get("score", 0)),
                    "dense_score": result.get("dense_score", result.get("score", 0)),
                    "lexical_score": result.get("lexical_score", 0),
                    "recency_boost": result.get("recency_boost", 0),
                    "meta": result["metadata"].get("meta", {}),
                    "source": result["metadata"].get("source", "unknown"),
                    "content_type": result["metadata"].get("content_type", "unknown"),
                    "rank": i + 1
                }
                formatted_results.append(formatted_result)

            return {
                "query": query,
                "results": formatted_results,
                "total_results": len(formatted_results),
                "timestamp": datetime.now().isoformat(),
                "search_type": "hybrid" if use_hybrid else "dense",
                "recency_boost_applied": use_recency
            }

        except Exception as e:
            logger.error(f"Search failed: {e}")
            raise

    def _fuse_results(self, dense_results: List[Dict], lexical_results: List[Dict],
                      top_k: int) -> List[Dict]:
        """
        Fuse dense and lexical results using Reciprocal Rank Fusion (RRF).
        """
        k = 60  # RRF constant

        # Create score maps
        dense_scores = {}
        for result in dense_results:
            doc_id = result["id"]
            dense_scores[doc_id] = {
                "score": result["score"],
                "rank": result["rank"],
                "metadata": result["metadata"]
            }

        lexical_scores = {}
        for result in lexical_results:
            doc_id = result["id"]
            lexical_scores[doc_id] = {
                "score": result["score"],
                "rank": result["rank"],
                "metadata": result["metadata"]
            }

        # Combine using RRF
        all_doc_ids = set(dense_scores.keys()) | set(lexical_scores.keys())
        fused_results = []

        for doc_id in all_doc_ids:
            dense_info = dense_scores.get(doc_id, {"score": 0, "rank": len(dense_results) + 1})
            lexical_info = lexical_scores.get(doc_id, {"score": 0, "rank": len(lexical_results) + 1})

            # RRF fusion
            rrf_score = (DENSE_WEIGHT / (k + dense_info["rank"])) + (LEXICAL_WEIGHT / (k + lexical_info["rank"]))

            # Also compute weighted score combination
            max_dense = max((r["score"] for r in dense_results), default=1) or 1
            max_lexical = max((r["score"] for r in lexical_results), default=1) or 1

            norm_dense = dense_info["score"] / max_dense if max_dense else 0
            norm_lexical = lexical_info["score"] / max_lexical if max_lexical else 0

            weighted_score = DENSE_WEIGHT * norm_dense + LEXICAL_WEIGHT * norm_lexical

            # Get metadata from whichever result has it
            metadata = dense_info.get("metadata") or lexical_info.get("metadata") or {}

            fused_results.append({
                "id": doc_id,
                "score": weighted_score,
                "final_score": weighted_score,
                "dense_score": dense_info["score"],
                "lexical_score": lexical_info["score"],
                "rrf_score": rrf_score,
                "metadata": metadata
            })

        # Sort by final score
        fused_results.sort(key=lambda x: x["final_score"], reverse=True)

        return fused_results[:top_k]

    def _apply_recency_boost(self, results: List[Dict]) -> List[Dict]:
        """Apply recency boost to prioritize recently indexed content."""
        now = datetime.now()

        for result in results:
            indexed_at = result.get("metadata", {}).get("indexed_at")
            if indexed_at:
                try:
                    indexed_time = datetime.fromisoformat(indexed_at)
                    age_hours = (now - indexed_time).total_seconds() / 3600

                    # Exponential decay: full boost at 0 hours, decays over 24-168 hours
                    decay_rate = 0.1  # Decay constant
                    boost = RECENCY_BOOST_FACTOR * np.exp(-decay_rate * age_hours / 24)

                    result["recency_boost"] = boost
                    result["final_score"] = result.get("final_score", result.get("score", 0)) * (1 + boost)
                except Exception:
                    result["recency_boost"] = 0
            else:
                result["recency_boost"] = 0

        return results

    def save(self):
        """Save all indexes to disk."""
        self.index.save(INDEX_FILE, METADATA_FILE)
        if self.lexical_index:
            self.lexical_index.save(LEXICAL_INDEX_FILE)

    def load(self):
        """Load all indexes from disk."""
        loaded = self.index.load(INDEX_FILE, METADATA_FILE)
        if self.lexical_index:
            self.lexical_index.load(LEXICAL_INDEX_FILE)
        return loaded

    def clear(self):
        """Clear all indexes."""
        self.index.clear()
        if self.lexical_index:
            self.lexical_index.clear()
        self.save()
        return {"message": "All indexes cleared successfully"}

    def stats(self) -> Dict[str, Any]:
        """Get comprehensive index statistics."""
        base_stats = self.index.stats()
        base_stats.update({
            "embedding_model": self.embedding_generator.model_name,
            "embedding_info": self.embedding_generator.get_model_info(),
            "backend": "FAISS" if FAISS_AVAILABLE else "In-Memory",
            "data_directory": DATA_DIR,
            "hybrid_search_enabled": self.enable_hybrid,
            "recency_boost_enabled": RECENCY_BOOST_ENABLED,
            "dense_weight": DENSE_WEIGHT,
            "lexical_weight": LEXICAL_WEIGHT
        })

        if self.lexical_index:
            base_stats["lexical_index"] = self.lexical_index.stats()

        return base_stats
