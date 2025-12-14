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
    CSharpChunker,
    RustChunker,
    RChunker,
    JavaChunker,
    GoChunker,
    SwiftChunker,
    KotlinChunker,
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
        # PythonChunker uses 'function_name' not 'name'
        assert func_chunk["meta"]["function_name"] == "hello_world"
    
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
        # PythonChunker uses 'class_name' not 'name'
        assert class_chunk["meta"]["class_name"] == "Calculator"
    
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
        # Module docstring must be at the very start (no leading newline)
        code = '''"""
This is a module docstring.
It describes what the module does.
"""

def some_function():
    pass
'''

        chunks = self.chunker.chunk(code, "module.py")

        # PythonChunker uses 'module_docstring' not 'docstring'
        docstring_chunks = [c for c in chunks if c["meta"]["chunk_type"] == "module_docstring"]
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

const asyncFunction = async (data) => {
    const result = await processData(data);
    return result;
};
'''

        chunks = self.chunker.chunk(code, "arrows.js")

        # JavaScriptChunker uses 'arrow_function' type for arrow functions
        # Note: Only arrow functions with braces {} are detected
        function_chunks = [c for c in chunks if c["meta"]["chunk_type"] == "arrow_function"]
        assert len(function_chunks) == 2

        # Check that arrow functions are detected
        function_names = [c["meta"]["name"] for c in function_chunks]
        assert "add" in function_names
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


class TestCSharpChunker:
    """Test the CSharpChunker functionality."""

    def setup_method(self):
        """Set up test fixtures."""
        self.chunker = CSharpChunker()

    def test_csharp_chunker_initialization(self):
        """Test CSharpChunker initializes correctly."""
        assert isinstance(self.chunker, BaseChunker)
        assert self.chunker.get_language() == "csharp"

    def test_chunk_namespace_and_class(self):
        """Test chunking C# namespace and class."""
        code = '''
using System;
using System.Collections.Generic;

namespace MyApp.Models
{
    /// <summary>
    /// Represents a user in the system.
    /// </summary>
    public class User
    {
        public string Name { get; set; }
        public int Age { get; set; }

        public User(string name, int age)
        {
            Name = name;
            Age = age;
        }

        public string GetGreeting()
        {
            return $"Hello, {Name}!";
        }
    }
}
'''

        chunks = self.chunker.chunk(code, "User.cs")

        assert len(chunks) > 0

        # Should find using statements
        using_chunks = [c for c in chunks if c["meta"]["chunk_type"] == "using"]
        assert len(using_chunks) >= 2

        # Should find namespace
        namespace_chunks = [c for c in chunks if c["meta"]["chunk_type"] == "namespace"]
        assert len(namespace_chunks) >= 1

        # Should find class
        class_chunks = [c for c in chunks if c["meta"]["chunk_type"] == "class"]
        assert len(class_chunks) >= 1

        # Should find methods
        method_chunks = [c for c in chunks if c["meta"]["chunk_type"] == "method"]
        assert len(method_chunks) >= 1

    def test_chunk_interface(self):
        """Test chunking C# interface."""
        code = '''
namespace MyApp.Interfaces
{
    public interface IRepository<T>
    {
        T GetById(int id);
        void Save(T entity);
        void Delete(int id);
    }
}
'''

        chunks = self.chunker.chunk(code, "IRepository.cs")

        interface_chunks = [c for c in chunks if c["meta"]["chunk_type"] == "interface"]
        assert len(interface_chunks) >= 1


class TestRustChunker:
    """Test the RustChunker functionality."""

    def setup_method(self):
        """Set up test fixtures."""
        self.chunker = RustChunker()

    def test_rust_chunker_initialization(self):
        """Test RustChunker initializes correctly."""
        assert isinstance(self.chunker, BaseChunker)
        assert self.chunker.get_language() == "rust"

    def test_chunk_struct_and_impl(self):
        """Test chunking Rust struct and impl block."""
        code = '''
use std::fmt;

/// A point in 2D space.
#[derive(Debug, Clone)]
pub struct Point {
    pub x: f64,
    pub y: f64,
}

impl Point {
    /// Creates a new point.
    pub fn new(x: f64, y: f64) -> Self {
        Point { x, y }
    }

    /// Calculates distance from origin.
    pub fn distance_from_origin(&self) -> f64 {
        (self.x.powi(2) + self.y.powi(2)).sqrt()
    }
}

impl fmt::Display for Point {
    fn fmt(&self, f: &mut fmt::Formatter) -> fmt::Result {
        write!(f, "({}, {})", self.x, self.y)
    }
}
'''

        chunks = self.chunker.chunk(code, "point.rs")

        assert len(chunks) > 0

        # Should find use statements
        use_chunks = [c for c in chunks if c["meta"]["chunk_type"] == "use"]
        assert len(use_chunks) >= 1

        # Should find struct
        struct_chunks = [c for c in chunks if c["meta"]["chunk_type"] == "struct"]
        assert len(struct_chunks) >= 1

        # Should find impl blocks
        impl_chunks = [c for c in chunks if c["meta"]["chunk_type"] == "impl"]
        assert len(impl_chunks) >= 2

    def test_chunk_enum_and_trait(self):
        """Test chunking Rust enum and trait."""
        code = '''
pub enum Status {
    Active,
    Inactive,
    Pending,
}

pub trait Drawable {
    fn draw(&self);
    fn bounds(&self) -> (f64, f64, f64, f64);
}
'''

        chunks = self.chunker.chunk(code, "traits.rs")

        enum_chunks = [c for c in chunks if c["meta"]["chunk_type"] == "enum"]
        assert len(enum_chunks) >= 1

        trait_chunks = [c for c in chunks if c["meta"]["chunk_type"] == "trait"]
        assert len(trait_chunks) >= 1


class TestRChunker:
    """Test the RChunker functionality."""

    def setup_method(self):
        """Set up test fixtures."""
        self.chunker = RChunker()

    def test_r_chunker_initialization(self):
        """Test RChunker initializes correctly."""
        assert isinstance(self.chunker, BaseChunker)
        assert self.chunker.get_language() == "r"

    def test_chunk_functions(self):
        """Test chunking R functions."""
        code = '''
library(ggplot2)
library(dplyr)

#' Calculate the mean of a vector
#' @param x A numeric vector
#' @return The mean value
calculate_mean <- function(x) {
    sum(x) / length(x)
}

#' Filter data by threshold
filter_data = function(data, threshold) {
    data[data > threshold]
}

plot_histogram <- function(data, title = "Histogram") {
    ggplot(data, aes(x = value)) +
        geom_histogram() +
        ggtitle(title)
}
'''

        chunks = self.chunker.chunk(code, "analysis.R")

        assert len(chunks) > 0

        # Should find library statements
        library_chunks = [c for c in chunks if c["meta"]["chunk_type"] == "library"]
        assert len(library_chunks) >= 2

        # Should find functions
        function_chunks = [c for c in chunks if c["meta"]["chunk_type"] == "function"]
        assert len(function_chunks) >= 3


class TestJavaChunker:
    """Test the JavaChunker functionality."""

    def setup_method(self):
        """Set up test fixtures."""
        self.chunker = JavaChunker()

    def test_java_chunker_initialization(self):
        """Test JavaChunker initializes correctly."""
        assert isinstance(self.chunker, BaseChunker)
        assert self.chunker.get_language() == "java"

    def test_chunk_class_and_methods(self):
        """Test chunking Java class and methods."""
        code = '''
package com.example.models;

import java.util.List;
import java.util.ArrayList;

/**
 * Represents a user in the system.
 */
public class User {
    private String name;
    private int age;

    /**
     * Creates a new user.
     * @param name The user's name
     * @param age The user's age
     */
    public User(String name, int age) {
        this.name = name;
        this.age = age;
    }

    public String getName() {
        return name;
    }

    public void setName(String name) {
        this.name = name;
    }
}
'''

        chunks = self.chunker.chunk(code, "User.java")

        assert len(chunks) > 0

        # Should find package
        package_chunks = [c for c in chunks if c["meta"]["chunk_type"] == "package"]
        assert len(package_chunks) >= 1

        # Should find imports
        import_chunks = [c for c in chunks if c["meta"]["chunk_type"] == "import"]
        assert len(import_chunks) >= 2

        # Should find class
        class_chunks = [c for c in chunks if c["meta"]["chunk_type"] == "class"]
        assert len(class_chunks) >= 1

        # Should find methods
        method_chunks = [c for c in chunks if c["meta"]["chunk_type"] == "method"]
        assert len(method_chunks) >= 3

    def test_chunk_interface_and_enum(self):
        """Test chunking Java interface and enum."""
        code = '''
package com.example;

public interface Repository<T> {
    T findById(int id);
    void save(T entity);
}

public enum Status {
    ACTIVE,
    INACTIVE,
    PENDING
}
'''

        chunks = self.chunker.chunk(code, "Types.java")

        interface_chunks = [c for c in chunks if c["meta"]["chunk_type"] == "interface"]
        assert len(interface_chunks) >= 1

        enum_chunks = [c for c in chunks if c["meta"]["chunk_type"] == "enum"]
        assert len(enum_chunks) >= 1


class TestGoChunker:
    """Test the GoChunker functionality."""

    def setup_method(self):
        """Set up test fixtures."""
        self.chunker = GoChunker()

    def test_go_chunker_initialization(self):
        """Test GoChunker initializes correctly."""
        assert isinstance(self.chunker, BaseChunker)
        assert self.chunker.get_language() == "go"

    def test_chunk_package_and_functions(self):
        """Test chunking Go package and functions."""
        code = '''
package main

import (
    "fmt"
    "strings"
)

// User represents a user in the system.
type User struct {
    Name string
    Age  int
}

// NewUser creates a new user.
func NewUser(name string, age int) *User {
    return &User{
        Name: name,
        Age:  age,
    }
}

// Greet returns a greeting message.
func (u *User) Greet() string {
    return fmt.Sprintf("Hello, %s!", u.Name)
}

func main() {
    user := NewUser("Alice", 30)
    fmt.Println(user.Greet())
}
'''

        chunks = self.chunker.chunk(code, "main.go")

        assert len(chunks) > 0

        # Should find package
        package_chunks = [c for c in chunks if c["meta"]["chunk_type"] == "package"]
        assert len(package_chunks) >= 1

        # Should find imports
        import_chunks = [c for c in chunks if c["meta"]["chunk_type"] == "import"]
        assert len(import_chunks) >= 1

        # Should find struct
        struct_chunks = [c for c in chunks if c["meta"]["chunk_type"] == "struct"]
        assert len(struct_chunks) >= 1

        # Should find functions
        function_chunks = [c for c in chunks if c["meta"]["chunk_type"] == "function"]
        assert len(function_chunks) >= 3

    def test_chunk_interface(self):
        """Test chunking Go interface."""
        code = '''
package storage

type Repository interface {
    Get(id int) (interface{}, error)
    Save(entity interface{}) error
    Delete(id int) error
}
'''

        chunks = self.chunker.chunk(code, "repository.go")

        interface_chunks = [c for c in chunks if c["meta"]["chunk_type"] == "interface"]
        assert len(interface_chunks) >= 1


class TestSwiftChunker:
    """Test the SwiftChunker functionality."""

    def setup_method(self):
        """Set up test fixtures."""
        self.chunker = SwiftChunker()

    def test_swift_chunker_initialization(self):
        """Test SwiftChunker initializes correctly."""
        assert isinstance(self.chunker, BaseChunker)
        assert self.chunker.get_language() == "swift"

    def test_chunk_class_and_struct(self):
        """Test chunking Swift class and struct."""
        code = '''
import Foundation
import UIKit

/// Represents a user in the system.
class User {
    var name: String
    var age: Int

    init(name: String, age: Int) {
        self.name = name
        self.age = age
    }

    func greet() -> String {
        return "Hello, \\(name)!"
    }
}

struct Point {
    var x: Double
    var y: Double

    func distance(to other: Point) -> Double {
        let dx = x - other.x
        let dy = y - other.y
        return sqrt(dx * dx + dy * dy)
    }
}
'''

        chunks = self.chunker.chunk(code, "Models.swift")

        assert len(chunks) > 0

        # Should find imports
        import_chunks = [c for c in chunks if c["meta"]["chunk_type"] == "import"]
        assert len(import_chunks) >= 2

        # Should find class
        class_chunks = [c for c in chunks if c["meta"]["chunk_type"] == "class"]
        assert len(class_chunks) >= 1

        # Should find struct
        struct_chunks = [c for c in chunks if c["meta"]["chunk_type"] == "struct"]
        assert len(struct_chunks) >= 1

        # Should find functions
        function_chunks = [c for c in chunks if c["meta"]["chunk_type"] == "function"]
        assert len(function_chunks) >= 2

    def test_chunk_protocol_and_extension(self):
        """Test chunking Swift protocol and extension."""
        code = '''
protocol Drawable {
    func draw()
    var bounds: CGRect { get }
}

extension User: Drawable {
    func draw() {
        print("Drawing user")
    }

    var bounds: CGRect {
        return CGRect.zero
    }
}
'''

        chunks = self.chunker.chunk(code, "Protocols.swift")

        protocol_chunks = [c for c in chunks if c["meta"]["chunk_type"] == "protocol"]
        assert len(protocol_chunks) >= 1

        extension_chunks = [c for c in chunks if c["meta"]["chunk_type"] == "extension"]
        assert len(extension_chunks) >= 1


class TestKotlinChunker:
    """Test the KotlinChunker functionality."""

    def setup_method(self):
        """Set up test fixtures."""
        self.chunker = KotlinChunker()

    def test_kotlin_chunker_initialization(self):
        """Test KotlinChunker initializes correctly."""
        assert isinstance(self.chunker, BaseChunker)
        assert self.chunker.get_language() == "kotlin"

    def test_chunk_class_and_functions(self):
        """Test chunking Kotlin class and functions."""
        code = '''
package com.example.models

import java.util.Date

/**
 * Represents a user in the system.
 */
data class User(
    val name: String,
    val age: Int
) {
    fun greet(): String {
        return "Hello, $name!"
    }

    fun isAdult(): Boolean {
        return age >= 18
    }
}

fun createUser(name: String, age: Int): User {
    return User(name, age)
}
'''

        chunks = self.chunker.chunk(code, "User.kt")

        assert len(chunks) > 0

        # Should find package
        package_chunks = [c for c in chunks if c["meta"]["chunk_type"] == "package"]
        assert len(package_chunks) >= 1

        # Should find imports
        import_chunks = [c for c in chunks if c["meta"]["chunk_type"] == "import"]
        assert len(import_chunks) >= 1

        # Should find class
        class_chunks = [c for c in chunks if c["meta"]["chunk_type"] == "class"]
        assert len(class_chunks) >= 1

        # Should find functions
        function_chunks = [c for c in chunks if c["meta"]["chunk_type"] == "function"]
        assert len(function_chunks) >= 3

    def test_chunk_interface_and_object(self):
        """Test chunking Kotlin interface and object."""
        code = '''
package com.example

interface Repository<T> {
    fun findById(id: Int): T?
    fun save(entity: T)
}

object UserRepository : Repository<User> {
    override fun findById(id: Int): User? {
        return null
    }

    override fun save(entity: User) {
        // Save implementation
    }
}
'''

        chunks = self.chunker.chunk(code, "Repository.kt")

        interface_chunks = [c for c in chunks if c["meta"]["chunk_type"] == "interface"]
        assert len(interface_chunks) >= 1

        object_chunks = [c for c in chunks if c["meta"]["chunk_type"] == "object"]
        assert len(object_chunks) >= 1


class TestChunkerFactory:
    """Test the ChunkerFactory functionality."""

    def test_get_chunker_python(self):
        """Test getting Python chunker."""
        chunker = ChunkerFactory.get_chunker("test.py")
        assert isinstance(chunker, PythonChunker)

        # Note: .pyx is not supported, only .py

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

    def test_get_chunker_csharp(self):
        """Test getting C# chunker."""
        chunker = ChunkerFactory.get_chunker("User.cs")
        assert isinstance(chunker, CSharpChunker)

    def test_get_chunker_rust(self):
        """Test getting Rust chunker."""
        chunker = ChunkerFactory.get_chunker("main.rs")
        assert isinstance(chunker, RustChunker)

    def test_get_chunker_r(self):
        """Test getting R chunker."""
        r_files = ["analysis.r", "script.R", "report.rmd", "notebook.Rmd"]

        for filename in r_files:
            chunker = ChunkerFactory.get_chunker(filename)
            assert isinstance(chunker, RChunker)

    def test_get_chunker_java(self):
        """Test getting Java chunker."""
        chunker = ChunkerFactory.get_chunker("User.java")
        assert isinstance(chunker, JavaChunker)

    def test_get_chunker_go(self):
        """Test getting Go chunker."""
        chunker = ChunkerFactory.get_chunker("main.go")
        assert isinstance(chunker, GoChunker)

    def test_get_chunker_swift(self):
        """Test getting Swift chunker."""
        chunker = ChunkerFactory.get_chunker("ViewController.swift")
        assert isinstance(chunker, SwiftChunker)

    def test_get_chunker_kotlin(self):
        """Test getting Kotlin chunker."""
        kt_files = ["User.kt", "build.gradle.kts"]

        for filename in kt_files:
            chunker = ChunkerFactory.get_chunker(filename)
            assert isinstance(chunker, KotlinChunker)

    def test_get_chunker_unsupported(self):
        """Test getting chunker for unsupported file type."""
        # ChunkerFactory returns JavaScriptChunker as default for unsupported types
        chunker = ChunkerFactory.get_chunker("data.csv")
        assert isinstance(chunker, JavaScriptChunker)

        chunker = ChunkerFactory.get_chunker("image.png")
        assert isinstance(chunker, JavaScriptChunker)

    def test_get_supported_extensions(self):
        """Test getting list of supported extensions."""
        # Method is 'supported_extensions' not 'get_supported_extensions'
        extensions = ChunkerFactory.supported_extensions()

        assert isinstance(extensions, list)
        assert ".py" in extensions
        assert ".js" in extensions
        assert ".md" in extensions
        # Check new language extensions
        assert ".cs" in extensions
        assert ".rs" in extensions
        assert ".r" in extensions
        assert ".java" in extensions
        assert ".go" in extensions
        assert ".swift" in extensions
        assert ".kt" in extensions
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
