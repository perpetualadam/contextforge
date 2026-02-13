"""
Tree-sitter parser for semantic code parsing.

This module provides tree-sitter-based parsing with incremental parsing support
for real-time code editing scenarios.
"""

import logging
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
from enum import Enum

try:
    from tree_sitter import Language, Parser, Tree, Node
    import tree_sitter_python
    import tree_sitter_javascript
    import tree_sitter_typescript
    import tree_sitter_java
    import tree_sitter_rust
    import tree_sitter_go
    import tree_sitter_cpp
    import tree_sitter_c_sharp
    import tree_sitter_ruby
    import tree_sitter_php
    import tree_sitter_kotlin
    import tree_sitter_julia
    import tree_sitter_html
    import tree_sitter_css
    TREE_SITTER_AVAILABLE = True
except ImportError:
    TREE_SITTER_AVAILABLE = False

logger = logging.getLogger(__name__)


class NodeType(Enum):
    """AST node types for semantic chunking."""
    FUNCTION = "function"
    CLASS = "class"
    METHOD = "method"
    IMPORT = "import"
    COMMENT = "comment"
    DOCSTRING = "docstring"
    VARIABLE = "variable"
    STATEMENT = "statement"
    EXPRESSION = "expression"
    BLOCK = "block"


class RelationshipType(Enum):
    """Types of code relationships extracted from AST."""
    IMPORTS = "IMPORTS"
    CALLS = "CALLS"
    INHERITS = "INHERITS"
    CONTAINS = "CONTAINS"


@dataclass
class Relationship:
    """A code relationship between two symbols."""
    rel_type: RelationshipType
    target: str  # Target symbol name
    context: str = ""  # Additional context (e.g., import alias)

    def to_dict(self) -> Dict[str, str]:
        result = {"type": self.rel_type.value, "target": self.target}
        if self.context:
            result["context"] = self.context
        return result


@dataclass
class ParsedNode:
    """Represents a parsed AST node."""
    node_type: NodeType
    name: str
    start_byte: int
    end_byte: int
    start_point: Tuple[int, int]  # (row, column)
    end_point: Tuple[int, int]    # (row, column)
    text: str
    children: List['ParsedNode'] = None
    relationships: List[Relationship] = None
    parent_name: str = ""  # Name of containing class/module

    def __post_init__(self):
        if self.children is None:
            self.children = []
        if self.relationships is None:
            self.relationships = []


class TreeSitterParser:
    """
    Tree-sitter parser with incremental parsing support.

    Features:
    - Multi-language support (Python, JavaScript, TypeScript, Java, Rust, Go, etc.)
    - Incremental parsing for live editing
    - Semantic node extraction (functions, classes, methods, imports)
    - Relationship extraction (calls, imports, inheritance, containment)
    - AST traversal and querying
    """

    # Language mappings
    LANGUAGE_MAP = {
        'python': tree_sitter_python if TREE_SITTER_AVAILABLE else None,
        'javascript': tree_sitter_javascript if TREE_SITTER_AVAILABLE else None,
        'typescript': tree_sitter_typescript if TREE_SITTER_AVAILABLE else None,
        'java': tree_sitter_java if TREE_SITTER_AVAILABLE else None,
        'rust': tree_sitter_rust if TREE_SITTER_AVAILABLE else None,
        'go': tree_sitter_go if TREE_SITTER_AVAILABLE else None,
        'cpp': tree_sitter_cpp if TREE_SITTER_AVAILABLE else None,
        'c': tree_sitter_cpp if TREE_SITTER_AVAILABLE else None,
        'csharp': tree_sitter_c_sharp if TREE_SITTER_AVAILABLE else None,
        'ruby': tree_sitter_ruby if TREE_SITTER_AVAILABLE else None,
        'php': tree_sitter_php if TREE_SITTER_AVAILABLE else None,
        'kotlin': tree_sitter_kotlin if TREE_SITTER_AVAILABLE else None,
        'julia': tree_sitter_julia if TREE_SITTER_AVAILABLE else None,
        'html': tree_sitter_html if TREE_SITTER_AVAILABLE else None,
        'css': tree_sitter_css if TREE_SITTER_AVAILABLE else None,
    }

    # Extension to language mapping for tree-sitter
    EXTENSION_TO_LANGUAGE = {
        '.py': 'python',
        '.js': 'javascript',
        '.jsx': 'javascript',
        '.ts': 'typescript',
        '.tsx': 'typescript',
        '.java': 'java',
        '.rs': 'rust',
        '.go': 'go',
        '.cpp': 'cpp', '.cc': 'cpp', '.cxx': 'cpp', '.hpp': 'cpp',
        '.c': 'c', '.h': 'c',
        '.cs': 'csharp',
        '.rb': 'ruby',
        '.php': 'php',
        '.kt': 'kotlin', '.kts': 'kotlin',
        '.jl': 'julia',
        '.html': 'html', '.htm': 'html',
        '.css': 'css', '.scss': 'css', '.sass': 'css', '.less': 'css',
    }

    # Node type mappings for different languages
    FUNCTION_NODES = {
        'python': ['function_definition', 'async_function_definition'],
        'javascript': ['function_declaration', 'arrow_function', 'function_expression'],
        'typescript': ['function_declaration', 'arrow_function', 'function_expression', 'method_definition'],
        'java': ['method_declaration', 'constructor_declaration'],
        'rust': ['function_item'],
        'go': ['function_declaration', 'method_declaration'],
        'cpp': ['function_definition'],
        'csharp': ['method_declaration', 'constructor_declaration'],
        'ruby': ['method', 'singleton_method'],
        'php': ['function_definition', 'method_declaration'],
        'kotlin': ['function_declaration'],
        'julia': ['function_definition'],
    }

    CLASS_NODES = {
        'python': ['class_definition'],
        'javascript': ['class_declaration'],
        'typescript': ['class_declaration', 'interface_declaration'],
        'java': ['class_declaration', 'interface_declaration'],
        'rust': ['struct_item', 'enum_item', 'trait_item'],
        'go': ['type_declaration'],
        'cpp': ['class_specifier', 'struct_specifier'],
        'csharp': ['class_declaration', 'interface_declaration', 'struct_declaration'],
        'ruby': ['class', 'module'],
        'php': ['class_declaration', 'interface_declaration', 'trait_declaration'],
        'kotlin': ['class_declaration', 'interface_declaration'],
        'julia': ['struct_definition'],
    }

    IMPORT_NODES = {
        'python': ['import_statement', 'import_from_statement'],
        'javascript': ['import_statement'],
        'typescript': ['import_statement'],
        'java': ['import_declaration'],
        'rust': ['use_declaration'],
        'go': ['import_declaration'],
        'cpp': ['preproc_include'],
        'csharp': ['using_directive'],
        'ruby': ['call'],  # require/include are method calls in Ruby
        'php': ['namespace_use_declaration'],
        'kotlin': ['import_header'],
        'julia': ['import_statement', 'using_clause'],
    }

    def __init__(self, language: str):
        """
        Initialize tree-sitter parser for a specific language.

        Args:
            language: Programming language (e.g., 'python', 'javascript')
        """
        if not TREE_SITTER_AVAILABLE:
            raise ImportError("tree-sitter is not installed. Install with: pip install tree-sitter")

        self.language_name = language.lower()
        if self.language_name not in self.LANGUAGE_MAP:
            raise ValueError(f"Unsupported language: {language}")

        # Get language module
        lang_module = self.LANGUAGE_MAP[self.language_name]
        if lang_module is None:
            raise ValueError(f"Language module not available for: {language}")

        # Initialize parser
        self.parser = Parser()
        self.language = Language(lang_module.language())
        self.parser.language = self.language

        logger.info(f"Initialized tree-sitter parser for {language}")

    @classmethod
    def language_for_extension(cls, ext: str) -> Optional[str]:
        """Get the tree-sitter language name for a file extension.

        Args:
            ext: File extension including dot (e.g., '.py')

        Returns:
            Language name or None if unsupported
        """
        return cls.EXTENSION_TO_LANGUAGE.get(ext.lower())

    @classmethod
    def supports_language(cls, language: str) -> bool:
        """Check if tree-sitter supports a given language."""
        return (
            TREE_SITTER_AVAILABLE
            and language.lower() in cls.LANGUAGE_MAP
            and cls.LANGUAGE_MAP[language.lower()] is not None
        )

    def parse(self, code: str) -> Tree:
        """
        Parse code and return AST.

        Args:
            code: Source code to parse

        Returns:
            Tree: Parsed AST tree
        """
        code_bytes = code.encode('utf-8')
        tree = self.parser.parse(code_bytes)
        return tree

    def incremental_parse(self, old_tree: Tree, code: str, edits: List[Dict[str, Any]]) -> Tree:
        """
        Incrementally parse code with edits.

        Args:
            old_tree: Previous AST tree
            code: Updated source code
            edits: List of edits applied

        Returns:
            Tree: Updated AST tree
        """
        code_bytes = code.encode('utf-8')

        for edit in edits:
            old_tree.edit(
                start_byte=edit['start_byte'],
                old_end_byte=edit['old_end_byte'],
                new_end_byte=edit['new_end_byte'],
                start_point=edit['start_point'],
                old_end_point=edit['old_end_point'],
                new_end_point=edit['new_end_point']
            )

        new_tree = self.parser.parse(code_bytes, old_tree)
        return new_tree

    def extract_nodes(
        self,
        tree: Tree,
        code: str,
        node_types: Optional[List[NodeType]] = None,
        extract_relationships: bool = True,
    ) -> List[ParsedNode]:
        """
        Extract semantic nodes from AST.

        Args:
            tree: Parsed AST tree
            code: Source code
            node_types: Types of nodes to extract (default: functions, classes, methods, imports)
            extract_relationships: Whether to extract code relationships

        Returns:
            List of ParsedNode objects
        """
        if node_types is None:
            node_types = [NodeType.FUNCTION, NodeType.CLASS, NodeType.METHOD, NodeType.IMPORT]

        code_bytes = code.encode('utf-8')
        nodes = []

        def traverse(node: Node, parent_class_name: str = ""):
            parsed_node = self._node_to_parsed_node(
                node, code_bytes, node_types, parent_class_name
            )
            if parsed_node:
                # Extract relationships if requested
                if extract_relationships:
                    parsed_node.relationships = self._extract_relationships(
                        node, code_bytes, parsed_node
                    )
                nodes.append(parsed_node)

                # If this is a class, traverse children with class name context
                if parsed_node.node_type == NodeType.CLASS:
                    for child in node.children:
                        traverse(child, parent_class_name=parsed_node.name)
                    return  # Don't re-traverse children

            # Traverse children
            for child in node.children:
                traverse(child, parent_class_name)

        traverse(tree.root_node)
        return nodes

    def _node_to_parsed_node(
        self,
        node: Node,
        code_bytes: bytes,
        node_types: List[NodeType],
        parent_class_name: str = "",
    ) -> Optional[ParsedNode]:
        """Convert tree-sitter node to ParsedNode if it matches requested types."""
        text = code_bytes[node.start_byte:node.end_byte].decode('utf-8', errors='replace')

        # Check for import nodes
        if NodeType.IMPORT in node_types and self._is_import_node(node):
            return ParsedNode(
                node_type=NodeType.IMPORT,
                name=self._get_import_name(node, code_bytes),
                start_byte=node.start_byte,
                end_byte=node.end_byte,
                start_point=(node.start_point[0], node.start_point[1]),
                end_point=(node.end_point[0], node.end_point[1]),
                text=text,
            )

        # Check for function nodes
        if NodeType.FUNCTION in node_types and self._is_function_node(node):
            # If inside a class, it's a method
            actual_type = NodeType.METHOD if parent_class_name else NodeType.FUNCTION
            return ParsedNode(
                node_type=actual_type,
                name=self._get_node_name(node, code_bytes),
                start_byte=node.start_byte,
                end_byte=node.end_byte,
                start_point=(node.start_point[0], node.start_point[1]),
                end_point=(node.end_point[0], node.end_point[1]),
                text=text,
                parent_name=parent_class_name,
            )

        # Check for class nodes
        if NodeType.CLASS in node_types and self._is_class_node(node):
            return ParsedNode(
                node_type=NodeType.CLASS,
                name=self._get_node_name(node, code_bytes),
                start_byte=node.start_byte,
                end_byte=node.end_byte,
                start_point=(node.start_point[0], node.start_point[1]),
                end_point=(node.end_point[0], node.end_point[1]),
                text=text,
            )

        return None

    def _extract_relationships(
        self, node: Node, code_bytes: bytes, parsed_node: ParsedNode
    ) -> List[Relationship]:
        """Extract code relationships from an AST node."""
        relationships = []

        if parsed_node.node_type == NodeType.IMPORT:
            # The import itself is a relationship
            relationships.append(Relationship(
                rel_type=RelationshipType.IMPORTS,
                target=parsed_node.name,
            ))

        elif parsed_node.node_type == NodeType.CLASS:
            # Extract inheritance (base classes / superclasses)
            bases = self._extract_base_classes(node, code_bytes)
            for base in bases:
                relationships.append(Relationship(
                    rel_type=RelationshipType.INHERITS,
                    target=base,
                ))
            # Extract contained methods
            methods = self._extract_method_names(node, code_bytes)
            for method in methods:
                relationships.append(Relationship(
                    rel_type=RelationshipType.CONTAINS,
                    target=method,
                ))

        elif parsed_node.node_type in (NodeType.FUNCTION, NodeType.METHOD):
            # Extract function calls within the body
            calls = self._extract_function_calls(node, code_bytes)
            for call_name in calls:
                relationships.append(Relationship(
                    rel_type=RelationshipType.CALLS,
                    target=call_name,
                ))
            # If this is a method, record containment
            if parsed_node.parent_name:
                relationships.append(Relationship(
                    rel_type=RelationshipType.CONTAINS,
                    target=parsed_node.parent_name,
                    context="member_of",
                ))

        return relationships

    def _extract_base_classes(self, node: Node, code_bytes: bytes) -> List[str]:
        """Extract base class names from a class definition node."""
        bases = []
        for child in node.children:
            # Python: argument_list contains base classes
            if child.type in ('argument_list', 'superclass', 'super_interfaces',
                              'superclasses', 'class_heritage'):
                for arg in child.children:
                    if arg.type in ('identifier', 'dotted_name', 'type_identifier',
                                    'scoped_identifier', 'attribute'):
                        name = code_bytes[arg.start_byte:arg.end_byte].decode('utf-8', errors='replace')
                        if name not in ('(', ')', ',', ' '):
                            bases.append(name)
        return bases

    def _extract_method_names(self, node: Node, code_bytes: bytes) -> List[str]:
        """Extract method names defined inside a class body."""
        methods = []
        function_types = self.FUNCTION_NODES.get(self.language_name, [])
        for child in node.children:
            # Look inside class body
            if child.type in ('block', 'class_body', 'body', 'declaration_list'):
                for member in child.children:
                    if member.type in function_types:
                        name = self._get_node_name(member, code_bytes)
                        if name:
                            methods.append(name)
            elif child.type in function_types:
                name = self._get_node_name(child, code_bytes)
                if name:
                    methods.append(name)
        return methods

    def _extract_function_calls(self, node: Node, code_bytes: bytes) -> List[str]:
        """Extract function call names from within a node (non-recursive into nested defs)."""
        calls = set()
        function_types = set(self.FUNCTION_NODES.get(self.language_name, []))
        class_types = set(self.CLASS_NODES.get(self.language_name, []))

        def walk(n: Node):
            # Don't recurse into nested function/class definitions
            if n != node and n.type in (function_types | class_types):
                return
            if n.type == 'call':
                # Get the function name from the call expression
                call_name = self._get_call_name(n, code_bytes)
                if call_name:
                    calls.add(call_name)
            for child in n.children:
                walk(child)

        walk(node)
        return list(calls)

    def _get_call_name(self, call_node: Node, code_bytes: bytes) -> str:
        """Extract the function name from a call expression node."""
        if not call_node.children:
            return ""
        # The first child of a call is usually the function expression
        func_node = call_node.children[0]
        text = code_bytes[func_node.start_byte:func_node.end_byte].decode('utf-8', errors='replace')
        # Simplify: for `self.method()` return `method`, for `obj.func()` return `obj.func`
        # For `func()` return `func`
        if '.' in text and text.startswith('self.'):
            return text[5:]  # strip 'self.'
        return text

    def _is_function_node(self, node: Node) -> bool:
        """Check if node is a function."""
        function_types = self.FUNCTION_NODES.get(self.language_name, [])
        return node.type in function_types

    def _is_class_node(self, node: Node) -> bool:
        """Check if node is a class."""
        class_types = self.CLASS_NODES.get(self.language_name, [])
        return node.type in class_types

    def _is_import_node(self, node: Node) -> bool:
        """Check if node is an import statement."""
        import_types = self.IMPORT_NODES.get(self.language_name, [])
        return node.type in import_types

    def _get_import_name(self, node: Node, code_bytes: bytes) -> str:
        """Extract the module/package name from an import node."""
        text = code_bytes[node.start_byte:node.end_byte].decode('utf-8', errors='replace').strip()
        # Try to find a dotted_name or module_name child
        for child in node.children:
            if child.type in ('dotted_name', 'module_name', 'scoped_identifier',
                              'identifier', 'string_literal', 'call_expression'):
                return code_bytes[child.start_byte:child.end_byte].decode('utf-8', errors='replace')
        # Fallback: return the full import text
        return text

    def _get_node_name(self, node: Node, code_bytes: bytes) -> str:
        """
        Extract name from node.

        Args:
            node: Tree-sitter node
            code_bytes: Source code as bytes

        Returns:
            Node name or empty string
        """
        for child in node.children:
            if 'name' in child.type or child.type == 'identifier':
                return code_bytes[child.start_byte:child.end_byte].decode('utf-8', errors='replace')

        # Fallback: use node type
        return node.type
