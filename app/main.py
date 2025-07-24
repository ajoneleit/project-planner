"""
FastAPI application entry point for the Project Planner Bot.
Serves both API endpoints and static frontend files.
"""

from fastapi import FastAPI, HTTPException, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import StreamingResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import os
import json
import asyncio
import logging
import time
import uuid
from pathlib import Path
from typing import List, Dict, Any

# Configure logging with structured format
logging.basicConfig(
    level=getattr(logging, os.getenv('LOG_LEVEL', 'INFO')),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Project Planner Bot", 
    version="1.0.0",
    description="AI-powered project planning with markdown memory"
)

# Add CORS middleware for development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"] if os.getenv("ENVIRONMENT") == "development" else [],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Request logging middleware
@app.middleware("http")
async def log_requests(request: Request, call_next):
    start_time = time.time()
    
    # Log request
    logger.info(f"Request: {request.method} {request.url.path}")
    
    response = await call_next(request)
    
    # Log response
    process_time = time.time() - start_time
    logger.info(f"Response: {response.status_code} - {process_time:.4f}s")
    
    return response

# Request/Response models
class CreateProjectRequest(BaseModel):
    name: str
    description: str = ""

class ChatRequest(BaseModel):
    message: str
    model: str = "gpt-4o-mini"

class ProjectResponse(BaseModel):
    slug: str
    name: str
    created: str
    status: str

# Mount static files (Next.js build output)
web_path = Path(__file__).parent.parent / "web"
if web_path.exists():
    # This is a simplified approach - in production you'd use a proper Next.js server
    # For now, serve the static files that don't require server-side rendering
    pass

@app.get("/health")
async def health_check():
    """Health check endpoint with observability info."""
    return {
        "status": "healthy",
        "service": "planner-bot",
        "version": "1.0.0",
        "environment": os.getenv("ENVIRONMENT", "unknown"),
        "langsmith_enabled": os.getenv("LANGCHAIN_TRACING_V2", "false").lower() == "true",
        "timestamp": time.time()
    }

@app.post("/api/projects", response_model=Dict[str, str])
async def create_project(request: CreateProjectRequest):
    """Create a new project with auto-generated slug."""
    
    try:
        logger.info(f"Creating project: {request.name}")
        
        from .langgraph_runner import ProjectRegistry, MarkdownMemory
        
        # Generate slug from name
        slug = request.name.lower().replace(" ", "-").replace("_", "-")
        slug = "".join(c for c in slug if c.isalnum() or c == "-")
        
        # Ensure uniqueness
        projects = await ProjectRegistry.list_projects()
        original_slug = slug
        counter = 1
        while slug in projects:
            slug = f"{original_slug}-{counter}"
            counter += 1
        
        # Add to registry
        await ProjectRegistry.add_project(slug, {
            "name": request.name,
            "description": request.description
        })
        
        # Initialize markdown file
        memory = MarkdownMemory(slug)
        await memory.ensure_file_exists()
        
        logger.info(f"Project created successfully: {slug}")
        
        return {
            "slug": slug,
            "message": f"Project '{request.name}' created successfully"
        }
        
    except Exception as e:
        logger.error(f"Error creating project: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/projects", response_model=List[ProjectResponse])
async def list_projects():
    """List all projects."""
    
    try:
        from .langgraph_runner import ProjectRegistry
        
        projects_dict = await ProjectRegistry.list_projects()
        
        projects = []
        for slug, data in projects_dict.items():
            projects.append(ProjectResponse(
                slug=slug,
                name=data.get("name", slug.replace("-", " ").title()),
                created=data.get("created", ""),
                status=data.get("status", "active")
            ))
        
        return sorted(projects, key=lambda x: x.created, reverse=True)
        
    except Exception as e:
        logger.error(f"Error listing projects: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/projects/{slug}/chat")
async def chat_with_project(slug: str, request: ChatRequest):
    """Stream chat responses for a specific project."""
    
    try:
        from .langgraph_runner import ProjectRegistry, stream_chat_response
        
        # Verify project exists
        projects = await ProjectRegistry.list_projects()
        if slug not in projects:
            raise HTTPException(status_code=404, detail="Project not found")
        
        # Stream the response
        return StreamingResponse(
            stream_chat_response(slug, request.message, request.model),
            media_type="text/plain",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "Content-Type": "text/event-stream",
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in chat endpoint: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/projects/{slug}/file")
async def get_project_file(slug: str):
    """Get the raw markdown content for a project."""
    
    try:
        from .langgraph_runner import ProjectRegistry, MarkdownMemory
        
        # Verify project exists
        projects = await ProjectRegistry.list_projects()
        if slug not in projects:
            raise HTTPException(status_code=404, detail="Project not found")
        
        # Read markdown content
        memory = MarkdownMemory(slug)
        content = await memory.read_content()
        
        return {"content": content}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error reading project file: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Observability endpoints
@app.get("/api/observability/metrics")
async def get_metrics():
    """Get basic application metrics."""
    try:
        from .langgraph_runner import ProjectRegistry
        projects = await ProjectRegistry.list_projects()
        return {
            "projects_count": len(projects),
            "langsmith_enabled": os.getenv("LANGCHAIN_TRACING_V2", "false").lower() == "true",
            "model": os.getenv("DEFAULT_MODEL", "unknown"),
            "timestamp": time.time()
        }
    except Exception as e:
        logger.error(f"Error getting metrics: {e}")
        return {"error": str(e)}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)