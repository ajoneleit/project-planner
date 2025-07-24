System Architecture Plan
Overview
A conversational AI project planning bot that maintains project state in markdown files within the same Git repository. Built with FastAPI backend and Next.js frontend, deployed as a single containerized service on AWS App Runner.
Technology Stack
LayerTechnologyPurposeRuntimePython 3.11 + Node 20Multi-stage Docker buildBackendFastAPI + LangGraphAPI server with SSE streamingLLMOpenAI o3 (fallback: gpt-4o-mini)Switchable via ?model= parameterMemoryMarkdown files (app/memory/*.md)Version-controlled project stateFrontendNext.js 14 + shadcn/ui + TailwindStatic chat interfaceDeploymentAWS App RunnerSingle container, HTTPS, auto-scalingObservabilityLangSmith → OTLP → CloudWatchDistributed tracing and logging
System Architecture
Copy
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   Next.js UI    │◄──►│   FastAPI API    │◄──►│   OpenAI LLM    │
│  (Static SPA)   │    │   + LangGraph    │    │  (o3/gpt-4o)    │
└─────────────────┘    └──────────────────┘    └─────────────────┘
                              │
                              ▼
                       ┌──────────────┐
                       │  Markdown    │
                       │  Memory      │
                       │  (Git Repo)  │
                       └──────────────┘
Repository Structure
Copyplanner-bot/
├── app/
│   ├── main.py              # FastAPI application
│   ├── langgraph_runner.py  # LangGraph workflow + memory
│   └── memory/              # Project markdown files
├── web/                     # Next.js frontend source
│   ├── src/
│   ├── components/
│   └── next.config.mjs
├── prompts/
│   └── project_planner.md   # System prompts
├── tests/
├── Dockerfile               # Multi-stage build
├── .github/workflows/       # CI/CD
└── README.md
Core Components
Backend (app/)
FastAPI Server (main.py)

POST /projects - Create new project with slug and markdown file
GET /projects - List all project slugs
POST /projects/{slug}/chat - Stream chat responses via SSE
GET /projects/{slug}/file - Serve raw markdown content
Serves static frontend files from /

LangGraph Runner (langgraph_runner.py)

MarkdownMemory class with async file locking
make_graph(md_path, model) - Creates stateful conversation graph
Appends Q&A pairs to project markdown files

Frontend (web/)
Core Components

ProjectSidebar - Lists projects, highlights current
ChatWindow - Streaming chat interface with auto-scroll
MarkdownViewer - Displays current project file content
[slug] route - Dynamic project pages

Build Strategy

Next.js static export (output: "export")
Built files served by FastAPI as static assets
Single-page application with client-side routing

Memory System
Markdown Files (app/memory/)

One .md file per project (named by slug)
Append-only conversation history
Version controlled with Git
Structured format: metadata + Q&A pairs

Development Workflow
Day 1: Repository Bootstrap
bashCopy# Initialize project structure
git init planner-bot && cd planner-bot
poetry init  # Backend dependencies
npx create-next-app@latest web --ts --tailwind --app
cd web && npx shadcn-ui@latest init
Day 2: Core Backend

Implement MarkdownMemory with file locking
Build FastAPI endpoints
Create LangGraph conversation flow
Unit tests for core functionality

Day 3: Frontend MVP

Build React components
Implement chat streaming
Add project sidebar navigation
Configure static export

Day 4: Containerization & Deployment
Multi-stage Dockerfile:
dockerfileCopy# Stage 1: Build frontend
FROM node:20-alpine AS web
# ... build Next.js static files

# Stage 2: Python backend + static files
FROM python:3.11-slim AS api
# ... install Python deps
COPY --from=web /app/web/out ./static
GitHub Actions CI/CD:

Build and push to ECR
Deploy to App Runner

Day 5: Observability
LangSmith Setup:
envCopyLANGCHAIN_TRACING_V2=true
LANGCHAIN_ENDPOINT=https://api.smith.langchain.com
LANGCHAIN_API_KEY=<key>
OTLP Collector:

Side-car container for trace forwarding
Export to CloudWatch Logs

Day 6: Documentation

Complete README with setup instructions
Architecture diagrams
Sample project demo
Makefile for common tasks

Day 7: Testing & Polish

End-to-end integration tests
UI improvements (loading states, error handling)
Deployment verification

API Endpoints
MethodEndpointPurposeGET/Serve Next.js frontendPOST/projectsCreate new projectGET/projectsList all projectsPOST/projects/{slug}/chatStream chat responsesGET/projects/{slug}/fileGet markdown content
Environment Configuration
envCopy# LLM Configuration
OPENAI_API_KEY=<key>
DEFAULT_MODEL=o3

# Observability
LANGCHAIN_TRACING_V2=true
LANGCHAIN_ENDPOINT=https://api.smith.langchain.com
LANGCHAIN_API_KEY=<key>
Deployment Architecture
AWS App Runner:

Single container deployment
Automatic HTTPS termination
Auto-scaling based on traffic
Direct ECR integration

Monitoring Stack:

LangSmith for LLM traces
OTLP collector for distributed tracing
CloudWatch for application logs
GitHub Actions for deployment pipeline

Key Design Decisions

Markdown Memory: Human-readable, version-controlled project state
Static Frontend: Simplified deployment, better caching
Single Container: Reduced complexity, easier development
Streaming Chat: Real-time user experience
Model Switching: Runtime LLM selection for testing

Success Metrics

 End-to-end project creation and chat flow working
 Static frontend served by FastAPI
 Markdown files persist conversation history
 LangSmith traces visible
 CloudWatch logs flowing
 Single docker run command works
 GitHub Actions deploys successfully
Add to Conversation