"""
Tests for Vector Index functionality.

Includes tests for:
- EmbeddingGenerator with code-specific embeddings
- LexicalIndex for BM25 search
- Hybrid retrieval with RRF fusion
- Recency boost
- Enhanced metadata handling
"""

import pytest
import numpy as np
import tempfile
import os
from unittest.mock import Mock, patch
from datetime import datetime, timedelta

# Import the modules to test
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'services', 'vector_index'))

from services.vector_index.index import VectorIndex, EmbeddingGenerator, FAISSIndex, SimpleInMemoryIndex, LexicalIndex


class TestEmbeddingGenerator:
    """Test the EmbeddingGenerator functionality."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.generator = EmbeddingGenerator()
    
    def test_embedding_generator_initialization(self):
        """Test EmbeddingGenerator initializes correctly."""
        assert hasattr(self.generator, 'model')
        assert hasattr(self.generator, 'dimension')
        assert self.generator.dimension > 0
    
    def test_encode_single_text(self):
        """Test encoding a single text."""
        text = "This is a test sentence."
        embedding = self.generator.encode([text])
        
        assert isinstance(embedding, np.ndarray)
        assert embedding.shape == (1, self.generator.dimension)
        assert embedding.dtype == np.float32
    
    def test_encode_multiple_texts(self):
        """Test encoding multiple texts."""
        texts = [
            "This is the first sentence.",
            "This is the second sentence.",
            "This is the third sentence."
        ]
        embeddings = self.generator.encode(texts)
        
        assert isinstance(embeddings, np.ndarray)
        assert embeddings.shape == (3, self.generator.dimension)
        assert embeddings.dtype == np.float32
    
    def test_encode_empty_list(self):
        """Test encoding empty list."""
        embeddings = self.generator.encode([])

        assert isinstance(embeddings, np.ndarray)
        # Empty list returns empty array (shape may vary by implementation)
        assert embeddings.size == 0
    
    def test_encode_consistency(self):
        """Test that encoding the same text produces consistent results."""
        text = "Consistent test sentence."
        
        embedding1 = self.generator.encode([text])
        embedding2 = self.generator.encode([text])
        
        # Should be very similar (allowing for minor floating point differences)
        np.testing.assert_allclose(embedding1, embedding2, rtol=1e-5)
    
    def test_encode_different_texts(self):
        """Test that different texts produce different embeddings."""
        text1 = "This is about cats."
        text2 = "This is about dogs."

        embedding1 = self.generator.encode([text1])
        embedding2 = self.generator.encode([text2])

        # Should be different
        assert not np.allclose(embedding1, embedding2, rtol=1e-3)

    def test_encode_with_file_paths(self):
        """Test encoding with file paths for code detection."""
        texts = ["def hello(): pass", "function hello() { }"]
        file_paths = ["test.py", "test.js"]

        embeddings = self.generator.encode(texts, file_paths)

        assert isinstance(embeddings, np.ndarray)
        assert embeddings.shape[0] == 2

    def test_encode_single_convenience(self):
        """Test the encode_single convenience method."""
        text = "This is a single text to encode."

        embedding = self.generator.encode_single(text)

        assert isinstance(embedding, np.ndarray)
        assert embedding.shape == (self.generator.dimension,)

    def test_model_info(self):
        """Test getting model info."""
        info = self.generator.get_model_info()

        assert "primary_model" in info
        assert "primary_dimension" in info
        assert info["primary_dimension"] == self.generator.dimension

    def test_is_code_content_detection(self):
        """Test code content detection for specialized embeddings."""
        # Test with file paths
        code_content = "def hello(): pass"
        non_code_content = "This is a regular text document."

        # Code files should be detected as code
        assert self.generator._is_code_content(code_content, "test.py") == True
        assert self.generator._is_code_content(code_content, "app.js") == True

        # Non-code files should not be detected as code
        assert self.generator._is_code_content(non_code_content, "readme.md") == False
        assert self.generator._is_code_content(non_code_content, "doc.txt") == False


class TestLexicalIndex:
    """Test the LexicalIndex for BM25-style search."""

    def setup_method(self):
        """Set up test fixtures."""
        self.index = LexicalIndex()
        self.test_docs = [
            {"id": 0, "text": "Python is a high-level programming language", "meta": {"source": "python.txt"}},
            {"id": 1, "text": "JavaScript is used for web development", "meta": {"source": "js.txt"}},
            {"id": 2, "text": "Machine learning with Python and TensorFlow", "meta": {"source": "ml.txt"}},
            {"id": 3, "text": "React is a JavaScript framework for UI", "meta": {"source": "react.txt"}},
            {"id": 4, "text": "Natural language processing with transformers", "meta": {"source": "nlp.txt"}},
        ]

    def test_lexical_index_initialization(self):
        """Test LexicalIndex initializes correctly."""
        assert len(self.index.inverted_index) == 0
        assert self.index.total_docs == 0
        assert self.index.k1 == 1.5
        assert self.index.b == 0.75

    def test_add_documents(self):
        """Test adding documents to lexical index."""
        for doc in self.test_docs:
            self.index.add(doc["id"], doc["text"], doc["meta"])

        assert self.index.total_docs == 5
        assert len(self.index.inverted_index) > 0
        assert "python" in self.index.inverted_index
        # JavaScript is split into "java" and "script" by camelCase tokenization
        assert "java" in self.index.inverted_index or "script" in self.index.inverted_index

    def test_search_basic(self):
        """Test basic BM25 search."""
        for doc in self.test_docs:
            self.index.add(doc["id"], doc["text"], doc["meta"])

        results = self.index.search("Python programming", top_k=3)

        assert len(results) > 0
        assert results[0]["score"] > 0
        # Python documents should rank higher
        assert "python" in results[0]["metadata"]["source"].lower()

    def test_search_relevance(self):
        """Test that search returns relevant results."""
        for doc in self.test_docs:
            self.index.add(doc["id"], doc["text"], doc["meta"])

        # Search for JavaScript-related content
        results = self.index.search("JavaScript web development React", top_k=5)

        assert len(results) > 0
        # JavaScript or React docs should be in top results
        top_sources = [r["metadata"]["source"] for r in results[:2]]
        assert any("js" in s or "react" in s for s in top_sources)

    def test_search_empty_query(self):
        """Test search with empty query."""
        for doc in self.test_docs:
            self.index.add(doc["id"], doc["text"], doc["meta"])

        results = self.index.search("", top_k=3)
        assert len(results) == 0

    def test_search_no_match(self):
        """Test search with no matching terms."""
        for doc in self.test_docs:
            self.index.add(doc["id"], doc["text"], doc["meta"])

        results = self.index.search("kubernetes docker containers", top_k=3)
        # Should return empty or low-scoring results
        assert len(results) == 0 or all(r["score"] < 0.5 for r in results)

    def test_tokenization_camelcase(self):
        """Test tokenization handles camelCase."""
        tokens = self.index._tokenize("calculateUserScore processData")

        assert "calculate" in tokens
        assert "user" in tokens
        assert "score" in tokens
        assert "process" in tokens
        assert "data" in tokens

    def test_tokenization_snake_case(self):
        """Test tokenization handles snake_case."""
        tokens = self.index._tokenize("user_name get_user_data")

        assert "user" in tokens
        assert "name" in tokens
        assert "get" in tokens
        assert "data" in tokens

    def test_clear_index(self):
        """Test clearing lexical index."""
        for doc in self.test_docs:
            self.index.add(doc["id"], doc["text"], doc["meta"])

        assert self.index.total_docs == 5

        self.index.clear()

        assert self.index.total_docs == 0
        assert len(self.index.inverted_index) == 0

    def test_stats(self):
        """Test getting index statistics."""
        for doc in self.test_docs:
            self.index.add(doc["id"], doc["text"], doc["meta"])

        stats = self.index.stats()

        assert stats["total_docs"] == 5
        assert stats["unique_terms"] > 0
        assert stats["avg_doc_length"] > 0
        assert stats["index_type"] == "BM25 Lexical"

    def test_save_and_load(self):
        """Test saving and loading lexical index."""
        for doc in self.test_docs:
            self.index.add(doc["id"], doc["text"], doc["meta"])

        with tempfile.NamedTemporaryFile(delete=False, suffix=".json") as tmp:
            tmp_path = tmp.name

        try:
            self.index.save(tmp_path)

            new_index = LexicalIndex()
            loaded = new_index.load(tmp_path)

            assert loaded == True
            assert new_index.total_docs == 5

            # Search should still work
            results = new_index.search("Python", top_k=3)
            assert len(results) > 0
        finally:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)


class TestSimpleInMemoryIndex:
    """Test the SimpleInMemoryIndex functionality."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.index = SimpleInMemoryIndex(dimension=384)
        self.test_embeddings = np.random.rand(5, 384).astype(np.float32)
        self.test_metadata = [
            {"text": "First document", "source": "doc1.txt"},
            {"text": "Second document", "source": "doc2.txt"},
            {"text": "Third document", "source": "doc3.txt"},
            {"text": "Fourth document", "source": "doc4.txt"},
            {"text": "Fifth document", "source": "doc5.txt"}
        ]
    
    def test_index_initialization(self):
        """Test SimpleInMemoryIndex initializes correctly."""
        assert self.index.dimension == 384
        assert len(self.index.embeddings) == 0
        assert len(self.index.metadata) == 0
    
    def test_add_single_embedding(self):
        """Test adding a single embedding."""
        embedding = self.test_embeddings[0:1]
        metadata = [self.test_metadata[0]]
        
        self.index.add(embedding, metadata)
        
        assert len(self.index.embeddings) == 1
        assert len(self.index.metadata) == 1
        assert self.index.metadata[0] == metadata[0]
    
    def test_add_multiple_embeddings(self):
        """Test adding multiple embeddings."""
        self.index.add(self.test_embeddings, self.test_metadata)
        
        assert len(self.index.embeddings) == 5
        assert len(self.index.metadata) == 5
        assert self.index.metadata == self.test_metadata
    
    def test_search_basic(self):
        """Test basic search functionality."""
        # Add embeddings to index
        self.index.add(self.test_embeddings, self.test_metadata)

        # Search with the first embedding (should return itself as top result)
        query_embedding = self.test_embeddings[0]
        results = self.index.search(query_embedding, top_k=3)

        assert len(results) == 3
        assert results[0]["id"] == 0  # First result should be index 0
        assert results[0]["score"] > 0.99  # Should have very high similarity to itself

    def test_search_empty_index(self):
        """Test search on empty index."""
        query_embedding = np.random.rand(384).astype(np.float32)
        results = self.index.search(query_embedding, top_k=5)
        
        assert len(results) == 0
    
    def test_search_k_larger_than_index(self):
        """Test search with k larger than index size."""
        # Add only 2 embeddings
        self.index.add(self.test_embeddings[:2], self.test_metadata[:2])

        query_embedding = self.test_embeddings[0]
        results = self.index.search(query_embedding, top_k=10)

        # Should return only 2 results
        assert len(results) == 2
    
    def test_clear_index(self):
        """Test clearing the index."""
        self.index.add(self.test_embeddings, self.test_metadata)
        assert len(self.index.embeddings) == 5
        
        self.index.clear()
        assert len(self.index.embeddings) == 0
        assert len(self.index.metadata) == 0
    
    def test_stats(self):
        """Test getting index statistics."""
        stats = self.index.stats()
        assert stats["total_vectors"] == 0
        assert stats["dimension"] == 384

        self.index.add(self.test_embeddings, self.test_metadata)
        stats = self.index.stats()
        assert stats["total_vectors"] == 5
        assert stats["dimension"] == 384


class TestFAISSIndex:
    """Test the FAISSIndex functionality (if FAISS is available)."""
    
    def setup_method(self):
        """Set up test fixtures."""
        try:
            self.index = FAISSIndex(dimension=384)
            self.faiss_available = True
        except ImportError:
            self.faiss_available = False
            pytest.skip("FAISS not available")
        
        self.test_embeddings = np.random.rand(5, 384).astype(np.float32)
        self.test_metadata = [
            {"text": "First document", "source": "doc1.txt"},
            {"text": "Second document", "source": "doc2.txt"},
            {"text": "Third document", "source": "doc3.txt"},
            {"text": "Fourth document", "source": "doc4.txt"},
            {"text": "Fifth document", "source": "doc5.txt"}
        ]
    
    def test_faiss_index_initialization(self):
        """Test FAISSIndex initializes correctly."""
        if not self.faiss_available:
            pytest.skip("FAISS not available")
        
        assert self.index.dimension == 384
        assert hasattr(self.index, 'index')
        assert hasattr(self.index, 'metadata')
    
    def test_faiss_add_and_search(self):
        """Test adding embeddings and searching with FAISS."""
        if not self.faiss_available:
            pytest.skip("FAISS not available")

        # Add embeddings
        self.index.add(self.test_embeddings, self.test_metadata)

        # Search with the exact same embedding that was added
        query_embedding = self.test_embeddings[0].copy()
        results = self.index.search(query_embedding, top_k=3)

        assert len(results) == 3
        # The first result should be the query itself (id=0)
        # Since we're searching for an exact match, it should be in the results
        result_ids = [r["id"] for r in results]
        assert 0 in result_ids, f"Query embedding (id=0) not found in results: {result_ids}"

        # Find the matching result
        matching_result = next(r for r in results if r["id"] == 0)
        # For normalized vectors with inner product, identical vectors should have score close to 1.0
        # Allow some tolerance for floating point precision and HNSW approximation
        assert matching_result["score"] > 0.95, f"Expected score > 0.95, got {matching_result['score']}"

    def test_faiss_save_load(self):
        """Test saving and loading FAISS index."""
        if not self.faiss_available:
            pytest.skip("FAISS not available")

        # Add some data
        self.index.add(self.test_embeddings, self.test_metadata)

        # Save to temporary files
        with tempfile.NamedTemporaryFile(delete=False, suffix=".bin") as tmp_file:
            index_path = tmp_file.name
        metadata_path = index_path.replace(".bin", "_metadata.json")

        try:
            self.index.save(index_path, metadata_path)

            # Create new index and load
            new_index = FAISSIndex(dimension=384)
            loaded = new_index.load(index_path, metadata_path)

            assert loaded == True

            # Test that loaded index works
            query_embedding = self.test_embeddings[0]
            results = new_index.search(query_embedding, top_k=3)

            assert len(results) == 3
            assert results[0]["id"] == 0

        finally:
            # Clean up
            if os.path.exists(index_path):
                os.unlink(index_path)
            if os.path.exists(metadata_path):
                os.unlink(metadata_path)


class TestVectorIndex:
    """Test the main VectorIndex class."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.index = VectorIndex()
    
    def test_vector_index_initialization(self):
        """Test VectorIndex initializes correctly."""
        assert hasattr(self.index, 'embedding_generator')
        assert hasattr(self.index, 'index')
        assert hasattr(self.index, 'insert')
        assert hasattr(self.index, 'search')
    
    def test_insert_single_chunk(self):
        """Test inserting a single text chunk."""
        self.index.clear()  # Clear any existing data
        chunk = {
            "text": "This is a test document about machine learning.",
            "meta": {"source": "test.txt", "chunk_id": "1", "file_path": "test.txt"}
        }

        result = self.index.insert([chunk])

        assert "indexed_count" in result
        assert result["indexed_count"] == 1

    def test_insert_multiple_chunks(self):
        """Test inserting multiple text chunks."""
        self.index.clear()  # Clear any existing data
        chunks = [
            {
                "text": "First document about AI.",
                "meta": {"source": "doc1.txt", "chunk_id": "1", "file_path": "doc1.txt"}
            },
            {
                "text": "Second document about ML.",
                "meta": {"source": "doc2.txt", "chunk_id": "2", "file_path": "doc2.txt"}
            },
            {
                "text": "Third document about NLP.",
                "meta": {"source": "doc3.txt", "chunk_id": "3", "file_path": "doc3.txt"}
            }
        ]

        result = self.index.insert(chunks)

        assert result["indexed_count"] == 3
    
    def test_search_after_insert(self):
        """Test searching after inserting documents."""
        self.index.clear()  # Clear any existing data
        chunks = [
            {
                "text": "Machine learning is a subset of artificial intelligence.",
                "meta": {"source": "ml.txt", "chunk_id": "1", "file_path": "ml.txt"}
            },
            {
                "text": "Natural language processing deals with text analysis.",
                "meta": {"source": "nlp.txt", "chunk_id": "2", "file_path": "nlp.txt"}
            },
            {
                "text": "Computer vision focuses on image recognition.",
                "meta": {"source": "cv.txt", "chunk_id": "3", "file_path": "cv.txt"}
            }
        ]

        # Insert chunks
        self.index.insert(chunks)

        # Search for machine learning related content
        search_response = self.index.search("artificial intelligence and machine learning", top_k=2)

        assert "results" in search_response
        results = search_response["results"]
        assert len(results) <= 2
        assert len(results) > 0

        # Check result format
        for result in results:
            assert "text" in result
            assert "score" in result
            assert "meta" in result
            assert "rank" in result
            assert isinstance(result["score"], float)
            assert isinstance(result["rank"], int)

    def test_search_empty_index(self):
        """Test searching an empty index."""
        self.index.clear()  # Clear any existing data
        search_response = self.index.search("test query", top_k=5)
        assert len(search_response["results"]) == 0
    
    def test_stats(self):
        """Test getting index statistics."""
        stats = self.index.stats()

        assert "total_vectors" in stats
        assert "dimension" in stats
        assert "backend" in stats
        assert isinstance(stats["total_vectors"], int)
        assert isinstance(stats["dimension"], int)
        assert isinstance(stats["backend"], str)
    
    def test_clear_index(self):
        """Test clearing the index."""
        # Insert some data
        chunks = [
            {
                "text": "Test document for clearing",
                "meta": {"source": "test.txt", "chunk_id": "1", "file_path": "test.txt"}
            }
        ]
        self.index.insert(chunks)

        # Verify data exists
        stats_before = self.index.stats()
        assert stats_before["total_vectors"] > 0

        # Clear index
        self.index.clear()

        # Verify index is empty
        stats_after = self.index.stats()
        assert stats_after["total_vectors"] == 0

    def test_insert_empty_chunks(self):
        """Test inserting empty chunks list."""
        result = self.index.insert([])

        assert result["indexed_count"] == 0

    def test_insert_chunks_with_empty_text(self):
        """Test inserting chunks with empty text."""
        self.index.clear()  # Clear any existing data
        chunks = [
            {
                "text": "",
                "meta": {"source": "empty.txt", "chunk_id": "1", "file_path": "empty.txt"}
            },
            {
                "text": "Valid text content for testing",
                "meta": {"source": "valid.txt", "chunk_id": "2", "file_path": "valid.txt"}
            }
        ]

        result = self.index.insert(chunks)

        # Should skip empty text and only index valid content
        assert result["indexed_count"] >= 1


class TestVectorIndexHybridSearch:
    """Test hybrid search functionality in VectorIndex."""

    def setup_method(self):
        """Set up test fixtures with hybrid search enabled."""
        self.index = VectorIndex(enable_hybrid=True)
        self.index.clear()  # Clear any existing data

    def test_hybrid_search_initialization(self):
        """Test VectorIndex with hybrid search enabled."""
        assert self.index.enable_hybrid == True
        assert self.index.lexical_index is not None

    def test_hybrid_search_disabled(self):
        """Test VectorIndex with hybrid search disabled."""
        index = VectorIndex(enable_hybrid=False)
        index.clear()

        assert index.enable_hybrid == False
        assert index.lexical_index is None

    def test_hybrid_search_insert_updates_lexical(self):
        """Test that insert updates both vector and lexical indexes."""
        chunks = [
            {"text": "Python machine learning TensorFlow", "meta": {"file_path": "ml.py"}},
            {"text": "React JavaScript frontend development", "meta": {"file_path": "app.jsx"}}
        ]

        result = self.index.insert(chunks)

        assert result["indexed_count"] == 2
        assert result["hybrid_enabled"] == True

        # Lexical index should have docs (at least the ones we just added)
        assert self.index.lexical_index.total_docs >= 2

    def test_hybrid_search_combines_results(self):
        """Test that hybrid search combines vector and lexical results."""
        # Insert documents with distinctive keywords
        chunks = [
            {"text": "def calculate_fibonacci(n): return fib(n-1) + fib(n-2)", "meta": {"file_path": "math.py"}},
            {"text": "The Fibonacci sequence is a mathematical pattern", "meta": {"file_path": "docs.md"}},
            {"text": "async function fetchData() { return await api.get() }", "meta": {"file_path": "api.js"}}
        ]

        self.index.insert(chunks)

        # Search should use hybrid retrieval
        results = self.index.search("Fibonacci function", top_k=3, enable_hybrid=True)

        assert len(results["results"]) > 0
        assert results["search_type"] == "hybrid"

        # Results should have both dense and lexical scores
        for r in results["results"]:
            assert "dense_score" in r
            assert "lexical_score" in r

    def test_dense_only_search(self):
        """Test search with hybrid disabled at query time."""
        chunks = [
            {"text": "Python programming is fun", "meta": {"file_path": "intro.py"}}
        ]
        self.index.insert(chunks)

        results = self.index.search("Python programming", enable_hybrid=False)

        assert results["search_type"] == "dense"

    def test_search_result_format(self):
        """Test the enhanced search result format."""
        chunks = [
            {"text": "Machine learning algorithms", "meta": {"file_path": "ml.py"}}
        ]
        self.index.insert(chunks)

        results = self.index.search("machine learning", top_k=1)

        assert "query" in results
        assert "results" in results
        assert "total_results" in results
        assert "timestamp" in results
        assert "search_type" in results

        if len(results["results"]) > 0:
            result = results["results"][0]
            assert "text" in result
            assert "score" in result
            assert "rank" in result
            assert "content_type" in result


class TestRecencyBoost:
    """Test recency boost functionality."""

    def setup_method(self):
        """Set up test fixtures."""
        self.index = VectorIndex(enable_hybrid=True)

    def test_recency_boost_recent_content(self):
        """Test that recent content gets boosted."""
        # Insert a document
        chunks = [{"text": "Recent code update for API", "meta": {"file_path": "api.py"}}]
        self.index.insert(chunks)

        # Search with recency boost
        results = self.index.search("API update", recency_boost=True)

        assert results["recency_boost_applied"] == True

        if len(results["results"]) > 0:
            # Recently indexed content should have recency boost
            assert "recency_boost" in results["results"][0]

    def test_recency_boost_disabled(self):
        """Test search without recency boost."""
        chunks = [{"text": "Some code content", "meta": {"file_path": "code.py"}}]
        self.index.insert(chunks)

        results = self.index.search("code content", recency_boost=False)

        assert results["recency_boost_applied"] == False


class TestContentTypeDetection:
    """Test content type detection in VectorIndex."""

    def setup_method(self):
        """Set up test fixtures."""
        self.index = VectorIndex(enable_hybrid=True)

    def test_detect_test_content(self):
        """Test detection of test files."""
        chunks = [{"text": "def test_function(): assert True", "meta": {"file_path": "tests/test_api.py"}}]
        result = self.index.insert(chunks)

        # The content type should be detected during insert
        assert result["indexed_count"] == 1

    def test_detect_config_content(self):
        """Test detection of config files."""
        chunks = [{"text": '{"key": "value"}', "meta": {"file_path": "config/settings.json"}}]
        result = self.index.insert(chunks)

        assert result["indexed_count"] == 1

    def test_detect_documentation(self):
        """Test detection of documentation files."""
        chunks = [{"text": "# API Documentation\n\nThis is the API docs.", "meta": {"file_path": "docs/api.md"}}]
        result = self.index.insert(chunks)

        assert result["indexed_count"] == 1


class TestVectorIndexIntegration:
    """Integration tests for the vector index system."""

    def test_end_to_end_workflow(self):
        """Test complete workflow from insertion to search."""
        index = VectorIndex(enable_hybrid=True)

        # Clear any existing data first
        index.clear()

        # Sample documents
        documents = [
            {
                "text": "Python is a high-level programming language known for its simplicity and readability.",
                "meta": {"source": "python_intro.txt", "chunk_id": "1", "language": "python", "file_path": "intro.py"}
            },
            {
                "text": "JavaScript is a versatile programming language used for web development.",
                "meta": {"source": "js_intro.txt", "chunk_id": "2", "language": "javascript", "file_path": "intro.js"}
            },
            {
                "text": "Machine learning algorithms can automatically learn patterns from data.",
                "meta": {"source": "ml_basics.txt", "chunk_id": "3", "topic": "machine_learning", "file_path": "ml.py"}
            },
            {
                "text": "React is a JavaScript library for building user interfaces.",
                "meta": {"source": "react_intro.txt", "chunk_id": "4", "framework": "react", "file_path": "app.jsx"}
            }
        ]

        # Insert documents
        insert_result = index.insert(documents)
        assert insert_result["indexed_count"] == 4

        # Test various searches with hybrid retrieval
        test_queries = [
            "Python programming",
            "web development JavaScript",
            "machine learning patterns",
            "React user interface"
        ]

        for query in test_queries:
            results = index.search(query, top_k=2)

            assert len(results["results"]) > 0
            # Top result should have reasonable similarity
            top_result = results["results"][0]
            assert top_result["score"] > 0

            # Check enhanced result format
            assert "meta" in top_result
            assert "dense_score" in top_result
            assert "content_type" in top_result

        # Test statistics (enhanced)
        stats = index.stats()
        assert stats["total_vectors"] == 4
        assert stats["dimension"] > 0
        assert "hybrid_search_enabled" in stats
        assert "lexical_index" in stats

        # Test clearing
        index.clear()
        stats_after_clear = index.stats()
        assert stats_after_clear["total_vectors"] == 0

    def test_hybrid_vs_dense_comparison(self):
        """Test that hybrid search can find results dense search might miss."""
        index = VectorIndex(enable_hybrid=True)

        # Insert documents where keyword matching is important
        documents = [
            {"text": "The calculateUserMetrics function computes user statistics", "meta": {"file_path": "metrics.py"}},
            {"text": "User interface for displaying metrics dashboard", "meta": {"file_path": "ui.py"}},
        ]
        index.insert(documents)

        # Search for exact function name (lexical should help)
        hybrid_results = index.search("calculateUserMetrics", enable_hybrid=True)
        dense_results = index.search("calculateUserMetrics", enable_hybrid=False)

        # Both should find results, but hybrid should favor exact matches
        assert len(hybrid_results["results"]) > 0
        assert len(dense_results["results"]) > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
