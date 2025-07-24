# Project Planner Bot

A conversational AI project planning bot that maintains project state in markdown files within the same Git repository. Built with FastAPI backend and Next.js frontend, deployed as a single containerized service.

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

## Technology Stack

- **Runtime**: Python 3.11 + Node 20
- **Backend**: FastAPI + LangGraph (SSE streaming)
- **LLM**: OpenAI o3 (fallback: gpt-4o-mini)
- **Memory**: Markdown files in `app/memory/`
- **Frontend**: Next.js 14 + shadcn/ui + Tailwind
- **Deployment**: AWS App Runner (Docker container)
- **Observability**: LangSmith → OTLP → CloudWatch

## Project Structure

```
planner-bot/
├── app/
│   ├── __init__.py
│   ├── main.py              # FastAPI application
│   ├── langgraph_runner.py  # LangGraph workflow + memory
│   └── memory/              # Project markdown files
├── web/                     # Next.js frontend
│   ├── src/
│   ├── components/
│   └── [Next.js files]
├── prompts/
│   └── project_planner.md   # System prompts
├── tests/
├── Dockerfile               # Multi-stage build
├── .env.example
└── README.md
```

## Development Setup

### Prerequisites

- Python 3.11+
- Node.js 20+
- Poetry (for Python dependency management)

### Installation

1. **Clone and setup environment**:
   ```bash
   git clone <repository-url>
   cd project-planner
   cp .env.example .env
   # Edit .env with your OpenAI API key
   ```

2. **Backend setup**:
   ```bash
   poetry install
   ```

3. **Frontend setup**:
   ```bash
   cd web
   npm install
   cd ..
   ```

### Running the Application

#### Development Mode

1. **Start the backend**:
   ```bash
   export PATH="$HOME/.local/bin:$PATH"
   poetry run uvicorn app.main:app --reload --port 8000
   ```

2. **Start the frontend** (in another terminal):
   ```bash
   cd web
   npm run dev
   ```

3. **Access the application**:
   - Frontend: http://localhost:3000
   - Backend API: http://localhost:8000
   - API Docs: http://localhost:8000/docs

#### Production Mode

1. **Build the frontend**:
   ```bash
   cd web
   npm run build
   cd ..
   ```

2. **Run with Docker**:
   ```bash
   docker build -t planner-bot .
   docker run -p 8000:8000 --env-file .env planner-bot
   ```

## API Endpoints

- `GET /` - Serve Next.js frontend
- `POST /api/projects` - Create new project
- `GET /api/projects` - List all projects
- `POST /api/projects/{slug}/chat` - Stream chat responses (SSE)
- `GET /api/projects/{slug}/file` - Get project markdown file
- `GET /api/health` - Health check

## Memory System

Each project is stored as a markdown file in `app/memory/`:
- One `.md` file per project (named by slug)
- Append-only conversation history
- Version controlled with Git
- Structured format: metadata + Q&A pairs

## Testing

```bash
# Run Python tests
poetry run pytest tests/

# Run frontend tests (when implemented)
cd web && npm test
```

## Deployment

The application is designed for deployment on AWS App Runner:

1. Build and push Docker image to ECR
2. Deploy to App Runner with auto-scaling
3. Configure environment variables
4. Set up observability with LangSmith and CloudWatch

## Environment Variables

See `.env.example` for all configuration options. Key variables:

- `OPENAI_API_KEY` - Required for LLM functionality
- `DEFAULT_MODEL` - LLM model to use (o3, gpt-4o-mini)
- `LANGCHAIN_TRACING_V2` - Enable LangSmith tracing
- `ENVIRONMENT` - development/production

## Development Status

This is Day 1 bootstrap. The foundation is set up with:
- ✅ Project structure
- ✅ Basic FastAPI endpoints (placeholders)
- ✅ Next.js frontend scaffolding
- ✅ Poetry dependency management
- ✅ Docker configuration
- ✅ Memory system architecture

**Next Steps (Days 2-7)**:
- Implement LangGraph workflows
- Build React components for chat interface
- Add SSE streaming endpoints
- Implement markdown memory operations
- Add authentication and project management
- Set up CI/CD pipeline
- Deploy to AWS App Runner

## Contributing

1. Follow the existing code structure
2. Add tests for new functionality
3. Update documentation
4. Follow Python and TypeScript best practices