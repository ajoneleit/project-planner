# Multi-stage Dockerfile for Project Planner Bot
# Stage 1: Build Next.js frontend
FROM node:20-alpine AS web-builder

WORKDIR /app/web
COPY web/package*.json ./
RUN npm ci --only=production

COPY web/ ./
RUN npm run build

# Stage 2: Python backend with static files
FROM python:3.11-slim AS api

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Poetry
RUN pip install poetry

# Set working directory
WORKDIR /app

# Copy Poetry files
COPY pyproject.toml poetry.lock* ./

# Configure Poetry and install dependencies
RUN poetry config virtualenvs.create false \
    && poetry install --no-dev --no-interaction --no-ansi

# Copy application code
COPY app/ ./app/
COPY prompts/ ./prompts/

# Copy built frontend from previous stage
COPY --from=web-builder /app/web/out ./web/out

# Create memory directory
RUN mkdir -p app/memory

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/api/health || exit 1

# Run the application
CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]