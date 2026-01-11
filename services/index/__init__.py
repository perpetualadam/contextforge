"""
ContextForge Code Index Module

This module provides incremental, metadata-first code indexing:
- CodeFragment: Represents indexed code units (functions, classes, modules)
- IndexStats: Statistics about the index
- CodeIndex: Main indexing class with search capabilities

Extracted from services/core as part of Gap #6: Index Module Separation.
All classes maintain backwards compatibility via re-exports in services/core.

Copyright (c) 2025 ContextForge
"""

from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional
import logging

logger = logging.getLogger(__name__)


# Import utilities
try:
    from services.utils import utc_now
except ImportError:
    from datetime import datetime, timezone
    def utc_now():
        return datetime.now(timezone.utc)


@dataclass
class CodeFragment:
    """
    A single indexed code fragment.

    Represents a function, class, module, or other code unit
    indexed as a context object.
    
    Attributes:
        type: Fragment type (function, class, module, import, etc.)
        path: File path relative to repository root
        symbol: Symbol name (function/class name)
        language: Programming language
        hash: Content hash for change detection
        start_line: Starting line number (1-based)
        end_line: Ending line number (1-based)
        docstring: Extracted docstring
        dependencies: List of imported modules/symbols
        semantic_summary: AI-generated summary (optional)
        embedding_ref: Reference to vector embedding (optional)
        last_modified: ISO timestamp of last modification
        provenance: Origin of the fragment (ast, regex, fallback, filesystem)
    """
    type: str  # function, class, module, import, etc.
    path: str
    symbol: str = ""
    language: str = "unknown"
    hash: str = ""
    start_line: int = 0
    end_line: int = 0
    docstring: str = ""
    dependencies: list = field(default_factory=list)
    semantic_summary: str = ""  # Optional AI annotation
    embedding_ref: str = ""  # Optional vector reference
    last_modified: str = ""
    provenance: str = "filesystem"

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "type": self.type,
            "path": self.path,
            "symbol": self.symbol,
            "language": self.language,
            "hash": self.hash,
            "start_line": self.start_line,
            "end_line": self.end_line,
            "docstring": self.docstring,
            "dependencies": self.dependencies,
            "semantic_summary": self.semantic_summary,
            "embedding_ref": self.embedding_ref,
            "last_modified": self.last_modified,
            "provenance": self.provenance
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CodeFragment":
        """Create from dictionary."""
        return cls(**data)


@dataclass
class IndexStats:
    """
    Statistics about the code index.
    
    Attributes:
        total_files: Total number of files in the index
        total_symbols: Total number of indexed symbols
        languages: Count of files by language
        index_time_ms: Time taken to build the index
        last_indexed: ISO timestamp of last index operation
        is_incremental: Whether the last operation was incremental
        files_changed: Number of files that changed
        files_unchanged: Number of files that didn't change
    """
    total_files: int = 0
    total_symbols: int = 0
    languages: Dict[str, int] = field(default_factory=dict)
    index_time_ms: int = 0
    last_indexed: str = ""
    is_incremental: bool = False
    files_changed: int = 0
    files_unchanged: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "total_files": self.total_files,
            "total_symbols": self.total_symbols,
            "languages": dict(self.languages),
            "index_time_ms": self.index_time_ms,
            "last_indexed": self.last_indexed,
            "is_incremental": self.is_incremental,
            "files_changed": self.files_changed,
            "files_unchanged": self.files_unchanged
        }


class CodeIndex:
    """
    Incremental, metadata-first code index.

    Indexes code as context, not as executable logic.
    Read-only, incremental, and metadata-first.

    Indexing Process:
    1. Static Structure Pass - Parse file tree, identify symbols (AST)
    2. Semantic Annotation Pass - Optional AI-based summarization
    3. Incremental Updates - Hash-based change detection
    4. Multi-Index Strategy - Symbol, Dependency, Semantic indexes

    Usage:
        index = CodeIndex()
        index.index_repository("/path/to/repo")
        results = index.search("ClassName.method_name")
    """

    def __init__(self, storage_path: str = None):
        """
        Initialize code index.

        Args:
            storage_path: Path to store index data (default: in-memory)
        """
        self.storage_path = storage_path
        self._fragments: Dict[str, CodeFragment] = {}  # path:symbol -> fragment
        self._file_hashes: Dict[str, str] = {}  # path -> hash
        self._symbol_index: Dict[str, list] = {}  # symbol -> [fragment_keys]
        self._dependency_graph: Dict[str, list] = {}  # path -> [dependencies]
        self._stats = IndexStats()

        # Load existing index if available
        if storage_path:
            self._load_index()

    # Default file extensions for code indexing
    DEFAULT_EXTENSIONS = ['.py', '.js', '.ts', '.java', '.go', '.rs', '.cpp', '.c', '.h']

    # Directories to skip during indexing
    EXCLUDED_DIRECTORIES = ['node_modules', '.git', '__pycache__', 'venv', 'dist']

    def index_repository(
        self,
        repo_path: str,
        extensions: list = None,
        incremental: bool = True,
        annotate: bool = False
    ) -> IndexStats:
        """
        Index a repository.

        Args:
            repo_path: Path to repository root
            extensions: File extensions to index (default: common code files)
            incremental: Only re-index changed files
            annotate: Enable AI-based semantic annotation

        Returns:
            IndexStats with indexing results
        """
        import time
        from pathlib import Path

        start_time = time.time()
        extensions = extensions or self.DEFAULT_EXTENSIONS
        repo = Path(repo_path)

        # Collect files to index
        source_files = self._collect_source_files(repo, extensions)

        # Process all files and gather statistics
        indexing_result = self._process_files(
            source_files, repo, incremental, annotate
        )

        # Update stats
        self._stats = self._build_stats(
            total_files=len(source_files),
            languages=indexing_result['languages'],
            start_time=start_time,
            incremental=incremental,
            files_changed=indexing_result['files_changed'],
            files_unchanged=indexing_result['files_unchanged']
        )

        # Save index if storage configured
        if self.storage_path:
            self._save_index()

        logger.info(
            f"Indexed {indexing_result['files_processed']} files, "
            f"{len(self._fragments)} symbols in {self._stats.index_time_ms}ms"
        )

        return self._stats

    def _collect_source_files(self, repo_path, extensions: list) -> list:
        """
        Collect all source files in a repository matching the given extensions.

        Args:
            repo_path: Path object for the repository root
            extensions: List of file extensions to include

        Returns:
            List of Path objects for files to index
        """
        source_files = []
        for ext in extensions:
            for file_path in repo_path.rglob(f"*{ext}"):
                if not self._is_excluded_path(file_path):
                    source_files.append(file_path)
        return source_files

    def _is_excluded_path(self, file_path) -> bool:
        """
        Check if a file path should be excluded from indexing.

        Args:
            file_path: Path to check

        Returns:
            True if path should be excluded
        """
        path_str = str(file_path)
        return any(excluded in path_str for excluded in self.EXCLUDED_DIRECTORIES)

    def _process_files(
        self,
        source_files: list,
        repo_path,
        incremental: bool,
        annotate: bool
    ) -> Dict[str, Any]:
        """
        Process all source files and extract symbols.

        Args:
            source_files: List of file paths to process
            repo_path: Root repository path
            incremental: Whether to skip unchanged files
            annotate: Whether to add semantic annotations

        Returns:
            Dict with processing statistics
        """
        files_processed = 0
        files_changed = 0
        files_unchanged = 0
        languages: Dict[str, int] = {}

        for file_path in source_files:
            try:
                result = self._index_single_file(
                    file_path, repo_path, incremental, annotate
                )

                if result['skipped']:
                    files_unchanged += 1
                else:
                    files_changed += 1
                    files_processed += 1
                    lang = result['language']
                    languages[lang] = languages.get(lang, 0) + 1

            except Exception as e:
                logger.warning(f"Failed to index {file_path}: {e}")

        return {
            'files_processed': files_processed,
            'files_changed': files_changed,
            'files_unchanged': files_unchanged,
            'languages': languages
        }

    def _index_single_file(
        self,
        file_path,
        repo_path,
        incremental: bool,
        annotate: bool
    ) -> Dict[str, Any]:
        """
        Index a single file and extract its symbols.

        Args:
            file_path: Path to the file
            repo_path: Root repository path
            incremental: Whether to skip if unchanged
            annotate: Whether to add semantic annotations

        Returns:
            Dict with 'skipped' and 'language' keys
        """
        import hashlib

        content = file_path.read_text(encoding='utf-8', errors='ignore')
        file_hash = self._compute_file_hash(content)
        relative_path = str(file_path.relative_to(repo_path))

        # Check if file changed (incremental indexing)
        if incremental and self._file_unchanged(relative_path, file_hash):
            return {'skipped': True, 'language': None}

        self._file_hashes[relative_path] = file_hash

        # Detect language and extract symbols
        ext = file_path.suffix.lower()
        language = self._detect_language(ext)
        fragments = self._extract_symbols(content, relative_path, language, file_hash)

        # Optional semantic annotation
        if annotate:
            fragments = self._annotate_fragments(fragments)

        # Store fragments and update symbol index
        self._store_fragments(fragments)

        return {'skipped': False, 'language': language}

    def _compute_file_hash(self, content: str) -> str:
        """
        Compute a hash of file content for change detection.

        Args:
            content: File content as string

        Returns:
            Truncated SHA-256 hash
        """
        import hashlib
        return hashlib.sha256(content.encode()).hexdigest()[:16]

    def _file_unchanged(self, relative_path: str, file_hash: str) -> bool:
        """
        Check if a file has not changed since last indexing.

        Args:
            relative_path: Path relative to repo root
            file_hash: Current content hash

        Returns:
            True if file has not changed
        """
        return (
            relative_path in self._file_hashes and
            self._file_hashes[relative_path] == file_hash
        )

    def _store_fragments(self, fragments: List[CodeFragment]) -> None:
        """
        Store extracted fragments and update the symbol index.

        Args:
            fragments: List of CodeFragment objects to store
        """
        for frag in fragments:
            fragment_key = f"{frag.path}:{frag.symbol}"
            self._fragments[fragment_key] = frag

            if frag.symbol:
                if frag.symbol not in self._symbol_index:
                    self._symbol_index[frag.symbol] = []
                self._symbol_index[frag.symbol].append(fragment_key)

    def _build_stats(
        self,
        total_files: int,
        languages: Dict[str, int],
        start_time: float,
        incremental: bool,
        files_changed: int,
        files_unchanged: int
    ) -> IndexStats:
        """
        Build IndexStats from indexing results.

        Args:
            total_files: Total number of files found
            languages: Count of files by language
            start_time: Indexing start time
            incremental: Whether incremental mode was used
            files_changed: Number of files that changed
            files_unchanged: Number of files unchanged

        Returns:
            IndexStats object with results
        """
        import time
        return IndexStats(
            total_files=total_files,
            total_symbols=len(self._fragments),
            languages=languages,
            index_time_ms=int((time.time() - start_time) * 1000),
            last_indexed=utc_now().isoformat(),
            is_incremental=incremental,
            files_changed=files_changed,
            files_unchanged=files_unchanged
        )

    def _detect_language(self, ext: str) -> str:
        """Detect language from file extension."""
        lang_map = {
            '.py': 'python',
            '.js': 'javascript',
            '.ts': 'typescript',
            '.java': 'java',
            '.go': 'go',
            '.rs': 'rust',
            '.cpp': 'cpp',
            '.c': 'c',
            '.h': 'c',
            '.rb': 'ruby',
            '.php': 'php',
            '.swift': 'swift',
            '.kt': 'kotlin'
        }
        return lang_map.get(ext, 'unknown')

    def _extract_symbols(
        self,
        content: str,
        file_path: str,
        language: str,
        file_hash: str
    ) -> List[CodeFragment]:
        """
        Extract symbols using AST parsing (static structure pass).

        This is the core of metadata-first indexing:
        - Parse file structure
        - Identify symbols (functions, classes)
        - Extract docstrings and dependencies
        - NO AI/LLM calls - pure static analysis
        """
        fragments = []

        if language == 'python':
            fragments = self._extract_python_symbols(content, file_path, file_hash)
        elif language in ('javascript', 'typescript'):
            fragments = self._extract_js_symbols(content, file_path, file_hash, language)
        else:
            # Fallback: treat whole file as one fragment
            fragments = [CodeFragment(
                type="module",
                path=file_path,
                symbol=file_path.replace('/', '.').replace('\\', '.'),
                language=language,
                hash=file_hash,
                provenance="filesystem"
            )]

        return fragments

    def _extract_python_symbols(self, content: str, file_path: str, file_hash: str) -> List[CodeFragment]:
        """Extract Python symbols using AST."""
        import ast

        fragments = []

        try:
            tree = ast.parse(content)

            # Module-level docstring
            if (tree.body and isinstance(tree.body[0], ast.Expr) and
                isinstance(tree.body[0].value, ast.Constant)):
                docstring = tree.body[0].value.value if isinstance(tree.body[0].value.value, str) else ""
                fragments.append(CodeFragment(
                    type="module",
                    path=file_path,
                    symbol=file_path.replace('/', '.').replace('\\', '.').replace('.py', ''),
                    language="python",
                    hash=file_hash,
                    docstring=docstring[:500] if docstring else "",
                    provenance="ast"
                ))

            # Extract imports for dependency tracking
            imports = []
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        imports.append(alias.name)
                elif isinstance(node, ast.ImportFrom):
                    if node.module:
                        imports.append(node.module)

            # Functions and classes
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    docstring = ast.get_docstring(node) or ""
                    fragments.append(CodeFragment(
                        type="function",
                        path=file_path,
                        symbol=node.name,
                        language="python",
                        hash=file_hash,
                        start_line=node.lineno,
                        end_line=node.end_lineno or node.lineno,
                        docstring=docstring[:500],
                        dependencies=imports,
                        provenance="ast"
                    ))

                elif isinstance(node, ast.ClassDef):
                    docstring = ast.get_docstring(node) or ""
                    methods = [n.name for n in node.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
                    fragments.append(CodeFragment(
                        type="class",
                        path=file_path,
                        symbol=node.name,
                        language="python",
                        hash=file_hash,
                        start_line=node.lineno,
                        end_line=node.end_lineno or node.lineno,
                        docstring=docstring[:500],
                        dependencies=imports + methods,
                        provenance="ast"
                    ))

        except SyntaxError as e:
            logger.debug(f"Syntax error parsing {file_path}: {e}")
            # Fallback to module-level fragment
            fragments.append(CodeFragment(
                type="module",
                path=file_path,
                symbol=file_path,
                language="python",
                hash=file_hash,
                provenance="fallback"
            ))

        return fragments

    def _extract_js_symbols(self, content: str, file_path: str, file_hash: str, language: str) -> List[CodeFragment]:
        """Extract JavaScript/TypeScript symbols using regex (fallback without tree-sitter)."""
        import re

        fragments = []

        # Function patterns
        func_patterns = [
            r'function\s+(\w+)\s*\(',
            r'const\s+(\w+)\s*=\s*(?:async\s*)?\(',
            r'(?:export\s+)?(?:async\s+)?function\s+(\w+)',
        ]

        # Class patterns
        class_patterns = [
            r'class\s+(\w+)',
            r'(?:export\s+)?class\s+(\w+)'
        ]

        for pattern in func_patterns:
            for match in re.finditer(pattern, content):
                name = match.group(1)
                line_num = content[:match.start()].count('\n') + 1
                fragments.append(CodeFragment(
                    type="function",
                    path=file_path,
                    symbol=name,
                    language=language,
                    hash=file_hash,
                    start_line=line_num,
                    provenance="regex"
                ))

        for pattern in class_patterns:
            for match in re.finditer(pattern, content):
                name = match.group(1)
                line_num = content[:match.start()].count('\n') + 1
                fragments.append(CodeFragment(
                    type="class",
                    path=file_path,
                    symbol=name,
                    language=language,
                    hash=file_hash,
                    start_line=line_num,
                    provenance="regex"
                ))

        # If no symbols found, create module-level fragment
        if not fragments:
            fragments.append(CodeFragment(
                type="module",
                path=file_path,
                symbol=file_path,
                language=language,
                hash=file_hash,
                provenance="fallback"
            ))

        return fragments

    def _annotate_fragments(self, fragments: List[CodeFragment]) -> List[CodeFragment]:
        """
        Semantic annotation pass using LLM.

        This is optional and adds:
        - Semantic summaries
        - Responsibility descriptions
        - Architectural role tags
        """
        # Optional: implement LLM-based annotation
        # For now, return fragments as-is
        return fragments

    def search(self, query: str, top_k: int = 10) -> List[Dict[str, Any]]:
        """
        Search the index for symbols matching query.

        Searches in order of specificity:
        1. Exact symbol name match
        2. Partial symbol name match
        3. File path match

        Args:
            query: Search query (symbol name, partial match)
            top_k: Maximum results to return

        Returns:
            List of matching CodeFragment dictionaries
        """
        results = []
        query_lower = query.lower()

        # Search strategies in order of priority
        self._add_exact_symbol_matches(query, results, top_k)
        self._add_partial_symbol_matches(query_lower, results, top_k)
        self._add_path_matches(query_lower, results, top_k)

        return results

    def _add_exact_symbol_matches(
        self,
        query: str,
        results: List[Dict[str, Any]],
        top_k: int
    ) -> None:
        """
        Add exact symbol matches to results.

        Args:
            query: Exact symbol name to match
            results: List to append results to
            top_k: Maximum results allowed
        """
        if query not in self._symbol_index:
            return

        for fragment_key in self._symbol_index[query][:top_k]:
            if fragment_key in self._fragments:
                results.append(self._fragments[fragment_key].to_dict())

    def _add_partial_symbol_matches(
        self,
        query_lower: str,
        results: List[Dict[str, Any]],
        top_k: int
    ) -> None:
        """
        Add partial symbol name matches to results.

        Args:
            query_lower: Lowercase query for case-insensitive matching
            results: List to append results to
            top_k: Maximum results allowed
        """
        if len(results) >= top_k:
            return

        for symbol, fragment_keys in self._symbol_index.items():
            if query_lower not in symbol.lower():
                continue

            for fragment_key in fragment_keys:
                if len(results) >= top_k:
                    return
                if fragment_key not in self._fragments:
                    continue

                fragment_dict = self._fragments[fragment_key].to_dict()
                if fragment_dict not in results:
                    results.append(fragment_dict)

    def _add_path_matches(
        self,
        query_lower: str,
        results: List[Dict[str, Any]],
        top_k: int
    ) -> None:
        """
        Add file path matches to results.

        Args:
            query_lower: Lowercase query for case-insensitive matching
            results: List to append results to
            top_k: Maximum results allowed
        """
        if len(results) >= top_k:
            return

        for fragment_key, fragment in self._fragments.items():
            if len(results) >= top_k:
                return
            if query_lower not in fragment.path.lower():
                continue

            fragment_dict = fragment.to_dict()
            if fragment_dict not in results:
                results.append(fragment_dict)

    def get_dependencies(self, path: str) -> List[str]:
        """Get dependencies for a file."""
        deps = set()
        for key, frag in self._fragments.items():
            if frag.path == path:
                deps.update(frag.dependencies)
        return list(deps)

    def get_dependents(self, symbol: str) -> List[str]:
        """Get files that depend on a symbol."""
        dependents = []
        for key, frag in self._fragments.items():
            if symbol in frag.dependencies:
                dependents.append(frag.path)
        return list(set(dependents))

    def get_stats(self) -> Dict[str, Any]:
        """Get index statistics."""
        return self._stats.to_dict()

    def _save_index(self):
        """Save index to storage."""
        import json
        from pathlib import Path

        if not self.storage_path:
            return

        storage = Path(self.storage_path)
        storage.mkdir(parents=True, exist_ok=True)

        # Save fragments
        fragments_data = {k: v.to_dict() for k, v in self._fragments.items()}
        (storage / "fragments.json").write_text(json.dumps(fragments_data, indent=2))

        # Save hashes
        (storage / "hashes.json").write_text(json.dumps(self._file_hashes))

        # Save symbol index
        (storage / "symbols.json").write_text(json.dumps(self._symbol_index))

        logger.info(f"Index saved to {self.storage_path}")

    def _load_index(self):
        """Load index from storage."""
        import json
        from pathlib import Path

        if not self.storage_path:
            return

        storage = Path(self.storage_path)

        try:
            # Load fragments
            fragments_file = storage / "fragments.json"
            if fragments_file.exists():
                data = json.loads(fragments_file.read_text())
                for k, v in data.items():
                    self._fragments[k] = CodeFragment(**v)

            # Load hashes
            hashes_file = storage / "hashes.json"
            if hashes_file.exists():
                self._file_hashes = json.loads(hashes_file.read_text())

            # Load symbol index
            symbols_file = storage / "symbols.json"
            if symbols_file.exists():
                self._symbol_index = json.loads(symbols_file.read_text())

            logger.info(f"Index loaded from {self.storage_path}: {len(self._fragments)} symbols")

        except Exception as e:
            logger.warning(f"Failed to load index: {e}")


# Global code index instance
_code_index: Optional[CodeIndex] = None


def get_code_index(storage_path: str = None) -> CodeIndex:
    """Get or create the global code index."""
    global _code_index
    if _code_index is None:
        _code_index = CodeIndex(storage_path)
    return _code_index


# Export all symbols
__all__ = [
    "CodeFragment",
    "IndexStats",
    "CodeIndex",
    "get_code_index",
]
