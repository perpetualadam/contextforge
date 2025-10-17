"""
Tests for language chunkers functionality.
"""

import pytest
import tempfile
import os
from unittest.mock import Mock, patch

# Import the modules to test
import sys
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'services', 'preprocessor'))

from lang_chunkers import (
    BaseChunker,
    PythonChunker,
    JavaScriptChunker,
    MarkdownChunker,
    ChunkerFactory
)


class TestPythonChunker:
    """Test the PythonChunker functionality."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.chunker = PythonChunker()
    
    def test_python_chunker_initialization(self):
        """Test PythonChunker initializes correctly."""
        assert isinstance(self.chunker, BaseChunker)
        assert hasattr(self.chunker, 'chunk')
    
    def test_chunk_simple_function(self):
        """Test chunking a simple Python function."""
        code = '''
def hello_world():
    """Print hello world message."""
    print("Hello, World!")
    return "success"
'''
        
        chunks = self.chunker.chunk(code, "test.py")
        
        assert len(chunks) > 0
        
        # Should find the function
        function_chunks = [c for c in chunks if c["meta"]["chunk_type"] == "function"]
        assert len(function_chunks) == 1
        
        func_chunk = function_chunks[0]
        assert "hello_world" in func_chunk["text"]
        assert "Print hello world message" in func_chunk["text"]
        assert func_chunk["meta"]["name"] == "hello_world"
    
    def test_chunk_class_with_methods(self):
        """Test chunking a Python class with methods."""
        code = '''
class Calculator:
    """A simple calculator class."""
    
    def __init__(self, name="Calculator"):
        """Initialize the calculator."""
        self.name = name
    
    def add(self, a, b):
        """Add two numbers."""
        return a + b
    
    def multiply(self, a, b):
        """Multiply two numbers."""
        return a * b
'''
        
        chunks = self.chunker.chunk(code, "calculator.py")
        
        # Should find class and methods
        class_chunks = [c for c in chunks if c["meta"]["chunk_type"] == "class"]
        method_chunks = [c for c in chunks if c["meta"]["chunk_type"] == "function"]
        
        assert len(class_chunks) == 1
        assert len(method_chunks) == 3  # __init__, add, multiply
        
        # Check class chunk
        class_chunk = class_chunks[0]
        assert "Calculator" in class_chunk["text"]
        assert "A simple calculator class" in class_chunk["text"]
        assert class_chunk["meta"]["name"] == "Calculator"
    
    def test_chunk_imports(self):
        """Test chunking Python imports."""
        code = '''
import os
import sys
from datetime import datetime, timedelta
from typing import List, Dict, Optional

def main():
    pass
'''
        
        chunks = self.chunker.chunk(code, "imports.py")
        
        import_chunks = [c for c in chunks if c["meta"]["chunk_type"] == "import"]
        assert len(import_chunks) > 0
        
        # Check that imports are captured
        import_text = " ".join([c["text"] for c in import_chunks])
        assert "import os" in import_text
        assert "from datetime import" in import_text
    
    def test_chunk_module_docstring(self):
        """Test chunking module-level docstring."""
        code = '''
"""
This is a module docstring.
It describes what the module does.
"""

def some_function():
    pass
'''
        
        chunks = self.chunker.chunk(code, "module.py")
        
        docstring_chunks = [c for c in chunks if c["meta"]["chunk_type"] == "docstring"]
        assert len(docstring_chunks) == 1
        
        docstring_chunk = docstring_chunks[0]
        assert "This is a module docstring" in docstring_chunk["text"]
    
    def test_chunk_async_function(self):
        """Test chunking async Python function."""
        code = '''
async def fetch_data(url):
    """Fetch data from URL asynchronously."""
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            return await response.json()
'''
        
        chunks = self.chunker.chunk(code, "async.py")
        
        function_chunks = [c for c in chunks if c["meta"]["chunk_type"] == "function"]
        assert len(function_chunks) == 1
        
        func_chunk = function_chunks[0]
        assert func_chunk["meta"]["is_async"] == True
        assert "fetch_data" in func_chunk["text"]
    
    def test_chunk_invalid_syntax(self):
        """Test chunking Python code with syntax errors."""
        code = '''
def broken_function(
    # Missing closing parenthesis and colon
    print("This is broken")
'''
        
        # Should fallback to text chunking without raising exception
        chunks = self.chunker.chunk(code, "broken.py")
        assert len(chunks) > 0
        
        # Should contain the text as fallback chunks
        text_content = " ".join([c["text"] for c in chunks])
        assert "broken_function" in text_content


class TestJavaScriptChunker:
    """Test the JavaScriptChunker functionality."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.chunker = JavaScriptChunker()
    
    def test_javascript_chunker_initialization(self):
        """Test JavaScriptChunker initializes correctly."""
        assert isinstance(self.chunker, BaseChunker)
        assert hasattr(self.chunker, 'chunk')
    
    def test_chunk_function_declaration(self):
        """Test chunking JavaScript function declaration."""
        code = '''
function calculateSum(a, b) {
    // Calculate the sum of two numbers
    return a + b;
}

function greetUser(name) {
    console.log(`Hello, ${name}!`);
}
'''
        
        chunks = self.chunker.chunk(code, "functions.js")
        
        function_chunks = [c for c in chunks if c["meta"]["chunk_type"] == "function"]
        assert len(function_chunks) == 2
        
        # Check function names
        function_names = [c["meta"]["name"] for c in function_chunks]
        assert "calculateSum" in function_names
        assert "greetUser" in function_names
    
    def test_chunk_arrow_functions(self):
        """Test chunking JavaScript arrow functions."""
        code = '''
const add = (a, b) => {
    return a + b;
};

const multiply = (x, y) => x * y;

const asyncFunction = async (data) => {
    const result = await processData(data);
    return result;
};
'''
        
        chunks = self.chunker.chunk(code, "arrows.js")
        
        function_chunks = [c for c in chunks if c["meta"]["chunk_type"] == "function"]
        assert len(function_chunks) == 3
        
        # Check that arrow functions are detected
        function_names = [c["meta"]["name"] for c in function_chunks]
        assert "add" in function_names
        assert "multiply" in function_names
        assert "asyncFunction" in function_names
    
    def test_chunk_class_declaration(self):
        """Test chunking JavaScript class."""
        code = '''
class User {
    constructor(name, email) {
        this.name = name;
        this.email = email;
    }
    
    getName() {
        return this.name;
    }
    
    setEmail(email) {
        this.email = email;
    }
}
'''
        
        chunks = self.chunker.chunk(code, "user.js")
        
        class_chunks = [c for c in chunks if c["meta"]["chunk_type"] == "class"]
        assert len(class_chunks) == 1
        
        class_chunk = class_chunks[0]
        assert class_chunk["meta"]["name"] == "User"
        assert "constructor" in class_chunk["text"]
    
    def test_chunk_imports_exports(self):
        """Test chunking JavaScript imports and exports."""
        code = '''
import React from 'react';
import { useState, useEffect } from 'react';
import axios from 'axios';

export default function Component() {
    return <div>Hello</div>;
}

export const helper = () => {
    return "helper function";
};
'''
        
        chunks = self.chunker.chunk(code, "component.js")
        
        import_chunks = [c for c in chunks if c["meta"]["chunk_type"] == "import"]
        assert len(import_chunks) > 0
        
        # Check imports are captured
        import_text = " ".join([c["text"] for c in import_chunks])
        assert "import React" in import_text
        assert "import axios" in import_text
    
    def test_chunk_nested_functions(self):
        """Test chunking nested JavaScript functions."""
        code = '''
function outerFunction() {
    function innerFunction() {
        return "inner";
    }
    
    const arrowInner = () => {
        return "arrow inner";
    };
    
    return innerFunction() + arrowInner();
}
'''
        
        chunks = self.chunker.chunk(code, "nested.js")
        
        # Should capture the outer function with its content
        function_chunks = [c for c in chunks if c["meta"]["chunk_type"] == "function"]
        assert len(function_chunks) >= 1
        
        # Outer function should contain inner functions
        outer_chunk = next(c for c in function_chunks if c["meta"]["name"] == "outerFunction")
        assert "innerFunction" in outer_chunk["text"]
        assert "arrowInner" in outer_chunk["text"]


class TestMarkdownChunker:
    """Test the MarkdownChunker functionality."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.chunker = MarkdownChunker()
    
    def test_markdown_chunker_initialization(self):
        """Test MarkdownChunker initializes correctly."""
        assert isinstance(self.chunker, BaseChunker)
        assert hasattr(self.chunker, 'chunk')
    
    def test_chunk_headings(self):
        """Test chunking Markdown with different heading levels."""
        markdown = '''
# Main Title

This is the introduction section.

## Section 1

Content for section 1.

### Subsection 1.1

More detailed content.

## Section 2

Content for section 2.

# Another Main Title

More content here.
'''
        
        chunks = self.chunker.chunk(markdown, "document.md")
        
        # Should have chunks for each section
        assert len(chunks) > 0
        
        # Check heading levels
        heading_chunks = [c for c in chunks if "heading" in c["meta"]]
        assert len(heading_chunks) > 0
        
        # Check that content is associated with headings
        main_title_chunks = [c for c in chunks if "Main Title" in c["text"]]
        assert len(main_title_chunks) > 0
    
    def test_chunk_code_blocks(self):
        """Test chunking Markdown with code blocks."""
        markdown = '''
# Code Examples

Here's a Python example:

```python
def hello():
    print("Hello, World!")
```

And here's JavaScript:

```javascript
function greet(name) {
    console.log(`Hello, ${name}!`);
}
```

Some regular text after code blocks.
'''
        
        chunks = self.chunker.chunk(markdown, "code_examples.md")
        
        # Should detect code blocks
        code_chunks = [c for c in chunks if c["meta"].get("has_code", False)]
        assert len(code_chunks) > 0
        
        # Check that languages are detected
        chunk_text = " ".join([c["text"] for c in chunks])
        assert "python" in chunk_text.lower()
        assert "javascript" in chunk_text.lower()
    
    def test_chunk_lists_and_tables(self):
        """Test chunking Markdown with lists and tables."""
        markdown = '''
# Features

## List of Features

- Feature 1
- Feature 2
- Feature 3

## Comparison Table

| Feature | Version 1 | Version 2 |
|---------|-----------|-----------|
| Speed   | Fast      | Faster    |
| Memory  | Low       | Lower     |

## Numbered List

1. First step
2. Second step
3. Third step
'''
        
        chunks = self.chunker.chunk(markdown, "features.md")
        
        assert len(chunks) > 0
        
        # Should capture list and table content
        content = " ".join([c["text"] for c in chunks])
        assert "Feature 1" in content
        assert "Version 1" in content
        assert "First step" in content
    
    def test_chunk_empty_sections(self):
        """Test chunking Markdown with empty sections."""
        markdown = '''
# Title 1

## Empty Section

## Section with Content

This section has content.

# Title 2

'''
        
        chunks = self.chunker.chunk(markdown, "empty_sections.md")
        
        # Should handle empty sections gracefully
        assert len(chunks) > 0
        
        # Should still capture sections with content
        content_chunks = [c for c in chunks if "This section has content" in c["text"]]
        assert len(content_chunks) > 0


class TestChunkerFactory:
    """Test the ChunkerFactory functionality."""
    
    def test_get_chunker_python(self):
        """Test getting Python chunker."""
        chunker = ChunkerFactory.get_chunker("test.py")
        assert isinstance(chunker, PythonChunker)
        
        chunker = ChunkerFactory.get_chunker("module.pyx")
        assert isinstance(chunker, PythonChunker)
    
    def test_get_chunker_javascript(self):
        """Test getting JavaScript chunker."""
        js_files = ["script.js", "component.jsx", "module.ts", "types.tsx"]
        
        for filename in js_files:
            chunker = ChunkerFactory.get_chunker(filename)
            assert isinstance(chunker, JavaScriptChunker)
    
    def test_get_chunker_markdown(self):
        """Test getting Markdown chunker."""
        md_files = ["README.md", "docs.markdown"]
        
        for filename in md_files:
            chunker = ChunkerFactory.get_chunker(filename)
            assert isinstance(chunker, MarkdownChunker)
    
    def test_get_chunker_unsupported(self):
        """Test getting chunker for unsupported file type."""
        chunker = ChunkerFactory.get_chunker("data.csv")
        assert chunker is None
        
        chunker = ChunkerFactory.get_chunker("image.png")
        assert chunker is None
    
    def test_get_supported_extensions(self):
        """Test getting list of supported extensions."""
        extensions = ChunkerFactory.get_supported_extensions()
        
        assert isinstance(extensions, list)
        assert ".py" in extensions
        assert ".js" in extensions
        assert ".md" in extensions
        assert len(extensions) > 0


class TestChunkerIntegration:
    """Integration tests for chunkers."""
    
    def test_chunker_consistency(self):
        """Test that all chunkers return consistent chunk format."""
        test_files = [
            ("test.py", "def test(): pass"),
            ("test.js", "function test() { return true; }"),
            ("test.md", "# Test\n\nContent here.")
        ]
        
        for filename, content in test_files:
            chunker = ChunkerFactory.get_chunker(filename)
            if chunker:
                chunks = chunker.chunk(content, filename)
                
                for chunk in chunks:
                    # Check required fields
                    assert "text" in chunk
                    assert "meta" in chunk
                    
                    # Check text is not empty
                    assert len(chunk["text"].strip()) > 0
                    
                    # Check meta has required fields
                    meta = chunk["meta"]
                    assert "file_path" in meta
                    assert "chunk_type" in meta
                    assert "start_line" in meta
                    assert "end_line" in meta
    
    def test_chunker_with_real_files(self):
        """Test chunkers with actual file content."""
        # Create temporary files with real content
        test_contents = {
            "example.py": '''
"""Example Python module."""

import os
import sys

class ExampleClass:
    """An example class."""
    
    def __init__(self, name):
        self.name = name
    
    def greet(self):
        """Greet the user."""
        return f"Hello, {self.name}!"

def main():
    """Main function."""
    example = ExampleClass("World")
    print(example.greet())

if __name__ == "__main__":
    main()
''',
            "example.js": '''
// Example JavaScript module

import { Component } from 'react';

class ExampleComponent extends Component {
    constructor(props) {
        super(props);
        this.state = { count: 0 };
    }
    
    increment = () => {
        this.setState({ count: this.state.count + 1 });
    };
    
    render() {
        return (
            <div>
                <p>Count: {this.state.count}</p>
                <button onClick={this.increment}>Increment</button>
            </div>
        );
    }
}

export default ExampleComponent;
''',
            "example.md": '''
# Example Documentation

This is an example markdown document.

## Installation

To install the package:

```bash
npm install example-package
```

## Usage

Here's how to use it:

```javascript
import { example } from 'example-package';

const result = example.process(data);
```

## Features

- Feature 1: Does something useful
- Feature 2: Does something else
- Feature 3: Does more things

## API Reference

### `process(data)`

Processes the input data and returns a result.

**Parameters:**
- `data` (Object): The input data to process

**Returns:**
- (Object): The processed result
'''
        }
        
        for filename, content in test_contents.items():
            chunker = ChunkerFactory.get_chunker(filename)
            assert chunker is not None
            
            chunks = chunker.chunk(content, filename)
            assert len(chunks) > 0
            
            # Verify chunks contain meaningful content
            total_text = " ".join([c["text"] for c in chunks])
            assert len(total_text) > len(content) * 0.5  # Should capture most content


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
