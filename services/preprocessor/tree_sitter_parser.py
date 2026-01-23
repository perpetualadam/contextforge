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
    
    def __post_init__(self):
        if self.children is None:
            self.children = []


class TreeSitterParser:
    """
    Tree-sitter parser with incremental parsing support.
    
    Features:
    - Multi-language support (Python, JavaScript, TypeScript, Java, Rust, Go, etc.)
    - Incremental parsing for live editing
    - Semantic node extraction (functions, classes, methods)
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
            edits: List of edits applied (start_byte, old_end_byte, new_end_byte, start_point, old_end_point, new_end_point)

        Returns:
            Tree: Updated AST tree
        """
        code_bytes = code.encode('utf-8')

        # Apply edits to old tree
        for edit in edits:
            old_tree.edit(
                start_byte=edit['start_byte'],
                old_end_byte=edit['old_end_byte'],
                new_end_byte=edit['new_end_byte'],
                start_point=edit['start_point'],
                old_end_point=edit['old_end_point'],
                new_end_point=edit['new_end_point']
            )

        # Reparse with old tree
        new_tree = self.parser.parse(code_bytes, old_tree)
        return new_tree

    def extract_nodes(self, tree: Tree, code: str, node_types: Optional[List[NodeType]] = None) -> List[ParsedNode]:
        """
        Extract semantic nodes from AST.

        Args:
            tree: Parsed AST tree
            code: Source code
            node_types: Types of nodes to extract (default: all)

        Returns:
            List of ParsedNode objects
        """
        if node_types is None:
            node_types = [NodeType.FUNCTION, NodeType.CLASS, NodeType.METHOD]

        code_bytes = code.encode('utf-8')
        nodes = []

        def traverse(node: Node):
            # Check if this node matches any requested types
            parsed_node = self._node_to_parsed_node(node, code_bytes, node_types)
            if parsed_node:
                nodes.append(parsed_node)

            # Traverse children
            for child in node.children:
                traverse(child)

        traverse(tree.root_node)
        return nodes

    def _node_to_parsed_node(self, node: Node, code_bytes: bytes, node_types: List[NodeType]) -> Optional[ParsedNode]:
        """
        Convert tree-sitter node to ParsedNode if it matches requested types.

        Args:
            node: Tree-sitter node
            code_bytes: Source code as bytes
            node_types: Types of nodes to extract

        Returns:
            ParsedNode or None
        """
        # Check if node is a function
        if NodeType.FUNCTION in node_types and self._is_function_node(node):
            return ParsedNode(
                node_type=NodeType.FUNCTION,
                name=self._get_node_name(node, code_bytes),
                start_byte=node.start_byte,
                end_byte=node.end_byte,
                start_point=(node.start_point[0], node.start_point[1]),
                end_point=(node.end_point[0], node.end_point[1]),
                text=code_bytes[node.start_byte:node.end_byte].decode('utf-8')
            )

        # Check if node is a class
        if NodeType.CLASS in node_types and self._is_class_node(node):
            return ParsedNode(
                node_type=NodeType.CLASS,
                name=self._get_node_name(node, code_bytes),
                start_byte=node.start_byte,
                end_byte=node.end_byte,
                start_point=(node.start_point[0], node.start_point[1]),
                end_point=(node.end_point[0], node.end_point[1]),
                text=code_bytes[node.start_byte:node.end_byte].decode('utf-8')
            )

        return None

    def _is_function_node(self, node: Node) -> bool:
        """Check if node is a function."""
        function_types = self.FUNCTION_NODES.get(self.language_name, [])
        return node.type in function_types

    def _is_class_node(self, node: Node) -> bool:
        """Check if node is a class."""
        class_types = self.CLASS_NODES.get(self.language_name, [])
        return node.type in class_types

    def _get_node_name(self, node: Node, code_bytes: bytes) -> str:
        """
        Extract name from node.

        Args:
            node: Tree-sitter node
            code_bytes: Source code as bytes

        Returns:
            Node name or empty string
        """
        # Try to find name child node
        for child in node.children:
            if 'name' in child.type or child.type == 'identifier':
                return code_bytes[child.start_byte:child.end_byte].decode('utf-8')

        # Fallback: use node type
        return node.type

