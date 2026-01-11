"""
Tests for the ContextForge dependency graph module.

Copyright (c) 2025 ContextForge
"""

import pytest
from unittest.mock import patch, MagicMock


class TestDependencyType:
    """Test DependencyType enum."""
    
    def test_dependency_types(self):
        """Test dependency types exist."""
        from services.dependency_graph import DependencyType
        
        assert DependencyType.IMPORT.value == "import"
        assert DependencyType.CALL.value == "call"
        assert DependencyType.INHERITANCE.value == "inheritance"
        assert DependencyType.COMPOSITION.value == "composition"


class TestDependency:
    """Test Dependency dataclass."""
    
    def test_dependency_creation(self):
        """Test creating a Dependency."""
        from services.dependency_graph import Dependency, DependencyType
        
        dep = Dependency(
            source="module_a.py",
            target="module_b",
            dep_type=DependencyType.IMPORT,
            line=5
        )
        
        assert dep.source == "module_a.py"
        assert dep.target == "module_b"
        assert dep.dep_type == DependencyType.IMPORT
        assert dep.line == 5


class TestImpactResult:
    """Test ImpactResult dataclass."""
    
    def test_impact_result_creation(self):
        """Test creating an ImpactResult."""
        from services.dependency_graph import ImpactResult
        
        result = ImpactResult(
            changed_file="test.py",
            directly_affected=["a.py", "b.py"],
            risk_level="medium"
        )
        
        assert result.changed_file == "test.py"
        assert len(result.directly_affected) == 2
        assert result.risk_level == "medium"


class TestPythonImportVisitor:
    """Test PythonImportVisitor class."""
    
    def test_visit_import(self):
        """Test visiting import statements."""
        import ast
        from services.dependency_graph import PythonImportVisitor
        
        code = "import os\nimport sys"
        tree = ast.parse(code)
        
        visitor = PythonImportVisitor("test.py")
        visitor.visit(tree)
        
        assert len(visitor.imports) == 2
        assert visitor.imports[0].target == "os"
        assert visitor.imports[1].target == "sys"
    
    def test_visit_import_from(self):
        """Test visiting from...import statements."""
        import ast
        from services.dependency_graph import PythonImportVisitor
        
        code = "from os.path import join, exists"
        tree = ast.parse(code)
        
        visitor = PythonImportVisitor("test.py")
        visitor.visit(tree)
        
        assert len(visitor.imports) == 2
        assert "os.path.join" in visitor.imports[0].target
        assert "os.path.exists" in visitor.imports[1].target


class TestDependencyGraph:
    """Test DependencyGraph class."""
    
    def test_graph_creation(self):
        """Test creating a DependencyGraph."""
        from services.dependency_graph import DependencyGraph
        
        graph = DependencyGraph()
        assert graph is not None
    
    def test_add_file_with_content(self):
        """Test adding a file with content."""
        from services.dependency_graph import DependencyGraph
        
        graph = DependencyGraph()
        
        content = "import os\nfrom pathlib import Path"
        deps = graph.add_file("test.py", content)
        
        assert len(deps) == 2
    
    def test_get_dependencies(self):
        """Test getting dependencies of a file."""
        from services.dependency_graph import DependencyGraph
        
        graph = DependencyGraph()
        graph.add_file("test.py", "import os\nimport sys")
        
        deps = graph.get_dependencies("test.py")
        
        assert "os" in deps
        assert "sys" in deps
    
    def test_analyze_impact(self):
        """Test impact analysis."""
        from services.dependency_graph import DependencyGraph
        
        graph = DependencyGraph()
        graph.add_file("a.py", "import b")
        graph.add_file("b.py", "import c")
        
        impact = graph.analyze_impact("c.py")
        
        assert impact.changed_file == "c.py"
        assert impact.risk_level in ["low", "medium", "high", "critical"]
    
    def test_format_for_prompt(self):
        """Test formatting for prompt."""
        from services.dependency_graph import DependencyGraph
        
        graph = DependencyGraph()
        graph.add_file("test.py", "import os")
        
        formatted = graph.format_for_prompt("test.py")
        
        assert "Dependencies" in formatted
        assert "test.py" in formatted
    
    def test_to_mermaid(self):
        """Test Mermaid diagram generation."""
        from services.dependency_graph import DependencyGraph
        
        graph = DependencyGraph()
        graph.add_file("test.py", "import os")
        
        mermaid = graph.to_mermaid()
        
        assert "graph TD" in mermaid
    
    def test_singleton_accessor(self):
        """Test get_dependency_graph singleton."""
        from services.dependency_graph import get_dependency_graph
        import services.dependency_graph as dg_module
        
        dg_module._graph = None
        
        g1 = get_dependency_graph()
        g2 = get_dependency_graph()
        
        assert g1 is g2

