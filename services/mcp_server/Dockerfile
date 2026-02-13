FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy and install service-specific requirements (no ML bloat)
COPY services/mcp_server/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy shared modules needed by MCP server
COPY services/__init__.py /app/services/__init__.py
COPY services/utils /app/services/utils
COPY services/tools /app/services/tools

# Copy the MCP server code
COPY services/mcp_server /app/services/mcp_server

# Set environment variables
ENV PYTHONPATH=/app
ENV API_GATEWAY_URL=http://api-gateway:8000
ENV TERMINAL_EXECUTOR_URL=http://terminal-executor:8006

# Expose port for HTTP transport
EXPOSE 8010

# Default command runs with stdio transport
CMD ["python", "-m", "services.mcp_server.app", "stdio"]

