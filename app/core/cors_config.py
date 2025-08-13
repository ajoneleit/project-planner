"""
Secure CORS configuration with environment-based origin management
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from typing import List
import os
from .logging_config import get_secure_logger

logger = get_secure_logger(__name__)


class CORSConfig:
    """Secure CORS configuration"""
    
    @staticmethod
    def get_allowed_origins() -> List[str]:
        """Get allowed origins from environment with secure defaults"""
        # Get from environment variable
        origins_env = os.getenv("ALLOWED_ORIGINS", "")
        
        if origins_env:
            origins = [origin.strip() for origin in origins_env.split(",")]
            logger.info(f"Using CORS origins from environment: {len(origins)} origins configured")
        else:
            # Secure defaults for different environments
            environment = os.getenv("ENVIRONMENT", "development").lower()
            
            if environment == "production":
                origins = [
                    "https://yourdomain.com",
                    "https://www.yourdomain.com"
                ]
                logger.warning("Using production CORS defaults - update ALLOWED_ORIGINS environment variable")
            elif environment in ["development", "dev"]:
                origins = [
                    "http://localhost:3000",
                    "http://localhost:3001", 
                    "http://localhost:8000",
                    "http://127.0.0.1:3000",
                    "http://127.0.0.1:3001",
                    "http://127.0.0.1:8000"
                ]
                logger.info("Using development CORS defaults")
            else:
                # Safe fallback - no origins allowed
                origins = []
                logger.error("Unknown environment - no CORS origins allowed")
        
        # Validate origins
        validated_origins = []
        for origin in origins:
            if CORSConfig._is_valid_origin(origin):
                validated_origins.append(origin)
            else:
                logger.warning(f"Invalid CORS origin removed: {origin}")
        
        return validated_origins
    
    @staticmethod
    def _is_valid_origin(origin: str) -> bool:
        """Validate that an origin is properly formatted"""
        if not origin:
            return False
        
        # Must start with http:// or https://
        if not (origin.startswith('http://') or origin.startswith('https://')):
            return False
        
        # No wildcards allowed in specific origins
        if '*' in origin:
            return origin == '*'  # Only allow full wildcard, not partial
        
        return True
    
    @staticmethod
    def configure_cors(app: FastAPI) -> FastAPI:
        """Configure CORS with security best practices"""
        allowed_origins = CORSConfig.get_allowed_origins()
        
        # Security check: Never use "*" with credentials
        allow_credentials = len(allowed_origins) > 0 and "*" not in allowed_origins
        
        if "*" in allowed_origins and allow_credentials:
            logger.error("SECURITY ERROR: Cannot use wildcard origins with credentials")
            allowed_origins = []  # Block all origins as safety measure
            allow_credentials = False
        
        # Configure CORS middleware
        app.add_middleware(
            CORSMiddleware,
            allow_origins=allowed_origins,
            allow_credentials=allow_credentials,
            allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
            allow_headers=[
                "Accept", 
                "Accept-Language", 
                "Content-Language", 
                "Content-Type",
                "Authorization"
            ],
            max_age=600,  # Cache preflight requests for 10 minutes
        )
        
        logger.info(f"CORS configured with {len(allowed_origins)} allowed origins, credentials: {allow_credentials}")
        
        return app
    
    @staticmethod
    def validate_cors_config() -> List[str]:
        """Validate CORS configuration and return warnings"""
        warnings = []
        origins = CORSConfig.get_allowed_origins()
        
        if not origins:
            warnings.append("No CORS origins configured - frontend may not work")
        
        if "*" in origins:
            warnings.append("Wildcard CORS origin detected - security risk in production")
        
        for origin in origins:
            if origin.startswith("http://") and os.getenv("ENVIRONMENT") == "production":
                warnings.append(f"HTTP origin in production: {origin}")
        
        return warnings


def get_cors_middleware_config():
    """Get CORS middleware configuration as dict"""
    allowed_origins = CORSConfig.get_allowed_origins()
    allow_credentials = len(allowed_origins) > 0 and "*" not in allowed_origins
    
    return {
        "allow_origins": allowed_origins,
        "allow_credentials": allow_credentials,
        "allow_methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        "allow_headers": ["Accept", "Accept-Language", "Content-Language", "Content-Type", "Authorization"],
        "max_age": 600
    }