"""
FastAPI application entry point for the Project Planner Bot.
Serves both API endpoints and static frontend files.
"""

from fastapi import FastAPI, HTTPException, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import StreamingResponse, FileResponse, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import os
import json
import asyncio
import logging
import time
import uuid
import socket
from pathlib import Path
from typing import List, Dict, Any
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

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

# Enhanced CORS configuration
def get_cors_origins():
    """Get CORS origins based on environment with proper security."""
    env = os.getenv("ENVIRONMENT", "development")
    
    if env == "production":
        # Production: Only allow same-origin and specific production domains
        production_origins = []
        
        # Add App Runner domain if available
        app_runner_domain = os.getenv("PRODUCTION_DOMAIN")
        if app_runner_domain:
            production_origins.append(f"https://{app_runner_domain}")
        
        # Add custom production domains from environment
        custom_domains = os.getenv("CORS_PRODUCTION_ORIGINS", "")
        if custom_domains:
            production_origins.extend(custom_domains.split(","))
        
        # If no specific domains configured, allow same-origin only
        if not production_origins:
            # This is secure for same-origin requests when frontend is served by FastAPI
            return ["*"]
        
        logger.info(f"Production CORS origins: {production_origins}")
        return production_origins
    else:
        # Development: Allow comprehensive localhost and local network access
        origins = [
            # Standard development ports
            "http://localhost:3000",
            "http://localhost:3001",
            "http://localhost:8000",
            "http://localhost:8001",
            "http://127.0.0.1:3000",
            "http://127.0.0.1:3001",
            "http://127.0.0.1:8000",
            "http://127.0.0.1:8001",
        ]
        
        # Add custom development origins from environment
        custom_origins = os.getenv("CORS_DEVELOPMENT_ORIGINS", "")
        if custom_origins:
            origins.extend(custom_origins.split(","))
        
        # Add dynamic local network IPs for Docker/WSL scenarios
        try:
            hostname = socket.gethostname()
            local_ip = socket.gethostbyname(hostname)
            for port in [3000, 3001, 8000, 8001]:
                origins.extend([
                    f"http://{local_ip}:{port}",
                ])
        except Exception as e:
            logger.debug(f"Could not detect local IP for CORS: {e}")
        
        # Remove duplicates while preserving order
        unique_origins = []
        for origin in origins:
            if origin not in unique_origins:
                unique_origins.append(origin)
        
        return unique_origins

def get_cors_headers():
    """Get allowed headers for CORS."""
    return [
        # Standard headers
        "Accept",
        "Accept-Language",
        "Content-Language",
        "Content-Type",
        
        # Authentication headers
        "Authorization",
        "X-Requested-With",
        
        # Custom headers that might be used
        "X-CSRFToken",
        "X-User-ID",
        
        # Origin header for CORS
        "Origin",
        
        # Headers for SSE streaming
        "Cache-Control",
        "Connection",
    ]

def get_exposed_headers():
    """Get headers to expose to the client."""
    return [
        "Content-Length",
        "Content-Type",
        "Cache-Control",
        "Connection",
        "X-Request-ID",
    ]

def get_sse_headers(request: Request = None):
    """Get headers for Server-Sent Events (SSE) streaming with proper CORS."""
    headers = {
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
        "Content-Type": "text/event-stream",
        "X-Accel-Buffering": "no",  # Disable nginx buffering
    }
    
    # Add CORS headers for streaming
    if request:
        origin = request.headers.get("origin")
        if origin:
            # Check if origin is allowed
            allowed_origins = get_cors_origins()
            if "*" in allowed_origins or origin in allowed_origins:
                headers["Access-Control-Allow-Origin"] = origin
            else:
                headers["Access-Control-Allow-Origin"] = "*"
        else:
            headers["Access-Control-Allow-Origin"] = "*"
    else:
        headers["Access-Control-Allow-Origin"] = "*"
    
    # Additional CORS headers for streaming
    headers.update({
        "Access-Control-Allow-Credentials": "true",
        "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
        "Access-Control-Allow-Headers": "Content-Type, Authorization, X-Requested-With",
        "Access-Control-Expose-Headers": "Content-Type, Cache-Control, Connection",
    })
    
    return headers

# Configure CORS with enhanced security and development support
cors_origins = get_cors_origins()
cors_headers = get_cors_headers()
exposed_headers = get_exposed_headers()

logger.info(f"CORS origins configured: {cors_origins}")
logger.info(f"CORS headers allowed: {cors_headers}")

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "HEAD"],
    allow_headers=cors_headers,
    expose_headers=exposed_headers,
    max_age=86400,  # Cache preflight requests for 24 hours
)

# Request logging middleware
@app.middleware("http")
async def log_requests(request: Request, call_next):
    start_time = time.time()
    
    # Log request with origin for CORS debugging
    origin = request.headers.get("origin", "no-origin")
    logger.info(f"Request: {request.method} {request.url.path} (Origin: {origin})")
    
    response = await call_next(request)
    
    # Log response
    process_time = time.time() - start_time
    logger.info(f"Response: {response.status_code} - {process_time:.4f}s")
    
    return response

# Request/Response models
class CreateProjectRequest(BaseModel):
    name: str
    description: str = ""
    created_by: str = "anonymous"  # User ID who created the project

class ChatRequest(BaseModel):
    message: str
    model: str = "gpt-4o-mini"
    user_id: str = "anonymous"  # User ID for attribution

class ProjectResponse(BaseModel):
    slug: str
    name: str
    created: str
    status: str

class UserRegistrationRequest(BaseModel):
    first_name: str
    last_name: str

class UserResponse(BaseModel):
    id: str
    first_name: str
    last_name: str
    display_name: str
    created: str
    last_active: str

@app.get("/")
async def root():
    return {"message": "Project Planner Bot API", "docs": "/docs", "health": "/health"}

@app.get("/health")
async def health_check():
    """Health check endpoint with comprehensive system info."""
    static_dir = "static"
    return {
        "status": "healthy",
        "service": "planner-bot",
        "version": "1.0.0",
        "environment": os.getenv("ENVIRONMENT", "unknown"),
        "cors_origins": cors_origins,
        "langsmith_enabled": os.getenv("LANGCHAIN_TRACING_V2", "false").lower() == "true",
        "default_model": os.getenv("DEFAULT_MODEL", "gpt-4o-mini"),
        "static_files_mounted": os.path.exists(static_dir),
        "timestamp": time.time()
    }

# Enhanced CORS preflight handler
@app.options("/{full_path:path}")
async def options_handler(request: Request, full_path: str):
    """Handle CORS preflight requests with proper security."""
    
    # Get the requesting origin
    origin = request.headers.get("origin", "")
    allowed_origins = get_cors_origins()
    
    # Determine if origin is allowed
    if "*" in allowed_origins:
        allow_origin = origin if origin else "*"
    elif origin in allowed_origins:
        allow_origin = origin
    else:
        # Origin not allowed, but respond to avoid CORS errors
        allow_origin = "null"
    
    # Enhanced preflight response headers
    headers = {
        "Access-Control-Allow-Origin": allow_origin,
        "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE, OPTIONS, HEAD",
        "Access-Control-Allow-Headers": ", ".join(get_cors_headers()),
        "Access-Control-Allow-Credentials": "true",
        "Access-Control-Max-Age": "86400",  # 24 hours
        "Access-Control-Expose-Headers": ", ".join(get_exposed_headers()),
        "Vary": "Origin",  # Important for caching
    }
    
    # Add specific headers for SSE endpoints
    if "/chat" in full_path or "initial-message" in full_path:
        headers.update({
            "Access-Control-Allow-Headers": headers["Access-Control-Allow-Headers"] + ", Cache-Control, Connection",
        })
    
    logger.debug(f"CORS preflight for {full_path} from origin {origin}")
    
    return Response(
        status_code=200,
        headers=headers
    )

# User Management Endpoints
@app.post("/api/users", response_model=Dict[str, str])
async def register_user(request: UserRegistrationRequest):
    """Register a new user or get existing user by name."""
    
    try:
        logger.info(f"Registering user: {request.first_name} {request.last_name}")
        
        from .user_registry import UserRegistry, get_user_display_name
        
        user_id = await UserRegistry.register_user(request.first_name, request.last_name)
        display_name = await get_user_display_name(user_id)
        
        return {
            "user_id": user_id,
            "display_name": display_name
        }
        
    except Exception as e:
        logger.error(f"Error registering user: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/users/{user_id}", response_model=UserResponse)
async def get_user(user_id: str):
    """Get user details by ID."""
    
    try:
        from .user_registry import UserRegistry
        
        user = await UserRegistry.get_user(user_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        return UserResponse(
            id=user.id,
            first_name=user.first_name,
            last_name=user.last_name,
            display_name=user.display_name,
            created=user.created.isoformat(),
            last_active=user.last_active.isoformat()
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting user: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/users", response_model=List[UserResponse])
async def list_users():
    """List all users."""
    
    try:
        from .user_registry import UserRegistry
        
        users = await UserRegistry.list_users()
        
        return [
            UserResponse(
                id=user.id,
                first_name=user.first_name,
                last_name=user.last_name,
                display_name=user.display_name,
                created=user.created.isoformat(),
                last_active=user.last_active.isoformat()
            )
            for user in users
        ]
        
    except Exception as e:
        logger.error(f"Error listing users: {e}")
        raise HTTPException(status_code=500, detail=str(e))

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
    """List all active projects."""
    
    try:
        from .langgraph_runner import ProjectRegistry
        
        # Only get active projects
        projects_dict = await ProjectRegistry.get_projects_by_status("active")
        
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
async def chat_with_project(slug: str, request: ChatRequest, http_request: Request):
    """Stream chat responses for a specific project."""
    
    try:
        from .langgraph_runner import ProjectRegistry, stream_chat_response
        
        logger.info(f"Chat request for project {slug}: {request.message[:100]}...")
        
        # Verify project exists
        projects = await ProjectRegistry.list_projects()
        if slug not in projects:
            raise HTTPException(status_code=404, detail="Project not found")
        
        # Stream the response with proper CORS headers
        return StreamingResponse(
            stream_chat_response(slug, request.message, request.model, request.user_id),
            media_type="text/event-stream",
            headers=get_sse_headers(http_request)
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in chat endpoint: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/projects/{slug}/initial-message")
async def get_initial_message(slug: str, user_id: str = "anonymous", http_request: Request = None):
    """Get initial message for a project based on user state."""
    
    try:
        from .langgraph_runner import ProjectRegistry, stream_initial_message
        
        logger.info(f"Initial message request for project {slug} by user {user_id}")
        
        # Verify project exists
        projects = await ProjectRegistry.list_projects()
        if slug not in projects:
            raise HTTPException(status_code=404, detail="Project not found")
        
        # Stream the initial message with proper CORS headers
        return StreamingResponse(
            stream_initial_message(slug, user_id),
            media_type="text/event-stream",
            headers=get_sse_headers(http_request)
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in initial message endpoint: {e}")
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

@app.put("/api/projects/{slug}/archive")
async def archive_project(slug: str):
    """Archive a project."""
    
    try:
        from .langgraph_runner import ProjectRegistry
        
        success = await ProjectRegistry.archive_project(slug)
        
        if not success:
            raise HTTPException(status_code=404, detail="Project not found")
        
        return {"message": f"Project {slug} archived successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error archiving project: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.put("/api/projects/{slug}/unarchive")
async def unarchive_project(slug: str):
    """Unarchive a project."""
    
    try:
        from .langgraph_runner import ProjectRegistry
        
        success = await ProjectRegistry.unarchive_project(slug)
        
        if not success:
            raise HTTPException(status_code=404, detail="Project not found")
        
        return {"message": f"Project {slug} unarchived successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error unarchiving project: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/projects/{slug}")
async def delete_project(slug: str):
    """Delete a project permanently."""
    
    try:
        from .langgraph_runner import ProjectRegistry
        
        success = await ProjectRegistry.delete_project(slug)
        
        if not success:
            raise HTTPException(status_code=404, detail="Project not found")
        
        return {"message": f"Project {slug} deleted successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting project: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/projects/archived", response_model=List[ProjectResponse])
async def list_archived_projects():
    """List all archived projects."""
    
    try:
        from .langgraph_runner import ProjectRegistry
        
        projects = await ProjectRegistry.get_projects_by_status("archived")
        
        project_list = []
        for slug, metadata in projects.items():
            project_list.append(ProjectResponse(
                slug=slug,
                name=metadata.get("name", slug.replace("-", " ").title()),
                created=metadata.get("created", ""),
                status=metadata.get("status", "archived")
            ))
        
        # Sort by created date, newest first
        project_list.sort(key=lambda x: x.created, reverse=True)
        
        return project_list
        
    except Exception as e:
        logger.error(f"Error listing archived projects: {e}")
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
            "environment": os.getenv("ENVIRONMENT", "unknown"),
            "cors_origins_count": len(cors_origins),
            "timestamp": time.time()
        }
    except Exception as e:
        logger.error(f"Error getting metrics: {e}")
        return {"error": str(e)}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", 8000)))