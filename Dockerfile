# ---------- Frontend Build Stage ----------
FROM node:20-alpine AS web
WORKDIR /app

# Copy package files for better caching
COPY web/package*.json ./web/
RUN npm --prefix web ci

# Copy source and build
COPY web ./web
RUN npm --prefix web run build

# ---------- Backend Build Stage ----------
FROM python:3.11-slim AS api

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN groupadd -r appuser && useradd -r -g appuser appuser

# Set working directory
WORKDIR /app

# Copy Python dependency files
COPY requirements.txt ./

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY app ./app
COPY prompts ./prompts

# Copy static files from frontend build
COPY --from=web /app/web/.next ./web/.next
COPY --from=web /app/web/public ./web/public
COPY --from=web /app/web/package.json ./web/package.json

# Create necessary directories and set permissions
RUN mkdir -p app/memory \
    && chown -R appuser:appuser /app

# Switch to non-root user
USER appuser

# Environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app
ENV PORT=8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Expose port
EXPOSE 8000

# Start command
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]