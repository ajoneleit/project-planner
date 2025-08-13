# Project Planner Bot

AI-powered project planning bot with markdown memory and conversational interface.

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
make backend    # Terminal 1: Backend (localhost:8000)
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

- **Backend**: FastAPI + LangGraph + OpenAI o3/gpt-4o-mini
- **Frontend**: Next.js 14 + shadcn/ui + Tailwind CSS
- **Memory**: Markdown files (version-controlled project state)
- **Deployment**: AWS App Runner (single container)
- **Security**: Comprehensive input validation and sanitization

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

## Features ✅

- **Project Management**: Create, archive, delete projects
- **Real-time Chat**: Streaming responses via Server-Sent Events
- **Model Switching**: Runtime selection between o3 and gpt-4o-mini
- **Memory Persistence**: Markdown files for human-readable project state
- **Security**: Comprehensive input validation and API key protection
- **Production Ready**: AWS App Runner deployment with auto-scaling

## Documentation

- **📚 [Complete Documentation](PROJECT_DOCUMENTATION.md)** - Comprehensive guide
- **🚀 [Deployment Guide](DEPLOYMENT.md)** - AWS App Runner deployment
- **🔧 [Claude Integration](CLAUDE.md)** - Claude Code assistant guidance
- **📝 [System Prompts](PROMPTS.md)** - Prompt management guide

## Development

```bash
# Development mode
make dev

# Run tests
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
| `/health` | GET | System health and configuration |
| `/api/projects` | GET/POST | List/Create projects |
| `/api/projects/{slug}/chat` | POST | Streaming chat (SSE) |
| `/api/projects/{slug}/file` | GET | Project markdown content |

## Environment Variables

```env
# Required
OPENAI_API_KEY=your_openai_api_key
DEFAULT_MODEL=gpt-4o-mini

# Optional
LANGCHAIN_TRACING_V2=true
LANGCHAIN_API_KEY=your_langsmith_key
ENVIRONMENT=development
```

## Production Status

**🟢 Production Ready** - All critical security fixes implemented:
- ✅ API key security and sanitization
- ✅ CORS configuration and validation  
- ✅ Input validation and DoS protection
- ✅ Exception handling and error recovery
- ✅ Memory management and resource cleanup
- ✅ Agent architecture consolidation

## License

MIT License - see LICENSE file for details.

---

**For detailed documentation, deployment guides, and troubleshooting, see [PROJECT_DOCUMENTATION.md](PROJECT_DOCUMENTATION.md)**