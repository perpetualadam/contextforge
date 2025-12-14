"""
Language-aware chunking for different file types.

Supported languages:
- Python (.py) - AST-based parsing with docstring extraction
- JavaScript/TypeScript (.js, .jsx, .ts, .tsx) - Regex-based parsing
- Markdown (.md, .markdown) - Heading-based sectioning
- C# (.cs) - Regex-based with namespace, class, interface, method support
- Rust (.rs) - Regex-based with mod, fn, struct, enum, impl, trait support
- R (.r, .R, .rmd, .Rmd) - Regex-based with function, S4/R6 class support
- Java (.java) - Regex-based with package, class, interface, enum, method support
- Go (.go) - Regex-based with package, func, struct, interface support
- Swift (.swift) - Regex-based with class, struct, enum, protocol, extension support
- Kotlin (.kt, .kts) - Regex-based with class, interface, object, fun support
"""

import ast
import re
import logging
from typing import List, Dict, Any, Optional
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)


class BaseChunker(ABC):
    """Base class for language-specific chunkers."""
    
    def __init__(self, max_chunk_size: int = 1000, overlap: int = 100):
        self.max_chunk_size = max_chunk_size
        self.overlap = overlap
    
    @abstractmethod
    def chunk(self, content: str, file_path: str) -> List[Dict[str, Any]]:
        """Chunk content into meaningful segments."""
        pass
    
    def create_chunk(self, text: str, file_path: str, start_line: int, 
                    end_line: int, chunk_type: str = "text", 
                    metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Create a standardized chunk object."""
        return {
            "text": text.strip(),
            "meta": {
                "file_path": file_path,
                "start_line": start_line,
                "end_line": end_line,
                "chunk_type": chunk_type,
                "language": self.get_language(),
                **(metadata or {})
            }
        }
    
    @abstractmethod
    def get_language(self) -> str:
        """Get the language identifier."""
        pass


class PythonChunker(BaseChunker):
    """AST-based chunker for Python files."""
    
    def get_language(self) -> str:
        return "python"
    
    def chunk(self, content: str, file_path: str) -> List[Dict[str, Any]]:
        """Chunk Python code using AST analysis."""
        chunks = []
        lines = content.split('\n')
        
        try:
            tree = ast.parse(content)
            
            # Extract top-level definitions
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    chunk = self._extract_function(node, lines, file_path)
                    if chunk:
                        chunks.append(chunk)
                
                elif isinstance(node, ast.ClassDef):
                    chunk = self._extract_class(node, lines, file_path)
                    if chunk:
                        chunks.append(chunk)
                
                elif isinstance(node, ast.Import):
                    chunk = self._extract_import(node, lines, file_path)
                    if chunk:
                        chunks.append(chunk)
                
                elif isinstance(node, ast.ImportFrom):
                    chunk = self._extract_import_from(node, lines, file_path)
                    if chunk:
                        chunks.append(chunk)
            
            # Add module-level docstring if present
            if (tree.body and isinstance(tree.body[0], ast.Expr) and 
                isinstance(tree.body[0].value, ast.Constant) and 
                isinstance(tree.body[0].value.value, str)):
                
                docstring_node = tree.body[0]
                chunk = self.create_chunk(
                    text=docstring_node.value.value,
                    file_path=file_path,
                    start_line=docstring_node.lineno,
                    end_line=docstring_node.end_lineno or docstring_node.lineno,
                    chunk_type="module_docstring"
                )
                chunks.append(chunk)
        
        except SyntaxError as e:
            logger.warning(f"Syntax error in {file_path}: {e}")
            # Fall back to simple text chunking
            return self._fallback_chunk(content, file_path)
        
        # If no AST chunks found, fall back to simple chunking
        if not chunks:
            return self._fallback_chunk(content, file_path)
        
        return chunks
    
    def _extract_function(self, node: ast.FunctionDef, lines: List[str], 
                         file_path: str) -> Optional[Dict[str, Any]]:
        """Extract function definition and docstring."""
        start_line = node.lineno
        end_line = node.end_lineno or start_line
        
        # Get function text
        function_lines = lines[start_line-1:end_line]
        function_text = '\n'.join(function_lines)
        
        # Extract docstring if present
        docstring = ast.get_docstring(node)
        
        metadata = {
            "function_name": node.name,
            "is_async": isinstance(node, ast.AsyncFunctionDef),
            "args": [arg.arg for arg in node.args.args],
            "docstring": docstring
        }
        
        return self.create_chunk(
            text=function_text,
            file_path=file_path,
            start_line=start_line,
            end_line=end_line,
            chunk_type="function",
            metadata=metadata
        )
    
    def _extract_class(self, node: ast.ClassDef, lines: List[str], 
                      file_path: str) -> Optional[Dict[str, Any]]:
        """Extract class definition and docstring."""
        start_line = node.lineno
        end_line = node.end_lineno or start_line
        
        # Get class text
        class_lines = lines[start_line-1:end_line]
        class_text = '\n'.join(class_lines)
        
        # Extract docstring if present
        docstring = ast.get_docstring(node)
        
        # Get method names
        methods = []
        for item in node.body:
            if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                methods.append(item.name)
        
        metadata = {
            "class_name": node.name,
            "base_classes": [base.id if isinstance(base, ast.Name) else str(base) 
                           for base in node.bases],
            "methods": methods,
            "docstring": docstring
        }
        
        return self.create_chunk(
            text=class_text,
            file_path=file_path,
            start_line=start_line,
            end_line=end_line,
            chunk_type="class",
            metadata=metadata
        )
    
    def _extract_import(self, node: ast.Import, lines: List[str], 
                       file_path: str) -> Optional[Dict[str, Any]]:
        """Extract import statement."""
        line_num = node.lineno
        import_text = lines[line_num-1]
        
        modules = [alias.name for alias in node.names]
        
        metadata = {
            "import_type": "import",
            "modules": modules
        }
        
        return self.create_chunk(
            text=import_text,
            file_path=file_path,
            start_line=line_num,
            end_line=line_num,
            chunk_type="import",
            metadata=metadata
        )
    
    def _extract_import_from(self, node: ast.ImportFrom, lines: List[str], 
                           file_path: str) -> Optional[Dict[str, Any]]:
        """Extract from-import statement."""
        line_num = node.lineno
        import_text = lines[line_num-1]
        
        module = node.module or ""
        names = [alias.name for alias in node.names]
        
        metadata = {
            "import_type": "from_import",
            "module": module,
            "names": names
        }
        
        return self.create_chunk(
            text=import_text,
            file_path=file_path,
            start_line=line_num,
            end_line=line_num,
            chunk_type="import",
            metadata=metadata
        )
    
    def _fallback_chunk(self, content: str, file_path: str) -> List[Dict[str, Any]]:
        """Fallback to simple text chunking."""
        chunks = []
        lines = content.split('\n')
        
        current_chunk = []
        current_size = 0
        start_line = 1
        
        for i, line in enumerate(lines, 1):
            line_size = len(line)
            
            if current_size + line_size > self.max_chunk_size and current_chunk:
                # Create chunk
                chunk_text = '\n'.join(current_chunk)
                chunk = self.create_chunk(
                    text=chunk_text,
                    file_path=file_path,
                    start_line=start_line,
                    end_line=i-1,
                    chunk_type="text_block"
                )
                chunks.append(chunk)
                
                # Start new chunk with overlap
                overlap_lines = current_chunk[-self.overlap//20:] if current_chunk else []
                current_chunk = overlap_lines + [line]
                current_size = sum(len(l) for l in current_chunk)
                start_line = i - len(overlap_lines)
            else:
                current_chunk.append(line)
                current_size += line_size
        
        # Add final chunk
        if current_chunk:
            chunk_text = '\n'.join(current_chunk)
            chunk = self.create_chunk(
                text=chunk_text,
                file_path=file_path,
                start_line=start_line,
                end_line=len(lines),
                chunk_type="text_block"
            )
            chunks.append(chunk)
        
        return chunks


class JavaScriptChunker(BaseChunker):
    """Regex-based chunker for JavaScript/TypeScript files."""
    
    def __init__(self, max_chunk_size: int = 1000, overlap: int = 100):
        super().__init__(max_chunk_size, overlap)
        
        # Regex patterns for JS/TS constructs
        self.function_pattern = re.compile(
            r'(?:export\s+)?(?:async\s+)?function\s+(\w+)\s*\([^)]*\)\s*{',
            re.MULTILINE
        )
        self.arrow_function_pattern = re.compile(
            r'(?:const|let|var)\s+(\w+)\s*=\s*(?:async\s+)?\([^)]*\)\s*=>\s*{',
            re.MULTILINE
        )
        self.class_pattern = re.compile(
            r'(?:export\s+)?class\s+(\w+)(?:\s+extends\s+\w+)?\s*{',
            re.MULTILINE
        )
        self.import_pattern = re.compile(
            r'import\s+.*?from\s+[\'"][^\'"]+[\'"];?',
            re.MULTILINE
        )
    
    def get_language(self) -> str:
        return "javascript"
    
    def chunk(self, content: str, file_path: str) -> List[Dict[str, Any]]:
        """Chunk JavaScript/TypeScript code using regex patterns."""
        chunks = []
        lines = content.split('\n')
        
        # Extract imports
        for match in self.import_pattern.finditer(content):
            start_pos = match.start()
            end_pos = match.end()
            start_line = content[:start_pos].count('\n') + 1
            end_line = content[:end_pos].count('\n') + 1
            
            chunk = self.create_chunk(
                text=match.group(0),
                file_path=file_path,
                start_line=start_line,
                end_line=end_line,
                chunk_type="import"
            )
            chunks.append(chunk)
        
        # Extract functions
        for pattern, chunk_type in [
            (self.function_pattern, "function"),
            (self.arrow_function_pattern, "arrow_function"),
            (self.class_pattern, "class")
        ]:
            for match in pattern.finditer(content):
                function_chunk = self._extract_block(match, content, file_path, chunk_type)
                if function_chunk:
                    chunks.append(function_chunk)
        
        # If no structured chunks found, fall back to simple chunking
        if not chunks:
            return self._fallback_chunk(content, file_path)
        
        return chunks
    
    def _extract_block(self, match: re.Match, content: str, file_path: str, 
                      chunk_type: str) -> Optional[Dict[str, Any]]:
        """Extract a code block starting from a regex match."""
        start_pos = match.start()
        start_line = content[:start_pos].count('\n') + 1
        
        # Find the matching closing brace
        brace_count = 0
        pos = match.end() - 1  # Start from the opening brace
        
        while pos < len(content):
            if content[pos] == '{':
                brace_count += 1
            elif content[pos] == '}':
                brace_count -= 1
                if brace_count == 0:
                    break
            pos += 1
        
        if brace_count != 0:
            return None  # Unmatched braces
        
        end_pos = pos + 1
        end_line = content[:end_pos].count('\n') + 1
        
        block_text = content[start_pos:end_pos]
        
        metadata = {
            "name": match.group(1) if match.groups() else "anonymous",
            "block_type": chunk_type
        }
        
        return self.create_chunk(
            text=block_text,
            file_path=file_path,
            start_line=start_line,
            end_line=end_line,
            chunk_type=chunk_type,
            metadata=metadata
        )
    
    def _fallback_chunk(self, content: str, file_path: str) -> List[Dict[str, Any]]:
        """Fallback to simple text chunking."""
        # Similar to Python fallback but simpler
        chunks = []
        lines = content.split('\n')
        
        for i in range(0, len(lines), self.max_chunk_size // 50):
            chunk_lines = lines[i:i + self.max_chunk_size // 50]
            if chunk_lines:
                chunk_text = '\n'.join(chunk_lines)
                chunk = self.create_chunk(
                    text=chunk_text,
                    file_path=file_path,
                    start_line=i + 1,
                    end_line=min(i + len(chunk_lines), len(lines)),
                    chunk_type="text_block"
                )
                chunks.append(chunk)
        
        return chunks


class CSharpChunker(BaseChunker):
    """Regex-based chunker for C# files."""

    def __init__(self, max_chunk_size: int = 1000, overlap: int = 100):
        super().__init__(max_chunk_size, overlap)

        # Regex patterns for C# constructs
        self.namespace_pattern = re.compile(
            r'namespace\s+([\w.]+)\s*{',
            re.MULTILINE
        )
        self.class_pattern = re.compile(
            r'(?:public|private|protected|internal)?\s*(?:static\s+)?(?:partial\s+)?(?:abstract\s+)?(?:sealed\s+)?class\s+(\w+)(?:<[^>]+>)?(?:\s*:\s*[\w,\s<>]+)?\s*{',
            re.MULTILINE
        )
        self.interface_pattern = re.compile(
            r'(?:public|private|protected|internal)?\s*interface\s+(\w+)(?:<[^>]+>)?(?:\s*:\s*[\w,\s<>]+)?\s*{',
            re.MULTILINE
        )
        self.method_pattern = re.compile(
            r'(?:public|private|protected|internal)?\s*(?:static\s+)?(?:async\s+)?(?:virtual\s+)?(?:override\s+)?(?:abstract\s+)?[\w<>\[\],\s]+\s+(\w+)\s*\([^)]*\)\s*(?:where\s+[^{]+)?\s*{',
            re.MULTILINE
        )
        self.property_pattern = re.compile(
            r'(?:public|private|protected|internal)?\s*(?:static\s+)?(?:virtual\s+)?(?:override\s+)?[\w<>\[\]?]+\s+(\w+)\s*{\s*(?:get|set)',
            re.MULTILINE
        )
        self.using_pattern = re.compile(
            r'^using\s+[\w.]+(?:\s*=\s*[\w.]+)?;',
            re.MULTILINE
        )
        # XML doc comment pattern
        self.doc_comment_pattern = re.compile(
            r'///\s*<summary>(.*?)</summary>',
            re.DOTALL
        )

    def get_language(self) -> str:
        return "csharp"

    def chunk(self, content: str, file_path: str) -> List[Dict[str, Any]]:
        """Chunk C# code using regex patterns."""
        chunks = []

        # Extract using statements
        for match in self.using_pattern.finditer(content):
            start_pos = match.start()
            end_pos = match.end()
            start_line = content[:start_pos].count('\n') + 1
            end_line = content[:end_pos].count('\n') + 1

            chunk = self.create_chunk(
                text=match.group(0),
                file_path=file_path,
                start_line=start_line,
                end_line=end_line,
                chunk_type="using"
            )
            chunks.append(chunk)

        # Extract namespaces, classes, interfaces, methods
        for pattern, chunk_type in [
            (self.namespace_pattern, "namespace"),
            (self.class_pattern, "class"),
            (self.interface_pattern, "interface"),
            (self.method_pattern, "method"),
        ]:
            for match in pattern.finditer(content):
                block_chunk = self._extract_block(match, content, file_path, chunk_type)
                if block_chunk:
                    chunks.append(block_chunk)

        if not chunks:
            return self._fallback_chunk(content, file_path)

        return chunks

    def _extract_block(self, match: re.Match, content: str, file_path: str,
                      chunk_type: str) -> Optional[Dict[str, Any]]:
        """Extract a code block starting from a regex match."""
        start_pos = match.start()

        # Look for XML doc comments before the block
        doc_comment = None
        preceding_content = content[:start_pos]
        lines_before = preceding_content.split('\n')
        if lines_before:
            # Check last few lines for doc comments
            doc_lines = []
            for line in reversed(lines_before[-10:]):
                stripped = line.strip()
                if stripped.startswith('///'):
                    doc_lines.insert(0, stripped[3:].strip())
                elif stripped and not stripped.startswith('['):  # Skip attributes
                    break
            if doc_lines:
                doc_comment = ' '.join(doc_lines)

        start_line = content[:start_pos].count('\n') + 1

        # Find matching closing brace
        brace_count = 0
        pos = match.end() - 1

        while pos < len(content):
            if content[pos] == '{':
                brace_count += 1
            elif content[pos] == '}':
                brace_count -= 1
                if brace_count == 0:
                    break
            pos += 1

        if brace_count != 0:
            return None

        end_pos = pos + 1
        end_line = content[:end_pos].count('\n') + 1

        block_text = content[start_pos:end_pos]

        metadata = {
            "name": match.group(1) if match.groups() else "anonymous",
            "block_type": chunk_type,
            "doc_comment": doc_comment
        }

        return self.create_chunk(
            text=block_text,
            file_path=file_path,
            start_line=start_line,
            end_line=end_line,
            chunk_type=chunk_type,
            metadata=metadata
        )

    def _fallback_chunk(self, content: str, file_path: str) -> List[Dict[str, Any]]:
        """Fallback to simple text chunking."""
        chunks = []
        lines = content.split('\n')

        for i in range(0, len(lines), self.max_chunk_size // 50):
            chunk_lines = lines[i:i + self.max_chunk_size // 50]
            if chunk_lines:
                chunk_text = '\n'.join(chunk_lines)
                chunk = self.create_chunk(
                    text=chunk_text,
                    file_path=file_path,
                    start_line=i + 1,
                    end_line=min(i + len(chunk_lines), len(lines)),
                    chunk_type="text_block"
                )
                chunks.append(chunk)

        return chunks


class RustChunker(BaseChunker):
    """Regex-based chunker for Rust files."""

    def __init__(self, max_chunk_size: int = 1000, overlap: int = 100):
        super().__init__(max_chunk_size, overlap)

        # Regex patterns for Rust constructs
        self.mod_pattern = re.compile(
            r'(?:pub\s+)?mod\s+(\w+)\s*{',
            re.MULTILINE
        )
        self.fn_pattern = re.compile(
            r'(?:pub(?:\([^)]*\))?\s+)?(?:async\s+)?(?:unsafe\s+)?(?:extern\s+"[^"]+"\s+)?fn\s+(\w+)(?:<[^>]+>)?\s*\([^)]*\)(?:\s*->\s*[^{]+)?\s*(?:where\s+[^{]+)?\s*{',
            re.MULTILINE
        )
        self.struct_pattern = re.compile(
            r'(?:pub(?:\([^)]*\))?\s+)?struct\s+(\w+)(?:<[^>]+>)?(?:\s*\([^)]*\)\s*;|\s*(?:where\s+[^{]+)?\s*{)',
            re.MULTILINE
        )
        self.enum_pattern = re.compile(
            r'(?:pub(?:\([^)]*\))?\s+)?enum\s+(\w+)(?:<[^>]+>)?(?:\s*where\s+[^{]+)?\s*{',
            re.MULTILINE
        )
        self.impl_pattern = re.compile(
            r'impl(?:<[^>]+>)?\s+(?:([\w:]+)(?:<[^>]+>)?\s+for\s+)?([\w:]+)(?:<[^>]+>)?(?:\s*where\s+[^{]+)?\s*{',
            re.MULTILINE
        )
        self.trait_pattern = re.compile(
            r'(?:pub(?:\([^)]*\))?\s+)?(?:unsafe\s+)?trait\s+(\w+)(?:<[^>]+>)?(?:\s*:\s*[^{]+)?(?:\s*where\s+[^{]+)?\s*{',
            re.MULTILINE
        )
        self.use_pattern = re.compile(
            r'^use\s+[\w:]+(?:::\{[^}]+\})?(?:::\*)?;',
            re.MULTILINE
        )
        # Rust doc comment patterns
        self.doc_comment_pattern = re.compile(r'///\s*(.*)')
        self.block_doc_pattern = re.compile(r'/\*\*\s*(.*?)\*/', re.DOTALL)

    def get_language(self) -> str:
        return "rust"

    def chunk(self, content: str, file_path: str) -> List[Dict[str, Any]]:
        """Chunk Rust code using regex patterns."""
        chunks = []

        # Extract use statements
        for match in self.use_pattern.finditer(content):
            start_pos = match.start()
            end_pos = match.end()
            start_line = content[:start_pos].count('\n') + 1
            end_line = content[:end_pos].count('\n') + 1

            chunk = self.create_chunk(
                text=match.group(0),
                file_path=file_path,
                start_line=start_line,
                end_line=end_line,
                chunk_type="use"
            )
            chunks.append(chunk)

        # Extract modules, functions, structs, enums, impls, traits
        for pattern, chunk_type in [
            (self.mod_pattern, "module"),
            (self.fn_pattern, "function"),
            (self.struct_pattern, "struct"),
            (self.enum_pattern, "enum"),
            (self.impl_pattern, "impl"),
            (self.trait_pattern, "trait"),
        ]:
            for match in pattern.finditer(content):
                block_chunk = self._extract_block(match, content, file_path, chunk_type)
                if block_chunk:
                    chunks.append(block_chunk)

        if not chunks:
            return self._fallback_chunk(content, file_path)

        return chunks

    def _extract_block(self, match: re.Match, content: str, file_path: str,
                      chunk_type: str) -> Optional[Dict[str, Any]]:
        """Extract a code block starting from a regex match."""
        start_pos = match.start()

        # Look for doc comments before the block
        doc_comment = None
        preceding_content = content[:start_pos]
        lines_before = preceding_content.split('\n')
        if lines_before:
            doc_lines = []
            for line in reversed(lines_before[-15:]):
                stripped = line.strip()
                if stripped.startswith('///'):
                    doc_lines.insert(0, stripped[3:].strip())
                elif stripped.startswith('#[') or stripped == '':
                    continue  # Skip attributes and empty lines
                elif stripped:
                    break
            if doc_lines:
                doc_comment = ' '.join(doc_lines)

        start_line = content[:start_pos].count('\n') + 1

        # Check if this is a tuple struct (ends with semicolon)
        match_text = match.group(0)
        if match_text.rstrip().endswith(';'):
            end_pos = match.end()
            end_line = content[:end_pos].count('\n') + 1
            block_text = content[start_pos:end_pos]
        else:
            # Find matching closing brace
            brace_count = 0
            pos = match.end() - 1

            while pos < len(content):
                if content[pos] == '{':
                    brace_count += 1
                elif content[pos] == '}':
                    brace_count -= 1
                    if brace_count == 0:
                        break
                pos += 1

            if brace_count != 0:
                return None

            end_pos = pos + 1
            end_line = content[:end_pos].count('\n') + 1
            block_text = content[start_pos:end_pos]

        # Get the name from the match
        name = "anonymous"
        if match.groups():
            for group in match.groups():
                if group:
                    name = group
                    break

        metadata = {
            "name": name,
            "block_type": chunk_type,
            "doc_comment": doc_comment
        }

        return self.create_chunk(
            text=block_text,
            file_path=file_path,
            start_line=start_line,
            end_line=end_line,
            chunk_type=chunk_type,
            metadata=metadata
        )

    def _fallback_chunk(self, content: str, file_path: str) -> List[Dict[str, Any]]:
        """Fallback to simple text chunking."""
        chunks = []
        lines = content.split('\n')

        for i in range(0, len(lines), self.max_chunk_size // 50):
            chunk_lines = lines[i:i + self.max_chunk_size // 50]
            if chunk_lines:
                chunk_text = '\n'.join(chunk_lines)
                chunk = self.create_chunk(
                    text=chunk_text,
                    file_path=file_path,
                    start_line=i + 1,
                    end_line=min(i + len(chunk_lines), len(lines)),
                    chunk_type="text_block"
                )
                chunks.append(chunk)

        return chunks


class RChunker(BaseChunker):
    """Regex-based chunker for R files."""

    def __init__(self, max_chunk_size: int = 1000, overlap: int = 100):
        super().__init__(max_chunk_size, overlap)

        # Regex patterns for R constructs
        self.function_pattern = re.compile(
            r'(\w+)\s*<-\s*function\s*\([^)]*\)\s*{',
            re.MULTILINE
        )
        self.function_equals_pattern = re.compile(
            r'(\w+)\s*=\s*function\s*\([^)]*\)\s*{',
            re.MULTILINE
        )
        self.s4_class_pattern = re.compile(
            r'setClass\s*\(\s*["\'](\w+)["\']',
            re.MULTILINE
        )
        self.s4_method_pattern = re.compile(
            r'setMethod\s*\(\s*["\'](\w+)["\']',
            re.MULTILINE
        )
        self.r6_class_pattern = re.compile(
            r'(\w+)\s*<-\s*R6Class\s*\(',
            re.MULTILINE
        )
        self.library_pattern = re.compile(
            r'^library\s*\(\s*[\w"\']+\s*\)',
            re.MULTILINE
        )
        self.source_pattern = re.compile(
            r'^source\s*\(\s*["\'][^"\']+["\']\s*\)',
            re.MULTILINE
        )
        # R documentation comment pattern (roxygen2)
        self.roxygen_pattern = re.compile(r"#'\s*(.*)")

    def get_language(self) -> str:
        return "r"

    def chunk(self, content: str, file_path: str) -> List[Dict[str, Any]]:
        """Chunk R code using regex patterns."""
        chunks = []

        # Extract library/source statements
        for pattern in [self.library_pattern, self.source_pattern]:
            for match in pattern.finditer(content):
                start_pos = match.start()
                end_pos = match.end()
                start_line = content[:start_pos].count('\n') + 1
                end_line = content[:end_pos].count('\n') + 1

                chunk = self.create_chunk(
                    text=match.group(0),
                    file_path=file_path,
                    start_line=start_line,
                    end_line=end_line,
                    chunk_type="library"
                )
                chunks.append(chunk)

        # Extract functions and classes
        for pattern, chunk_type in [
            (self.function_pattern, "function"),
            (self.function_equals_pattern, "function"),
            (self.s4_class_pattern, "s4_class"),
            (self.s4_method_pattern, "s4_method"),
            (self.r6_class_pattern, "r6_class"),
        ]:
            for match in pattern.finditer(content):
                block_chunk = self._extract_block(match, content, file_path, chunk_type)
                if block_chunk:
                    chunks.append(block_chunk)

        if not chunks:
            return self._fallback_chunk(content, file_path)

        return chunks

    def _extract_block(self, match: re.Match, content: str, file_path: str,
                      chunk_type: str) -> Optional[Dict[str, Any]]:
        """Extract a code block starting from a regex match."""
        start_pos = match.start()

        # Look for roxygen2 comments before the block
        doc_comment = None
        preceding_content = content[:start_pos]
        lines_before = preceding_content.split('\n')
        if lines_before:
            doc_lines = []
            for line in reversed(lines_before[-20:]):
                stripped = line.strip()
                if stripped.startswith("#'"):
                    doc_lines.insert(0, stripped[2:].strip())
                elif stripped.startswith('#'):
                    continue  # Regular comments
                elif stripped:
                    break
            if doc_lines:
                doc_comment = ' '.join(doc_lines)

        start_line = content[:start_pos].count('\n') + 1

        # Find matching closing brace/paren
        # R uses { for function bodies and ( for setClass/setMethod
        open_char = '{'
        close_char = '}'
        if 'setClass' in match.group(0) or 'setMethod' in match.group(0) or 'R6Class' in match.group(0):
            open_char = '('
            close_char = ')'

        brace_count = 0
        pos = match.end() - 1

        # Find opening bracket
        while pos < len(content) and content[pos] not in ('{', '('):
            pos += 1

        if pos >= len(content):
            return None

        open_char = content[pos]
        close_char = '}' if open_char == '{' else ')'

        while pos < len(content):
            if content[pos] == open_char:
                brace_count += 1
            elif content[pos] == close_char:
                brace_count -= 1
                if brace_count == 0:
                    break
            pos += 1

        if brace_count != 0:
            return None

        end_pos = pos + 1
        end_line = content[:end_pos].count('\n') + 1

        block_text = content[start_pos:end_pos]

        metadata = {
            "name": match.group(1) if match.groups() else "anonymous",
            "block_type": chunk_type,
            "doc_comment": doc_comment
        }

        return self.create_chunk(
            text=block_text,
            file_path=file_path,
            start_line=start_line,
            end_line=end_line,
            chunk_type=chunk_type,
            metadata=metadata
        )

    def _fallback_chunk(self, content: str, file_path: str) -> List[Dict[str, Any]]:
        """Fallback to simple text chunking."""
        chunks = []
        lines = content.split('\n')

        for i in range(0, len(lines), self.max_chunk_size // 50):
            chunk_lines = lines[i:i + self.max_chunk_size // 50]
            if chunk_lines:
                chunk_text = '\n'.join(chunk_lines)
                chunk = self.create_chunk(
                    text=chunk_text,
                    file_path=file_path,
                    start_line=i + 1,
                    end_line=min(i + len(chunk_lines), len(lines)),
                    chunk_type="text_block"
                )
                chunks.append(chunk)

        return chunks


class JavaChunker(BaseChunker):
    """Regex-based chunker for Java files."""

    def __init__(self, max_chunk_size: int = 1000, overlap: int = 100):
        super().__init__(max_chunk_size, overlap)

        # Regex patterns for Java constructs
        self.package_pattern = re.compile(
            r'^package\s+[\w.]+;',
            re.MULTILINE
        )
        self.import_pattern = re.compile(
            r'^import\s+(?:static\s+)?[\w.*]+;',
            re.MULTILINE
        )
        self.class_pattern = re.compile(
            r'(?:public\s+|private\s+|protected\s+)?(?:static\s+)?(?:final\s+)?(?:abstract\s+)?class\s+(\w+)(?:<[^>]+>)?(?:\s+extends\s+[\w<>,\s]+)?(?:\s+implements\s+[\w<>,\s]+)?\s*{',
            re.MULTILINE
        )
        self.interface_pattern = re.compile(
            r'(?:public\s+|private\s+|protected\s+)?interface\s+(\w+)(?:<[^>]+>)?(?:\s+extends\s+[\w<>,\s]+)?\s*{',
            re.MULTILINE
        )
        self.enum_pattern = re.compile(
            r'(?:public\s+|private\s+|protected\s+)?enum\s+(\w+)(?:\s+implements\s+[\w<>,\s]+)?\s*{',
            re.MULTILINE
        )
        self.method_pattern = re.compile(
            r'(?:public\s+|private\s+|protected\s+)?(?:static\s+)?(?:final\s+)?(?:synchronized\s+)?(?:native\s+)?(?:abstract\s+)?(?:<[^>]+>\s+)?[\w<>\[\],\s]+\s+(\w+)\s*\([^)]*\)(?:\s+throws\s+[\w,\s]+)?\s*{',
            re.MULTILINE
        )
        self.annotation_pattern = re.compile(
            r'^@\w+(?:\([^)]*\))?',
            re.MULTILINE
        )
        # Javadoc pattern
        self.javadoc_pattern = re.compile(r'/\*\*\s*(.*?)\*/', re.DOTALL)

    def get_language(self) -> str:
        return "java"

    def chunk(self, content: str, file_path: str) -> List[Dict[str, Any]]:
        """Chunk Java code using regex patterns."""
        chunks = []

        # Extract package statement
        for match in self.package_pattern.finditer(content):
            start_pos = match.start()
            end_pos = match.end()
            start_line = content[:start_pos].count('\n') + 1
            end_line = content[:end_pos].count('\n') + 1

            chunk = self.create_chunk(
                text=match.group(0),
                file_path=file_path,
                start_line=start_line,
                end_line=end_line,
                chunk_type="package"
            )
            chunks.append(chunk)

        # Extract imports
        for match in self.import_pattern.finditer(content):
            start_pos = match.start()
            end_pos = match.end()
            start_line = content[:start_pos].count('\n') + 1
            end_line = content[:end_pos].count('\n') + 1

            chunk = self.create_chunk(
                text=match.group(0),
                file_path=file_path,
                start_line=start_line,
                end_line=end_line,
                chunk_type="import"
            )
            chunks.append(chunk)

        # Extract classes, interfaces, enums, methods
        for pattern, chunk_type in [
            (self.class_pattern, "class"),
            (self.interface_pattern, "interface"),
            (self.enum_pattern, "enum"),
            (self.method_pattern, "method"),
        ]:
            for match in pattern.finditer(content):
                block_chunk = self._extract_block(match, content, file_path, chunk_type)
                if block_chunk:
                    chunks.append(block_chunk)

        if not chunks:
            return self._fallback_chunk(content, file_path)

        return chunks

    def _extract_block(self, match: re.Match, content: str, file_path: str,
                      chunk_type: str) -> Optional[Dict[str, Any]]:
        """Extract a code block starting from a regex match."""
        start_pos = match.start()

        # Look for Javadoc comments before the block
        doc_comment = None
        preceding_content = content[:start_pos]
        javadoc_match = re.search(r'/\*\*\s*(.*?)\*/\s*$', preceding_content, re.DOTALL)
        if javadoc_match:
            doc_comment = javadoc_match.group(1).strip()
            # Clean up Javadoc formatting
            doc_comment = re.sub(r'\n\s*\*\s*', ' ', doc_comment)

        start_line = content[:start_pos].count('\n') + 1

        # Find matching closing brace
        brace_count = 0
        pos = match.end() - 1

        while pos < len(content):
            if content[pos] == '{':
                brace_count += 1
            elif content[pos] == '}':
                brace_count -= 1
                if brace_count == 0:
                    break
            pos += 1

        if brace_count != 0:
            return None

        end_pos = pos + 1
        end_line = content[:end_pos].count('\n') + 1

        block_text = content[start_pos:end_pos]

        metadata = {
            "name": match.group(1) if match.groups() else "anonymous",
            "block_type": chunk_type,
            "doc_comment": doc_comment
        }

        return self.create_chunk(
            text=block_text,
            file_path=file_path,
            start_line=start_line,
            end_line=end_line,
            chunk_type=chunk_type,
            metadata=metadata
        )

    def _fallback_chunk(self, content: str, file_path: str) -> List[Dict[str, Any]]:
        """Fallback to simple text chunking."""
        chunks = []
        lines = content.split('\n')

        for i in range(0, len(lines), self.max_chunk_size // 50):
            chunk_lines = lines[i:i + self.max_chunk_size // 50]
            if chunk_lines:
                chunk_text = '\n'.join(chunk_lines)
                chunk = self.create_chunk(
                    text=chunk_text,
                    file_path=file_path,
                    start_line=i + 1,
                    end_line=min(i + len(chunk_lines), len(lines)),
                    chunk_type="text_block"
                )
                chunks.append(chunk)

        return chunks


class GoChunker(BaseChunker):
    """Regex-based chunker for Go files."""

    def __init__(self, max_chunk_size: int = 1000, overlap: int = 100):
        super().__init__(max_chunk_size, overlap)

        # Regex patterns for Go constructs
        self.package_pattern = re.compile(
            r'^package\s+(\w+)',
            re.MULTILINE
        )
        self.import_pattern = re.compile(
            r'^import\s+(?:\(\s*([^)]+)\s*\)|"[^"]+")',
            re.MULTILINE | re.DOTALL
        )
        self.func_pattern = re.compile(
            r'func\s+(?:\([^)]+\)\s+)?(\w+)(?:\[[^\]]+\])?\s*\([^)]*\)(?:\s*(?:\([^)]*\)|[\w\[\]*]+))?\s*{',
            re.MULTILINE
        )
        self.type_struct_pattern = re.compile(
            r'type\s+(\w+)\s+struct\s*{',
            re.MULTILINE
        )
        self.type_interface_pattern = re.compile(
            r'type\s+(\w+)\s+interface\s*{',
            re.MULTILINE
        )
        self.type_alias_pattern = re.compile(
            r'type\s+(\w+)\s+(?:=\s+)?[\w\[\]*]+',
            re.MULTILINE
        )
        self.const_pattern = re.compile(
            r'const\s+(?:\(\s*([^)]+)\s*\)|(\w+)\s*=)',
            re.MULTILINE | re.DOTALL
        )
        self.var_pattern = re.compile(
            r'var\s+(?:\(\s*([^)]+)\s*\)|(\w+)\s+)',
            re.MULTILINE | re.DOTALL
        )
        # Go doc comment pattern
        self.doc_comment_pattern = re.compile(r'//\s*(.*)')

    def get_language(self) -> str:
        return "go"

    def chunk(self, content: str, file_path: str) -> List[Dict[str, Any]]:
        """Chunk Go code using regex patterns."""
        chunks = []

        # Extract package statement
        for match in self.package_pattern.finditer(content):
            start_pos = match.start()
            end_pos = match.end()
            start_line = content[:start_pos].count('\n') + 1
            end_line = content[:end_pos].count('\n') + 1

            chunk = self.create_chunk(
                text=match.group(0),
                file_path=file_path,
                start_line=start_line,
                end_line=end_line,
                chunk_type="package",
                metadata={"name": match.group(1)}
            )
            chunks.append(chunk)

        # Extract imports
        for match in self.import_pattern.finditer(content):
            start_pos = match.start()
            end_pos = match.end()
            start_line = content[:start_pos].count('\n') + 1
            end_line = content[:end_pos].count('\n') + 1

            chunk = self.create_chunk(
                text=match.group(0),
                file_path=file_path,
                start_line=start_line,
                end_line=end_line,
                chunk_type="import"
            )
            chunks.append(chunk)

        # Extract functions, types
        for pattern, chunk_type in [
            (self.func_pattern, "function"),
            (self.type_struct_pattern, "struct"),
            (self.type_interface_pattern, "interface"),
        ]:
            for match in pattern.finditer(content):
                block_chunk = self._extract_block(match, content, file_path, chunk_type)
                if block_chunk:
                    chunks.append(block_chunk)

        if not chunks:
            return self._fallback_chunk(content, file_path)

        return chunks

    def _extract_block(self, match: re.Match, content: str, file_path: str,
                      chunk_type: str) -> Optional[Dict[str, Any]]:
        """Extract a code block starting from a regex match."""
        start_pos = match.start()

        # Look for Go doc comments before the block
        doc_comment = None
        preceding_content = content[:start_pos]
        lines_before = preceding_content.split('\n')
        if lines_before:
            doc_lines = []
            for line in reversed(lines_before[-10:]):
                stripped = line.strip()
                if stripped.startswith('//'):
                    doc_lines.insert(0, stripped[2:].strip())
                elif stripped:
                    break
            if doc_lines:
                doc_comment = ' '.join(doc_lines)

        start_line = content[:start_pos].count('\n') + 1

        # Find matching closing brace
        brace_count = 0
        pos = match.end() - 1

        while pos < len(content):
            if content[pos] == '{':
                brace_count += 1
            elif content[pos] == '}':
                brace_count -= 1
                if brace_count == 0:
                    break
            pos += 1

        if brace_count != 0:
            return None

        end_pos = pos + 1
        end_line = content[:end_pos].count('\n') + 1

        block_text = content[start_pos:end_pos]

        metadata = {
            "name": match.group(1) if match.groups() else "anonymous",
            "block_type": chunk_type,
            "doc_comment": doc_comment
        }

        return self.create_chunk(
            text=block_text,
            file_path=file_path,
            start_line=start_line,
            end_line=end_line,
            chunk_type=chunk_type,
            metadata=metadata
        )

    def _fallback_chunk(self, content: str, file_path: str) -> List[Dict[str, Any]]:
        """Fallback to simple text chunking."""
        chunks = []
        lines = content.split('\n')

        for i in range(0, len(lines), self.max_chunk_size // 50):
            chunk_lines = lines[i:i + self.max_chunk_size // 50]
            if chunk_lines:
                chunk_text = '\n'.join(chunk_lines)
                chunk = self.create_chunk(
                    text=chunk_text,
                    file_path=file_path,
                    start_line=i + 1,
                    end_line=min(i + len(chunk_lines), len(lines)),
                    chunk_type="text_block"
                )
                chunks.append(chunk)

        return chunks


class SwiftChunker(BaseChunker):
    """Regex-based chunker for Swift files."""

    def __init__(self, max_chunk_size: int = 1000, overlap: int = 100):
        super().__init__(max_chunk_size, overlap)

        # Regex patterns for Swift constructs
        self.import_pattern = re.compile(
            r'^import\s+[\w.]+',
            re.MULTILINE
        )
        self.class_pattern = re.compile(
            r'(?:public\s+|private\s+|internal\s+|fileprivate\s+|open\s+)?(?:final\s+)?class\s+(\w+)(?:<[^>]+>)?(?:\s*:\s*[\w<>,\s]+)?\s*{',
            re.MULTILINE
        )
        self.struct_pattern = re.compile(
            r'(?:public\s+|private\s+|internal\s+|fileprivate\s+)?struct\s+(\w+)(?:<[^>]+>)?(?:\s*:\s*[\w<>,\s]+)?\s*{',
            re.MULTILINE
        )
        self.enum_pattern = re.compile(
            r'(?:public\s+|private\s+|internal\s+|fileprivate\s+)?enum\s+(\w+)(?:<[^>]+>)?(?:\s*:\s*[\w<>,\s]+)?\s*{',
            re.MULTILINE
        )
        self.protocol_pattern = re.compile(
            r'(?:public\s+|private\s+|internal\s+|fileprivate\s+)?protocol\s+(\w+)(?:\s*:\s*[\w<>,\s]+)?\s*{',
            re.MULTILINE
        )
        self.extension_pattern = re.compile(
            r'extension\s+(\w+)(?:<[^>]+>)?(?:\s*:\s*[\w<>,\s]+)?(?:\s+where\s+[^{]+)?\s*{',
            re.MULTILINE
        )
        self.func_pattern = re.compile(
            r'(?:public\s+|private\s+|internal\s+|fileprivate\s+|open\s+)?(?:static\s+)?(?:class\s+)?(?:override\s+)?(?:mutating\s+)?(?:@\w+\s+)*func\s+(\w+)(?:<[^>]+>)?\s*\([^)]*\)(?:\s*(?:throws|rethrows))?\s*(?:->\s*[^{]+)?\s*{',
            re.MULTILINE
        )
        self.property_pattern = re.compile(
            r'(?:public\s+|private\s+|internal\s+|fileprivate\s+)?(?:static\s+)?(?:lazy\s+)?(?:var|let)\s+(\w+)\s*:',
            re.MULTILINE
        )
        # Swift doc comment pattern
        self.doc_comment_pattern = re.compile(r'///\s*(.*)')

    def get_language(self) -> str:
        return "swift"

    def chunk(self, content: str, file_path: str) -> List[Dict[str, Any]]:
        """Chunk Swift code using regex patterns."""
        chunks = []

        # Extract imports
        for match in self.import_pattern.finditer(content):
            start_pos = match.start()
            end_pos = match.end()
            start_line = content[:start_pos].count('\n') + 1
            end_line = content[:end_pos].count('\n') + 1

            chunk = self.create_chunk(
                text=match.group(0),
                file_path=file_path,
                start_line=start_line,
                end_line=end_line,
                chunk_type="import"
            )
            chunks.append(chunk)

        # Extract classes, structs, enums, protocols, extensions, functions
        for pattern, chunk_type in [
            (self.class_pattern, "class"),
            (self.struct_pattern, "struct"),
            (self.enum_pattern, "enum"),
            (self.protocol_pattern, "protocol"),
            (self.extension_pattern, "extension"),
            (self.func_pattern, "function"),
        ]:
            for match in pattern.finditer(content):
                block_chunk = self._extract_block(match, content, file_path, chunk_type)
                if block_chunk:
                    chunks.append(block_chunk)

        if not chunks:
            return self._fallback_chunk(content, file_path)

        return chunks

    def _extract_block(self, match: re.Match, content: str, file_path: str,
                      chunk_type: str) -> Optional[Dict[str, Any]]:
        """Extract a code block starting from a regex match."""
        start_pos = match.start()

        # Look for Swift doc comments before the block
        doc_comment = None
        preceding_content = content[:start_pos]
        lines_before = preceding_content.split('\n')
        if lines_before:
            doc_lines = []
            for line in reversed(lines_before[-15:]):
                stripped = line.strip()
                if stripped.startswith('///'):
                    doc_lines.insert(0, stripped[3:].strip())
                elif stripped.startswith('@'):
                    continue  # Skip attributes
                elif stripped:
                    break
            if doc_lines:
                doc_comment = ' '.join(doc_lines)

        start_line = content[:start_pos].count('\n') + 1

        # Find matching closing brace
        brace_count = 0
        pos = match.end() - 1

        while pos < len(content):
            if content[pos] == '{':
                brace_count += 1
            elif content[pos] == '}':
                brace_count -= 1
                if brace_count == 0:
                    break
            pos += 1

        if brace_count != 0:
            return None

        end_pos = pos + 1
        end_line = content[:end_pos].count('\n') + 1

        block_text = content[start_pos:end_pos]

        metadata = {
            "name": match.group(1) if match.groups() else "anonymous",
            "block_type": chunk_type,
            "doc_comment": doc_comment
        }

        return self.create_chunk(
            text=block_text,
            file_path=file_path,
            start_line=start_line,
            end_line=end_line,
            chunk_type=chunk_type,
            metadata=metadata
        )

    def _fallback_chunk(self, content: str, file_path: str) -> List[Dict[str, Any]]:
        """Fallback to simple text chunking."""
        chunks = []
        lines = content.split('\n')

        for i in range(0, len(lines), self.max_chunk_size // 50):
            chunk_lines = lines[i:i + self.max_chunk_size // 50]
            if chunk_lines:
                chunk_text = '\n'.join(chunk_lines)
                chunk = self.create_chunk(
                    text=chunk_text,
                    file_path=file_path,
                    start_line=i + 1,
                    end_line=min(i + len(chunk_lines), len(lines)),
                    chunk_type="text_block"
                )
                chunks.append(chunk)

        return chunks


class KotlinChunker(BaseChunker):
    """Regex-based chunker for Kotlin files."""

    def __init__(self, max_chunk_size: int = 1000, overlap: int = 100):
        super().__init__(max_chunk_size, overlap)

        # Regex patterns for Kotlin constructs
        self.package_pattern = re.compile(
            r'^package\s+[\w.]+',
            re.MULTILINE
        )
        self.import_pattern = re.compile(
            r'^import\s+[\w.*]+(?:\s+as\s+\w+)?',
            re.MULTILINE
        )
        self.class_pattern = re.compile(
            r'(?:public\s+|private\s+|protected\s+|internal\s+)?(?:open\s+|abstract\s+|sealed\s+|data\s+|inner\s+|enum\s+)?class\s+(\w+)(?:<[^>]+>)?(?:\s*(?:\([^)]*\))?)?(?:\s*:\s*[\w<>(),\s]+)?\s*{',
            re.MULTILINE
        )
        self.interface_pattern = re.compile(
            r'(?:public\s+|private\s+|protected\s+|internal\s+)?interface\s+(\w+)(?:<[^>]+>)?(?:\s*:\s*[\w<>,\s]+)?\s*{',
            re.MULTILINE
        )
        self.object_pattern = re.compile(
            r'(?:companion\s+)?object\s+(\w+)?(?:\s*:\s*[\w<>(),\s]+)?\s*{',
            re.MULTILINE
        )
        self.fun_pattern = re.compile(
            r'(?:public\s+|private\s+|protected\s+|internal\s+)?(?:open\s+|override\s+|abstract\s+|inline\s+|suspend\s+)*fun\s+(?:<[^>]+>\s+)?(\w+)\s*\([^)]*\)(?:\s*:\s*[\w<>?]+)?\s*{',
            re.MULTILINE
        )
        self.val_var_pattern = re.compile(
            r'(?:public\s+|private\s+|protected\s+|internal\s+)?(?:override\s+)?(?:val|var)\s+(\w+)\s*:',
            re.MULTILINE
        )
        # KDoc pattern
        self.kdoc_pattern = re.compile(r'/\*\*\s*(.*?)\*/', re.DOTALL)

    def get_language(self) -> str:
        return "kotlin"

    def chunk(self, content: str, file_path: str) -> List[Dict[str, Any]]:
        """Chunk Kotlin code using regex patterns."""
        chunks = []

        # Extract package statement
        for match in self.package_pattern.finditer(content):
            start_pos = match.start()
            end_pos = match.end()
            start_line = content[:start_pos].count('\n') + 1
            end_line = content[:end_pos].count('\n') + 1

            chunk = self.create_chunk(
                text=match.group(0),
                file_path=file_path,
                start_line=start_line,
                end_line=end_line,
                chunk_type="package"
            )
            chunks.append(chunk)

        # Extract imports
        for match in self.import_pattern.finditer(content):
            start_pos = match.start()
            end_pos = match.end()
            start_line = content[:start_pos].count('\n') + 1
            end_line = content[:end_pos].count('\n') + 1

            chunk = self.create_chunk(
                text=match.group(0),
                file_path=file_path,
                start_line=start_line,
                end_line=end_line,
                chunk_type="import"
            )
            chunks.append(chunk)

        # Extract classes, interfaces, objects, functions
        for pattern, chunk_type in [
            (self.class_pattern, "class"),
            (self.interface_pattern, "interface"),
            (self.object_pattern, "object"),
            (self.fun_pattern, "function"),
        ]:
            for match in pattern.finditer(content):
                block_chunk = self._extract_block(match, content, file_path, chunk_type)
                if block_chunk:
                    chunks.append(block_chunk)

        if not chunks:
            return self._fallback_chunk(content, file_path)

        return chunks

    def _extract_block(self, match: re.Match, content: str, file_path: str,
                      chunk_type: str) -> Optional[Dict[str, Any]]:
        """Extract a code block starting from a regex match."""
        start_pos = match.start()

        # Look for KDoc comments before the block
        doc_comment = None
        preceding_content = content[:start_pos]
        kdoc_match = re.search(r'/\*\*\s*(.*?)\*/\s*$', preceding_content, re.DOTALL)
        if kdoc_match:
            doc_comment = kdoc_match.group(1).strip()
            doc_comment = re.sub(r'\n\s*\*\s*', ' ', doc_comment)

        start_line = content[:start_pos].count('\n') + 1

        # Find matching closing brace
        brace_count = 0
        pos = match.end() - 1

        while pos < len(content):
            if content[pos] == '{':
                brace_count += 1
            elif content[pos] == '}':
                brace_count -= 1
                if brace_count == 0:
                    break
            pos += 1

        if brace_count != 0:
            return None

        end_pos = pos + 1
        end_line = content[:end_pos].count('\n') + 1

        block_text = content[start_pos:end_pos]

        # Get name - for object, might be empty (companion object)
        name = "anonymous"
        if match.groups():
            for group in match.groups():
                if group:
                    name = group
                    break

        metadata = {
            "name": name,
            "block_type": chunk_type,
            "doc_comment": doc_comment
        }

        return self.create_chunk(
            text=block_text,
            file_path=file_path,
            start_line=start_line,
            end_line=end_line,
            chunk_type=chunk_type,
            metadata=metadata
        )

    def _fallback_chunk(self, content: str, file_path: str) -> List[Dict[str, Any]]:
        """Fallback to simple text chunking."""
        chunks = []
        lines = content.split('\n')

        for i in range(0, len(lines), self.max_chunk_size // 50):
            chunk_lines = lines[i:i + self.max_chunk_size // 50]
            if chunk_lines:
                chunk_text = '\n'.join(chunk_lines)
                chunk = self.create_chunk(
                    text=chunk_text,
                    file_path=file_path,
                    start_line=i + 1,
                    end_line=min(i + len(chunk_lines), len(lines)),
                    chunk_type="text_block"
                )
                chunks.append(chunk)

        return chunks


class MarkdownChunker(BaseChunker):
    """Chunker for Markdown files based on headings and paragraphs."""

    def get_language(self) -> str:
        return "markdown"
    
    def chunk(self, content: str, file_path: str) -> List[Dict[str, Any]]:
        """Chunk Markdown content by headings and paragraphs."""
        chunks = []
        lines = content.split('\n')
        
        current_section = []
        current_heading = None
        current_level = 0
        start_line = 1
        
        for i, line in enumerate(lines, 1):
            # Check if line is a heading
            heading_match = re.match(r'^(#{1,6})\s+(.+)$', line.strip())
            
            if heading_match:
                # Save previous section
                if current_section:
                    chunk = self._create_markdown_chunk(
                        current_section, file_path, start_line, i-1,
                        current_heading, current_level
                    )
                    chunks.append(chunk)
                
                # Start new section
                level = len(heading_match.group(1))
                heading_text = heading_match.group(2)
                
                current_section = [line]
                current_heading = heading_text
                current_level = level
                start_line = i
            else:
                current_section.append(line)
        
        # Add final section
        if current_section:
            chunk = self._create_markdown_chunk(
                current_section, file_path, start_line, len(lines),
                current_heading, current_level
            )
            chunks.append(chunk)
        
        return chunks
    
    def _create_markdown_chunk(self, lines: List[str], file_path: str,
                              start_line: int, end_line: int,
                              heading: Optional[str], level: int) -> Dict[str, Any]:
        """Create a markdown chunk with metadata."""
        text = '\n'.join(lines).strip()
        
        # Extract code blocks
        code_blocks = re.findall(r'```(\w+)?\n(.*?)\n```', text, re.DOTALL)
        
        metadata = {
            "heading": heading,
            "heading_level": level,
            "has_code": len(code_blocks) > 0,
            "code_languages": [lang for lang, _ in code_blocks if lang],
            "word_count": len(text.split())
        }
        
        chunk_type = "heading" if heading else "paragraph"
        
        return self.create_chunk(
            text=text,
            file_path=file_path,
            start_line=start_line,
            end_line=end_line,
            chunk_type=chunk_type,
            metadata=metadata
        )


class ChunkerFactory:
    """Factory for creating language-specific chunkers."""

    _chunkers = {
        # Python
        '.py': PythonChunker,
        # JavaScript/TypeScript
        '.js': JavaScriptChunker,
        '.jsx': JavaScriptChunker,
        '.ts': JavaScriptChunker,
        '.tsx': JavaScriptChunker,
        # Markdown
        '.md': MarkdownChunker,
        '.markdown': MarkdownChunker,
        # C#
        '.cs': CSharpChunker,
        # Rust
        '.rs': RustChunker,
        # R
        '.r': RChunker,
        '.R': RChunker,
        '.rmd': RChunker,
        '.Rmd': RChunker,
        # Java
        '.java': JavaChunker,
        # Go
        '.go': GoChunker,
        # Swift
        '.swift': SwiftChunker,
        # Kotlin
        '.kt': KotlinChunker,
        '.kts': KotlinChunker,
    }
    
    @classmethod
    def get_chunker(cls, file_path: str, **kwargs) -> BaseChunker:
        """Get appropriate chunker for file extension."""
        # Get file extension
        ext = None
        for extension in cls._chunkers.keys():
            if file_path.lower().endswith(extension):
                ext = extension
                break
        
        if ext and ext in cls._chunkers:
            return cls._chunkers[ext](**kwargs)
        else:
            # Default to JavaScript chunker for unknown types
            return JavaScriptChunker(**kwargs)
    
    @classmethod
    def supported_extensions(cls) -> List[str]:
        """Get list of supported file extensions."""
        return list(cls._chunkers.keys())
