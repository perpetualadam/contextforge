# ContextForge Architecture

## Overview

ContextForge is a local-first context engine designed for intelligent code analysis and retrieval. The system follows a microservices architecture with Docker Compose orchestration, providing semantic search, multi-LLM support, and VS Code integration.

## System Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              Client Layer                                   │
├─────────────────┬─────────────────┬─────────────────┬─────────────────────┤
│   VS Code       │   Web Interface │   CLI Scripts   │   Direct API        │
│   Extension     │   (Future)      │   & Tools       │   Integration       │
└─────────┬───────┴─────────┬───────┴─────────┬───────┴─────────┬───────────┘
          │                 │                 │                 │
          └─────────────────┼─────────────────┼─────────────────┘
                            │                 │
                   ┌────────▼─────────────────▼────────┐
                   │         API Gateway              │
                   │         (Port 8080)              │
                   │  ┌─────────────────────────────┐  │
                   │  │      RAG Pipeline           │  │
                   │  │  ┌─────────┬─────────────┐  │  │
                   │  │  │LLM Client│Search Adapter│  │  │
                   │  │  └─────────┴─────────────┘  │  │
                   │  └─────────────────────────────┘  │
                   └────────┬─────────────────────────┘
                            │
        ┌───────────────────┼───────────────────┐
        │                   │                   │
┌───────▼────────┐ ┌────────▼────────┐ ┌────────▼────────┐
│ Vector Index   │ │  Preprocessor   │ │   Connector     │
│ (Port 8001)    │ │  (Port 8003)    │ │   (Port 8002)   │
│                │ │                 │ │                 │
│ ┌────────────┐ │ │ ┌─────────────┐ │ │ ┌─────────────┐ │
│ │   FAISS    │ │ │ │ Python AST  │ │ │ │File Scanner │ │
│ │   Index    │ │ │ │  Chunker    │ │ │ │             │ │
│ └────────────┘ │ │ └─────────────┘ │ │ └─────────────┘ │
│ ┌────────────┐ │ │ ┌─────────────┐ │ │ ┌─────────────┐ │
│ │Embeddings  │ │ │ │JavaScript   │ │ │ │ Encoding    │ │
│ │Generator   │ │ │ │ Chunker     │ │ │ │ Detection   │ │
│ └────────────┘ │ │ └─────────────┘ │ │ └─────────────┘ │
│ ┌────────────┐ │ │ ┌─────────────┐ │ │ ┌─────────────┐ │
│ │In-Memory   │ │ │ │ Markdown    │ │ │ │ Pattern     │ │
│ │ Fallback   │ │ │ │ Chunker     │ │ │ │ Filtering   │ │
│ └────────────┘ │ │ └─────────────┘ │ │ └─────────────┘ │
└────────────────┘ └─────────────────┘ └─────────────────┘
        │                   │                   │
        └───────────────────┼───────────────────┘
                            │
        ┌───────────────────┼───────────────────┐
        │                   │                   │
┌───────▼────────┐ ┌────────▼────────┐ ┌────────▼────────┐
│  Web Fetcher   │ │  LLM Backends   │ │   Mock LLM      │
│  (Port 8004)   │ │  (External)     │ │   (Port 8005)   │
│                │ │                 │ │                 │
│ ┌────────────┐ │ │ ┌─────────────┐ │ │ ┌─────────────┐ │
│ │URL Fetcher │ │ │ │   Ollama    │ │ │ │ Deterministic│ │
│ └────────────┘ │ │ │(Port 11434) │ │ │ │  Responses  │ │
│ ┌────────────┐ │ │ └─────────────┘ │ │ └─────────────┘ │
│ │  Caching   │ │ │ ┌─────────────┐ │ │ ┌─────────────┐ │
│ └────────────┘ │ │ │ LM Studio   │ │ │ │   Testing   │ │
│ ┌────────────┐ │ │ │(Port 1234)  │ │ │ │   Support   │ │
│ │Rate Limiter│ │ │ └─────────────┘ │ │ └─────────────┘ │
│ └────────────┘ │ │ ┌─────────────┐ │ │ ┌─────────────┐ │
│ ┌────────────┐ │ │ │   OpenAI    │ │ │ │   Offline   │ │
│ │robots.txt  │ │ │ │  Anthropic  │ │ │ │Development  │ │
│ │ Compliance │ │ │ │   Mistral   │ │ │ └─────────────┘ │
│ └────────────┘ │ │ └─────────────┘ │ └─────────────────┘
└────────────────┘ └─────────────────┘
```

## Core Components

### API Gateway (Port 8080)
**Purpose**: Central orchestration and API endpoint management
**Technology**: FastAPI with structured logging
**Key Features**:
- RESTful API endpoints for all operations
- RAG pipeline orchestration
- Request validation and error handling
- CORS middleware for cross-origin requests
- Health monitoring and status reporting

**Main Endpoints**:
- `POST /query` - Main question answering endpoint
- `POST /ingest` - Repository ingestion orchestration
- `POST /search/vector` - Direct vector search
- `POST /search/web` - Web search functionality
- `POST /llm/generate` - Direct LLM generation
- `GET /health` - Health check and status

### Vector Index Service (Port 8001)
**Purpose**: Semantic search and vector storage
**Technology**: FAISS with sentence-transformers
**Key Features**:
- High-performance vector similarity search
- Embedding generation using all-MiniLM-L6-v2 (384 dimensions)
- Persistent storage with save/load functionality
- In-memory fallback when FAISS unavailable
- Cosine similarity using IndexFlatIP

**Data Flow**:
1. Receive text chunks with metadata
2. Generate embeddings using sentence-transformers
3. Store vectors in FAISS index with metadata
4. Provide similarity search with configurable top-k

### Preprocessor Service (Port 8003)
**Purpose**: Language-aware text chunking
**Technology**: AST parsing, regex, and markdown processing
**Key Features**:
- **Python**: AST-based extraction of functions, classes, imports, docstrings
- **JavaScript/TypeScript**: Regex-based function and class detection
- **Markdown**: Heading-based chunking with code block extraction
- Configurable chunk size and overlap
- Metadata preservation (file path, line numbers, chunk type)

**Chunking Strategies**:
- **Semantic Chunking**: Respects code structure boundaries
- **Overlap Management**: Prevents context loss at boundaries
- **Metadata Enrichment**: Adds source location and type information

### Connector Service (Port 8002)
**Purpose**: File system integration and repository scanning
**Technology**: Python file I/O with encoding detection
**Key Features**:
- Recursive directory traversal
- Pattern-based file filtering (include/exclude)
- Multiple encoding detection (UTF-8, UTF-16, Latin-1, CP1252)
- File size limits and safety checks
- Binary file detection and exclusion

**Default Exclusions**:
- Version control: `.git`, `.svn`, `.hg`
- Dependencies: `node_modules`, `venv`, `__pycache__`
- Build artifacts: `*.pyc`, `*.class`, `dist/`, `build/`
- Secrets: `*.env*`, `secrets/`, `credentials/`

### Web Fetcher Service (Port 8004)
**Purpose**: Web content retrieval and caching
**Technology**: BeautifulSoup with requests and robotparser
**Key Features**:
- robots.txt compliance checking
- Domain-based rate limiting
- Content caching with configurable TTL (24 hours default)
- HTML parsing and text extraction
- Script and style tag removal

**Search Provider Support**:
- SerpAPI (primary)
- Bing Search API
- Google Custom Search Engine
- Scraping fallback for basic search

### Mock LLM Service (Port 8005)
**Purpose**: Testing and offline development
**Technology**: FastAPI with template-based responses
**Key Features**:
- Multiple endpoint formats (Ollama, OpenAI, simple)
- Context-aware response templates
- Configurable response delays
- Error simulation for testing
- Deterministic responses for reproducible tests

## Data Flow Architecture

### Ingestion Pipeline
```
Repository Files → Connector → Preprocessor → Vector Index
     ↓               ↓            ↓             ↓
1. File Discovery  2. Chunking   3. Embedding  4. Storage
   - Scan files      - AST parse   - Generate    - FAISS index
   - Filter types    - Extract     - Vectors     - Metadata
   - Encoding        - Metadata    - 384-dim     - Persistence
```

### Query Pipeline
```
User Query → API Gateway → RAG Pipeline → Response
    ↓            ↓             ↓            ↓
1. Validation  2. Context    3. Generation 4. Formatting
   - Input       - Vector      - LLM call    - JSON response
   - Parameters  - Web search  - Prompt      - Metadata
   - Auth        - Ranking     - Fallback    - Sources
```

### RAG (Retrieval-Augmented Generation) Pipeline
```
Question → Vector Search → Web Search → Context Ranking → Prompt Composition → LLM → Answer
    ↓           ↓             ↓             ↓                ↓               ↓       ↓
1. Parse    2. Semantic   3. External   4. Score &      5. Template     6. Generate 7. Format
   query       similarity    sources      combine         with context    response   with meta
```

## Technology Stack

### Backend Services
- **FastAPI**: Modern Python web framework with automatic OpenAPI
- **FAISS**: Facebook AI Similarity Search for vector operations
- **sentence-transformers**: Pre-trained embedding models
- **BeautifulSoup**: HTML parsing and text extraction
- **structlog**: Structured JSON logging
- **tenacity**: Retry logic with exponential backoff

### Language Processing
- **tree-sitter**: Syntax tree parsing for Python
- **AST**: Python Abstract Syntax Tree parsing
- **Regex**: JavaScript/TypeScript pattern matching
- **Markdown**: Heading-based document structure

### Infrastructure
- **Docker Compose**: Service orchestration and networking
- **Docker**: Containerization for all services
- **nginx**: Reverse proxy and load balancing (production)
- **Redis**: Caching and session storage (production)

### Development & Testing
- **pytest**: Comprehensive testing framework
- **black**: Code formatting
- **flake8**: Linting and style checking
- **mypy**: Static type checking
- **GitHub Actions**: CI/CD pipeline

## Security Architecture

### Privacy Modes
1. **Local Mode**: All processing local, no external API calls
2. **Hybrid Mode**: Local processing with remote LLM fallback
3. **Remote Mode**: Uses remote LLMs for generation

### Security Features
- **Environment Variables**: All secrets in environment, not code
- **Input Validation**: Pydantic models for request validation
- **Rate Limiting**: Per-domain and per-service rate limits
- **CORS Configuration**: Controlled cross-origin access
- **Container Isolation**: Docker container security boundaries
- **Sensitive Data Filtering**: Logs exclude sensitive information

### Data Handling
- **Code Privacy**: Only relevant snippets sent to LLMs
- **Local Storage**: Vector data stored in local Docker volumes
- **Cache Management**: Web cache with configurable retention
- **Audit Logging**: Structured logs for security monitoring

## Scalability Considerations

### Horizontal Scaling
- **Stateless Services**: All services designed for horizontal scaling
- **Load Balancing**: nginx for request distribution
- **Database Sharding**: Vector index partitioning for large datasets
- **Cache Distribution**: Redis cluster for shared caching

### Performance Optimization
- **Vector Index**: FAISS optimized for similarity search
- **Embedding Caching**: Pre-computed embeddings for common queries
- **Connection Pooling**: HTTP client connection reuse
- **Async Processing**: FastAPI async endpoints for I/O operations

### Resource Management
- **Memory Limits**: Docker container resource constraints
- **Disk Usage**: Configurable cache sizes and retention
- **CPU Optimization**: Multi-core embedding generation
- **Network Efficiency**: Request batching and compression

## Deployment Architecture

### Development Environment
```
Docker Compose → Local Services → Local Storage
     ↓               ↓               ↓
- Hot reload    - Debug logging  - Volume mounts
- Mock services - Dev databases  - Local cache
- Test data     - Fast startup   - Easy cleanup
```

### Production Environment
```
Load Balancer → API Gateway → Service Mesh → Persistent Storage
     ↓              ↓             ↓              ↓
- SSL termination - Auth layer  - Service mesh - PostgreSQL
- Rate limiting   - Validation  - Monitoring   - Redis cluster
- Health checks   - Logging     - Tracing      - File storage
```

## Monitoring and Observability

### Logging Strategy
- **Structured Logging**: JSON format with consistent fields
- **Log Levels**: DEBUG, INFO, WARNING, ERROR, CRITICAL
- **Correlation IDs**: Request tracing across services
- **Performance Metrics**: Latency, throughput, error rates

### Health Monitoring
- **Service Health**: Individual service health endpoints
- **Dependency Checks**: External service availability
- **Resource Monitoring**: CPU, memory, disk usage
- **Alert Configuration**: Threshold-based alerting

### Metrics Collection
- **Application Metrics**: Request counts, response times
- **Business Metrics**: Query success rates, user engagement
- **Infrastructure Metrics**: Container resource usage
- **Custom Metrics**: Domain-specific measurements

## Extension Points

### Adding New Languages
1. Create new chunker class inheriting from `BaseChunker`
2. Implement language-specific parsing logic
3. Register in `ChunkerFactory`
4. Add file extension mappings

### Adding New LLM Providers
1. Create adapter class inheriting from `BaseAdapter`
2. Implement `generate()` method with provider API
3. Add to `LLMClient` initialization
4. Configure in environment variables

### Adding New Search Providers
1. Create provider class with `search()` method
2. Implement provider-specific API integration
3. Add to `SearchAdapter` provider list
4. Configure API keys and settings

This architecture provides a solid foundation for intelligent code analysis while maintaining flexibility for future enhancements and scaling requirements.
