"""
Tests for the ContextForge code index module.

Tests cover:
- CodeFragment dataclass
- IndexStats dataclass
- CodeIndex class (indexing, search, dependencies)
- Backwards compatibility with services.core imports

Copyright (c) 2025 ContextForge
"""

import pytest
import tempfile
import os
from pathlib import Path
from unittest.mock import patch, MagicMock


class TestCodeFragment:
    """Test CodeFragment dataclass."""
    
    def test_code_fragment_creation(self):
        """Test creating a CodeFragment with required fields."""
        from services.index import CodeFragment
        
        frag = CodeFragment(
            type="function",
            path="src/utils.py"
        )
        
        assert frag.type == "function"
        assert frag.path == "src/utils.py"
        assert frag.symbol == ""
        assert frag.language == "unknown"
        assert frag.hash == ""
    
    def test_code_fragment_full_creation(self):
        """Test creating a CodeFragment with all fields."""
        from services.index import CodeFragment
        
        frag = CodeFragment(
            type="class",
            path="src/models.py",
            symbol="UserModel",
            language="python",
            hash="abc123",
            start_line=10,
            end_line=50,
            docstring="User model class.",
            dependencies=["dataclasses", "typing"],
            semantic_summary="Represents a user entity.",
            embedding_ref="vec_001",
            last_modified="2025-01-01T00:00:00Z",
            provenance="ast"
        )
        
        assert frag.type == "class"
        assert frag.symbol == "UserModel"
        assert frag.language == "python"
        assert frag.start_line == 10
        assert frag.end_line == 50
        assert "dataclasses" in frag.dependencies
        assert frag.provenance == "ast"
    
    def test_code_fragment_to_dict(self):
        """Test CodeFragment serialization to dict."""
        from services.index import CodeFragment
        
        frag = CodeFragment(
            type="function",
            path="test.py",
            symbol="my_func",
            language="python",
            hash="xyz789"
        )
        
        data = frag.to_dict()
        
        assert isinstance(data, dict)
        assert data["type"] == "function"
        assert data["path"] == "test.py"
        assert data["symbol"] == "my_func"
        assert data["language"] == "python"
        assert data["hash"] == "xyz789"


class TestIndexStats:
    """Test IndexStats dataclass."""
    
    def test_index_stats_defaults(self):
        """Test IndexStats default values."""
        from services.index import IndexStats
        
        stats = IndexStats()
        
        assert stats.total_files == 0
        assert stats.total_symbols == 0
        assert stats.languages == {}
        assert stats.index_time_ms == 0
        assert stats.is_incremental == False
    
    def test_index_stats_with_values(self):
        """Test IndexStats with values."""
        from services.index import IndexStats
        
        stats = IndexStats(
            total_files=10,
            total_symbols=50,
            languages={"python": 8, "javascript": 2},
            index_time_ms=150,
            last_indexed="2025-01-01T00:00:00Z",
            is_incremental=True,
            files_changed=3,
            files_unchanged=7
        )
        
        assert stats.total_files == 10
        assert stats.total_symbols == 50
        assert stats.languages["python"] == 8
        assert stats.is_incremental == True
        assert stats.files_changed == 3
    
    def test_index_stats_to_dict(self):
        """Test IndexStats serialization to dict."""
        from services.index import IndexStats
        
        stats = IndexStats(total_files=5, total_symbols=20)
        data = stats.to_dict()
        
        assert isinstance(data, dict)
        assert data["total_files"] == 5
        assert data["total_symbols"] == 20


class TestCodeIndex:
    """Test CodeIndex class."""
    
    def test_code_index_creation(self):
        """Test creating a CodeIndex."""
        from services.index import CodeIndex
        
        idx = CodeIndex()
        
        assert idx.storage_path is None
        assert idx._fragments == {}
        assert idx._file_hashes == {}
    
    def test_code_index_get_stats_empty(self):
        """Test get_stats on empty index."""
        from services.index import CodeIndex
        
        idx = CodeIndex()
        stats = idx.get_stats()
        
        assert stats["total_files"] == 0
        assert stats["total_symbols"] == 0
    
    def test_code_index_search_empty(self):
        """Test search on empty index."""
        from services.index import CodeIndex

        idx = CodeIndex()
        results = idx.search("anything")

        assert results == []

    def test_code_index_with_temp_storage(self):
        """Test CodeIndex with temporary storage path."""
        from services.index import CodeIndex

        with tempfile.TemporaryDirectory() as tmpdir:
            idx = CodeIndex(storage_path=tmpdir)
            assert idx.storage_path == tmpdir

    def test_index_repository_basic(self):
        """Test indexing a simple repository."""
        from services.index import CodeIndex

        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a simple Python file
            test_file = Path(tmpdir) / "test_module.py"
            test_file.write_text('''
"""Test module docstring."""

def hello_world():
    """Say hello."""
    return "Hello, World!"

class Greeter:
    """A greeter class."""

    def greet(self, name):
        """Greet someone."""
        return f"Hello, {name}!"
''')

            idx = CodeIndex()
            stats = idx.index_repository(tmpdir)

            assert stats.total_files >= 1
            assert stats.total_symbols >= 1
            assert "python" in stats.languages

    def test_index_search_by_symbol(self):
        """Test searching by symbol name."""
        from services.index import CodeIndex

        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "utils.py"
            test_file.write_text('''
def calculate_sum(a, b):
    """Add two numbers."""
    return a + b

def calculate_product(a, b):
    """Multiply two numbers."""
    return a * b
''')

            idx = CodeIndex()
            idx.index_repository(tmpdir)

            results = idx.search("calculate_sum")
            assert len(results) >= 1
            assert any(r["symbol"] == "calculate_sum" for r in results)

    def test_index_incremental_update(self):
        """Test incremental indexing."""
        from services.index import CodeIndex

        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "app.py"
            test_file.write_text('def original(): pass')

            idx = CodeIndex()
            stats1 = idx.index_repository(tmpdir, incremental=True)

            # Re-index without changes
            stats2 = idx.index_repository(tmpdir, incremental=True)

            assert stats2.is_incremental == True
            assert stats2.files_unchanged >= 1

    def test_get_dependencies(self):
        """Test getting dependencies for a file."""
        from services.index import CodeIndex

        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "service.py"
            test_file.write_text('''
import os
import json
from typing import List

def process():
    pass
''')

            idx = CodeIndex()
            idx.index_repository(tmpdir)

            deps = idx.get_dependencies("service.py")
            assert "os" in deps or "json" in deps or "typing" in deps


class TestBackwardsCompatibility:
    """Test backwards compatibility with services.core imports."""

    def test_import_from_core(self):
        """Test that classes can be imported from services.core."""
        from services.core import CodeFragment, IndexStats, CodeIndex, get_code_index

        # These should all be importable
        assert CodeFragment is not None
        assert IndexStats is not None
        assert CodeIndex is not None
        assert get_code_index is not None

    def test_import_from_index(self):
        """Test that classes can be imported from services.index."""
        from services.index import CodeFragment, IndexStats, CodeIndex, get_code_index

        assert CodeFragment is not None
        assert IndexStats is not None
        assert CodeIndex is not None
        assert get_code_index is not None

    def test_same_class_behavior(self):
        """Test that both imports behave the same."""
        from services.index import CodeFragment as IndexFragment
        from services.core import CodeFragment as CoreFragment

        # Both should create similar objects
        idx_frag = IndexFragment(type="function", path="test.py", symbol="foo")
        core_frag = CoreFragment(type="function", path="test.py", symbol="foo")

        assert idx_frag.type == core_frag.type
        assert idx_frag.path == core_frag.path
        assert idx_frag.symbol == core_frag.symbol


class TestPythonSymbolExtraction:
    """Test Python symbol extraction."""

    def test_extract_function(self):
        """Test extracting function symbols."""
        from services.index import CodeIndex

        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "funcs.py"
            test_file.write_text('''
def my_function():
    """A function docstring."""
    pass

async def async_function():
    """An async function."""
    pass
''')

            idx = CodeIndex()
            idx.index_repository(tmpdir)

            results = idx.search("my_function")
            assert len(results) >= 1

            func = next((r for r in results if r["symbol"] == "my_function"), None)
            assert func is not None
            assert func["type"] == "function"
            assert func["language"] == "python"

    def test_extract_class(self):
        """Test extracting class symbols."""
        from services.index import CodeIndex

        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "models.py"
            test_file.write_text('''
class MyClass:
    """A class docstring."""

    def method(self):
        pass
''')

            idx = CodeIndex()
            idx.index_repository(tmpdir)

            results = idx.search("MyClass")
            assert len(results) >= 1

            cls = next((r for r in results if r["symbol"] == "MyClass"), None)
            assert cls is not None
            assert cls["type"] == "class"


class TestJavaScriptSymbolExtraction:
    """Test JavaScript/TypeScript symbol extraction."""

    def test_extract_js_function(self):
        """Test extracting JavaScript function symbols."""
        from services.index import CodeIndex

        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "utils.js"
            test_file.write_text('''
function calculateTotal(items) {
    return items.reduce((sum, item) => sum + item.price, 0);
}

async function fetchData(url) {
    return await fetch(url);
}
''')

            idx = CodeIndex()
            idx.index_repository(tmpdir, extensions=['.js'])

            results = idx.search("calculateTotal")
            assert len(results) >= 1

            func = next((r for r in results if r["symbol"] == "calculateTotal"), None)
            assert func is not None
            assert func["type"] == "function"
            assert func["language"] == "javascript"

    def test_extract_js_class(self):
        """Test extracting JavaScript class symbols."""
        from services.index import CodeIndex

        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "models.js"
            test_file.write_text('''
class UserService {
    constructor() {
        this.users = [];
    }

    addUser(user) {
        this.users.push(user);
    }
}

export class ProductService {
    getProducts() {
        return [];
    }
}
''')

            idx = CodeIndex()
            idx.index_repository(tmpdir, extensions=['.js'])

            results = idx.search("UserService")
            assert len(results) >= 1

            cls = next((r for r in results if r["symbol"] == "UserService"), None)
            assert cls is not None
            assert cls["type"] == "class"

    def test_extract_typescript_symbols(self):
        """Test extracting TypeScript symbols."""
        from services.index import CodeIndex

        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "service.ts"
            test_file.write_text('''
export class ApiClient {
    private baseUrl: string;

    constructor(url: string) {
        this.baseUrl = url;
    }
}

export async function makeRequest(url: string): Promise<Response> {
    return fetch(url);
}
''')

            idx = CodeIndex()
            idx.index_repository(tmpdir, extensions=['.ts'])

            results = idx.search("ApiClient")
            assert len(results) >= 1

            cls = next((r for r in results if r["symbol"] == "ApiClient"), None)
            assert cls is not None
            assert cls["language"] == "typescript"


class TestIndexPersistence:
    """Test index save and load functionality."""

    def test_save_and_load_index(self):
        """Test saving and loading index from storage."""
        from services.index import CodeIndex

        with tempfile.TemporaryDirectory() as tmpdir:
            repo_dir = Path(tmpdir) / "repo"
            repo_dir.mkdir()
            storage_dir = Path(tmpdir) / "storage"

            # Create test file
            test_file = repo_dir / "app.py"
            test_file.write_text('''
def main():
    """Main entry point."""
    print("Hello")

class Application:
    """Main application class."""
    pass
''')

            # Index and save
            idx1 = CodeIndex(storage_path=str(storage_dir))
            stats1 = idx1.index_repository(str(repo_dir))

            # Verify files were created
            assert (storage_dir / "fragments.json").exists()
            assert (storage_dir / "hashes.json").exists()
            assert (storage_dir / "symbols.json").exists()

            # Create new index and load
            idx2 = CodeIndex(storage_path=str(storage_dir))

            # Verify loaded data
            assert len(idx2._fragments) == len(idx1._fragments)
            assert len(idx2._file_hashes) == len(idx1._file_hashes)

    def test_load_nonexistent_index(self):
        """Test loading from non-existent storage path."""
        from services.index import CodeIndex

        with tempfile.TemporaryDirectory() as tmpdir:
            storage_dir = Path(tmpdir) / "nonexistent"

            # Should not raise an error
            idx = CodeIndex(storage_path=str(storage_dir))
            assert idx._fragments == {}


class TestSearchFeatures:
    """Test advanced search features."""

    def test_search_partial_match(self):
        """Test partial symbol matching in search."""
        from services.index import CodeIndex

        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "handlers.py"
            test_file.write_text('''
def handle_user_request():
    pass

def handle_admin_request():
    pass

def process_data():
    pass
''')

            idx = CodeIndex()
            idx.index_repository(tmpdir)

            # Partial match should find both handlers
            results = idx.search("handle")
            assert len(results) >= 2
            symbols = [r["symbol"] for r in results]
            assert "handle_user_request" in symbols
            assert "handle_admin_request" in symbols

    def test_search_by_path(self):
        """Test searching by file path."""
        from services.index import CodeIndex

        with tempfile.TemporaryDirectory() as tmpdir:
            # Create files in different directories
            utils_dir = Path(tmpdir) / "utils"
            utils_dir.mkdir()
            models_dir = Path(tmpdir) / "models"
            models_dir.mkdir()

            (utils_dir / "helpers.py").write_text('def helper(): pass')
            (models_dir / "user.py").write_text('class User: pass')

            idx = CodeIndex()
            idx.index_repository(tmpdir)

            # Search by path
            results = idx.search("utils")
            assert len(results) >= 1
            assert any("utils" in r["path"] for r in results)

    def test_search_top_k_limit(self):
        """Test that search respects top_k limit."""
        from services.index import CodeIndex

        with tempfile.TemporaryDirectory() as tmpdir:
            # Create file with many functions
            test_file = Path(tmpdir) / "many_funcs.py"
            funcs = "\n".join([f"def func_{i}(): pass" for i in range(20)])
            test_file.write_text(funcs)

            idx = CodeIndex()
            idx.index_repository(tmpdir)

            results = idx.search("func", top_k=5)
            assert len(results) <= 5


class TestDependencyTracking:
    """Test dependency tracking features."""

    def test_get_dependents(self):
        """Test getting files that depend on a symbol."""
        from services.index import CodeIndex

        with tempfile.TemporaryDirectory() as tmpdir:
            # Create files with dependencies
            (Path(tmpdir) / "utils.py").write_text('''
def helper():
    pass
''')
            (Path(tmpdir) / "service.py").write_text('''
from utils import helper

def process():
    helper()
''')

            idx = CodeIndex()
            idx.index_repository(tmpdir)

            dependents = idx.get_dependents("utils")
            assert "service.py" in dependents


class TestLanguageDetection:
    """Test language detection from file extensions."""

    def test_detect_python(self):
        """Test Python language detection."""
        from services.index import CodeIndex

        idx = CodeIndex()
        assert idx._detect_language('.py') == 'python'

    def test_detect_javascript(self):
        """Test JavaScript language detection."""
        from services.index import CodeIndex

        idx = CodeIndex()
        assert idx._detect_language('.js') == 'javascript'

    def test_detect_typescript(self):
        """Test TypeScript language detection."""
        from services.index import CodeIndex

        idx = CodeIndex()
        assert idx._detect_language('.ts') == 'typescript'

    def test_detect_java(self):
        """Test Java language detection."""
        from services.index import CodeIndex

        idx = CodeIndex()
        assert idx._detect_language('.java') == 'java'

    def test_detect_go(self):
        """Test Go language detection."""
        from services.index import CodeIndex

        idx = CodeIndex()
        assert idx._detect_language('.go') == 'go'

    def test_detect_rust(self):
        """Test Rust language detection."""
        from services.index import CodeIndex

        idx = CodeIndex()
        assert idx._detect_language('.rs') == 'rust'

    def test_detect_unknown(self):
        """Test unknown extension detection."""
        from services.index import CodeIndex

        idx = CodeIndex()
        assert idx._detect_language('.xyz') == 'unknown'


class TestErrorHandling:
    """Test error handling in indexing."""

    def test_syntax_error_fallback(self):
        """Test fallback behavior on Python syntax errors."""
        from services.index import CodeIndex

        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "broken.py"
            test_file.write_text('''
def incomplete_function(
    # Missing closing paren and body
''')

            idx = CodeIndex()
            # Should not raise, should use fallback
            stats = idx.index_repository(tmpdir)

            # Should still create a fragment (fallback module-level)
            assert stats.total_files >= 1

    def test_unreadable_file_handling(self):
        """Test handling of files that can't be read."""
        from services.index import CodeIndex

        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a valid file
            (Path(tmpdir) / "valid.py").write_text('def valid(): pass')

            idx = CodeIndex()
            stats = idx.index_repository(tmpdir)

            # Should index the valid file
            assert stats.total_files >= 1


class TestGlobalCodeIndex:
    """Test global code index singleton."""

    def test_get_code_index_singleton(self):
        """Test that get_code_index returns singleton."""
        from services.index import get_code_index

        # Reset global for test
        import services.index
        services.index._code_index = None

        idx1 = get_code_index()
        idx2 = get_code_index()

        assert idx1 is idx2

    def test_get_code_index_with_storage(self):
        """Test get_code_index with storage path."""
        from services.index import get_code_index
        import services.index

        # Reset global for test
        services.index._code_index = None

        with tempfile.TemporaryDirectory() as tmpdir:
            idx = get_code_index(storage_path=tmpdir)
            assert idx.storage_path == tmpdir

