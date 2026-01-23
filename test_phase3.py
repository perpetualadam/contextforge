"""
Phase 3 Test Suite: Language Support Expansion
Tests for HTML, CSS, and Julia chunkers.
"""

import sys
import os

# Add services directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'services'))

from preprocessor.lang_chunkers import (
    HTMLChunker, CSSChunker, JuliaChunker, ChunkerFactory
)


def test_html_chunker():
    """Test HTML chunking."""
    print("\n=== Testing HTMLChunker ===")
    
    html_content = """
<!DOCTYPE html>
<html>
<head>
    <title>Test Page</title>
    <style>
        body { margin: 0; }
    </style>
</head>
<body>
    <header id="main-header" class="sticky">
        <nav>Navigation</nav>
    </header>
    <main>
        <section id="content">
            <h1>Welcome</h1>
            <p>Content here</p>
        </section>
    </main>
    <script>
        console.log('Hello');
    </script>
    <form action="/submit" method="post">
        <input type="text" name="username">
    </form>
</body>
</html>
    """
    
    chunker = HTMLChunker()
    chunks = chunker.chunk(html_content, "test.html")
    
    print(f"✓ Generated {len(chunks)} chunks")
    assert len(chunks) > 0, "Should generate at least one chunk"
    assert chunker.get_language() == "html", "Language should be 'html'"
    
    # Check for script chunks
    script_chunks = [c for c in chunks if c['meta']['chunk_type'] == 'script']
    print(f"✓ Found {len(script_chunks)} script chunks")
    assert len(script_chunks) > 0, "Should find script blocks"
    
    # Check for style chunks
    style_chunks = [c for c in chunks if c['meta']['chunk_type'] == 'style']
    print(f"✓ Found {len(style_chunks)} style chunks")
    assert len(style_chunks) > 0, "Should find style blocks"
    
    # Check for section chunks
    section_chunks = [c for c in chunks if c['meta']['chunk_type'] == 'section']
    print(f"✓ Found {len(section_chunks)} section chunks")
    
    # Check for form chunks
    form_chunks = [c for c in chunks if c['meta']['chunk_type'] == 'form']
    print(f"✓ Found {len(form_chunks)} form chunks")
    assert len(form_chunks) > 0, "Should find form blocks"
    
    print("✅ HTMLChunker tests passed!")
    return True


def test_css_chunker():
    """Test CSS chunking."""
    print("\n=== Testing CSSChunker ===")
    
    css_content = """
@import url('https://fonts.googleapis.com/css2?family=Roboto');

@font-face {
    font-family: 'CustomFont';
    src: url('font.woff2');
}

body {
    margin: 0;
    padding: 0;
    font-family: 'Roboto', sans-serif;
}

.container {
    max-width: 1200px;
    margin: 0 auto;
}

@media (max-width: 768px) {
    .container {
        max-width: 100%;
    }
}

@keyframes fadeIn {
    from { opacity: 0; }
    to { opacity: 1; }
}

#header {
    background: #333;
    color: white;
}
    """
    
    chunker = CSSChunker()
    chunks = chunker.chunk(css_content, "test.css")
    
    print(f"✓ Generated {len(chunks)} chunks")
    assert len(chunks) > 0, "Should generate at least one chunk"
    assert chunker.get_language() == "css", "Language should be 'css'"
    
    # Check for import chunks
    import_chunks = [c for c in chunks if c['meta']['chunk_type'] == 'import']
    print(f"✓ Found {len(import_chunks)} import chunks")
    assert len(import_chunks) > 0, "Should find @import statements"
    
    # Check for font-face chunks
    font_chunks = [c for c in chunks if c['meta']['chunk_type'] == 'font_face']
    print(f"✓ Found {len(font_chunks)} font-face chunks")
    assert len(font_chunks) > 0, "Should find @font-face rules"
    
    # Check for media query chunks
    media_chunks = [c for c in chunks if c['meta']['chunk_type'] == 'media_query']
    print(f"✓ Found {len(media_chunks)} media query chunks")
    assert len(media_chunks) > 0, "Should find @media queries"
    
    # Check for keyframes chunks
    keyframe_chunks = [c for c in chunks if c['meta']['chunk_type'] == 'keyframes']
    print(f"✓ Found {len(keyframe_chunks)} keyframes chunks")
    assert len(keyframe_chunks) > 0, "Should find @keyframes"
    
    # Check for regular rule chunks
    rule_chunks = [c for c in chunks if c['meta']['chunk_type'] == 'rule']
    print(f"✓ Found {len(rule_chunks)} CSS rule chunks")
    
    print("✅ CSSChunker tests passed!")
    return True


def test_julia_chunker():
    """Test Julia chunking."""
    print("\n=== Testing JuliaChunker ===")

    julia_content = """
using LinearAlgebra
import Statistics: mean, std

\"\"\"
    fibonacci(n::Int)

Calculate the nth Fibonacci number.
\"\"\"
function fibonacci(n::Int)::Int
    if n <= 1
        return n
    end
    return fibonacci(n-1) + fibonacci(n-2)
end

# Short-form function
square(x) = x * x

\"\"\"
A simple point structure.
\"\"\"
struct Point{T}
    x::T
    y::T
end

mutable struct Counter
    count::Int
end

module MyModule
    export greet

    function greet(name::String)
        println("Hello, $name!")
    end
end

macro debug(expr)
    quote
        println("Debug: ", \\$(string(expr)))
        \\$expr
    end
end

abstract type Animal end
primitive type Byte 8 end
    """

    chunker = JuliaChunker()
    chunks = chunker.chunk(julia_content, "test.jl")

    print(f"✓ Generated {len(chunks)} chunks")
    assert len(chunks) > 0, "Should generate at least one chunk"
    assert chunker.get_language() == "julia", "Language should be 'julia'"

    # Check for import chunks
    import_chunks = [c for c in chunks if c['meta']['chunk_type'] == 'import']
    print(f"✓ Found {len(import_chunks)} import chunks")
    assert len(import_chunks) > 0, "Should find using/import statements"

    # Check for function chunks
    function_chunks = [c for c in chunks if c['meta']['chunk_type'] == 'function']
    print(f"✓ Found {len(function_chunks)} function chunks")
    assert len(function_chunks) > 0, "Should find function definitions"

    # Check for struct chunks
    struct_chunks = [c for c in chunks if c['meta']['chunk_type'] == 'struct']
    print(f"✓ Found {len(struct_chunks)} struct chunks")
    assert len(struct_chunks) > 0, "Should find struct definitions"

    # Check for module chunks
    module_chunks = [c for c in chunks if c['meta']['chunk_type'] == 'module']
    print(f"✓ Found {len(module_chunks)} module chunks")
    assert len(module_chunks) > 0, "Should find module definitions"

    # Check for macro chunks
    macro_chunks = [c for c in chunks if c['meta']['chunk_type'] == 'macro']
    print(f"✓ Found {len(macro_chunks)} macro chunks")
    assert len(macro_chunks) > 0, "Should find macro definitions"

    # Check for type chunks
    type_chunks = [c for c in chunks if c['meta']['chunk_type'] == 'type']
    print(f"✓ Found {len(type_chunks)} type chunks")
    assert len(type_chunks) > 0, "Should find type definitions"

    print("✅ JuliaChunker tests passed!")
    return True


def test_chunker_factory():
    """Test ChunkerFactory integration."""
    print("\n=== Testing ChunkerFactory ===")

    # Test HTML
    html_chunker = ChunkerFactory.get_chunker("test.html")
    assert isinstance(html_chunker, HTMLChunker), "Should return HTMLChunker for .html"
    print("✓ ChunkerFactory returns HTMLChunker for .html")

    html_chunker2 = ChunkerFactory.get_chunker("test.htm")
    assert isinstance(html_chunker2, HTMLChunker), "Should return HTMLChunker for .htm"
    print("✓ ChunkerFactory returns HTMLChunker for .htm")

    # Test CSS
    css_chunker = ChunkerFactory.get_chunker("test.css")
    assert isinstance(css_chunker, CSSChunker), "Should return CSSChunker for .css"
    print("✓ ChunkerFactory returns CSSChunker for .css")

    scss_chunker = ChunkerFactory.get_chunker("test.scss")
    assert isinstance(scss_chunker, CSSChunker), "Should return CSSChunker for .scss"
    print("✓ ChunkerFactory returns CSSChunker for .scss")

    sass_chunker = ChunkerFactory.get_chunker("test.sass")
    assert isinstance(sass_chunker, CSSChunker), "Should return CSSChunker for .sass"
    print("✓ ChunkerFactory returns CSSChunker for .sass")

    less_chunker = ChunkerFactory.get_chunker("test.less")
    assert isinstance(less_chunker, CSSChunker), "Should return CSSChunker for .less"
    print("✓ ChunkerFactory returns CSSChunker for .less")

    # Test Julia
    julia_chunker = ChunkerFactory.get_chunker("test.jl")
    assert isinstance(julia_chunker, JuliaChunker), "Should return JuliaChunker for .jl"
    print("✓ ChunkerFactory returns JuliaChunker for .jl")

    # Check supported extensions
    supported = ChunkerFactory.supported_extensions()
    assert '.html' in supported, ".html should be in supported extensions"
    assert '.htm' in supported, ".htm should be in supported extensions"
    assert '.css' in supported, ".css should be in supported extensions"
    assert '.scss' in supported, ".scss should be in supported extensions"
    assert '.sass' in supported, ".sass should be in supported extensions"
    assert '.less' in supported, ".less should be in supported extensions"
    assert '.jl' in supported, ".jl should be in supported extensions"
    print(f"✓ All new extensions in supported list ({len(supported)} total)")

    print("✅ ChunkerFactory tests passed!")
    return True


def test_existing_languages():
    """Verify existing language support still works."""
    print("\n=== Testing Existing Language Support ===")

    # Test that requested languages are supported
    from preprocessor.lang_chunkers import (
        JavaScriptChunker, KotlinChunker, GoChunker, JavaChunker, RustChunker
    )

    # JavaScript
    js_chunker = ChunkerFactory.get_chunker("test.js")
    assert isinstance(js_chunker, JavaScriptChunker), "JavaScript support exists"
    print("✓ JavaScript (.js) supported")

    # TypeScript
    ts_chunker = ChunkerFactory.get_chunker("test.ts")
    assert isinstance(ts_chunker, JavaScriptChunker), "TypeScript support exists"
    print("✓ TypeScript (.ts) supported")

    # Kotlin
    kt_chunker = ChunkerFactory.get_chunker("test.kt")
    assert isinstance(kt_chunker, KotlinChunker), "Kotlin support exists"
    print("✓ Kotlin (.kt) supported")

    # Go
    go_chunker = ChunkerFactory.get_chunker("test.go")
    assert isinstance(go_chunker, GoChunker), "Go support exists"
    print("✓ Go (.go) supported")

    # Java
    java_chunker = ChunkerFactory.get_chunker("test.java")
    assert isinstance(java_chunker, JavaChunker), "Java support exists"
    print("✓ Java (.java) supported")

    # Rust
    rust_chunker = ChunkerFactory.get_chunker("test.rs")
    assert isinstance(rust_chunker, RustChunker), "Rust support exists"
    print("✓ Rust (.rs) supported")

    print("✅ All requested languages supported!")
    return True


def main():
    """Run all Phase 3 tests."""
    print("=" * 60)
    print("Phase 3 Test Suite: Language Support Expansion")
    print("Testing HTML, CSS, Julia chunkers + existing language support")
    print("=" * 60)

    tests = [
        ("HTML Chunker", test_html_chunker),
        ("CSS Chunker", test_css_chunker),
        ("Julia Chunker", test_julia_chunker),
        ("ChunkerFactory Integration", test_chunker_factory),
        ("Existing Language Support", test_existing_languages),
    ]

    passed = 0
    failed = 0

    for test_name, test_func in tests:
        try:
            if test_func():
                passed += 1
        except Exception as e:
            print(f"❌ {test_name} FAILED: {e}")
            import traceback
            traceback.print_exc()
            failed += 1

    print("\n" + "=" * 60)
    print(f"Test Results: {passed} passed, {failed} failed")
    print("=" * 60)

    if failed == 0:
        print("\n🎉 All Phase 3 tests passed! Ready to commit.")
        return 0
    else:
        print(f"\n⚠️  {failed} test(s) failed. Please fix before committing.")
        return 1


if __name__ == "__main__":
    sys.exit(main())

