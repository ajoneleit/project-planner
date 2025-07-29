# ---------- Frontend Build Stage ----------
FROM node:20-alpine AS web
WORKDIR /app

# Copy package files for better caching
COPY web/package*.json ./web/
RUN npm --prefix web ci

# Copy source and build with production API URL
COPY web ./web
ENV NEXT_PUBLIC_API_URL=https://fbm26vyfbw.us-east-1.awsapprunner.com
RUN npm --prefix web run build

# ---------- Frontend Server Stage ----------
FROM node:20-alpine AS frontend
WORKDIR /app
RUN addgroup --system --gid 1001 nodejs
RUN adduser --system --uid 1001 nextjs

# Copy built application
COPY --from=web /app/web/.next/standalone ./
COPY --from=web /app/web/.next/static ./.next/static
COPY --from=web /app/web/public ./public

# Fix permissions for nextjs user
RUN chown -R nextjs:nodejs /app

USER nextjs
EXPOSE 3000
ENV PORT=3000
ENV HOSTNAME="0.0.0.0"
ENV NEXT_PUBLIC_API_URL=https://fbm26vyfbw.us-east-1.awsapprunner.com
CMD ["node", "server.js"]

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