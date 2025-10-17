"""
Language-aware chunking for different file types.
Supports Python (AST-based), JavaScript/TypeScript, and Markdown.
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
        '.py': PythonChunker,
        '.js': JavaScriptChunker,
        '.jsx': JavaScriptChunker,
        '.ts': JavaScriptChunker,
        '.tsx': JavaScriptChunker,
        '.md': MarkdownChunker,
        '.markdown': MarkdownChunker,
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
