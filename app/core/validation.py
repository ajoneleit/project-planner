"""
Unified Input Validation Module
Centralizes all validation logic for the project planner system.

Provides:
1. Standardized validation functions
2. Security-focused input sanitization
3. Consistent error handling
4. Configurable limits and patterns
"""

import re
import json
from typing import Any, Optional

# Security constants
MAX_PROJECT_NAME_LENGTH = 100
MAX_CONTENT_SIZE = 10 * 1024 * 1024  # 10MB
MAX_USER_ID_LENGTH = 50
MAX_CONVERSATION_ID_LENGTH = 200

# Validation patterns
VALID_PROJECT_NAME_PATTERN = re.compile(r'^[a-zA-Z0-9_-]+$')
VALID_USER_ID_PATTERN = re.compile(r'^[a-zA-Z0-9_@.-]+$')

# Default values
DEFAULT_USER_ID = "anonymous"


def validate_project_name(project_name: str, normalize: bool = True) -> str:
    """
    Validate and sanitize project name with comprehensive security checks.
    
    Args:
        project_name: Input project name to validate
        normalize: Whether to normalize to lowercase (default: True)
        
    Returns:
        Validated and sanitized project name
        
    Raises:
        ValueError: If validation fails
    """
    if not project_name or not isinstance(project_name, str):
        raise ValueError("Project name must be a non-empty string")
    
    # Length check
    if len(project_name) > MAX_PROJECT_NAME_LENGTH:
        raise ValueError(f"Project name too long (max {MAX_PROJECT_NAME_LENGTH} chars)")
    
    # Normalize if requested
    sanitized = project_name.strip()
    if normalize:
        sanitized = sanitized.lower()
    
    # Remove path traversal attempts
    sanitized = sanitized.replace('..', '').replace('/', '').replace('\\', '')
    
    # Validate format
    if not VALID_PROJECT_NAME_PATTERN.match(sanitized):
        raise ValueError("Project name can only contain letters, numbers, underscores, and hyphens")
    
    # Final empty check after sanitization
    if not sanitized:
        raise ValueError("Project name cannot be empty after sanitization")
    
    return sanitized


def validate_user_id(user_id: Optional[str], strict: bool = False) -> str:
    """
    Validate and sanitize user ID with flexible handling.
    
    Args:
        user_id: Input user ID to validate (can be None)
        strict: If True, raise exceptions; if False, return default on invalid input
        
    Returns:
        Validated user ID or default value
        
    Raises:
        ValueError: If validation fails and strict=True
    """
    if not user_id or not isinstance(user_id, str):
        if strict:
            raise ValueError("User ID must be a non-empty string")
        return DEFAULT_USER_ID
    
    # Remove whitespace
    sanitized = user_id.strip()
    
    # Use default if empty after stripping
    if not sanitized:
        if strict:
            raise ValueError("User ID cannot be empty after trimming")
        return DEFAULT_USER_ID
    
    # Length check
    if len(sanitized) > MAX_USER_ID_LENGTH:
        if strict:
            raise ValueError(f"User ID too long (max {MAX_USER_ID_LENGTH} chars)")
        sanitized = sanitized[:MAX_USER_ID_LENGTH]
    
    # Sanitize characters
    if strict:
        # Strict mode: validate pattern exactly
        if not VALID_USER_ID_PATTERN.match(sanitized):
            raise ValueError("User ID can only contain letters, numbers, underscores, @, dot, and hyphen")
    else:
        # Permissive mode: remove invalid characters
        sanitized = re.sub(r'[^a-zA-Z0-9_@.-]', '', sanitized)
        if not sanitized:
            return DEFAULT_USER_ID
    
    return sanitized


def validate_conversation_id(conversation_id: str, allow_simple: bool = True) -> str:
    """
    Validate conversation ID format.
    
    Args:
        conversation_id: The conversation ID to validate
        allow_simple: Whether to allow simple project names (for legacy support)
        
    Returns:
        Validated conversation ID
        
    Raises:
        ValueError: If validation fails
    """
    if not conversation_id or not isinstance(conversation_id, str):
        raise ValueError("Conversation ID must be a non-empty string")
    
    if len(conversation_id) > MAX_CONVERSATION_ID_LENGTH:
        raise ValueError(f"Conversation ID too long (max {MAX_CONVERSATION_ID_LENGTH} chars)")
    
    # Check for project:user format
    if ':' in conversation_id:
        parts = conversation_id.split(':')
        if len(parts) != 2:
            raise ValueError("Conversation ID format must be 'project:user'")
        project_part, user_part = parts
        
        # Validate both parts (non-strict to avoid raising errors)
        try:
            validate_project_name(project_part, normalize=False)
            validate_user_id(user_part, strict=True)
        except ValueError as e:
            raise ValueError(f"Invalid conversation ID format: {e}")
    
    elif allow_simple:
        # Simple project format - validate as project name
        try:
            validate_project_name(conversation_id, normalize=False)
        except ValueError as e:
            raise ValueError(f"Invalid simple conversation ID: {e}")
    else:
        raise ValueError("Conversation ID must be in 'project:user' format")
    
    return conversation_id


def validate_content_size(content: str, max_size: Optional[int] = None) -> None:
    """
    Validate content size to prevent DoS attacks.
    
    Args:
        content: Content to validate
        max_size: Maximum size in bytes (defaults to MAX_CONTENT_SIZE)
        
    Raises:
        ValueError: If content is too large
    """
    if not isinstance(content, str):
        raise ValueError("Content must be a string")
    
    max_bytes = max_size or MAX_CONTENT_SIZE
    content_size = len(content.encode('utf-8'))
    
    if content_size > max_bytes:
        raise ValueError(f"Content too large ({content_size} bytes, max {max_bytes} bytes)")


def validate_json_data(data: Any, max_size: int = 1024 * 1024) -> None:
    """
    Validate JSON data to prevent DoS attacks via large payloads.
    
    Args:
        data: Data to validate (will be JSON serialized)
        max_size: Maximum size in bytes
        
    Raises:
        ValueError: If JSON data is too large
        TypeError: If data is not JSON serializable
    """
    try:
        json_str = json.dumps(data)
    except TypeError as e:
        raise TypeError(f"Data is not JSON serializable: {e}")
    
    json_size = len(json_str.encode('utf-8'))
    if json_size > max_size:
        raise ValueError(f"JSON data too large ({json_size} bytes, max {max_size} bytes)")


def validate_section_name(section: str) -> str:
    """
    Validate markdown section name.
    
    Args:
        section: Section name to validate
        
    Returns:
        Validated section name
        
    Raises:
        ValueError: If validation fails
    """
    if not section or not isinstance(section, str):
        raise ValueError("Section name must be a non-empty string")
    
    sanitized = section.strip()
    if not sanitized:
        raise ValueError("Section name cannot be empty after trimming")
    
    if len(sanitized) > 200:
        raise ValueError("Section name too long (max 200 chars)")
    
    # Basic sanitization - remove problematic characters
    sanitized = re.sub(r'[<>:"/\\|?*]', '', sanitized)
    
    if not sanitized:
        raise ValueError("Section name cannot be empty after sanitization")
    
    return sanitized


def validate_contributor_name(contributor: Optional[str]) -> str:
    """
    Validate contributor name.
    
    Args:
        contributor: Contributor name to validate
        
    Returns:
        Validated contributor name
    """
    if not contributor:
        return "User"
    
    return validate_user_id(contributor, strict=False)


def validate_file_path_security(file_path: "Path", base_directory: "Path") -> bool:
    """
    Validate that a file path is within the expected base directory.
    
    Args:
        file_path: The file path to validate
        base_directory: The base directory that should contain the file
        
    Returns:
        True if path is safe, False otherwise
    """
    try:
        # Resolve both paths to handle symlinks and relative paths
        resolved_file = file_path.resolve()
        resolved_base = base_directory.resolve()
        
        # Check if file path is within base directory
        try:
            resolved_file.relative_to(resolved_base)
            return True
        except ValueError:
            # relative_to raises ValueError if path is not relative to base
            return False
            
    except (OSError, RuntimeError):
        # Handle cases where paths cannot be resolved
        return False