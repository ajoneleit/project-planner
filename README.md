# Project Planner Bot

AI-powered project planning bot with markdown memory and conversational interface. Prompts users for information regarding new projects to flesh out details and create centralized document to collaborate with multiple people. 

**MIGRATION STATUS**: Currently transitioning from LangGraph to OpenAI Agents SDK. 

## Quick Start

### Prerequisites
- Python 3.11+ and Poetry
- Node.js 20+ and npm  
- OpenAI API Key

### Installation
```bash
# 1. Install dependencies
make install-deps

# 2. Set environment variables
cp .env.example .env
# Edit .env with your OpenAI API key

# 3. Start development servers
# Option A: Use LangGraph (default/stable)
make backend    # Terminal 1: Backend (localhost:8000)

# Option B: Use OpenAI Agents SDK (experimental)
USE_OPENAI_AGENTS=true make backend    # Terminal 1: Backend (localhost:8000)

make frontend   # Terminal 2: Frontend (localhost:3000)
```

### Quick Test
```bash
# Basic functionality
python tests/test_simple.py

# API health check
curl http://localhost:8000/health
```

## Technology Stack

**Current Implementation:**
- **Backend**: FastAPI with dual agent systems
  - **LangGraph**: Current system with known conversation/document issues (default)
  - **OpenAI Agents SDK**: Migration target attempting to fix LangGraph issues (experimental)
- **Frontend**: Next.js 14 + shadcn/ui + Tailwind CSS
- **Memory**: 
  - LangGraph: Markdown files + SQLite unified memory
  - OpenAI Agents SDK: SQLiteSession conversations + Markdown project files
- **LLM**: OpenAI gpt-4o-mini/o3 (runtime switchable)
- **Deployment**: AWS App Runner (single container)

## Architecture

**Dual System Architecture:**
```
┌─────────────────┐    ┌──────────────────────────────────┐    ┌─────────────────┐
│   Next.js UI   │◄──►│        FastAPI Backend           │◄──►│   OpenAI LLM    │
│  (Static SPA)  │    │                                  │    │ (gpt-4o/o3)     │
│                │    │  ┌─────────────┬─────────────┐    │    │                 │
│ • React Query  │    │  │ LangGraph   │OpenAI Agents│    │    │                 │
│ • shadcn/ui    │    │  │ (Stable)    │SDK (Exp.)   │    │    │                 │
│ • SSE Client   │    │  │ Default     │USE_OPENAI_  │    │    │                 │
└─────────────────┘    │  │             │AGENTS=true  │    │    └─────────────────┘
                       │  └─────────────┴─────────────┘    │
                       │                │                  │
                       │  ┌─────────────▼─────────────┐    │
                       │  │     Memory Systems        │    │
                       │  │                           │    │
                       │  │ LangGraph: Unified Memory │    │
                       │  │ OpenAI: SQLite + MD Files │    │
                       │  └───────────────────────────┘    │
                       └──────────────────────────────────┘
```

## Current Status

**DEVELOPMENT STATUS: MIGRATION IN PROGRESS** - Attempting to fix LangGraph issues by migrating to OpenAI Agents SDK.

### Original Issues (LangGraph System)
1. **Document Updates**: Content replaces existing information instead of appending
2. **Memory Persistence**: Inconsistent conversation history between requests, only uses project document for memory not conversation history
3. **Tool Execution**: Poor visibility into what operations are happening

### Migration Status
- **LangGraph (Current Default)**: Has the original issues but system is stable
- **OpenAI Agents SDK (Migration Attempt)**: Implementation complete but **issues persist** - conversation agent still can't remember chat history or previous messages, severely limiting usability

### System Selection
```bash
# Use current LangGraph system (has original issues but stable)
make backend

# Use OpenAI Agents SDK migration (attempted fix but issues persist)
USE_OPENAI_AGENTS=true make backend
```

## Features

**Current Features (Both Systems):**
- Project management (create, archive, delete)
- Real-time streaming chat responses
- Markdown project documentation view, automatically extracting and saving information from chat

**Known Issues (LangGraph - Current Default):**
- Document updates replace content instead of appending
- Can't refrence previous messages, always defaults to project document for memory when it should use both
- Limited tool execution feedback

**Migration Results (OpenAI Agents SDK):**
- **Document Updates**: Still has issues with content replacement
- **Conversation Memory**: Agent still cannot remember chat history or previous messages, severely limiting usability  
- **Tool Execution**: Some improvement in visibility but inconsistent

## Documentation

- [Complete Documentation](PROJECT_DOCUMENTATION.md) - Comprehensive guide
- [Deployment Guide](DEPLOYMENT.md) - AWS App Runner deployment
- [Claude Integration](CLAUDE.md) - Claude Code assistant guidance
- [System Prompts](PROMPTS.md) - Prompt management guide

## Development

```bash
# Stable development (LangGraph)
make backend

# Experimental development (OpenAI Agents SDK)
USE_OPENAI_AGENTS=true make backend

# Frontend development
cd web && npm run dev

# Testing
make test

# Build for production
make build
make docker

# Deploy to AWS
./deploy-backend.sh
```

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | System health and agent system status |
| `/api/projects` | GET/POST | List/Create projects |
| `/api/projects/{slug}/chat` | POST | Streaming chat (SSE) |
| `/api/projects/{slug}/file` | GET | Project markdown content |

## Environment Variables

```env
# Required
OPENAI_API_KEY=your_openai_api_key
DEFAULT_MODEL=gpt-4o-mini

# Agent System Selection
USE_OPENAI_AGENTS=false  # true for OpenAI Agents SDK, false for LangGraph

# LangChain/LangGraph (legacy system)
LANGCHAIN_TRACING_V2=true
LANGCHAIN_API_KEY=your_langsmith_key
LANGCHAIN_ENDPOINT=https://api.smith.langchain.com

# Optional
ENVIRONMENT=development
LOG_LEVEL=INFO
CORS_ORIGINS=http://localhost:3000,http://localhost:3001
```

## Dependencies

**Core Dependencies:**
```toml
# Agent Systems
langgraph = "^0.2.0"           # Legacy stable system
openai-agents = "^0.2.6"       # New experimental system

# LangChain Stack (for LangGraph)
langchain-openai = "^0.2.0"
langchain-core = "^0.3.66"
langchain = "^0.3.26"

# FastAPI & Core
fastapi = "^0.115.0"
uvicorn = "^0.24.0"
aiosqlite = "^0.21.0"
```

## Production Readiness

**CURRENT STATUS: NOT PRODUCTION READY**

**Blocking Issues:**
- OpenAI Agents SDK migration incomplete with critical functionality issues
- Document updates by replacing information in each section rather than appending new information 
- Converstaion agent is unable to reference previous messages which limits usability
- Tool execution feedback is inconsistent

**Security & Infrastructure (Ready):**
- API key security and sanitization
- CORS configuration and validation  
- Input validation and DoS protection
- Exception handling and error recovery
- Memory management and resource cleanup

## Migration from LangChain to OpenAI Agents SDK

**Background:** The LangGraph system has persistent issues with document updates, conversation memory, and tool execution feedback. We attempted to migrate to OpenAI Agents SDK to address these fundamental problems.

**Issues with LangGraph System:**
- **Document Updates**: Content replaces existing information instead of appending
- **Memory Problems**: Agent can't reference chat history or previous messages
- **Tool Feedback**: Limited visibility into what operations are executing

**Migration Attempt Results (OpenAI Agents SDK):**
- **Document Updates**: **UNRESOLVED** - Still has issues where new content replaces old content on document rather than appending
- **Conversation Memory**: **UNRESOLVED** - Agent still cannot remember chat history or previous messages, severely limiting usability
- **Tool Execution**: **PARTIAL** - Some improvement in visibility but inconsistent

**Current Status:**
- **LangGraph**: Default system with known issues but stable
- **OpenAI Agents SDK**: Migration attempted but failed to resolve core issues, functionality is the same as before

## How to Help Debug

```bash
# 1. Test LangGraph system (current system with known issues)
make backend
# Try document updates, observe replacement behavior instead of appending
# Test conversation memory, observe inconsistencies

# 2. Test OpenAI Agents SDK (migration attempt - issues persist)
USE_OPENAI_AGENTS=true make backend
# Test document updates - still has replacement issues
# Test conversation memory - agent CANNOT remember previous messages

# 3. Check actual file contents after operations
ls -la app/memory/
cat app/memory/your-project.md

# 4. Monitor conversation memory
# Make multiple requests, check if agent remembers context

# 5. Watch streaming responses
# Verify tool execution indicators appear: [Executing tool...] [Tool completed]
```

## License

MIT License - see LICENSE file for details.

---

**For detailed documentation, deployment guides, and troubleshooting, see [PROJECT_DOCUMENTATION.md](PROJECT_DOCUMENTATION.md)**