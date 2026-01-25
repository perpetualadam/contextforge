# Tree-sitter Future-Proofing Strategy

## Executive Summary

**Current Decision:** Regex-based parsing is the right choice for ContextForge's **current** chunking needs.

**Future Consideration:** Tree-sitter will become **essential** when ContextForge adds:
1. **Real-time incremental parsing** for live file editing
2. **IDE-like features** (code navigation, refactoring, semantic highlighting)
3. **Precise code transformations** (automated refactoring, code generation)

This document outlines a migration strategy to add tree-sitter **alongside** regex when needed.

---

## Critical Gap in Original Analysis

### What I Missed: ContextForge HAS File Editing Tools! 🚨

ContextForge already has:
- ✅ **File editing** (`str-replace-editor`, `save-file`, `remove-files`)
- ✅ **File watching** (`FileWatcher` with real-time monitoring)
- ✅ **VS Code integration** (IDE diagnostics, live editing)
- ✅ **Incremental indexing** (hash-based change detection)

**Current Limitation:** File watching triggers **full re-parsing** of modified files, not incremental updates.

---

## When Tree-sitter Becomes Necessary

### Scenario 1: Real-Time Incremental Parsing (IDE Integration)

**Current Behavior:**
```python
# services/tools/file_watcher.py
def _watch_loop(self, watch_id: int):
    # Detects file modifications
    if mtime > old_state[file_path]:
        event_queue.put(FileEvent(FileEventType.MODIFIED, file_path))
        # Triggers FULL re-parse of entire file
```

**Problem:** When user edits a 10,000-line file in VS Code:
- Regex approach: Re-parse entire file (slow, inefficient)
- Tree-sitter approach: Parse only changed lines (fast, incremental)

**Tree-sitter Advantage:**
```python
# With tree-sitter incremental parsing
tree = parser.parse(old_source_code, old_tree)
# Only re-parses changed regions, reuses unchanged subtrees
# 10-100x faster for large files with small edits
```

### Scenario 2: Precise Code Transformations

**Current Capability:** String replacement
```python
# services/tools/file_editor.py - str_replace
content = content[:start_pos] + entry.new_str + content[end_pos:]
# Works for simple edits, but fragile for complex transformations
```

**Future Need:** Semantic code transformations
- Rename variable across scope (not just text search)
- Extract method with proper scope analysis
- Auto-import management
- Refactoring that preserves semantics

**Tree-sitter Advantage:**
- Understands scope boundaries
- Tracks symbol references
- Enables safe automated refactoring

### Scenario 3: Advanced IDE Features

**Potential Future Features:**
- **Go to definition** - Requires precise symbol resolution
- **Find all references** - Needs scope-aware search
- **Semantic highlighting** - Requires AST-level understanding
- **Code folding** - Needs structural boundaries
- **Auto-completion** - Requires context-aware parsing

---

## Migration Strategy: Hybrid Approach

### Phase 1: Keep Regex for Chunking (Current)
✅ **Status:** Implemented and working

**Use Cases:**
- Initial repository indexing
- Batch processing
- Embedding generation
- Simple symbol extraction

### Phase 2: Add Tree-sitter for Live Editing (Future)

**Architecture:**
```python
class HybridParser:
    """Combines regex (batch) and tree-sitter (incremental)."""
    
    def __init__(self, language: str):
        self.regex_chunker = ChunkerFactory.get_chunker(language)
        self.tree_sitter_parser = TreeSitterParser(language)  # NEW
        self.cached_trees: Dict[str, Tree] = {}
    
    def parse_full_file(self, content: str, file_path: str):
        """Use regex for full file parsing (fast, simple)."""
        return self.regex_chunker.chunk(content, file_path)
    
    def parse_incremental(self, content: str, file_path: str, 
                         old_content: str, edit_range: Range):
        """Use tree-sitter for incremental updates (efficient)."""
        old_tree = self.cached_trees.get(file_path)
        new_tree = self.tree_sitter_parser.parse(
            content.encode(), 
            old_tree=old_tree
        )
        self.cached_trees[file_path] = new_tree
        
        # Extract only changed chunks
        return self._extract_changed_chunks(new_tree, edit_range)
```

### Phase 3: Integration Points

**1. File Watcher Integration**
```python
# services/tools/file_watcher.py
class FileWatcher:
    def __init__(self, use_incremental_parsing: bool = False):
        self.use_incremental = use_incremental_parsing
        self.hybrid_parser = HybridParser() if use_incremental else None
    
    def _handle_modification(self, event: FileEvent):
        if self.use_incremental and event.edit_range:
            # Use tree-sitter for incremental update
            chunks = self.hybrid_parser.parse_incremental(...)
        else:
            # Use regex for full re-parse
            chunks = self.regex_chunker.chunk(...)
```

**2. Index Update Strategy**
```python
# services/index/__init__.py
class CodeIndex:
    def update_file_incremental(self, file_path: str, 
                                edit_range: Range, 
                                new_content: str):
        """Incrementally update index for file edit."""
        # Use tree-sitter to find affected chunks
        affected_chunks = self.hybrid_parser.parse_incremental(...)
        
        # Only re-embed affected chunks (not entire file)
        for chunk in affected_chunks:
            self.vector_index.update_chunk(chunk)
```

**3. VS Code Extension Integration**
```typescript
// vscode-extension/src/tools/fileTools.ts
export class FileTools {
    async onDocumentChange(event: vscode.TextDocumentChangeEvent) {
        // Send incremental edit to backend
        await axios.post(`${this._config.apiUrl}/index/incremental-update`, {
            file_path: event.document.fileName,
            changes: event.contentChanges.map(c => ({
                range: { start: c.range.start, end: c.range.end },
                text: c.text
            }))
        });
    }
}
```

---

## Implementation Roadmap

### When to Implement Tree-sitter

**Trigger Conditions:**
1. Users request real-time code navigation features
2. File editing becomes a primary use case (not just indexing)
3. Performance issues with large file re-parsing
4. Need for semantic code transformations

### Estimated Effort

**Phase 2A: Tree-sitter Foundation** (2-3 weeks)
- Install tree-sitter Python bindings
- Create TreeSitterParser wrapper class
- Implement for Python, JavaScript, TypeScript (most common)
- Add incremental parsing support

**Phase 2B: Hybrid Integration** (1-2 weeks)
- Create HybridParser class
- Update FileWatcher to use incremental parsing
- Add incremental index update API
- Update VS Code extension

**Phase 2C: Testing & Optimization** (1 week)
- Performance benchmarks (regex vs tree-sitter)
- Memory usage profiling
- Edge case testing
- Documentation

**Total:** 4-6 weeks when needed

---

## Technical Considerations

### Dependency Management
```toml
# pyproject.toml (when tree-sitter is added)
[tool.poetry.dependencies]
tree-sitter = "^0.20.0"
tree-sitter-python = "^0.20.0"
tree-sitter-javascript = "^0.20.0"
tree-sitter-typescript = "^0.20.0"
# Add more as needed
```

### Binary Compilation
- Tree-sitter requires compiling language grammars
- Pre-built wheels available for common platforms
- May need custom build step for exotic platforms

### Memory Overhead
- Each parsed tree consumes memory
- Need cache eviction strategy for large projects
- Estimate: ~1-5MB per cached tree

---

## Conclusion

**Current State:** Regex is the right choice ✅
- Simple, fast, zero dependencies
- Perfect for batch indexing and chunking

**Future State:** Tree-sitter will be essential when:
- Real-time incremental parsing is needed
- IDE-like features are added
- Semantic code transformations are required

**Strategy:** Hybrid approach
- Keep regex for batch operations
- Add tree-sitter for incremental updates
- Implement when user demand justifies the complexity

**Timeline:** Implement tree-sitter in Phase 7 or when triggered by user needs.

---

## References

- Tree-sitter documentation: https://tree-sitter.github.io/tree-sitter/
- Incremental parsing: https://tree-sitter.github.io/tree-sitter/using-parsers#incremental-parsing
- Python bindings: https://github.com/tree-sitter/py-tree-sitter

