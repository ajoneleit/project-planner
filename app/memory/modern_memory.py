"""
Modern memory system using LangGraph persistence.
Replaces deprecated ConversationBufferMemory with thread-based state management.
"""

import json
import logging
import sqlite3
import asyncio
from typing import Dict, List, Any, Optional, TypedDict
from pathlib import Path
from datetime import datetime

from langchain_core.messages import BaseMessage, HumanMessage, AIMessage
from langgraph.graph import StateGraph, END

logger = logging.getLogger(__name__)


class ProjectPlannerState(TypedDict):
    """State schema for project planner conversations."""
    messages: List[BaseMessage]
    project_slug: str
    user_id: str
    document_updates: List[Dict[str, Any]]
    metadata: Dict[str, Any]


class ModernConversationMemory:
    """
    Modern conversation memory with SQLite persistence.
    Provides thread-based conversation management with automatic persistence.
    """
    
    def __init__(self, db_path: str = "app/memory/conversations.db"):
        """Initialize with SQLite database."""
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(exist_ok=True)
        
        # Initialize SQLite database
        self._init_database()
        
    def _init_database(self):
        """Initialize SQLite database schema."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS conversations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    thread_id TEXT NOT NULL,
                    project_slug TEXT NOT NULL,
                    user_id TEXT NOT NULL,
                    message_type TEXT NOT NULL,
                    content TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    metadata TEXT DEFAULT '{}'
                )
            """)
            
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_thread_id ON conversations(thread_id)
            """)
            
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_project_user ON conversations(project_slug, user_id)
            """)
            
            conn.commit()
    
    def get_thread_id(self, project_slug: str, user_id: str = "default") -> str:
        """Generate thread ID for conversation isolation."""
        return f"{project_slug}:{user_id}"
    
    async def add_message(self, project_slug: str, message: BaseMessage, user_id: str = "default") -> None:
        """Add a message to the conversation thread."""
        thread_id = self.get_thread_id(project_slug, user_id)
        
        try:
            # Determine message type
            if isinstance(message, HumanMessage):
                message_type = "human"
            elif isinstance(message, AIMessage):
                message_type = "ai"
            else:
                message_type = "system"
            
            # Store in database
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("""
                    INSERT INTO conversations 
                    (thread_id, project_slug, user_id, message_type, content, timestamp, metadata)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    thread_id, 
                    project_slug, 
                    user_id, 
                    message_type, 
                    message.content,
                    datetime.now().isoformat(),
                    json.dumps(getattr(message, 'additional_kwargs', {}))
                ))
                conn.commit()
                
            logger.debug(f"Added {message_type} message to thread {thread_id}")
            
        except Exception as e:
            logger.error(f"Error adding message to thread {thread_id}: {e}")
            raise
    
    async def get_conversation_state(self, project_slug: str, user_id: str = "default") -> ProjectPlannerState:
        """Get current conversation state for a thread."""
        try:
            messages = await self.get_messages(project_slug, user_id)
            
            return ProjectPlannerState(
                messages=messages,
                project_slug=project_slug,
                user_id=user_id,
                document_updates=[],  # TODO: Implement document updates storage
                metadata={}
            )
                
        except Exception as e:
            logger.error(f"Error getting state for thread {project_slug}:{user_id}: {e}")
            # Return empty state as fallback
            return ProjectPlannerState(
                messages=[],
                project_slug=project_slug,
                user_id=user_id,
                document_updates=[],
                metadata={}
            )
    
    async def get_messages(self, project_slug: str, user_id: str = "default", limit: Optional[int] = None) -> List[BaseMessage]:
        """Get conversation messages for a thread."""
        thread_id = self.get_thread_id(project_slug, user_id)
        
        try:
            with sqlite3.connect(self.db_path) as conn:
                query = """
                    SELECT message_type, content, metadata
                    FROM conversations 
                    WHERE thread_id = ?
                    ORDER BY id ASC
                """
                if limit:
                    query += f" LIMIT {limit}"
                
                cursor = conn.execute(query, (thread_id,))
                rows = cursor.fetchall()
                
                messages = []
                for message_type, content, metadata_json in rows:
                    metadata = json.loads(metadata_json) if metadata_json else {}
                    
                    if message_type == "human":
                        messages.append(HumanMessage(content=content, additional_kwargs=metadata))
                    elif message_type == "ai":
                        messages.append(AIMessage(content=content, additional_kwargs=metadata))
                    else:
                        # Handle system messages if needed
                        messages.append(HumanMessage(content=content, additional_kwargs=metadata))
                
                return messages
                
        except Exception as e:
            logger.error(f"Error getting messages for thread {thread_id}: {e}")
            return []
    
    async def clear_conversation(self, project_slug: str, user_id: str = "default") -> None:
        """Clear conversation history for a thread."""
        thread_id = self.get_thread_id(project_slug, user_id)
        
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("DELETE FROM conversations WHERE thread_id = ?", (thread_id,))
                conn.commit()
            
            logger.info(f"Cleared conversation for thread {thread_id}")
            
        except Exception as e:
            logger.error(f"Error clearing conversation for thread {thread_id}: {e}")
            raise
    
    async def add_document_update(self, project_slug: str, update: Dict[str, Any], user_id: str = "default") -> None:
        """Add a document update to the conversation state."""
        # TODO: Implement document updates storage in separate table
        logger.info(f"Document update for {project_slug}: {update}")
    
    async def get_conversation_summary(self, project_slug: str, user_id: str = "default") -> Dict[str, Any]:
        """Get a summary of the conversation state."""
        thread_id = self.get_thread_id(project_slug, user_id)
        
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute("""
                    SELECT COUNT(*), MAX(timestamp) 
                    FROM conversations 
                    WHERE thread_id = ?
                """, (thread_id,))
                
                count, last_activity = cursor.fetchone()
                
                return {
                    "project_slug": project_slug,
                    "user_id": user_id,
                    "message_count": count or 0,
                    "document_updates_count": 0,  # TODO: Implement
                    "last_activity": last_activity,
                    "thread_id": thread_id
                }
                
        except Exception as e:
            logger.error(f"Error getting summary for thread {thread_id}: {e}")
            return {
                "project_slug": project_slug,
                "user_id": user_id,
                "message_count": 0,
                "document_updates_count": 0,
                "last_activity": None,
                "thread_id": thread_id
            }


class ConversationMigrator:
    """Utility class for migrating existing JSON conversations to LangGraph format."""
    
    def __init__(self, modern_memory: ModernConversationMemory):
        self.modern_memory = modern_memory
    
    async def migrate_json_conversation(self, json_file_path: str, project_slug: str) -> bool:
        """Migrate a JSON conversation file to the new memory system."""
        try:
            with open(json_file_path, 'r') as f:
                conversation_data = json.load(f)
            
            # Convert JSON messages to BaseMessage objects
            messages = []
            for msg in conversation_data.get("messages", []):
                if msg.get("type") == "human":
                    messages.append(HumanMessage(content=msg["content"]))
                elif msg.get("type") == "ai":
                    messages.append(AIMessage(content=msg["content"]))
            
            # Add messages to new system
            for message in messages:
                await self.modern_memory.add_message(project_slug, message)
            
            logger.info(f"Successfully migrated {len(messages)} messages from {json_file_path}")
            return True
            
        except Exception as e:
            logger.error(f"Error migrating conversation from {json_file_path}: {e}")
            return False
    
    async def migrate_all_conversations(self, memory_dir: str = "app/memory") -> Dict[str, bool]:
        """Migrate all JSON conversation files in the memory directory."""
        memory_path = Path(memory_dir)
        results = {}
        
        for json_file in memory_path.glob("*_conversations.json"):
            # Extract project slug from filename
            project_slug = json_file.stem.replace("_conversations", "")
            
            success = await self.migrate_json_conversation(str(json_file), project_slug)
            results[str(json_file)] = success
        
        return results