# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

A conversational AI project planning bot that maintains project state in markdown files within the same Git repository. Built with FastAPI backend and Next.js frontend, deployed as a single containerized service on AWS App Runner.

**MIGRATION STATUS**: Migrating from LangGraph to OpenAI Agents SDK. **CONVERSATION MEMORY FIXED** ✅ - SQLiteSession working correctly. Document updates and tool execution feedback still need work.

## Technology Stack

- **Runtime**: Python 3.11 + Node 20 (Multi-stage Docker build)
- **Backend**: FastAPI + OpenAI Agents SDK (API server with SSE streaming)
- **LLM**: OpenAI o3 (fallback: gpt-4o-mini) - Switchable via ?model= parameter
- **Memory**: Dual system - SQLiteSession (conversations) + Markdown files (project state)
- **Frontend**: Next.js 14 + shadcn/ui + Tailwind (Static chat interface)
- **Deployment**: AWS App Runner (Single container, HTTPS, auto-scaling)
- **Observability**: LangSmith → OTLP → CloudWatch

## Architecture

```
┌─────────────────┐    ┌──────────────────────────┐    ┌─────────────────┐
│   Next.js UI   │◄──►│     FastAPI Backend      │◄──►│   OpenAI LLM    │
│  (Static SPA)  │    │  ┌─────────────────────┐  │    │  (o3/gpt-4o)    │
│                │    │  │ OpenAI Agents SDK   │  │    │                 │
│ • React Query  │    │  │ • SQLiteSession     │  │    │ • Function      │
│ • shadcn/ui    │    │  │ • Agent Runner      │  │    │   Tools         │
│ • SSE Client   │    │  │ • Streaming Events  │  │    │ • Tool Calling  │
└─────────────────┘    │  └─────────────────────┘  │    │                 │
                       │            │              │    └─────────────────┘
                       │            ▼              │
                       │  ┌─────────────────────┐  │
                       │  │   Memory Systems    │  │
                       │  │                     │  │
                       │  │ ┌──────┬──────────┐ │  │
                       │  │ │SQLite│Markdown  │ │  │
                       │  │ │  DB  │  Files   │ │  │
                       │  │ │(Conv)│(Projects)│ │  │
                       │  │ └──────┴──────────┘ │  │
                       │  └─────────────────────┘  │
                       └──────────────────────────┘
                                     │
                                     ▼
                              ┌──────────────┐
                              │   Git Repo   │
                              │ Version Ctrl │
                              └──────────────┘
```

## Repository Structure

- `app/` - FastAPI backend
  - `main.py` - FastAPI application with API endpoints and streaming handlers
  - `openai_agents_runner.py` - OpenAI Agents SDK implementation with tools
  - `langgraph_runner.py` - Legacy LangGraph (fallback compatibility)
  - `memory/` - Project markdown files + SQLite conversations DB
- `web/` - Next.js frontend source
  - Static export configuration (`output: "export"`)
  - Built files served by FastAPI as static assets
- `prompts/` - System prompts (`conversational_nai_agent.md`)
- `tests/` - Test files

## API Endpoints

- `GET /` - Serve Next.js frontend
- `POST /projects` - Create new project with slug and markdown file
- `GET /projects` - List all project slugs
- `POST /projects/{slug}/chat` - Stream chat responses via SSE
- `GET /projects/{slug}/file` - Serve raw markdown content

## Memory System

**Dual Memory Architecture:**
- **SQLiteSession**: Persistent conversation history with automatic memory management
- **Markdown Files**: Human-readable project documents in `app/memory/{slug}.md`
- **Version Control**: All project documents tracked with Git
- **Migration**: Automatic migration from legacy LangGraph system

## Common Development Commands

```bash
# Backend development (OpenAI Agents SDK)
USE_OPENAI_AGENTS=true make backend

# Backend development (Legacy LangGraph)
make backend

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

# Migration (LangGraph to OpenAI Agents)
USE_OPENAI_AGENTS=true python migrate_to_openai_agents.py

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
DEFAULT_MODEL=gpt-4o-mini  # Recommended for stability

# Agent System Selection
USE_OPENAI_AGENTS=true    # Enable OpenAI Agents SDK (recommended)

# Observability
LANGCHAIN_TRACING_V2=true
LANGCHAIN_ENDPOINT=https://api.smith.langchain.com
LANGCHAIN_API_KEY=<key>
```

## Key Design Decisions

- **Markdown Memory**: Human-readable, version-controlled project state
- **Static Frontend**: Simplified deployment, better caching
- **Single Container**: Reduced complexity, easier development
- **Streaming Chat**: Real-time user experience via SSE with tool execution visibility
- **Model Switching**: Runtime LLM selection for testing
- **Dual Memory**: SQLiteSession for conversation persistence + Markdown for project documents
- **Migration Strategy**: Backward-compatible transition from LangGraph to OpenAI Agents SDK

## Migration Status & Known Issues

### Current Migration State

The project is **migrating from LangGraph to OpenAI Agents SDK** to address fundamental issues with the current system.

### Original Issues (LangGraph System)

1. **Document Update Behavior**
   - **Problem**: When users request document updates (e.g., "add React to Tech Stack"), new information replaces existing content instead of appending to it
   - **Impact**: Users lose existing project information when making updates
   - **LangGraph Status**: This is the core issue we're trying to fix with migration

2. **Conversation Memory Issues**
   - **Problem**: Agent inconsistently references previous messages or maintains conversation context
   - **Impact**: Agent doesn't remember what was discussed earlier in conversations
   - **LangGraph Status**: Persistent issue with current memory implementation

3. **Tool Execution Visibility**
   - **Problem**: Users don't see clear feedback when tools are executing
   - **Impact**: Users unsure if their document update requests are being processed
   - **LangGraph Status**: Limited tool execution transparency

### Migration Progress (OpenAI Agents SDK)

**Goal**: Fix these fundamental issues by implementing:
- Proper document update logic that appends instead of replaces
- Reliable conversation memory with SQLiteSession
- Clear tool execution feedback with streaming indicators

**Current Status**: Migration **PARTIALLY SUCCESSFUL**
- Document updates still replace instead of append *(UNRESOLVED)*
- **Conversation memory WORKING** ✅ - SQLiteSession properly stores and retrieves conversation history
- Tool execution has some improvements but remains inconsistent

### System Selection

- **Current Default**: LangGraph system (has original issues)
- **Migration Path**: Set `USE_OPENAI_AGENTS=true` to use OpenAI Agents SDK
- **Memory Status**: OpenAI Agents SDK successfully fixed conversation memory - messages are properly stored in SQLiteSession database

### For Developers

To understand the current migration state:
1. Test LangGraph system - observe document replacement and memory issues
2. Test OpenAI Agents SDK - **conversation memory now works correctly** ✅
3. Check actual markdown file content after document updates 
4. Test conversation memory - **OpenAI agent properly remembers previous messages in SQLiteSession**
5. Monitor streaming responses for tool execution indicators
6. Verify memory persistence by checking `app/memory/conversations.db`