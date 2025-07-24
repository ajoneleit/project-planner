"""
FastAPI application entry point for the Project Planner Bot.
Serves both API endpoints and static frontend files.
"""

from fastapi import FastAPI, HTTPException, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import StreamingResponse, FileResponse
from pydantic import BaseModel
import os
import json
import logging
from pathlib import Path
from typing import List, Dict, Any

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Project Planner Bot",
    description="Conversational AI project planning bot with markdown memory",
    version="0.1.0"
)

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
static_path = Path(__file__).parent.parent / "static"
if static_path.exists():
    app.mount("/", StaticFiles(directory=static_path, html=True), name="static")

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "service": "project-planner-bot"}

@app.post("/api/projects", response_model=Dict[str, str])
async def create_project(request: CreateProjectRequest):
    """Create a new project with auto-generated slug."""
    
    try:
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
        
        return {
            "slug": slug,
            "message": f"Project '{request.name}' created successfully"
        }
        
    except Exception as e:
        logger.error(f"Error creating project: {e}")
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

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)