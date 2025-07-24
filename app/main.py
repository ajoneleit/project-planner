"""
FastAPI application entry point for the Project Planner Bot.
Serves both API endpoints and static frontend files.
"""

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import os
from pathlib import Path

app = FastAPI(
    title="Project Planner Bot",
    description="Conversational AI project planning bot with markdown memory",
    version="0.1.0"
)

# Mount static files (Next.js build output)
static_path = Path(__file__).parent.parent / "web" / "out"
if static_path.exists():
    app.mount("/static", StaticFiles(directory=static_path), name="static")

@app.get("/")
async def read_root():
    """Serve the Next.js frontend."""
    return {"message": "Project Planner Bot API", "status": "running"}

@app.get("/api/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "service": "project-planner-bot"}

@app.post("/api/projects")
async def create_project():
    """Create a new project."""
    # TODO: Implement project creation
    return {"message": "Project creation endpoint - TODO"}

@app.get("/api/projects")
async def list_projects():
    """List all projects."""
    # TODO: Implement project listing
    return {"projects": [], "message": "Project listing endpoint - TODO"}

@app.post("/api/projects/{slug}/chat")
async def chat_with_project(slug: str):
    """Chat with a specific project using SSE streaming."""
    # TODO: Implement LangGraph chat streaming
    return {"message": f"Chat endpoint for project {slug} - TODO"}

@app.get("/api/projects/{slug}/file")
async def get_project_file(slug: str):
    """Get the markdown file for a specific project."""
    # TODO: Implement markdown file retrieval
    return {"message": f"File endpoint for project {slug} - TODO"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)