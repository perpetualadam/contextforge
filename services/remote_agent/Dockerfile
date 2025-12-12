FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy service code
COPY services/remote_agent /app/remote_agent
COPY services/api_gateway/rag.py /app/rag.py
COPY services/api_gateway/llm_client.py /app/llm_client.py
COPY services/api_gateway/search_adapter.py /app/search_adapter.py
COPY services/preprocessor /app/preprocessor

# Set Python path
ENV PYTHONPATH=/app

# Default to coordinator mode
ENV COORDINATOR_MODE=true
ENV WORKER_MODE=false
ENV PORT=8011

EXPOSE 8011

CMD ["python", "-m", "remote_agent.app"]

