.PHONY: help dev test build docker clean install-deps

help:
	@echo "Available commands:"
	@echo "  dev          - Start development server"
	@echo "  test         - Run all tests"
	@echo "  build        - Build frontend and prepare for deployment"
	@echo "  docker       - Build Docker image"
	@echo "  clean        - Clean build artifacts"
	@echo "  install-deps - Install all dependencies"

install-deps:
	export PATH="$$HOME/.local/bin:$$PATH" && poetry install
	cd web && npm install

dev:
	export PATH="$$HOME/.local/bin:$$PATH" && poetry run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

test:
	export PATH="$$HOME/.local/bin:$$PATH" && poetry run pytest tests/ -v

build:
	cd web && npm run build
	mkdir -p static
	cp -r web/out/* static/

docker:
	docker build -t planner-bot .

clean:
	rm -rf static/
	rm -rf web/out/
	rm -rf web/.next/
	find . -type d -name __pycache__ -delete
	find . -name "*.pyc" -delete