# Example Repository for ContextForge

This is a small example repository designed to demonstrate ContextForge's capabilities. It contains various file types and programming languages that showcase different aspects of the context engine.

## Repository Structure

```
examples/small-repo/
├── README.md                 # This file
├── python/
│   ├── auth.py              # Authentication module
│   ├── database.py          # Database connection utilities
│   └── api.py               # REST API endpoints
├── javascript/
│   ├── utils.js             # Utility functions
│   ├── components.jsx       # React components
│   └── api-client.ts        # TypeScript API client
├── docs/
│   ├── architecture.md      # System architecture documentation
│   └── api-reference.md     # API documentation
└── config/
    └── settings.json        # Configuration file
```

## Features Demonstrated

### 1. Multi-Language Support
- **Python**: Classes, functions, docstrings, imports
- **JavaScript/TypeScript**: Functions, arrow functions, classes, modules
- **Markdown**: Headings, code blocks, documentation structure

### 2. Code Patterns
- Authentication and authorization
- Database operations
- REST API design
- Frontend components
- Configuration management

### 3. Documentation
- Architecture documentation
- API reference
- Code comments and docstrings

## Usage with ContextForge

### Ingestion
```bash
# Ingest this example repository
python scripts/ingest_example.py --path examples/small-repo

# Or using make
make ingest-example
```

### Example Queries

Try these queries after ingesting the repository:

1. **Authentication**: "How does user authentication work?"
2. **Database**: "How do I connect to the database?"
3. **API**: "What API endpoints are available?"
4. **Frontend**: "What React components are defined?"
5. **Configuration**: "How is the application configured?"

### Expected Results

When you query ContextForge about this repository, you should see:

- **Code Contexts**: Relevant code snippets from the appropriate files
- **Source Citations**: File paths and line numbers for each result
- **Semantic Understanding**: Contextually relevant results even when exact keywords don't match

## Testing ContextForge Features

This repository is designed to test various ContextForge capabilities:

### Language Processing
- Python AST parsing (classes, functions, docstrings)
- JavaScript/TypeScript regex parsing (functions, classes)
- Markdown heading-based chunking

### Semantic Search
- Finding related concepts across different files
- Understanding code relationships and dependencies
- Matching queries to relevant documentation

### Context Retrieval
- Retrieving relevant code snippets
- Providing proper source attribution
- Ranking results by relevance

## Sample Queries and Expected Sources

| Query | Expected Sources |
|-------|------------------|
| "user authentication" | `python/auth.py`, `docs/architecture.md` |
| "database connection" | `python/database.py`, `config/settings.json` |
| "API endpoints" | `python/api.py`, `docs/api-reference.md` |
| "React components" | `javascript/components.jsx` |
| "configuration settings" | `config/settings.json`, `docs/architecture.md` |

## Acceptance Criteria

After ingesting this repository, ContextForge should be able to:

1. ✅ **Index all files** (Python, JavaScript, TypeScript, Markdown, JSON)
2. ✅ **Extract meaningful chunks** from each file type
3. ✅ **Answer questions** about the codebase with relevant context
4. ✅ **Provide source citations** with file paths and line numbers
5. ✅ **Rank results** by semantic relevance
6. ✅ **Handle cross-file relationships** (e.g., API client using API endpoints)

## Troubleshooting

If you encounter issues:

1. **No results**: Ensure the repository was ingested successfully
2. **Irrelevant results**: Try more specific queries
3. **Missing files**: Check file patterns and exclusion rules
4. **Encoding errors**: All files use UTF-8 encoding

## Contributing

This example repository can be extended with:

- Additional programming languages
- More complex code patterns
- Different documentation formats
- Configuration file types
- Test files and examples
