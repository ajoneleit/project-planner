# Project Planner Bot - Complete Documentation

AI-powered project planning bot with markdown memory and conversational interface.

## Table of Contents

1. [Quick Start](#quick-start)
2. [Project Overview](#project-overview)
3. [Development Setup](#development-setup)
4. [API Reference](#api-reference)
5. [Deployment Guide](#deployment-guide)
6. [Security & Maintenance](#security--maintenance)
7. [Architecture & Design](#architecture--design)
8. [Troubleshooting](#troubleshooting)

---

## Quick Start

### Prerequisites
- Node.js 20+ and npm
- Python 3.11+
- Poetry (recommended)
- OpenAI API Key

### Installation & Setup
```bash
# 1. Install dependencies
make install-deps

# 2. Set environment variables
cp .env.example .env
# Edit .env with your API keys

# 3. Start development servers
make backend    # Terminal 1: Backend (http://localhost:8000)
make frontend   # Terminal 2: Frontend (http://localhost:3000)

# 4. Access the application
# Frontend: http://localhost:3000
# Backend API: http://localhost:8000
# Health Check: http://localhost:8000/health
```

### Quick Test
```bash
# Basic functionality test
python tests/test_simple.py

# API test
curl http://localhost:8000/health
```

---

## Project Overview

### Technology Stack

| Layer | Technology | Purpose |
|-------|------------|---------|
| **Runtime** | Python 3.11 + Node 20 | Multi-stage Docker build |
| **Backend** | FastAPI + OpenAI Agents SDK / LangGraph | API server with SSE streaming (migration in progress) |
| **LLM** | OpenAI o3 (fallback: gpt-4o-mini) | Switchable via ?model= parameter |
| **Memory** | Markdown files in `app/memory/*.md` | Version-controlled project state |
| **Frontend** | Next.js 14 + shadcn/ui + Tailwind | Static chat interface |
| **Deployment** | AWS App Runner | Single container, HTTPS, auto-scaling |
| **Observability** | LangSmith → OTLP → CloudWatch | Distributed tracing and logging |

### Architecture Diagram

```
┌─────────────────┐    ┌──────────────────────────────────┐    ┌─────────────────┐
│   Next.js UI   │◄──►│        FastAPI Backend           │◄──►│   OpenAI LLM    │
│  (Static SPA)  │    │  ┌─────────────┬─────────────┐    │    │ (o3/gpt-4o-mini)│
│                │    │  │ API Routes  │ Openai agent│    │    │  Switchable     │
│ • React Query  │    │  │ /projects   │ SDK         │    │    │                 │
│ • shadcn/ui    │    │  │ /chat       │ + Agents    │    │    │                 │
│ • SSE Client   │    │  │ /health     │             │    │    │                 │
└─────────────────┘    │  └─────────────┴─────────────┘    │    └─────────────────┘
                       │                │                  │
                       │  ┌─────────────▼─────────────┐    │
                       │  │     Memory System         │    │
                       │  │                           │    │
                       │  │ ┌──────────┬──────────┐   │    │
                       │  │ │ SQLite   │Markdown  │   │    │
                       │  │ │Database  │ Files    │   │    │
                       │  │ │(Sessions)│(Projects)│   │    │
                       │  │ └──────────┴──────────┘   │    │
                       │  └───────────────────────────┘    │
                       └──────────────────────────────────┘
                                     │
                                     ▼
                              ┌──────────────┐
                              │ Git Repo     │
                              │ Version      │
                              │ Control      │
                              └──────────────┘
```

**Key Components:**
- **Frontend**: React-based SPA with real-time chat via SSE
- **API Layer**: RESTful endpoints with streaming responses  
- **LangGraph**: Agent workflow system with conversation routing
- **Dual Memory**: SQLite for structured data, Markdown for human-readable content
- **LLM Integration**: Runtime model switching (o3 ↔ gpt-4o-mini)
- **Version Control**: Git-tracked project history

### Key Design Decisions
- **Markdown Memory**: Human-readable, version-controlled project state
- **Static Frontend**: Simplified deployment, better caching
- **Single Container**: Reduced complexity, easier development
- **Streaming Chat**: Real-time user experience via SSE
- **Model Switching**: Runtime LLM selection for testing

---

## Development Setup

### Repository Structure
```
project-planner/
├── app/                        # FastAPI backend
│   ├── main.py                 # FastAPI application with API endpoints
│   ├── langgraph_runner.py     # LangGraph workflow + memory management
│   ├── openai_agents_runner.py # OpenAI Agents SDK runner (migration system)
│   ├── user_registry.py       # User management system
│   ├── config/                 # Configuration files
│   │   └── feature_flags.json  # Feature flag settings
│   ├── core/                   # Core utilities
│   │   ├── config.py           # Core configuration
│   │   ├── conversation_id_manager.py # Conversation ID management
│   │   ├── cors_config.py      # CORS configuration
│   │   ├── data_validator.py   # Data validation utilities
│   │   ├── feature_flags.py    # Feature flag system
│   │   ├── logging_config.py   # Secure logging framework
│   │   ├── memory_compatibility.py # Compatibility wrappers
│   │   ├── memory_unified.py   # Unified memory system
│   │   ├── migration_logging.py # Migration logging utilities
│   │   ├── security.py         # Security utilities & sanitization
│   │   └── validation.py       # Input validation
│   └── memory/                 # Project markdown files & databases
│       ├── *.md                # Individual project documents
│       ├── conversations.db*   # SQLite conversation database
│       ├── unified.db*         # Unified memory database
│       └── index.json          # Project registry
├── web/                        # Next.js frontend source
│   ├── src/
│   │   ├── app/                # Next.js App Router
│   │   ├── components/         # React components
│   │   │   ├── ui/             # shadcn/ui components
│   │   │   └── providers/      # React Query provider
│   │   ├── contexts/           # React contexts
│   │   ├── hooks/              # React hooks
│   │   ├── lib/                # Utility libraries
│   │   ├── types/              # TypeScript types
│   │   └── utils/              # Utility functions
│   ├── public/                 # Static assets
│   ├── next.config.ts          # Static export configuration
│   └── package.json            # Frontend dependencies
├── prompts/                    # System prompts
│   ├── project_planner.md      # Main system prompt
│   ├── conversational_nai_agent.md # Conversational agent prompt
│   └── info_agent.md           # Info agent prompt
├── tests/                      # Test files
├── scripts/                    # Utility scripts
├── logs/                       # Application logs
├── migration_backups/          # Database migration backups
├── cleanup_reports/            # System cleanup reports
├── validation_reports/         # System validation reports
├── Dockerfile                  # Multi-stage build (Node.js + Python)
├── deploy-backend.sh           # AWS deployment script
├── Makefile                    # Build commands
├── pyproject.toml              # Poetry configuration
├── requirements.txt            # Pip dependencies
├── CLAUDE.md                   # Claude Code assistant guidance
├── PROJECT_DOCUMENTATION.md   # This comprehensive documentation
└── README.md                   # Project overview and quick start
```

### Development Commands

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

### Environment Variables

```bash
# LLM Configuration
OPENAI_API_KEY=<key>
DEFAULT_MODEL=o3

# Observability
LANGCHAIN_TRACING_V2=true
LANGCHAIN_ENDPOINT=https://api.smith.langchain.com
LANGCHAIN_API_KEY=<key>

# Development
ENVIRONMENT=development
LOG_LEVEL=INFO
CORS_ORIGINS=http://localhost:3000,http://localhost:3001
```

---

## API Reference

### Core Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | Serve Next.js frontend |
| `/health` | GET | Health check with system info |
| `/api/projects` | GET | List all projects |
| `/api/projects` | POST | Create new project |
| `/api/projects/{slug}/chat` | POST | Chat with project (streaming SSE) |
| `/api/projects/{slug}/file` | GET | Get project markdown content |
| `/api/projects/{slug}/archive` | PUT | Archive a project |
| `/api/projects/{slug}/unarchive` | PUT | Unarchive a project |
| `/api/projects/{slug}` | DELETE | Delete project permanently |

### API Usage Examples

#### Health Check
```bash
curl http://localhost:8000/health
```

#### Create Project
```bash
curl -X POST "http://localhost:8000/api/projects" \
  -H "Content-Type: application/json" \
  -d '{"name": "My Test Project", "description": "A test project"}'
```

#### Chat with Project
```bash
curl -X POST "http://localhost:8000/api/projects/my-test-project/chat" \
  -H "Content-Type: application/json" \
  -d '{"message": "Help me plan this project", "model": "gpt-4o-mini"}'
```

### Memory System
- One `.md` file per project (named by slug) in `app/memory/`
- Append-only conversation history
- Version controlled with Git
- Structured format: metadata + Q&A pairs

---

## Deployment Guide

### Automated Deployment (Recommended)

```bash
# Deploy to production
./deploy-backend.sh

# Preview what will be deployed
./deploy-backend.sh --dry-run

# Deploy with verbose output
./deploy-backend.sh --verbose
```

### AWS App Runner Setup

#### Prerequisites
1. **Docker installed and running**
   ```bash
   docker --version
   ```

2. **AWS CLI configured**
   ```bash
   aws --version
   aws sts get-caller-identity --profile 348204830428_SoftwareEngineering
   ```

3. **ECR repository access**
   - Repository: `348204830428.dkr.ecr.us-east-1.amazonaws.com/planner-bot`

4. **App Runner service created**
   - Service ARN: `arn:aws:apprunner:us-east-1:348204830428:service/project-planner/ca84d56e96234bb5b625287285c78cc9`

#### Manual Deployment Steps

1. **Build and push Docker image**:
   ```bash
   # Login to ECR
   aws ecr get-login-password --region us-east-1 --profile 348204830428_SoftwareEngineering | docker login --username AWS --password-stdin 348204830428.dkr.ecr.us-east-1.amazonaws.com
   
   # Build and tag image
   docker build -t planner-bot .
   docker tag planner-bot:latest 348204830428.dkr.ecr.us-east-1.amazonaws.com/planner-bot:latest
   
   # Push to ECR
   docker push 348204830428.dkr.ecr.us-east-1.amazonaws.com/planner-bot:latest
   
   # Deploy to App Runner
   aws apprunner start-deployment --service-arn arn:aws:apprunner:us-east-1:348204830428:service/project-planner/ca84d56e96234bb5b625287285c78cc9 --region us-east-1 --profile 348204830428_SoftwareEngineering
   ```

2. **Monitor deployment**:
   - AWS Console: https://console.aws.amazon.com/apprunner/
   - Health Check: https://fbm26vyfbw.us-east-1.awsapprunner.com/health
   - API Docs: https://fbm26vyfbw.us-east-1.awsapprunner.com/docs

### Environment Configuration

**Required Environment Variables:**
- `OPENAI_API_KEY` - From AWS Secrets Manager
- `LANGCHAIN_API_KEY` - From AWS Secrets Manager  
- `ENVIRONMENT=production`
- `USE_OPENAI_AGENTS=true`

**Optional:**
- `DEFAULT_MODEL=gpt-4o-mini`
- `LANGCHAIN_TRACING_V2=true`
- `LOG_LEVEL=INFO`

**AWS Secrets Manager Format:**
```json
{
  "OPENAI_API_KEY": "sk-proj-...",
  "LANGCHAIN_API_KEY": "lsv2_sk_..."
}
```

---

## Security & Maintenance

### Security Fixes Implemented

#### 1. API Key Security Exposure - FIXED
- **Issue**: API keys logged in plain text
- **Fix**: Comprehensive sanitization in `app/core/security.py`
- **Coverage**: All sensitive data automatically sanitized before logging

#### 2. CORS Security Misconfiguration - FIXED  
- **Issue**: Insecure wildcard CORS with credentials
- **Fix**: Environment-aware CORS in `app/core/cors_config.py`
- **Security**: Production restricts to specific domains

#### 3. Input Validation - COMPREHENSIVE COVERAGE
- **Coverage**: All API entry points with Pydantic validation
- **Protection**: Path traversal, DoS, injection prevention
- **Implementation**: Enhanced models with custom validators

#### 4. Exception Handling - CRITICAL PATHS REFACTORED
- **Completed**: 50+ critical exception handlers improved
- **Pattern**: Specific error types instead of generic `Exception`
- **Files**: `main.py` (100%), `langgraph_runner.py` (critical paths), memory systems

### System Improvements 

#### Memory Management
- **Memory Leaks**: Fixed with automatic cleanup system
- **Connection Pooling**: Complete coverage implemented
- **Resource Management**: Production-ready with lifecycle management

#### Agent Architecture
- **Consolidated**: From multiple agents to 3 core agents
- **Structure**: ConversationAgent, ProjectAgent, IntentRouter
- **Benefits**: Reduced complexity, improved maintainability

### Production Readiness Status

| Component | Status | Notes |
|-----------|--------|-------|
| **Resource Management** |  PRODUCTION READY | Automatic cleanup, connection pooling |
| **Error Handling** |  CRITICAL PATHS READY | Specific error types, proper recovery |
| **Input Security** |  PRODUCTION READY | Comprehensive validation coverage |
| **Memory System** | PRODUCTION READY | Agents can reference conversation history |
| **Agent Architecture** |  PRODUCTION READY | Consolidated, efficient design |

---

## Architecture & Design

### Core Components

#### 1. Unified Memory System
- **SQLite Database**: Structured data (conversations, metadata, sessions)
- **File System**: Human-readable documents (markdown projects)
- **Compatibility Wrappers**: Zero breaking changes to existing code
- **Async-Safe Operations**: ThreadPoolExecutor pattern

#### 2. Agent System
- **ConversationAgent**: Handles chat interactions and context
- **ProjectAgent**: Manages project-specific operations
- **IntentRouter**: Routes requests to appropriate agents

#### 3. Security Framework
- **Automatic Sanitization**: All sensitive data redacted in logs
- **Input Validation**: Comprehensive protection against attacks
- **CORS Protection**: Environment-aware security policies

#### 4. Streaming Architecture
- **Server-Sent Events (SSE)**: Real-time chat responses
- **Proper Error Recovery**: Graceful degradation on failures
- **Model Switching**: Runtime LLM selection capability

---

## Troubleshooting

### Common Issues & Solutions

#### CORS Issues
If you see "Failed to fetch" or CORS errors:
1. **Check backend is running**: Visit http://localhost:8000/health
2. **Verify CORS configuration**: Check health endpoint shows your origin in `cors_origins`
3. **Port conflicts**: Ensure frontend on port 3000, backend on port 8000
4. **Network issues**: Try using 127.0.0.1 instead of localhost

#### Connection Issues
1. **Test API connectivity:**
   ```bash
   curl http://localhost:8000/health
   ```

2. **Check processes:**
   ```bash
   # Check what's running on port 8000
   lsof -i :8000
   
   # Check what's running on port 3000  
   lsof -i :3000
   ```

3. **Reset everything:**
   ```bash
   make clean
   make install-deps
   make backend &
   make frontend
   ```

#### Import Errors
**"ModuleNotFoundError: No module named 'app'"**
- Make sure you're running from the project root directory
- Use `poetry run` if you installed with Poetry
- Activate your virtual environment if using pip

**"ModuleNotFoundError: No module named 'langgraph'"**
- Dependencies not installed: run `poetry install` or `pip install -r requirements.txt`
- Wrong Python environment: use `poetry run python` or activate your venv

#### Docker Issues
1. **Test Docker build:**
   ```bash
   make docker-test
   ```

2. **Check Docker logs:**
   ```bash
   docker logs planner-bot-container-name
   ```

3. **Reset Docker:**
   ```bash
   docker system prune -f
   make docker-build
   ```

### Verification Commands

**Check Poetry environment:**
```bash
poetry env info
poetry show  # List installed packages
```

**Check basic functionality:**
```bash
poetry run python -c "from app.main import app; print(' FastAPI app loads')"
```

**Test imports:**
```bash
poetry run python -c "import app.main; import app.langgraph_runner; print(' All imports successful')"
```

### Development Workflow

1. **Start Development Environment**
   ```bash
   # Terminal 1: Backend
   make dev
   
   # Terminal 2: Frontend (optional)
   cd web && npm run dev
   
   # Terminal 3: Tests (optional)
   pytest tests/ -v
   ```

2. **Make Changes**
   - Edit files in `app/` for backend changes
   - Edit files in `web/src/` for frontend changes
   - Add tests in `tests/`

3. **Test Changes**
   ```bash
   # Run specific tests
   pytest tests/test_core.py -v
   
   # Test API endpoints
   curl http://localhost:8000/health
   ```

4. **Build for Production**
   ```bash
   make build
   make docker
   ```

---

## Development Status

**Core Implementation Complete** :
- FastAPI backend with streaming chat endpoints
- LangGraph / Openai Agents SDK workflow integration
- Next.js frontend with chat interface
- Markdown-based memory system
- Docker multi-stage build
- AWS App Runner deployment ready
- React Query for state management
- shadcn/ui component library

**Security & Production Readiness** :
- Comprehensive security fixes implemented
- Input validation and sanitization
- Proper error handling and recovery
- Resource management and cleanup
- Agent architecture consolidation

**Features**:
-  Project creation and management
-  Real-time chat with streaming responses (SSE)
-  Markdown project file memory 
-  Responsive UI with project sidebar
-  Health checks and observability hooks
-  Static file serving via FastAPI
-  User management and attribution
-  Project archiving and lifecycle management

---

## Migration Status & Known Issues

### OpenAI Agents SDK Migration

**Status**: **MIGRATION PARTIALLY SUCCESSFUL** - LangGraph to OpenAI Agents SDK transition with conversation memory fixed

The project is migrating from LangGraph to OpenAI Agents SDK to address fundamental problems with document updates, conversation memory, and tool execution feedback. **CONVERSATION MEMORY NOW WORKING** ✅ - SQLiteSession properly stores and retrieves chat history.

#### Current System Selection
```bash
# Use OpenAI Agents SDK (conversation memory fixed)
USE_OPENAI_AGENTS=true make backend

# Use LangGraph (current system with original issues)
make backend
```

#### Issues Being Addressed by Migration

**Problems with LangGraph (Current System):**

1. **Document Update Behavior**
   - **Problem**: Document updates replace existing content instead of appending
   - **Location**: LangGraph tool execution logic
   - **Migration Result**: **UNRESOLVED** - OpenAI Agents SDK still has issues with content replacement

2. **Conversation Memory Persistence** 
   - **Problem**: Agent inconsistently references previous conversation context
   - **Location**: LangGraph memory management
   - **Migration Result**: **RESOLVED** ✅ - OpenAI Agents SDK with SQLiteSession now properly stores and retrieves chat history and previous messages

3. **Tool Execution Visibility**
   - **Problem**: Users don't see clear feedback when tools execute
   - **Location**: LangGraph streaming implementation
   - **Migration Result**: **PARTIAL** - Some improvement in visibility but still inconsistent

#### TODO
1. **Inconsistent Document Behavior**
   - The info agent is supposed to extract all important information from the conversation to automatically add to project document
   - Doesn't always extract all info or add all info that its told to
   - Formatting is inconsistent, somnetimes just adds all info to bottom of document rather than updating correct areas by category unless specifically told

2. **NAI helper** 
   - The conversation agent should follow the conversational_nai_agent.md prompt which details an introduction and interview like process to gain project information from the user
   - Agent doesn't go through introduction setup or ask sets of questions like detailed in the prompt

3. **User permissions**
   - Add logins and ability to create public or private projects
   - Set up project permissions

#### For Developers
- Test both systems with `USE_OPENAI_AGENTS=true/false`
- **Fixed**: ✅ **Conversation memory now working** - OpenAI Agents SDK properly remembers previous messages via SQLiteSession. Document updates still have replacement issues.
- Verify actual markdown file content after document updates - issues persist in both systems
- Monitor streaming responses for tool execution indicators

---

**Last Updated**: January 2025  
**Version**: 2.1.0-beta  
**Status**: Migration Partially Successful - Conversation Memory Fixed ✅