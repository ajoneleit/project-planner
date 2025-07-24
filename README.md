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
project-planner/
├── app/
│   ├── __init__.py
│   ├── main.py              # FastAPI application
│   ├── langgraph_runner.py  # LangGraph workflow + memory
│   └── memory/              # Project markdown files
│       ├── index.json       # Project index
│       └── *.md             # Individual project files
├── web/                     # Next.js frontend
│   ├── src/
│   │   ├── app/             # Next.js App Router
│   │   │   ├── p/[slug]/    # Dynamic project pages
│   │   │   └── layout.tsx
│   │   ├── components/      # React components
│   │   │   ├── ui/          # shadcn/ui components
│   │   │   └── providers/   # React Query provider
│   │   └── lib/
│   ├── package.json
│   └── next.config.ts
├── prompts/
│   └── project_planner.md   # System prompts
├── tests/
├── Dockerfile               # Multi-stage build (Node.js + Python)
├── Makefile                 # Build commands
├── pyproject.toml           # Poetry configuration
├── requirements.txt         # Pip dependencies
├── .env.example
└── README.md
```

## Development Setup

### Prerequisites

- Python 3.11+
- Node.js 20+
- Poetry (recommended) OR pip for Python dependency management

### Installation

1. **Clone and setup environment**:
   ```bash
   git clone <repository-url>
   cd project-planner
   cp .env.example .env
   # Edit .env with your OpenAI API key
   ```

2. **Backend setup** (choose one):

   **Option A: Using Poetry (recommended)**:
   ```bash
   poetry install
   ```

   **Option B: Using pip**:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   pip install -r requirements.txt
   ```

3. **Frontend setup**:
   ```bash
   cd web
   npm install
   cd ..
   ```

### Running the Application

#### Development Mode

**Using Make (recommended)**:
```bash
make dev
```

**Or manually**:
1. **Start the backend**:
   ```bash
   export PATH="$HOME/.local/bin:$PATH"
   poetry run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
   ```

2. **Access the application**:
   - Application: http://localhost:8000
   - API Docs: http://localhost:8000/docs
   - Health Check: http://localhost:8000/health

*Note: The frontend is served by FastAPI as static files, not as a separate dev server.*

#### Production Mode

**Using Make**:
```bash
make build    # Build frontend static files
make docker   # Build Docker image
```

**Or manually**:
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
- `POST /projects` - Create new project
- `GET /projects` - List all projects
- `POST /projects/{slug}/chat` - Stream chat responses (SSE)
- `GET /projects/{slug}/file` - Get project markdown file
- `GET /health` - Health check

## Memory System

Each project is stored as a markdown file in `app/memory/`:
- One `.md` file per project (named by slug)
- Append-only conversation history
- Version controlled with Git
- Structured format: metadata + Q&A pairs

## Testing

```bash
# Using Make
make test

# Or manually
poetry run pytest tests/ -v

# Frontend tests (when implemented)
cd web && npm test
```

## Deployment

### AWS App Runner (Recommended)

The application is designed for deployment on AWS App Runner using a multi-stage Docker build:

1. **Build and push Docker image to ECR**:
   ```bash
   # Login to ECR
   aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin <account>.dkr.ecr.us-east-1.amazonaws.com
   
   # Build and tag image
   docker build -t planner-bot .
   docker tag planner-bot:latest <account>.dkr.ecr.us-east-1.amazonaws.com/planner-bot:latest
   
   # Push to ECR
   docker push <account>.dkr.ecr.us-east-1.amazonaws.com/planner-bot:latest
   ```

2. **Create App Runner service** (see `aws-setup.md` for detailed instructions)
3. **Configure environment variables** in App Runner console
4. **Set up observability** with LangSmith and CloudWatch

### Docker Compose (Development)

```bash
# Run locally with Docker
docker build -t planner-bot .
docker run -p 8000:8000 --env-file .env planner-bot
```

### Manual Deployment

```bash
# Install dependencies
poetry install
cd web && npm install && cd ..

# Build frontend
cd web && npm run build && cd ..

# Start production server
poetry run uvicorn app.main:app --host 0.0.0.0 --port 8000
```

## Environment Variables

See `.env.example` for all configuration options. Key variables:

- `OPENAI_API_KEY` - Required for LLM functionality
- `DEFAULT_MODEL` - LLM model to use (gpt-4o-mini, o3)
- `LANGCHAIN_TRACING_V2` - Enable LangSmith tracing
- `ENVIRONMENT` - development/production

## Development Status

**Core Implementation Complete** ✅:
- FastAPI backend with streaming chat endpoints
- LangGraph workflow integration
- Next.js frontend with chat interface
- Markdown-based memory system
- Docker multi-stage build
- AWS App Runner deployment ready
- React Query for state management
- shadcn/ui component library

**Features**:
- ✅ Project creation and management
- ✅ Real-time chat with streaming responses (SSE)
- ✅ Markdown memory persistence
- ✅ Model switching (o3/gpt-4o-mini)
- ✅ Responsive UI with project sidebar
- ✅ Health checks and observability hooks
- ✅ Static file serving via FastAPI

## Contributing

1. Follow the existing code structure
2. Add tests for new functionality
3. Update documentation
4. Follow Python and TypeScript best practices