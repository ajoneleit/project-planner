# Project Planner Bot

AI-powered project planning bot with markdown memory and conversational interface.

## Quick Start

### Prerequisites
- Node.js 20+ and npm
- Python 3.11+
- Poetry
- OpenAI API Key

### Development Setup

1. **Install dependencies**
   ```bash
   make install-deps
   ```

2. **Set environment variables**
   ```bash
   cp .env.example .env
   # Edit .env with your API keys
   ```

3. **Start development servers**
   ```bash
   # Terminal 1: Backend (http://localhost:8000)
   make backend

   # Terminal 2: Frontend (http://localhost:3000)  
   make frontend
   ```

4. **Access the application**
   - Frontend: http://localhost:3000
   - Backend API: http://localhost:8000
   - Health Check: http://localhost:8000/health

## Troubleshooting

### CORS Issues
If you see "Failed to fetch" or CORS errors:

1. **Check backend is running**: Visit http://localhost:8000/health
2. **Verify CORS configuration**: Check the health endpoint shows your origin in `cors_origins`
3. **Port conflicts**: Ensure frontend is on port 3000, backend on port 8000
4. **Network issues**: Try using 127.0.0.1 instead of localhost

### Connection Issues

1. **Test API connectivity:**
   ```bash
   node test-api-connectivity.js
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

### Docker Issues

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

## Environment Variables

**Required for development:**
```env
OPENAI_API_KEY=your_openai_api_key
DEFAULT_MODEL=gpt-4o-mini
LANGCHAIN_TRACING_V2=true
LANGCHAIN_API_KEY=your_langsmith_api_key
```

**Optional:**
```env
ENVIRONMENT=development
LOG_LEVEL=INFO
CORS_ORIGINS=http://localhost:3000,http://localhost:3001
```

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Health check with system info |
| `/api/projects` | GET | List all projects |
| `/api/projects` | POST | Create new project |
| `/api/projects/{slug}/chat` | POST | Chat with project (streaming) |
| `/api/projects/{slug}/file` | GET | Get project markdown |

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