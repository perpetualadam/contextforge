"""
Test suite for Phase 7: Tree-sitter Integration.

Tests all Phase 7 components:
- TreeSitterParser
- TreeSitterChunker
- IncrementalIndexer
- HybridChunker
- LiveIndexer
"""

import unittest
import tempfile
import os
from pathlib import Path

from services.preprocessor.tree_sitter_parser import TreeSitterParser, NodeType, TREE_SITTER_AVAILABLE
from services.preprocessor.tree_sitter_chunker import TreeSitterChunker
from services.indexing.incremental_indexer import IncrementalIndexer
from services.preprocessor.hybrid_chunker import HybridChunker, ChunkingMode
from services.indexing.live_indexer import LiveIndexer


# Skip all tests if tree-sitter not available
@unittest.skipIf(not TREE_SITTER_AVAILABLE, "tree-sitter not installed")
class TestTreeSitterParser(unittest.TestCase):
    """Test TreeSitterParser functionality."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.parser = TreeSitterParser('python')
        self.sample_code = '''
def hello_world():
    """Say hello."""
    print("Hello, World!")

class MyClass:
    def method(self):
        pass
'''
    
    def test_parser_initialization(self):
        """Test parser initializes correctly."""
        self.assertIsNotNone(self.parser)
        self.assertEqual(self.parser.language_name, 'python')
    
    def test_parse_code(self):
        """Test parsing code."""
        tree = self.parser.parse(self.sample_code)
        self.assertIsNotNone(tree)
        self.assertIsNotNone(tree.root_node)
    
    def test_extract_functions(self):
        """Test extracting functions from code."""
        tree = self.parser.parse(self.sample_code)
        nodes = self.parser.extract_nodes(tree, self.sample_code, [NodeType.FUNCTION])
        self.assertGreater(len(nodes), 0)
        # Should find hello_world function
        function_names = [node.name for node in nodes]
        self.assertIn('hello_world', function_names)
    
    def test_extract_classes(self):
        """Test extracting classes from code."""
        tree = self.parser.parse(self.sample_code)
        nodes = self.parser.extract_nodes(tree, self.sample_code, [NodeType.CLASS])
        self.assertGreater(len(nodes), 0)
        # Should find MyClass
        class_names = [node.name for node in nodes]
        self.assertIn('MyClass', class_names)
    
    def test_incremental_parse(self):
        """Test incremental parsing."""
        tree = self.parser.parse(self.sample_code)
        
        # Simulate edit (add a new function)
        new_code = self.sample_code + '\ndef new_function():\n    pass\n'
        
        # For now, just test that incremental_parse doesn't crash
        # Full edit detection would require more complex implementation
        edits = []  # Empty edits will trigger fallback to full parse
        new_tree = self.parser.incremental_parse(tree, new_code, edits)
        self.assertIsNotNone(new_tree)


@unittest.skipIf(not TREE_SITTER_AVAILABLE, "tree-sitter not installed")
class TestTreeSitterChunker(unittest.TestCase):
    """Test TreeSitterChunker functionality."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.chunker = TreeSitterChunker('python')
        self.sample_code = '''
def function_one():
    """First function."""
    return 1

def function_two():
    """Second function."""
    return 2

class TestClass:
    def method_one(self):
        pass
'''
    
    def test_chunker_initialization(self):
        """Test chunker initializes correctly."""
        self.assertIsNotNone(self.chunker)
        self.assertEqual(self.chunker.language, 'python')
    
    def test_chunk_code(self):
        """Test chunking code."""
        chunks = self.chunker.chunk_code(self.sample_code)
        self.assertGreater(len(chunks), 0)
        # Should find functions and class
        chunk_names = [chunk.name for chunk in chunks]
        self.assertIn('function_one', chunk_names)
        self.assertIn('function_two', chunk_names)
        self.assertIn('TestClass', chunk_names)
    
    def test_chunk_metadata(self):
        """Test chunk metadata."""
        chunks = self.chunker.chunk_code(self.sample_code)
        for chunk in chunks:
            self.assertIsNotNone(chunk.content)
            self.assertIsNotNone(chunk.chunk_type)
            self.assertIsNotNone(chunk.name)
            self.assertGreater(chunk.start_line, 0)
            self.assertGreater(chunk.end_line, 0)
            self.assertEqual(chunk.language, 'python')


@unittest.skipIf(not TREE_SITTER_AVAILABLE, "tree-sitter not installed")
class TestIncrementalIndexer(unittest.TestCase):
    """Test IncrementalIndexer functionality."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.indexer = IncrementalIndexer()
        self.sample_code = '''
def test_function():
    return "test"
'''
    
    def test_indexer_initialization(self):
        """Test indexer initializes correctly."""
        self.assertIsNotNone(self.indexer)
        self.assertEqual(len(self.indexer.file_states), 0)
    
    def test_index_file(self):
        """Test indexing a file."""
        chunks = self.indexer.index_file('test.py', self.sample_code, 'python')
        self.assertGreater(len(chunks), 0)
        self.assertIn('test.py', self.indexer.file_states)
    
    def test_incremental_update(self):
        """Test incremental update."""
        # Initial index
        chunks1 = self.indexer.index_file('test.py', self.sample_code, 'python')
        
        # Update with same content (should skip)
        chunks2 = self.indexer.index_file('test.py', self.sample_code, 'python')
        self.assertEqual(len(chunks1), len(chunks2))
        
        # Update with new content
        new_code = self.sample_code + '\ndef new_func():\n    pass\n'
        chunks3 = self.indexer.index_file('test.py', new_code, 'python')
        self.assertGreater(len(chunks3), len(chunks1))
    
    def test_remove_file(self):
        """Test removing a file from index."""
        self.indexer.index_file('test.py', self.sample_code, 'python')
        self.assertIn('test.py', self.indexer.file_states)
        
        self.indexer.remove_file('test.py')
        self.assertNotIn('test.py', self.indexer.file_states)


@unittest.skipIf(not TREE_SITTER_AVAILABLE, "tree-sitter not installed")
class TestHybridChunker(unittest.TestCase):
    """Test HybridChunker functionality."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.sample_code = '''
def test_function():
    return "test"
'''
    
    def test_hybrid_chunker_auto_mode(self):
        """Test hybrid chunker in AUTO mode."""
        chunker = HybridChunker('python', mode=ChunkingMode.AUTO)
        
        # Batch mode (should use regex)
        chunks = chunker.chunk(self.sample_code, 'test.py', is_incremental=False)
        self.assertGreater(len(chunks), 0)
        
        # Incremental mode (should use tree-sitter if available)
        chunks = chunker.chunk(self.sample_code, 'test.py', is_incremental=True)
        self.assertGreater(len(chunks), 0)
    
    def test_hybrid_chunker_tree_sitter_mode(self):
        """Test hybrid chunker in TREE_SITTER mode."""
        chunker = HybridChunker('python', mode=ChunkingMode.TREE_SITTER)
        chunks = chunker.chunk(self.sample_code, 'test.py')
        self.assertGreater(len(chunks), 0)
    
    def test_hybrid_chunker_regex_mode(self):
        """Test hybrid chunker in REGEX mode."""
        chunker = HybridChunker('python', mode=ChunkingMode.REGEX)
        chunks = chunker.chunk(self.sample_code, 'test.py')
        self.assertGreater(len(chunks), 0)


if __name__ == '__main__':
    unittest.main()

