FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy and install service-specific requirements (ML stack)
COPY services/vector_index/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code as a package (supports relative imports)
COPY services/vector_index/ /app/vector_index/

# Create data directory
RUN mkdir -p /app/data

# Expose port
EXPOSE 8001

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8001/health || exit 1

# Run the application as a module
CMD ["python", "-m", "uvicorn", "vector_index.app:app", "--host", "0.0.0.0", "--port", "8001"]
