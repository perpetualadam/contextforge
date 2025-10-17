# Data Privacy and Security Guidelines

## Overview

ContextForge is designed as a **local-first** context engine that prioritizes your data privacy and security. This document explains the privacy implications of different configuration options and how to ensure your code and data remain private.

## Privacy Modes

### 🔒 Local-Only Mode (Recommended for Sensitive Code)

**Configuration:**
```bash
LLM_PRIORITY=ollama,mock
PRIVACY_MODE=local
```

**What stays local:**
- All repository code and content
- All embeddings and vector indices
- All search queries and results
- All LLM processing

**Requirements:**
- Ollama or LM Studio running locally
- No internet connection required for core functionality

### 🔄 Hybrid Mode (Balanced Approach)

**Configuration:**
```bash
LLM_PRIORITY=ollama,openai
PRIVACY_MODE=hybrid
ENABLE_WEB_SEARCH=True
```

**What stays local:**
- Repository code (processed by local LLM)
- Vector indices and embeddings

**What may go remote:**
- Web search queries (to search APIs)
- Fallback LLM requests (if local LLM fails)

### ☁️ Remote Mode (Maximum Functionality)

**Configuration:**
```bash
LLM_PRIORITY=openai,anthropic,ollama
PRIVACY_MODE=remote
ENABLE_WEB_SEARCH=True
```

**Privacy implications:**
- Repository code may be sent to remote LLM providers
- Search queries sent to external APIs
- Responses cached locally but processed remotely

## Data Flow and Storage

### Local Storage
- **Vector indices:** `./data/vector_index/`
- **Repository cache:** `./data/repos/`
- **Web cache:** `./data/web_cache/`
- **Logs:** Docker container logs (not persisted by default)

### Remote Data Transmission

When using remote LLM providers, the following data may be transmitted:

1. **Code snippets** from your repository (for context)
2. **User queries** and questions
3. **Retrieved context** from vector search
4. **Web search results** (if enabled)

### What is NEVER transmitted:
- Complete repository contents (only relevant snippets)
- API keys or secrets (stored in environment variables)
- Vector indices or embeddings
- Local file paths or directory structures

## Security Best Practices

### 1. Environment Variables
```bash
# ✅ Good: Use environment variables
export OPENAI_API_KEY="your-key-here"

# ❌ Bad: Never put keys in code
OPENAI_API_KEY = "sk-..."  # DON'T DO THIS
```

### 2. Docker Secrets (Production)
```yaml
# docker-compose.prod.yml
services:
  api_gateway:
    secrets:
      - openai_key
secrets:
  openai_key:
    file: ./secrets/openai_key.txt
```

### 3. Network Isolation
```bash
# Block external network access for local-only mode
docker-compose up --build --network none
```

### 4. Code Filtering
Configure which file types and directories to exclude:

```python
# In connector service configuration
EXCLUDE_PATTERNS = [
    "*.env*",
    "*.key",
    "*.pem",
    "*secret*",
    "*password*",
    ".git/",
    "node_modules/",
    "__pycache__/"
]
```

## Compliance Considerations

### GDPR Compliance
- All personal data processing happens locally by default
- Remote processing requires explicit configuration
- Users can delete all data by removing `./data/` directory

### Enterprise Security
- Use `PRIVACY_MODE=local` for sensitive codebases
- Deploy behind corporate firewall
- Use private LLM endpoints (Azure OpenAI, AWS Bedrock)

### Audit Trail
- All LLM requests logged with backend information
- Search queries logged locally
- No persistent storage of sensitive data in logs

## Recommended Configurations

### For Open Source Projects
```bash
LLM_PRIORITY=ollama,openai
ENABLE_WEB_SEARCH=True
PRIVACY_MODE=hybrid
```

### For Proprietary/Sensitive Code
```bash
LLM_PRIORITY=ollama,mock
ENABLE_WEB_SEARCH=False
PRIVACY_MODE=local
```

### For Enterprise Deployment
```bash
LLM_PRIORITY=azure_openai,ollama
ENABLE_WEB_SEARCH=True
PRIVACY_MODE=hybrid
# Use private endpoints and VPC
```

## Monitoring and Alerts

Set up monitoring to detect unexpected remote calls:

```bash
# Monitor network traffic
docker-compose logs api_gateway | grep "remote_llm_call"

# Check privacy mode violations
grep "PRIVACY_VIOLATION" ./data/logs/api_gateway.log
```

## Questions and Support

If you have questions about data privacy or need help configuring ContextForge for your security requirements, please:

1. Review this document
2. Check the configuration examples
3. Open an issue on GitHub
4. Contact the maintainers

Remember: **When in doubt, use local-only mode.**
