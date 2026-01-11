"""
ContextForge Dependency Graph Module.

Provides dependency analysis and impact detection:
- Import/dependency tracking
- Call graph analysis
- Impact analysis for changes
- Module relationship visualization

Uses networkx for graph operations.

Copyright (c) 2025 ContextForge
"""

import logging
import re
import ast
from dataclasses import dataclass, field
from typing import Dict, List, Set, Optional, Any, Tuple
from pathlib import Path
from enum import Enum

logger = logging.getLogger(__name__)

# Try to import networkx, provide fallback
try:
    import networkx as nx
    NETWORKX_AVAILABLE = True
except ImportError:
    NETWORKX_AVAILABLE = False
    logger.warning("networkx not installed. Graph features limited.")


class DependencyType(Enum):
    """Types of dependencies."""
    IMPORT = "import"
    CALL = "call"
    INHERITANCE = "inheritance"
    COMPOSITION = "composition"


@dataclass
class Dependency:
    """Single dependency relationship."""
    source: str  # Source file/module/function
    target: str  # Target file/module/function
    dep_type: DependencyType
    line: int = 0
    context: str = ""  # e.g., function name where import occurs


@dataclass
class ImpactResult:
    """Result of impact analysis."""
    changed_file: str
    directly_affected: List[str] = field(default_factory=list)
    transitively_affected: List[str] = field(default_factory=list)
    test_files_affected: List[str] = field(default_factory=list)
    risk_level: str = "low"  # low, medium, high, critical
    summary: str = ""


class PythonImportVisitor(ast.NodeVisitor):
    """AST visitor to extract Python imports."""
    
    def __init__(self, file_path: str):
        self.file_path = file_path
        self.imports: List[Dependency] = []
        self.current_function: Optional[str] = None
    
    def visit_Import(self, node):
        for alias in node.names:
            self.imports.append(Dependency(
                source=self.file_path,
                target=alias.name,
                dep_type=DependencyType.IMPORT,
                line=node.lineno,
                context=self.current_function or "module"
            ))
        self.generic_visit(node)
    
    def visit_ImportFrom(self, node):
        module = node.module or ""
        for alias in node.names:
            target = f"{module}.{alias.name}" if module else alias.name
            self.imports.append(Dependency(
                source=self.file_path,
                target=target,
                dep_type=DependencyType.IMPORT,
                line=node.lineno,
                context=self.current_function or "module"
            ))
        self.generic_visit(node)
    
    def visit_FunctionDef(self, node):
        old_func = self.current_function
        self.current_function = node.name
        self.generic_visit(node)
        self.current_function = old_func
    
    def visit_AsyncFunctionDef(self, node):
        self.visit_FunctionDef(node)


class DependencyGraph:
    """
    Manages dependency relationships between files and modules.
    
    Usage:
        graph = DependencyGraph()
        graph.add_file("path/to/file.py")
        impact = graph.analyze_impact("path/to/changed_file.py")
    """
    
    def __init__(self):
        if NETWORKX_AVAILABLE:
            self._graph = nx.DiGraph()
        else:
            self._graph = None
        self._dependencies: List[Dependency] = []
        self._file_to_deps: Dict[str, List[Dependency]] = {}
    
    def add_file(self, file_path: str, content: str = None) -> List[Dependency]:
        """
        Add a file to the dependency graph.
        
        Args:
            file_path: Path to the file
            content: Optional content (will read from disk if not provided)
            
        Returns:
            List of dependencies found
        """
        if content is None:
            try:
                content = Path(file_path).read_text(encoding='utf-8', errors='ignore')
            except Exception as e:
                logger.warning(f"Could not read {file_path}: {e}")
                return []
        
        ext = Path(file_path).suffix.lower()
        
        if ext == ".py":
            deps = self._parse_python_imports(file_path, content)
        else:
            deps = self._parse_generic_imports(file_path, content)
        
        self._file_to_deps[file_path] = deps
        self._dependencies.extend(deps)
        
        # Add to networkx graph
        if self._graph is not None:
            for dep in deps:
                self._graph.add_edge(dep.source, dep.target, type=dep.dep_type.value)
        
        return deps
    
    def _parse_python_imports(self, file_path: str, content: str) -> List[Dependency]:
        """Parse Python imports using AST."""
        try:
            tree = ast.parse(content)
            visitor = PythonImportVisitor(file_path)
            visitor.visit(tree)
            return visitor.imports
        except SyntaxError as e:
            logger.debug(f"Could not parse {file_path}: {e}")
            return self._parse_generic_imports(file_path, content)
    
    def _parse_generic_imports(self, file_path: str, content: str) -> List[Dependency]:
        """Fallback regex-based import parsing."""
        deps = []
        
        # Python-style imports
        for match in re.finditer(r'^(?:from\s+(\S+)\s+)?import\s+(.+)$', content, re.MULTILINE):
            from_mod = match.group(1) or ""
            imports = match.group(2)
            for imp in imports.split(","):
                imp = imp.strip().split()[0]  # Handle "as" aliases
                target = f"{from_mod}.{imp}" if from_mod else imp
                deps.append(Dependency(
                    source=file_path,
                    target=target,
                    dep_type=DependencyType.IMPORT
                ))
        
        # JavaScript/TypeScript imports
        for match in re.finditer(r"(?:import|require)\s*\(?['\"](.+?)['\"]", content):
            deps.append(Dependency(
                source=file_path,
                target=match.group(1),
                dep_type=DependencyType.IMPORT
            ))

        return deps

    def get_dependents(self, target: str) -> List[str]:
        """
        Get all files that depend on a target.

        Args:
            target: Module or file path

        Returns:
            List of files that import/depend on target
        """
        if self._graph is not None:
            try:
                return list(self._graph.predecessors(target))
            except nx.NetworkXError:
                return []

        # Fallback without networkx
        dependents = []
        for dep in self._dependencies:
            if dep.target == target or dep.target.startswith(f"{target}."):
                if dep.source not in dependents:
                    dependents.append(dep.source)
        return dependents

    def get_dependencies(self, source: str) -> List[str]:
        """
        Get all dependencies of a file.

        Args:
            source: Source file path

        Returns:
            List of modules/files that source depends on
        """
        if self._graph is not None:
            try:
                return list(self._graph.successors(source))
            except nx.NetworkXError:
                return []

        deps = self._file_to_deps.get(source, [])
        return [d.target for d in deps]

    def analyze_impact(self, changed_file: str) -> ImpactResult:
        """
        Analyze the impact of changing a file.

        Args:
            changed_file: Path to the file being changed

        Returns:
            ImpactResult with affected files and risk assessment
        """
        result = ImpactResult(changed_file=changed_file)

        # Find direct dependents
        direct = self.get_dependents(changed_file)
        result.directly_affected = direct

        # Find transitive dependents (files that depend on dependents)
        transitive = set()
        if self._graph is not None:
            try:
                for node in direct:
                    ancestors = nx.ancestors(self._graph, node)
                    transitive.update(ancestors)
            except nx.NetworkXError:
                pass
        else:
            # Simple 1-level transitive without networkx
            for dep_file in direct:
                for dep in self._dependencies:
                    if dep.target == dep_file and dep.source not in direct:
                        transitive.add(dep.source)

        result.transitively_affected = list(transitive - set(direct))

        # Find affected test files
        all_affected = set(direct) | transitive
        test_patterns = ['test_', '_test.py', 'tests/', 'spec/']
        result.test_files_affected = [
            f for f in all_affected
            if any(p in f.lower() for p in test_patterns)
        ]

        # Calculate risk level
        total_affected = len(result.directly_affected) + len(result.transitively_affected)
        if total_affected == 0:
            result.risk_level = "low"
        elif total_affected <= 3:
            result.risk_level = "medium"
        elif total_affected <= 10:
            result.risk_level = "high"
        else:
            result.risk_level = "critical"

        result.summary = (
            f"Changing {changed_file} affects {len(result.directly_affected)} files directly, "
            f"{len(result.transitively_affected)} transitively. "
            f"{len(result.test_files_affected)} test files may need updates."
        )

        return result

    def get_module_graph(self) -> Dict[str, Any]:
        """
        Get a simplified module-level graph.

        Returns:
            Dict with nodes and edges for visualization
        """
        modules: Dict[str, Set[str]] = {}

        for dep in self._dependencies:
            # Extract module from file path
            source_module = self._path_to_module(dep.source)
            target_module = dep.target.split(".")[0]

            if source_module not in modules:
                modules[source_module] = set()
            modules[source_module].add(target_module)

        nodes = list(modules.keys())
        edges = []
        for source, targets in modules.items():
            for target in targets:
                if target in nodes:
                    edges.append({"source": source, "target": target})

        return {"nodes": nodes, "edges": edges}

    def _path_to_module(self, path: str) -> str:
        """Convert file path to module name."""
        path = path.replace("\\", "/")
        if "/" in path:
            parts = path.split("/")
            # Find 'services' or similar root
            for i, part in enumerate(parts):
                if part in ("services", "src", "lib"):
                    return parts[i + 1] if i + 1 < len(parts) else part
            return parts[-2] if len(parts) > 1 else parts[0]
        return Path(path).stem

    def format_for_prompt(self, file_path: str) -> str:
        """Format dependency info for prompt injection."""
        deps = self.get_dependencies(file_path)
        dependents = self.get_dependents(file_path)

        lines = [f"## Dependencies for {file_path}"]

        if deps:
            lines.append("### Imports:")
            for d in deps[:10]:
                lines.append(f"- {d}")

        if dependents:
            lines.append("### Imported by:")
            for d in dependents[:10]:
                lines.append(f"- {d}")

        if not deps and not dependents:
            lines.append("No dependency information available.")

        return "\n".join(lines)

    def to_mermaid(self) -> str:
        """Export graph as Mermaid diagram syntax."""
        lines = ["graph TD"]
        seen_edges = set()

        for dep in self._dependencies[:50]:  # Limit for readability
            source = self._sanitize_mermaid_id(dep.source)
            target = self._sanitize_mermaid_id(dep.target)
            edge = f"{source} --> {target}"
            if edge not in seen_edges:
                lines.append(f"    {edge}")
                seen_edges.add(edge)

        return "\n".join(lines)

    def _sanitize_mermaid_id(self, name: str) -> str:
        """Sanitize name for Mermaid diagram."""
        # Remove path, keep filename
        name = Path(name).stem if "/" in name or "\\" in name else name
        # Replace invalid characters
        return re.sub(r'[^a-zA-Z0-9_]', '_', name)


# Singleton accessor
_graph: Optional[DependencyGraph] = None


def get_dependency_graph() -> DependencyGraph:
    """Get singleton DependencyGraph instance."""
    global _graph
    if _graph is None:
        _graph = DependencyGraph()
    return _graph


def analyze_repository(repo_path: str, extensions: List[str] = None) -> DependencyGraph:
    """
    Analyze an entire repository and build dependency graph.

    Args:
        repo_path: Path to repository root
        extensions: File extensions to include (default: ['.py'])

    Returns:
        Populated DependencyGraph
    """
    if extensions is None:
        extensions = ['.py', '.js', '.ts']

    graph = DependencyGraph()
    repo = Path(repo_path)

    for ext in extensions:
        for file_path in repo.rglob(f"*{ext}"):
            # Skip common non-source directories
            if any(p in str(file_path) for p in ['node_modules', '.git', '__pycache__', 'venv']):
                continue
            graph.add_file(str(file_path))

    logger.info(f"Analyzed {len(graph._dependencies)} dependencies in {repo_path}")
    return graph

