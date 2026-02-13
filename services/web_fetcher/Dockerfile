FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy and install service-specific requirements (no ML bloat)
COPY services/web_fetcher/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY services/web_fetcher/ .

# Create cache directory
RUN mkdir -p /app/cache

# Expose port
EXPOSE 8004

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8004/health || exit 1

# Run the application
CMD ["python", "app.py"]
