# ContextForge VS Code Extension

A powerful VS Code extension that integrates with the ContextForge local-first context engine to provide AI-powered code assistance directly in your editor.

## Features

- **Workspace Ingestion**: Automatically index your entire codebase for intelligent search and retrieval
- **AI-Powered Queries**: Ask questions about your code and get contextual answers with source citations
- **Code Navigation**: Click on search results to jump directly to relevant code sections
- **Web Search Integration**: Optionally include web search results for additional context
- **Privacy-First**: All processing happens locally by default, with configurable remote LLM support

## Installation

### From VSIX Package

1. Download the latest `.vsix` file from the releases
2. Open VS Code
3. Go to Extensions view (`Ctrl+Shift+X`)
4. Click the "..." menu and select "Install from VSIX..."
5. Select the downloaded `.vsix` file

### From Source

1. Clone the ContextForge repository
2. Navigate to the `vscode-extension` directory
3. Run `npm install`
4. Run `npm run compile`
5. Press `F5` to open a new Extension Development Host window

## Setup

### Prerequisites

1. **ContextForge API Gateway**: The extension requires the ContextForge API Gateway to be running locally
2. **Docker**: For the easiest setup, use Docker Compose to run all ContextForge services

### Quick Start

1. **Start ContextForge Services**:
   ```bash
   cd /path/to/contextforge
   make dev
   ```

2. **Configure the Extension**:
   - Open VS Code settings (`Ctrl+,`)
   - Search for "ContextForge"
   - Set the API URL (default: `http://localhost:8080`)

3. **Ingest Your Workspace**:
   - Open a project in VS Code
   - Use `Ctrl+Shift+I` or run "ContextForge: Ingest Workspace" from the command palette
   - Wait for ingestion to complete

4. **Start Asking Questions**:
   - Use `Ctrl+Shift+C` or run "ContextForge: Ask" from the command palette
   - Type your question about the codebase
   - View results in the ContextForge panel

## Commands

| Command | Keybinding | Description |
|---------|------------|-------------|
| `ContextForge: Ask` | `Ctrl+Shift+C` | Ask a question about your codebase |
| `ContextForge: Ingest Workspace` | `Ctrl+Shift+I` | Index the current workspace |
| `ContextForge: Open Index Panel` | - | Show the ContextForge index status |
| `ContextForge: Clear Index` | - | Clear the entire search index |
| `ContextForge: Settings` | - | Open ContextForge settings |

## Configuration

### Extension Settings

- **`contextforge.apiUrl`**: ContextForge API Gateway URL (default: `http://localhost:8080`)
- **`contextforge.autoIngest`**: Automatically ingest workspace on startup (default: `false`)
- **`contextforge.maxResults`**: Maximum number of search results (default: `10`)
- **`contextforge.enableWebSearch`**: Enable web search for additional context (default: `true`)
- **`contextforge.showLineNumbers`**: Show line numbers in code snippets (default: `true`)

### ContextForge API Configuration

Configure the ContextForge API Gateway through environment variables:

```bash
# Local-only mode (recommended for sensitive code)
LLM_PRIORITY=ollama,mock
PRIVACY_MODE=local

# Hybrid mode (local + remote fallback)
LLM_PRIORITY=ollama,openai
PRIVACY_MODE=hybrid
OPENAI_API_KEY=your-key-here

# Enable web search
ENABLE_WEB_SEARCH=True
SERPAPI_KEY=your-serpapi-key  # Optional
```

## Usage Examples

### Code Understanding
```
Q: How does user authentication work in this project?
```

### API Documentation
```
Q: What are all the API endpoints and what do they do?
```

### Code Search
```
Q: Where is the database connection configured?
```

### Architecture Questions
```
Q: What design patterns are used in this codebase?
```

### Debugging Help
```
Q: How is error handling implemented in the payment module?
```

## Privacy and Security

### Local-First Operation

By default, ContextForge operates in local-only mode:
- All code analysis happens locally
- No data is sent to external services
- Requires local LLM (Ollama recommended)

### Remote LLM Support

When configured with remote LLM providers:
- Only relevant code snippets are sent (not entire files)
- API keys are stored in environment variables
- You can review what data is being sent in the query results

### Data Storage

- **Index Data**: Stored locally in Docker volumes
- **Cache**: Web search results cached locally
- **Logs**: Service logs available through Docker

## Troubleshooting

### Extension Not Working

1. **Check API Gateway**: Ensure ContextForge services are running
   ```bash
   curl http://localhost:8080/health
   ```

2. **Check Configuration**: Verify the API URL in VS Code settings

3. **Check Logs**: View the VS Code Developer Console (`Help > Toggle Developer Tools`)

### Ingestion Issues

1. **Large Repositories**: Ingestion may take time for large codebases
2. **File Permissions**: Ensure VS Code has read access to your workspace
3. **Disk Space**: Check available disk space for index storage

### Query Issues

1. **No Results**: Try ingesting the workspace first
2. **Slow Responses**: Check LLM backend performance
3. **Error Messages**: Check ContextForge service logs

### Performance Optimization

1. **Exclude Patterns**: Configure file exclusion patterns in the connector service
2. **Chunk Size**: Adjust preprocessing chunk size for your use case
3. **Vector Index**: Use FAISS for better performance with large codebases

## Development

### Building the Extension

```bash
cd vscode-extension
npm install
npm run compile
```

### Packaging

```bash
npm run package
```

This creates a `.vsix` file that can be installed in VS Code.

### Testing

```bash
npm test
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## Support

- **Issues**: Report bugs and feature requests on GitHub
- **Documentation**: See the main ContextForge README
- **Community**: Join discussions in GitHub Discussions

## License

MIT License - see the main ContextForge repository for details.
