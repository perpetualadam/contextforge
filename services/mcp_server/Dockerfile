FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

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

