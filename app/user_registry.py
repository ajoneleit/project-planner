"""
User registry system for project planner.
Handles user identification without authentication - simple first/last name tracking.
"""

import asyncio
import aiofiles
import json
import os
from datetime import datetime
from typing import Dict, Any, Optional, List
from pathlib import Path
import logging
from pydantic import BaseModel

logger = logging.getLogger(__name__)

MEMORY_DIR = Path("app/memory")
USERS_FILE = MEMORY_DIR / "users.json"

class User(BaseModel):
    """User model for simple identification."""
    id: str
    first_name: str
    last_name: str
    display_name: str
    created: datetime
    last_active: datetime

class UserRegistry:
    """Manages user registration and retrieval without authentication."""
    
    _lock = asyncio.Lock()
    
    @staticmethod
    async def _load_users() -> Dict[str, Any]:
        """Load users from JSON file."""
        if not USERS_FILE.exists():
            return {"users": {}, "next_id": 1}
        
        try:
            async with aiofiles.open(USERS_FILE, 'r', encoding='utf-8') as f:
                content = await f.read()
                return json.loads(content) if content.strip() else {"users": {}, "next_id": 1}
        except Exception as e:
            logger.error(f"Error loading users file: {e}")
            return {"users": {}, "next_id": 1}
    
    @staticmethod
    async def _save_users(data: Dict[str, Any]) -> None:
        """Save users to JSON file."""
        MEMORY_DIR.mkdir(exist_ok=True)
        
        async with aiofiles.open(USERS_FILE, 'w', encoding='utf-8') as f:
            await f.write(json.dumps(data, indent=2, default=str))
    
    @staticmethod
    async def register_user(first_name: str, last_name: str) -> str:
        """Register a new user or get existing user by name."""
        async with UserRegistry._lock:
            data = await UserRegistry._load_users()
            
            # Clean and validate names
            first_name = first_name.strip().title()
            last_name = last_name.strip().title()
            
            if not first_name or not last_name:
                raise ValueError("First name and last name are required")
            
            # Check if user already exists by name
            existing_user = await UserRegistry.find_user_by_name(first_name, last_name)
            if existing_user:
                # Update last active time
                user_data = data["users"][existing_user.id]
                user_data["last_active"] = datetime.now().isoformat()
                await UserRegistry._save_users(data)
                logger.info(f"Returning existing user: {existing_user.display_name}")
                return existing_user.id
            
            # Create new user
            user_id = f"user_{data['next_id']}"
            display_name = f"{first_name} {last_name}"
            current_time = datetime.now()
            
            user_data = {
                "id": user_id,
                "first_name": first_name,
                "last_name": last_name,
                "display_name": display_name,
                "created": current_time.isoformat(),
                "last_active": current_time.isoformat()
            }
            
            data["users"][user_id] = user_data
            data["next_id"] = data["next_id"] + 1
            
            await UserRegistry._save_users(data)
            
            logger.info(f"Registered new user: {display_name} ({user_id})")
            return user_id
    
    @staticmethod
    async def get_user(user_id: str) -> Optional[User]:
        """Get user by ID."""
        data = await UserRegistry._load_users()
        user_data = data["users"].get(user_id)
        
        if not user_data:
            return None
        
        return User(
            id=user_data["id"],
            first_name=user_data["first_name"],
            last_name=user_data["last_name"],
            display_name=user_data["display_name"],
            created=datetime.fromisoformat(user_data["created"]),
            last_active=datetime.fromisoformat(user_data["last_active"])
        )
    
    @staticmethod
    async def find_user_by_name(first_name: str, last_name: str) -> Optional[User]:
        """Find user by first and last name."""
        data = await UserRegistry._load_users()
        
        first_name = first_name.strip().title()
        last_name = last_name.strip().title()
        
        for user_data in data["users"].values():
            if (user_data["first_name"] == first_name and 
                user_data["last_name"] == last_name):
                return User(
                    id=user_data["id"],
                    first_name=user_data["first_name"],
                    last_name=user_data["last_name"],
                    display_name=user_data["display_name"],
                    created=datetime.fromisoformat(user_data["created"]),
                    last_active=datetime.fromisoformat(user_data["last_active"])
                )
        
        return None
    
    @staticmethod
    async def list_users() -> List[User]:
        """List all users."""
        data = await UserRegistry._load_users()
        users = []
        
        for user_data in data["users"].values():
            users.append(User(
                id=user_data["id"],
                first_name=user_data["first_name"],
                last_name=user_data["last_name"],
                display_name=user_data["display_name"],
                created=datetime.fromisoformat(user_data["created"]),
                last_active=datetime.fromisoformat(user_data["last_active"])
            ))
        
        return sorted(users, key=lambda u: u.last_active, reverse=True)
    
    @staticmethod
    async def update_last_active(user_id: str) -> None:
        """Update user's last active timestamp."""
        async with UserRegistry._lock:
            data = await UserRegistry._load_users()
            if user_id in data["users"]:
                data["users"][user_id]["last_active"] = datetime.now().isoformat()
                await UserRegistry._save_users(data)

# Helper functions for user-related operations
async def get_user_display_name(user_id: str) -> str:
    """Get user display name, with fallback for unknown users."""
    if not user_id or user_id == "anonymous":
        return "Anonymous User"
    
    user = await UserRegistry.get_user(user_id)
    return user.display_name if user else f"Unknown User ({user_id})"

async def validate_user(user_id: str) -> bool:
    """Validate that a user ID exists."""
    if not user_id or user_id == "anonymous":
        return False
    
    user = await UserRegistry.get_user(user_id)
    return user is not None