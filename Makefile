# ContextForge Makefile
# Local-first context engine and augment/assistant pipeline

.PHONY: help venv dev build clean test format lint ingest-example query-example llm-test

# Default target
help:
	@echo "ContextForge - Local-first context engine"
	@echo ""
	@echo "Available targets:"
	@echo "  venv           - Create Python virtual environment"
	@echo "  dev            - Start development environment (docker-compose up --build)"
	@echo "  build          - Build all Docker images"
	@echo "  clean          - Stop and remove containers, volumes"
	@echo "  test           - Run unit tests"
	@echo "  format         - Format code with black and isort"
	@echo "  lint           - Lint code with flake8"
	@echo "  ingest-example - Ingest example repository"
	@echo "  query-example  - Run example query"
	@echo "  llm-test       - Test LLM adapters"
	@echo "  terminal-test  - Test terminal execution functionality"

# Python virtual environment
venv:
	python -m venv venv
	@echo "Activate with: source venv/bin/activate (Linux/Mac) or venv\\Scripts\\activate (Windows)"

# Development environment
dev:
	docker-compose up --build

# Build all images
build:
	docker-compose build

# Clean up
clean:
	docker-compose down -v
	docker system prune -f

# Testing
test:
	python -m pytest tests/ -v

# Code formatting
format:
	python -m black services/ scripts/ tests/
	python -m isort services/ scripts/ tests/

# Linting
lint:
	python -m flake8 services/ scripts/ tests/

# Example ingestion
ingest-example:
	python scripts/ingest_example.py --path examples/small-repo

# Example query
query-example:
	python scripts/query_example.py --query "API_TOKEN"

# Test LLM adapters
llm-test:
	python scripts/test_llm.py

# Install development dependencies
install-dev:
	pip install -r requirements.txt
	pip install -r requirements-dev.txt

# VS Code extension
vscode-build:
	cd vscode-extension && npm install && npm run compile

vscode-package:
	cd vscode-extension && npm run package

# Terminal execution test
terminal-test:
	@echo "Testing terminal execution functionality..."
	@echo "1. Testing allowed commands endpoint..."
	@curl -s http://localhost:8080/terminal/allowed-commands | python -m json.tool
	@echo "\n2. Testing simple command execution..."
	@curl -s -X POST http://localhost:8080/terminal/execute \
		-H "Content-Type: application/json" \
		-d '{"command": "echo Hello ContextForge", "timeout": 10}' | python -m json.tool
	@echo "\n3. Testing command suggestion..."
	@curl -s -X POST http://localhost:8080/terminal/suggest \
		-H "Content-Type: application/json" \
		-d '{"task_description": "check git status"}' | python -m json.tool

# Docker health check
health:
	@echo "Checking service health..."
	@curl -f http://localhost:8080/health || echo "API Gateway not ready"
	@curl -f http://localhost:8001/health || echo "Vector Index not ready"
	@curl -f http://localhost:8002/health || echo "Connector not ready"
	@curl -f http://localhost:8003/health || echo "Preprocessor not ready"
	@curl -f http://localhost:8004/health || echo "Web Fetcher not ready"
	@curl -f http://localhost:8005/health || echo "Mock LLM not ready"
	@curl -f http://localhost:8006/health || echo "Terminal Executor not ready"
