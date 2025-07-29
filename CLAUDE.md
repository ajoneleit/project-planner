# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

A conversational AI project planning bot that maintains project state in markdown files within the same Git repository. Built with FastAPI backend and Next.js frontend, deployed as a single containerized service on AWS App Runner.

## Technology Stack

- **Runtime**: Python 3.11 + Node 20 (Multi-stage Docker build)
- **Backend**: FastAPI + LangGraph (API server with SSE streaming)
- **LLM**: OpenAI o3 (fallback: gpt-4o-mini) - Switchable via ?model= parameter
- **Memory**: Markdown files in `app/memory/*.md` (Version-controlled project state)
- **Frontend**: Next.js 14 + shadcn/ui + Tailwind (Static chat interface)
- **Deployment**: AWS App Runner (Single container, HTTPS, auto-scaling)
- **Observability**: LangSmith → OTLP → CloudWatch

## Architecture

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   Next.js UI   │◄──►│   FastAPI API    │◄──►│   OpenAI LLM    │
│  (Static SPA)  │    │   + LangGraph    │    │  (o3/gpt-4o)    │
└─────────────────┘    └──────────────────┘    └─────────────────┘
                              │
                              ▼
                       ┌──────────────┐
                       │  Markdown    │
                       │  Memory      │
                       │  (Git Repo)  │
                       └──────────────┘
```

## Repository Structure

- `app/` - FastAPI backend
  - `main.py` - FastAPI application with API endpoints
  - `langgraph_runner.py` - LangGraph workflow + memory management
  - `memory/` - Project markdown files (one per project slug)
- `web/` - Next.js frontend source
  - Static export configuration (`output: "export"`)
  - Built files served by FastAPI as static assets
- `prompts/` - System prompts (`project_planner.md`)
- `tests/` - Test files

## API Endpoints

- `GET /` - Serve Next.js frontend
- `POST /projects` - Create new project with slug and markdown file
- `GET /projects` - List all project slugs
- `POST /projects/{slug}/chat` - Stream chat responses via SSE
- `GET /projects/{slug}/file` - Serve raw markdown content

## Memory System

- One `.md` file per project (named by slug) in `app/memory/`
- Append-only conversation history
- Version controlled with Git
- Structured format: metadata + Q&A pairs

## Common Development Commands

```bash
# Backend development
poetry install
poetry run uvicorn app.main:app --reload

# Frontend development
cd web
npm install
npm run dev
npm run build  # For static export

# Container build
docker build -t planner-bot .
docker run -p 8000:8000 planner-bot

# Testing
pytest tests/

# Deployment
./deploy-backend.sh              # Deploy to AWS App Runner
./deploy-backend.sh --dry-run    # Preview deployment
make deploy                      # Deploy via Make
make deploy-dry-run             # Preview via Make
```

## Environment Variables

```bash
# LLM Configuration
OPENAI_API_KEY=<key>
DEFAULT_MODEL=o3

# Observability
LANGCHAIN_TRACING_V2=true
LANGCHAIN_ENDPOINT=https://api.smith.langchain.com
LANGCHAIN_API_KEY=<key>
```

## Key Design Decisions

- **Markdown Memory**: Human-readable, version-controlled project state
- **Static Frontend**: Simplified deployment, better caching
- **Single Container**: Reduced complexity, easier development
- **Streaming Chat**: Real-time user experience via SSE
- **Model Switching**: Runtime LLM selection for testing