FROM python:3.11-slim

WORKDIR /app

# Install curl for healthcheck
RUN apt-get update && apt-get install -y curl && rm -rf /var/lib/apt/lists/*

# Copy and install service-specific requirements (no ML bloat)
COPY services/metrics/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code as a package (supports relative imports)
COPY services/metrics/ /app/metrics/

# Expose port
EXPOSE 8012

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8012/health || exit 1

# Run the application as a module
CMD ["python", "-m", "uvicorn", "metrics.app:app", "--host", "0.0.0.0", "--port", "8012"]
