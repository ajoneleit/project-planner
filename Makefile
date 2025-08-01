.PHONY: help dev frontend backend test build docker docker-test docker-run clean install-deps install-pip dev-observability obs-up obs-down obs-logs obs-health deploy deploy-dry-run

help:
	@echo "Available commands:"
	@echo "  dev          - Instructions for full development stack"
	@echo "  frontend     - Start frontend development server (port 3000)"
	@echo "  backend      - Start backend development server (port 8000)"
	@echo "  test         - Run all tests"
	@echo "  build        - Build frontend and prepare for deployment"
	@echo "  docker       - Build Docker image"
	@echo "  docker-test  - Test Docker container"
	@echo "  docker-run   - Build and run Docker container"
	@echo "  clean        - Clean build artifacts"
	@echo "  install-deps - Install all dependencies (Poetry)"
	@echo "  install-pip  - Install dependencies using pip"
	@echo ""
	@echo "Deployment commands:"
	@echo "  deploy       - Deploy backend to AWS App Runner"
	@echo "  deploy-dry-run - Preview deployment without executing"
	@echo ""
	@echo "Observability commands:"
	@echo "  dev-observability - Start with full observability stack"
	@echo "  obs-up       - Start observability stack (Docker Compose)"
	@echo "  obs-down     - Stop observability stack"
	@echo "  obs-logs     - View observability logs"
	@echo "  obs-health   - Check observability health"

install-deps:
	export PATH="$$HOME/.local/bin:$$PATH" && poetry install
	cd web && npm install

install-pip:
	pip install -r requirements.txt
	cd web && npm install

# Start frontend development server
frontend:
	cd web && npm run dev

# Start backend development server  
backend:
	export PATH="$$HOME/.local/bin:$$PATH" && poetry run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Start full development stack (requires tmux or run in separate terminals)
dev:
	@echo "Starting development servers..."
	@echo "Backend: http://localhost:8000"
	@echo "Frontend: http://localhost:3000"
	@echo ""
	@echo "Run these commands in separate terminals:"
	@echo "  make backend"
	@echo "  make frontend"

test:
	export PATH="$$HOME/.local/bin:$$PATH" && poetry run pytest tests/ -v

build:
	cd web && npm run build
	mkdir -p static
	cp -r web/out/* static/

docker:
	docker build -t planner-bot .

docker-test: docker
	@echo "Testing Docker container..."
	@docker run -d --name planner-bot-test -p 8001:8000 \
		-e OPENAI_API_KEY=test \
		planner-bot:latest
	@sleep 5
	@if curl -f http://localhost:8001/health; then \
		echo "✅ Health check passed"; \
	else \
		echo "❌ Health check failed"; \
		exit 1; \
	fi
	@docker stop planner-bot-test
	@docker rm planner-bot-test
	@echo "🎉 Docker container test completed successfully"

docker-run: docker
	docker run -p 8000:8000 \
		-e OPENAI_API_KEY=${OPENAI_API_KEY} \
		-e DEFAULT_MODEL=gpt-4o-mini \
		planner-bot:latest

# Observability commands
dev-observability:
	@echo "Starting development server with full observability stack..."
	docker-compose -f docker-compose.dev.yml up --build

obs-up:
	@echo "Starting observability stack..."
	docker-compose up -d otel-collector
	@echo "✅ OTLP Collector running at http://localhost:4317 (gRPC) and http://localhost:4318 (HTTP)"

obs-down:
	@echo "Stopping observability stack..."
	docker-compose down

obs-logs:
	@echo "Viewing observability logs..."
	docker-compose logs -f otel-collector

obs-health:
	@echo "Checking observability health..."
	@if curl -f http://localhost:8000/health; then \
		echo "✅ Main application healthy"; \
	else \
		echo "❌ Main application not responding"; \
	fi
	@echo "OTLP Collector status:"
	@docker-compose ps otel-collector

clean:
	rm -rf static/
	rm -rf web/out/
	rm -rf web/.next/
	find . -type d -name __pycache__ -delete
	find . -name "*.pyc" -delete
	docker-compose down --volumes --remove-orphans

# Deployment commands
deploy: 
	@echo "🚀 Deploying backend to AWS App Runner..."
	./deploy-backend.sh

deploy-dry-run:
	@echo "🔍 Preview deployment (dry run)..."
	./deploy-backend.sh --dry-run