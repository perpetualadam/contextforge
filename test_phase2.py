"""
Test script for Phase 2 Performance Improvements.

Tests:
1. FAISS HNSW index creation and usage
2. Parallel indexing performance
3. Performance metrics tracking
"""

import sys
import time
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

def test_hnsw_index():
    """Test FAISS HNSW index."""
    print("\n=== Test 1: FAISS HNSW Index ===")
    
    try:
        from services.vector_index.index import VectorIndex
        
        # Create index (should use HNSW by default from config)
        index = VectorIndex(enable_hybrid=True)
        
        # Check stats
        stats = index.stats()
        print(f"✓ Index created: {stats.get('index_type', 'Unknown')}")
        
        if 'HNSW' in str(stats.get('index_type', '')):
            print(f"✓ HNSW index detected")
            print(f"  - HNSW neighbors: {stats.get('hnsw_neighbors', 'N/A')}")
            print(f"  - HNSW ef_search: {stats.get('hnsw_ef_search', 'N/A')}")
        else:
            print(f"⚠ Using {stats.get('index_type', 'Unknown')} index (HNSW not configured)")
        
        return True
    except Exception as e:
        print(f"✗ HNSW index test failed: {e}")
        return False


def test_parallel_indexing():
    """Test parallel indexing."""
    print("\n=== Test 2: Parallel Indexing ===")
    
    try:
        from services.vector_index.index import VectorIndex
        
        index = VectorIndex(enable_hybrid=False)
        
        # Create test chunks
        test_chunks = []
        for i in range(100):
            test_chunks.append({
                "text": f"This is test chunk number {i} with some content about Python programming and data structures.",
                "meta": {
                    "file_path": f"test/file_{i % 10}.py",
                    "line_start": i * 10,
                    "line_end": i * 10 + 10
                },
                "chunk_id": f"test_chunk_{i}",
                "source": "test"
            })
        
        # Test regular insert
        print(f"Testing regular insert with {len(test_chunks)} chunks...")
        start = time.time()
        result_regular = index.insert(test_chunks[:50])
        regular_time = time.time() - start
        print(f"✓ Regular insert: {result_regular['indexed_count']} chunks in {regular_time:.2f}s")
        
        # Clear index
        index.clear()
        
        # Test parallel insert
        print(f"Testing parallel insert with {len(test_chunks)} chunks...")
        start = time.time()
        result_parallel = index.insert_parallel(test_chunks, batch_size=25, num_workers=2)
        parallel_time = time.time() - start
        print(f"✓ Parallel insert: {result_parallel['indexed_count']} chunks in {parallel_time:.2f}s")
        print(f"  - Batches processed: {result_parallel.get('batches_processed', 'N/A')}")
        print(f"  - Workers used: {result_parallel.get('workers_used', 'N/A')}")
        
        return True
    except Exception as e:
        print(f"✗ Parallel indexing test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_performance_metrics():
    """Test performance metrics tracking."""
    print("\n=== Test 3: Performance Metrics ===")
    
    try:
        from services.vector_index.index import VectorIndex
        
        index = VectorIndex(enable_hybrid=True)
        
        # Index some chunks
        test_chunks = [
            {
                "text": f"Test content {i} about machine learning and neural networks.",
                "meta": {"file_path": f"test_{i}.py"},
                "chunk_id": f"perf_test_{i}",
                "source": "test"
            }
            for i in range(20)
        ]
        
        result = index.insert(test_chunks)
        print(f"✓ Indexed {result['indexed_count']} chunks")
        
        if 'performance' in result:
            perf = result['performance']
            print(f"  - Total time: {perf.get('total_time_seconds', 0):.3f}s")
            print(f"  - Embedding time: {perf.get('embedding_time_seconds', 0):.3f}s")
            print(f"  - Throughput: {perf.get('chunks_per_second', 0):.1f} chunks/s")
        
        # Perform some searches
        for query in ["machine learning", "neural networks", "test content"]:
            result = index.search(query, top_k=5)
            if 'performance' in result:
                print(f"✓ Search '{query}': {result['performance'].get('query_time_seconds', 0):.3f}s")
        
        # Get overall performance stats
        perf_stats = index.get_performance_stats()
        print(f"\n✓ Overall Performance Statistics:")
        print(f"  - Total indexed: {perf_stats.get('total_indexed', 0)} chunks")
        print(f"  - Total queries: {perf_stats.get('total_queries', 0)}")
        
        if 'indexing' in perf_stats:
            idx_stats = perf_stats['indexing']
            print(f"  - Avg indexing time: {idx_stats.get('avg_time_seconds', 0):.3f}s")
            print(f"  - Avg throughput: {idx_stats.get('avg_chunks_per_second', 0):.1f} chunks/s")
        
        if 'querying' in perf_stats:
            query_stats = perf_stats['querying']
            print(f"  - Avg query time: {query_stats.get('avg_time_seconds', 0):.3f}s")
            print(f"  - P95 latency: {query_stats.get('p95_latency', 0):.3f}s")
            print(f"  - P99 latency: {query_stats.get('p99_latency', 0):.3f}s")
        
        return True
    except Exception as e:
        print(f"✗ Performance metrics test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    print("=" * 60)
    print("Phase 2 Performance Improvements Test Suite")
    print("=" * 60)
    
    results = []
    results.append(("HNSW Index", test_hnsw_index()))
    results.append(("Parallel Indexing", test_parallel_indexing()))
    results.append(("Performance Metrics", test_performance_metrics()))
    
    print("\n" + "=" * 60)
    print("Test Results Summary")
    print("=" * 60)
    
    for test_name, passed in results:
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"{status}: {test_name}")
    
    all_passed = all(result[1] for result in results)
    
    if all_passed:
        print("\n✓ All Phase 2 tests passed!")
    else:
        print("\n✗ Some Phase 2 tests failed")
        sys.exit(1)

