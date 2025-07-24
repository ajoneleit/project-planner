# Usage Guide - Project Planner Bot

This guide shows you how to run and test the Project Planner Bot after installation.

## Quick Start

### 1. Install Dependencies

Choose your preferred method:

**Option A: Poetry (Recommended)**
```bash
export PATH="$HOME/.local/bin:$PATH"
poetry install
```

**Option B: pip**
```bash
pip install -r requirements.txt
```

### 2. Set Up Environment

```bash
cp .env.example .env
# Edit .env and add your OpenAI API key:
# OPENAI_API_KEY=your_openai_api_key_here
```

### 3. Run Tests

**Basic functionality test (no dependencies needed):**
```bash
python tests/test_simple.py
```

**With Poetry:**
```bash
poetry run python tests/test_simple.py
```

### 4. Start Development Server

**With Poetry:**
```bash
export PATH="$HOME/.local/bin:$PATH"
poetry run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

**With pip (if using virtual environment):**
```bash
source venv/bin/activate  # On Windows: venv\Scripts\activate
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

**Using Makefile:**
```bash
make dev
```

### 5. Test the API

Once the server is running, visit:
- **API Documentation**: http://localhost:8000/docs
- **Health Check**: http://localhost:8000/health

## API Endpoints

### Health Check
```bash
curl http://localhost:8000/health
```

### Create a Project
```bash
curl -X POST "http://localhost:8000/api/projects" \
  -H "Content-Type: application/json" \
  -d '{"name": "My Test Project", "description": "A test project"}'
```

### List Projects
```bash
curl http://localhost:8000/api/projects
```

### Chat with a Project (requires OpenAI API key)
```bash
curl -X POST "http://localhost:8000/api/projects/my-test-project/chat" \
  -H "Content-Type: application/json" \
  -d '{"message": "Help me plan this project", "model": "gpt-4o-mini"}'
```

### Get Project File
```bash
curl http://localhost:8000/api/projects/my-test-project/file
```

## Frontend Development

### Install Frontend Dependencies
```bash
cd web
npm install
```

### Run Frontend Development Server
```bash
cd web
npm run dev
```

### Build Frontend for Production
```bash
cd web
npm run build
```

## Testing

### Run All Tests
```bash
# With Poetry
make test
# OR
poetry run pytest tests/ -v

# Basic tests only
python tests/test_simple.py
```

### Run Specific Tests
```bash
poetry run pytest tests/test_core.py::test_markdown_memory_creation -v
```

## Docker

### Build Docker Image
```bash
make docker
# OR
docker build -t planner-bot .
```

### Run with Docker
```bash
docker run -p 8000:8000 --env-file .env planner-bot
```

## Troubleshooting

### Common Issues

**1. "ModuleNotFoundError: No module named 'app'"**
- Make sure you're running from the project root directory
- Use `poetry run` if you installed with Poetry
- Activate your virtual environment if using pip

**2. "ModuleNotFoundError: No module named 'langgraph'"**
- Dependencies not installed: run `poetry install` or `pip install -r requirements.txt`
- Wrong Python environment: use `poetry run python` or activate your venv

**3. "ImportError: cannot import name 'MessagesState'"**
- This has been fixed in the latest version
- Make sure you have the latest code: `git pull origin main`

**4. Tests failing**
- Check your Python version: requires Python 3.11+
- Ensure all dependencies are installed
- Run basic tests first: `python tests/test_simple.py`

### Verification Commands

**Check Poetry environment:**
```bash
poetry env info
poetry show  # List installed packages
```

**Check basic functionality:**
```bash
poetry run python -c "from app.langgraph_runner import MarkdownMemory; print('✅ Import successful')"
```

**Check API loading:**
```bash
poetry run python -c "from app.main import app; print('✅ FastAPI app loads')"
```

## Development Workflow

### 1. Start Development Environment
```bash
# Terminal 1: Backend
make dev

# Terminal 2: Frontend (optional)
cd web && npm run dev

# Terminal 3: Tests (optional)
poetry run pytest tests/ -v --watch
```

### 2. Make Changes
- Edit files in `app/` for backend changes
- Edit files in `web/src/` for frontend changes
- Add tests in `tests/`

### 3. Test Changes
```bash
# Run specific tests
poetry run pytest tests/test_core.py -v

# Test API endpoints
curl http://localhost:8000/health
```

### 4. Build for Production
```bash
make build
make docker
```

## Next Steps

1. **Add OpenAI API Key** to `.env` file for full functionality
2. **Frontend Development** - Build React components for chat interface
3. **Database Integration** - Optional: Replace file-based storage
4. **Authentication** - Add user management
5. **Deployment** - Deploy to AWS App Runner or similar platform

For more detailed information, see the README.md file.