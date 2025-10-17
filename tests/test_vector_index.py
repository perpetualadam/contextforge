"""
Tests for Vector Index functionality.
"""

import pytest
import numpy as np
import tempfile
import os
from unittest.mock import Mock, patch

# Import the modules to test
import sys
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'services', 'vector_index'))

from index import VectorIndex, EmbeddingGenerator, FAISSIndex, SimpleInMemoryIndex


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
        assert embeddings.shape == (0, self.generator.dimension)
    
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
        query_embedding = self.test_embeddings[0:1]
        results = self.index.search(query_embedding, k=3)
        
        assert len(results) == 3
        assert results[0][1] == 0  # First result should be index 0
        assert results[0][0] > 0.99  # Should have very high similarity to itself
    
    def test_search_empty_index(self):
        """Test search on empty index."""
        query_embedding = np.random.rand(1, 384).astype(np.float32)
        results = self.index.search(query_embedding, k=5)
        
        assert len(results) == 0
    
    def test_search_k_larger_than_index(self):
        """Test search with k larger than index size."""
        # Add only 2 embeddings
        self.index.add(self.test_embeddings[:2], self.test_metadata[:2])
        
        query_embedding = self.test_embeddings[0:1]
        results = self.index.search(query_embedding, k=10)
        
        # Should return only 2 results
        assert len(results) == 2
    
    def test_clear_index(self):
        """Test clearing the index."""
        self.index.add(self.test_embeddings, self.test_metadata)
        assert len(self.index.embeddings) == 5
        
        self.index.clear()
        assert len(self.index.embeddings) == 0
        assert len(self.index.metadata) == 0
    
    def test_get_stats(self):
        """Test getting index statistics."""
        stats = self.index.get_stats()
        assert stats["total_vectors"] == 0
        assert stats["dimension"] == 384
        
        self.index.add(self.test_embeddings, self.test_metadata)
        stats = self.index.get_stats()
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
        
        # Search
        query_embedding = self.test_embeddings[0:1]
        results = self.index.search(query_embedding, k=3)
        
        assert len(results) == 3
        assert results[0][1] == 0  # First result should be index 0
        assert results[0][0] > 0.99  # Should have very high similarity
    
    def test_faiss_save_load(self):
        """Test saving and loading FAISS index."""
        if not self.faiss_available:
            pytest.skip("FAISS not available")
        
        # Add some data
        self.index.add(self.test_embeddings, self.test_metadata)
        
        # Save to temporary file
        with tempfile.NamedTemporaryFile(delete=False) as tmp_file:
            tmp_path = tmp_file.name
        
        try:
            self.index.save(tmp_path)
            
            # Create new index and load
            new_index = FAISSIndex(dimension=384)
            new_index.load(tmp_path)
            
            # Test that loaded index works
            query_embedding = self.test_embeddings[0:1]
            results = new_index.search(query_embedding, k=3)
            
            assert len(results) == 3
            assert results[0][1] == 0
            
        finally:
            # Clean up
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
            if os.path.exists(tmp_path + ".meta"):
                os.unlink(tmp_path + ".meta")


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
        chunk = {
            "text": "This is a test document about machine learning.",
            "meta": {"source": "test.txt", "chunk_id": "1"}
        }
        
        result = self.index.insert([chunk])
        
        assert "chunks_processed" in result
        assert "chunks_indexed" in result
        assert result["chunks_processed"] == 1
        assert result["chunks_indexed"] == 1
    
    def test_insert_multiple_chunks(self):
        """Test inserting multiple text chunks."""
        chunks = [
            {
                "text": "First document about AI.",
                "meta": {"source": "doc1.txt", "chunk_id": "1"}
            },
            {
                "text": "Second document about ML.",
                "meta": {"source": "doc2.txt", "chunk_id": "2"}
            },
            {
                "text": "Third document about NLP.",
                "meta": {"source": "doc3.txt", "chunk_id": "3"}
            }
        ]
        
        result = self.index.insert(chunks)
        
        assert result["chunks_processed"] == 3
        assert result["chunks_indexed"] == 3
    
    def test_search_after_insert(self):
        """Test searching after inserting documents."""
        chunks = [
            {
                "text": "Machine learning is a subset of artificial intelligence.",
                "meta": {"source": "ml.txt", "chunk_id": "1"}
            },
            {
                "text": "Natural language processing deals with text analysis.",
                "meta": {"source": "nlp.txt", "chunk_id": "2"}
            },
            {
                "text": "Computer vision focuses on image recognition.",
                "meta": {"source": "cv.txt", "chunk_id": "3"}
            }
        ]
        
        # Insert chunks
        self.index.insert(chunks)
        
        # Search for machine learning related content
        results = self.index.search("artificial intelligence and machine learning", top_k=2)
        
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
        results = self.index.search("test query", top_k=5)
        assert len(results) == 0
    
    def test_get_stats(self):
        """Test getting index statistics."""
        stats = self.index.get_stats()
        
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
                "text": "Test document",
                "meta": {"source": "test.txt", "chunk_id": "1"}
            }
        ]
        self.index.insert(chunks)
        
        # Verify data exists
        stats_before = self.index.get_stats()
        assert stats_before["total_vectors"] > 0
        
        # Clear index
        self.index.clear()
        
        # Verify index is empty
        stats_after = self.index.get_stats()
        assert stats_after["total_vectors"] == 0
    
    def test_insert_empty_chunks(self):
        """Test inserting empty chunks list."""
        result = self.index.insert([])
        
        assert result["chunks_processed"] == 0
        assert result["chunks_indexed"] == 0
    
    def test_insert_chunks_with_empty_text(self):
        """Test inserting chunks with empty text."""
        chunks = [
            {
                "text": "",
                "meta": {"source": "empty.txt", "chunk_id": "1"}
            },
            {
                "text": "Valid text content",
                "meta": {"source": "valid.txt", "chunk_id": "2"}
            }
        ]
        
        result = self.index.insert(chunks)
        
        # Should process both but may skip empty text
        assert result["chunks_processed"] == 2
        # Implementation may choose to skip empty text chunks
        assert result["chunks_indexed"] >= 1


class TestVectorIndexIntegration:
    """Integration tests for the vector index system."""
    
    def test_end_to_end_workflow(self):
        """Test complete workflow from insertion to search."""
        index = VectorIndex()
        
        # Sample documents
        documents = [
            {
                "text": "Python is a high-level programming language known for its simplicity and readability.",
                "meta": {"source": "python_intro.txt", "chunk_id": "1", "language": "python"}
            },
            {
                "text": "JavaScript is a versatile programming language used for web development.",
                "meta": {"source": "js_intro.txt", "chunk_id": "2", "language": "javascript"}
            },
            {
                "text": "Machine learning algorithms can automatically learn patterns from data.",
                "meta": {"source": "ml_basics.txt", "chunk_id": "3", "topic": "machine_learning"}
            },
            {
                "text": "React is a JavaScript library for building user interfaces.",
                "meta": {"source": "react_intro.txt", "chunk_id": "4", "framework": "react"}
            }
        ]
        
        # Insert documents
        insert_result = index.insert(documents)
        assert insert_result["chunks_processed"] == 4
        assert insert_result["chunks_indexed"] == 4
        
        # Test various searches
        test_queries = [
            ("Python programming", "python"),
            ("web development JavaScript", "javascript"),
            ("machine learning patterns", "machine_learning"),
            ("React user interface", "react")
        ]
        
        for query, expected_topic in test_queries:
            results = index.search(query, top_k=2)
            
            assert len(results) > 0
            # Top result should be relevant
            top_result = results[0]
            assert top_result["score"] > 0.1  # Should have reasonable similarity
            
            # Check that metadata is preserved
            assert "meta" in top_result
            assert "source" in top_result["meta"]
            assert "chunk_id" in top_result["meta"]
        
        # Test statistics
        stats = index.get_stats()
        assert stats["total_vectors"] == 4
        assert stats["dimension"] > 0
        
        # Test clearing
        index.clear()
        stats_after_clear = index.get_stats()
        assert stats_after_clear["total_vectors"] == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
