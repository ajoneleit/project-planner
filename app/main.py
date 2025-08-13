"""
FastAPI application entry point for the Project Planner Bot.
Serves both API endpoints and static frontend files.
"""

from fastapi import FastAPI, HTTPException, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import StreamingResponse, FileResponse, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, validator
import os
import json
import asyncio
import logging
import time
import uuid
from datetime import datetime
import socket
from pathlib import Path
from typing import List, Dict, Any
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Configure SECURE logging that sanitizes sensitive data
from .core.logging_config import setup_secure_logging, get_secure_logger
logger = setup_secure_logging(os.getenv('LOG_LEVEL', 'INFO'))

# Additional secure logger for this module
module_logger = get_secure_logger(__name__)

app = FastAPI(
    title="Project Planner Bot", 
    version="1.0.0",
    description="AI-powered project planning with markdown memory"
)

# Enhanced CORS configuration
def get_cors_origins():
    """DEPRECATED: Use CORSConfig.get_allowed_origins() instead for security"""
    # Import the secure CORS configuration
    from .core.cors_config import CORSConfig
    
    module_logger.warning("Using deprecated get_cors_origins() - migrate to CORSConfig")
    return CORSConfig.get_allowed_origins()

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
# CORS configuration moved to secure CORSConfig class

# Configure SECURE CORS - replaces insecure configuration
from .core.cors_config import CORSConfig
app = CORSConfig.configure_cors(app)

# Validate CORS configuration and log warnings
cors_warnings = CORSConfig.validate_cors_config()
for warning in cors_warnings:
    module_logger.warning(f"CORS Security Warning: {warning}")

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
    name: str = Field(..., min_length=1, max_length=100, description="Project name")
    description: str = Field("", max_length=10000, description="Project description")
    created_by: str = Field("anonymous", max_length=50, description="User ID who created the project")
    
    @validator('name')
    def validate_name(cls, v):
        # Import security validation
        from .core.security import SecurityUtils
        sanitized = SecurityUtils.sanitize_for_logging(v.strip())
        if not sanitized or len(sanitized) < 1:
            raise ValueError("Project name cannot be empty")
        if len(sanitized) > 100:
            raise ValueError("Project name too long (max 100 characters)")
        # Check for path traversal attempts
        if '..' in sanitized or '/' in sanitized or '\\' in sanitized:
            raise ValueError("Project name contains invalid characters")
        return sanitized
    
    @validator('created_by')
    def validate_created_by(cls, v):
        from .core.memory_unified import validate_user_id
        return validate_user_id(v)

class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=50000, description="Chat message")
    model: str = Field("gpt-4o-mini", pattern=r'^(gpt-4o-mini|gpt-4o|o1-mini|o1-preview)$', description="AI model to use")
    user_id: str = Field("anonymous", max_length=50, description="User ID for attribution")
    
    @validator('message')
    def validate_message(cls, v):
        from .core.memory_unified import validate_content_size
        validate_content_size(v)  # Uses 10MB limit
        return v.strip()
    
    @validator('user_id')
    def validate_user_id(cls, v):
        from .core.memory_unified import validate_user_id
        return validate_user_id(v)

class ProjectResponse(BaseModel):
    slug: str
    name: str
    created: str
    status: str

class UserRegistrationRequest(BaseModel):
    first_name: str = Field(..., min_length=1, max_length=50, description="User first name")
    last_name: str = Field(..., min_length=1, max_length=50, description="User last name")
    
    @validator('first_name', 'last_name')
    def validate_names(cls, v):
        # Sanitize names
        import re
        sanitized = re.sub(r'[^a-zA-Z\s\'-]', '', v.strip())
        if not sanitized or len(sanitized) < 1:
            raise ValueError("Name cannot be empty or contain only special characters")
        if len(sanitized) > 50:
            raise ValueError("Name too long (max 50 characters)")
        return sanitized

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
        "cors_origins": get_cors_origins(),
        "langsmith_enabled": os.getenv("LANGCHAIN_TRACING_V2", "false").lower() == "true",
        "default_model": os.getenv("DEFAULT_MODEL", "gpt-4o-mini"),
        "static_files_mounted": os.path.exists(static_dir),
        "agent_system": "openai-agents-sdk" if os.getenv("USE_OPENAI_AGENTS", "false").lower() == "true" else "langgraph",
        "openai_agents_enabled": os.getenv("USE_OPENAI_AGENTS", "false").lower() == "true",
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
        
    except ValueError as e:
        logger.warning(f"Invalid user registration data: {e}")
        raise HTTPException(status_code=400, detail=f"Invalid input: {e}")
    except Exception as e:
        logger.error(f"Unexpected error registering user: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")

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
    except KeyError as e:
        logger.warning(f"User data missing required field: {e}")
        raise HTTPException(status_code=500, detail="Invalid user data format")
    except Exception as e:
        logger.error(f"Unexpected error getting user: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")

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
        
    except OSError as e:
        logger.error(f"Database access error listing users: {e}")
        raise HTTPException(status_code=503, detail="Database temporarily unavailable")
    except Exception as e:
        logger.error(f"Unexpected error listing users: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")

@app.post("/api/projects", response_model=Dict[str, str])
async def create_project(request: CreateProjectRequest):
    """Create a new project with auto-generated slug."""
    
    try:
        logger.info(f"Creating project: {request.name}")
        
        from .langgraph_runner import ProjectRegistry
        from .core.memory_unified import get_unified_memory
        from .core.feature_flags import is_feature_enabled
        
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
        
        # Phase 2: Initialize project using unified memory system
        if await is_feature_enabled("unified_memory_primary"):
            # Use unified memory system directly
            unified_memory = await get_unified_memory()
            
            # Create initial project document
            project_name = request.name.replace('-', ' ').title()
            current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            
            if request.description and request.description.strip():
                executive_summary = request.description.strip()
                context_content = request.description.strip()
            else:
                executive_summary = "Please provide more information about this project's purpose, goals, and context."
                context_content = "*Background and motivation for this project*"
            
            initial_content = f"""# {project_name}
_Last updated: {current_time}_

---

## Executive Summary
{executive_summary}

---

## Objective
- [ ] Define specific, measurable project goals
- [ ] Establish success criteria
- [ ] Identify key deliverables

---

## Context
{context_content}

---

## Glossary

| Term | Definition | Added by |

---

## Constraints & Risks
*Technical limitations, resource constraints, and identified risks*

---

## Stakeholders & Collaborators

| Role / Name | Responsibilities |

---

## Systems & Data Sources
*Technical infrastructure, data sources, tools and platforms*

---

## Attachments & Examples

| Item | Type | Location | Notes |

---

## Open Questions & Conflicts

| Question/Conflict | Owner | Priority | Status |

---

## Next Actions

| When | Action | Why it matters | Owner |

---

## Recent Updates
*Latest changes and additions to this document*

---

## Change Log

| Date | Contributor | User ID | Summary |
| {current_time} | System | system | Initial structured project document created |
"""
            
            await unified_memory.save_project(slug, initial_content, "system")
            logger.info(f"Project {slug} created using unified memory system")
            
        else:
            # Fallback to compatibility layer
            from .core.memory_compatibility import CompatibilityMarkdownMemory
            memory = CompatibilityMarkdownMemory(slug)
            await memory._create_initial_file(request.description)
            logger.info(f"Project {slug} created using compatibility layer")
        
        logger.info(f"Project created successfully: {slug}")
        
        return {
            "slug": slug,
            "message": f"Project '{request.name}' created successfully"
        }
        
    except ValueError as e:
        logger.warning(f"Invalid project creation data: {e}")
        raise HTTPException(status_code=400, detail=f"Invalid input: {e}")
    except OSError as e:
        logger.error(f"File system error creating project: {e}")
        raise HTTPException(status_code=503, detail="Storage temporarily unavailable")
    except Exception as e:
        logger.error(f"Unexpected error creating project: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")

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
        
    except OSError as e:
        logger.error(f"Database access error listing projects: {e}")
        raise HTTPException(status_code=503, detail="Database temporarily unavailable")
    except Exception as e:
        logger.error(f"Unexpected error listing projects: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")

@app.post("/api/projects/{slug}/chat")
async def chat_with_project(slug: str, request: ChatRequest, http_request: Request):
    """Stream chat responses for a specific project."""
    
    try:
        from .langgraph_runner import ProjectRegistry
        
        logger.info(f"Chat request for project {slug}: {request.message[:100]}...")
        
        # Verify project exists
        projects = await ProjectRegistry.list_projects()
        if slug not in projects:
            raise HTTPException(status_code=404, detail="Project not found")
        
        # Feature flag to choose between LangGraph and OpenAI Agents SDK
        use_openai_agents = os.getenv("USE_OPENAI_AGENTS", "false").lower() == "true"
        
        if use_openai_agents:
            # Use OpenAI Agents SDK
            from .openai_agents_runner import get_openai_runner
            
            async def stream_openai_agents_response():
                try:
                    runner = await get_openai_runner()
                    async for chunk in runner.run_conversation_stream(slug, request.message, request.model):
                        yield f"data: {chunk}\n\n"
                    yield "data: [DONE]\n\n"
                except Exception as e:
                    logger.error(f"Error in OpenAI Agents streaming: {e}")
                    yield f"data: Error: {str(e)}\n\n"
                    yield "data: [DONE]\n\n"
            
            return StreamingResponse(
                stream_openai_agents_response(),
                media_type="text/event-stream",
                headers=get_sse_headers(http_request)
            )
        else:
            # Use existing LangGraph system
            from .langgraph_runner import stream_chat_response
            
            return StreamingResponse(
                stream_chat_response(slug, request.message, request.model, request.user_id),
                media_type="text/event-stream",
                headers=get_sse_headers(http_request)
            )
        
    except HTTPException:
        raise
    except ValueError as e:
        logger.warning(f"Invalid chat request: {e}")
        raise HTTPException(status_code=400, detail=f"Invalid input: {e}")
    except OSError as e:
        logger.error(f"I/O error in chat endpoint: {e}")
        raise HTTPException(status_code=503, detail="Service temporarily unavailable")
    except Exception as e:
        logger.error(f"Unexpected error in chat endpoint: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")

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
    except ValueError as e:
        logger.warning(f"Invalid initial message request: {e}")
        raise HTTPException(status_code=400, detail=f"Invalid input: {e}")
    except OSError as e:
        logger.error(f"I/O error in initial message endpoint: {e}")
        raise HTTPException(status_code=503, detail="Service temporarily unavailable")
    except Exception as e:
        logger.error(f"Unexpected error in initial message endpoint: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")

@app.get("/api/projects/{slug}/file")
async def get_project_file(slug: str):
    """Get the raw markdown content for a project."""
    
    try:
        from .langgraph_runner import ProjectRegistry
        from .core.memory_unified import get_unified_memory
        from .core.feature_flags import is_feature_enabled
        
        # Verify project exists
        projects = await ProjectRegistry.list_projects()
        if slug not in projects:
            raise HTTPException(status_code=404, detail="Project not found")
        
        # Phase 2: Read using unified memory system
        if await is_feature_enabled("unified_memory_primary"):
            # Use unified memory system directly
            unified_memory = await get_unified_memory()
            content = await unified_memory.get_project(slug)
            
            if content is None:
                raise HTTPException(status_code=404, detail="Project content not found")
                
        else:
            # Fallback to compatibility layer
            from .core.memory_compatibility import CompatibilityMarkdownMemory
            memory = CompatibilityMarkdownMemory(slug)
            content = await memory.read_content()
        
        return {"content": content}
        
    except HTTPException:
        raise
    except FileNotFoundError as e:
        logger.warning(f"Project file not found: {e}")
        raise HTTPException(status_code=404, detail="Project file not found")
    except PermissionError as e:
        logger.error(f"Permission denied reading project file: {e}")
        raise HTTPException(status_code=403, detail="Access denied")
    except OSError as e:
        logger.error(f"File system error reading project: {e}")
        raise HTTPException(status_code=503, detail="Storage temporarily unavailable")
    except Exception as e:
        logger.error(f"Unexpected error reading project file: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")

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
    except ValueError as e:
        logger.warning(f"Invalid archive request: {e}")
        raise HTTPException(status_code=400, detail=f"Invalid input: {e}")
    except OSError as e:
        logger.error(f"Database error archiving project: {e}")
        raise HTTPException(status_code=503, detail="Database temporarily unavailable")
    except Exception as e:
        logger.error(f"Unexpected error archiving project: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")

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
    except ValueError as e:
        logger.warning(f"Invalid unarchive request: {e}")
        raise HTTPException(status_code=400, detail=f"Invalid input: {e}")
    except OSError as e:
        logger.error(f"Database error unarchiving project: {e}")
        raise HTTPException(status_code=503, detail="Database temporarily unavailable")
    except Exception as e:
        logger.error(f"Unexpected error unarchiving project: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")

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
    except ValueError as e:
        logger.warning(f"Invalid delete request: {e}")
        raise HTTPException(status_code=400, detail=f"Invalid input: {e}")
    except OSError as e:
        logger.error(f"Database error deleting project: {e}")
        raise HTTPException(status_code=503, detail="Database temporarily unavailable")
    except Exception as e:
        logger.error(f"Unexpected error deleting project: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")

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
        
    except OSError as e:
        logger.error(f"Database access error listing archived projects: {e}")
        raise HTTPException(status_code=503, detail="Database temporarily unavailable")
    except Exception as e:
        logger.error(f"Unexpected error listing archived projects: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")

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
            "cors_origins_count": len(get_cors_origins()),
            "timestamp": time.time()
        }
    except OSError as e:
        logger.error(f"Database access error getting metrics: {e}")
        return {"error": "Database temporarily unavailable", "timestamp": time.time()}
    except Exception as e:
        logger.error(f"Unexpected error getting metrics: {e}", exc_info=True)
        return {"error": "Internal server error", "timestamp": time.time()}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", 8000)))