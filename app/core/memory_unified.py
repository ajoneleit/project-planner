"""
Unified Memory System for Project Planner Bot

Consolidates all memory operations into a single, coherent system:
- ModernConversationMemory (SQLite) → Unified conversation storage  
- ConversationMemory (JSON) → Legacy compatibility layer
- MarkdownMemory (MD files) → Project document management
- LegacyMemoryWrapper → Eliminated through direct unified interface

Uses SQLite for structured data + file system for human-readable documents.
"""

import asyncio
import sqlite3
import json
import re
import aiosqlite
from pathlib import Path
from typing import Dict, Any, List, Optional, Union
from datetime import datetime
from abc import ABC, abstractmethod
import logging

from langchain_core.messages import BaseMessage, HumanMessage, AIMessage

logger = logging.getLogger(__name__)

# Import centralized validation functions
from .validation import (
    validate_project_name,
    validate_user_id,
    validate_content_size,
    validate_json_data,
    validate_conversation_id,
    validate_section_name,
    validate_contributor_name,
    validate_file_path_security
)

def _connection_is_closed(connection: aiosqlite.Connection) -> bool:
    """Check if aiosqlite connection is closed using private attribute."""
    return getattr(connection, '_closed', True)

# Use the same async-safe utilities from langgraph_runner
import concurrent.futures
from functools import lru_cache

# Global thread pool executor for file operations with proper cleanup
import threading
_file_executor: Optional[concurrent.futures.ThreadPoolExecutor] = None
_executor_lock = threading.Lock()
_executor_async_lock = asyncio.Lock()

def get_file_executor() -> concurrent.futures.ThreadPoolExecutor:
    """Get shared thread pool executor for file operations (thread-safe)."""
    global _file_executor
    
    # Double-checked locking pattern for thread safety
    if _file_executor is None or _file_executor._shutdown:
        with _executor_lock:
            # Check again inside the lock
            if _file_executor is None or _file_executor._shutdown:
                _file_executor = concurrent.futures.ThreadPoolExecutor(
                    max_workers=4, 
                    thread_name_prefix="memory_file_ops"
                )
    return _file_executor

async def shutdown_file_executor():
    """Shutdown the file executor and wait for completion."""
    global _file_executor
    
    async with _executor_async_lock:
        if _file_executor is not None and not _file_executor._shutdown:
            logger.info("Shutting down file operations thread pool")
            _file_executor.shutdown(wait=True)
            _file_executor = None


class DatabaseConnectionPool:
    """Simple connection pool for SQLite to prevent resource exhaustion"""
    
    def __init__(self, db_path: str, max_connections: int = 10):
        self.db_path = db_path
        self.max_connections = max_connections
        self._connections = asyncio.Queue(maxsize=max_connections)
        self._created_connections = 0
        self._lock = asyncio.Lock()
    
    async def get_connection(self) -> aiosqlite.Connection:
        """Get a connection from the pool"""
        max_retries = 5  # Prevent infinite loops
        retry_count = 0
        
        while retry_count < max_retries:
            try:
                # Try to get an existing connection
                connection = self._connections.get_nowait()
                # Verify connection is still valid
                if _connection_is_closed(connection):
                    async with self._lock:
                        self._created_connections -= 1
                    # Continue loop to try again instead of recursion
                    retry_count += 1
                    continue
                return connection
            except asyncio.QueueEmpty:
                # Create new connection if under limit
                async with self._lock:
                    if self._created_connections < self.max_connections:
                        try:
                            connection = await aiosqlite.connect(self.db_path)
                            # Enable WAL mode for better concurrency
                            await connection.execute("PRAGMA journal_mode=WAL")
                            await connection.execute("PRAGMA synchronous=NORMAL")
                            await connection.execute("PRAGMA temp_store=memory")
                            await connection.execute("PRAGMA mmap_size=268435456")  # 256MB
                            self._created_connections += 1
                            return connection
                        except Exception as e:
                            logger.error(f"Failed to create database connection to {self.db_path}: {e}")
                            raise
                    else:
                        # Wait for a connection to become available
                        try:
                            connection = await asyncio.wait_for(self._connections.get(), timeout=30.0)
                            # Verify the waited connection is still valid
                            if connection.is_closed():
                                async with self._lock:
                                    self._created_connections -= 1
                                # Continue loop to try again instead of recursion
                                retry_count += 1
                                continue
                            return connection
                        except asyncio.TimeoutError:
                            raise RuntimeError(f"Timeout waiting for database connection to {self.db_path}")
        
        # If we've exhausted all retries
        raise RuntimeError(f"Failed to get valid connection after {max_retries} attempts")
    
    async def return_connection(self, connection: aiosqlite.Connection):
        """Return a connection to the pool"""
        if connection is None:
            return
            
        # Check if connection is still valid
        if _connection_is_closed(connection):
            async with self._lock:
                self._created_connections -= 1
            return
            
        try:
            self._connections.put_nowait(connection)
        except asyncio.QueueFull:
            # Pool is full, close the connection
            try:
                await connection.close()
            except Exception as e:
                logger.warning(f"Error closing excess connection: {e}")
            async with self._lock:
                self._created_connections -= 1
        except Exception as e:
            logger.error(f"Error returning connection to pool: {e}")
            try:
                await connection.close()
            except Exception:
                pass
            async with self._lock:
                self._created_connections -= 1
    
    async def close_all(self):
        """Close all connections in the pool"""
        while not self._connections.empty():
            try:
                connection = self._connections.get_nowait()
                try:
                    if not connection.is_closed():
                        await connection.close()
                except Exception as e:
                    logger.warning(f"Error closing pooled connection: {e}")
            except asyncio.QueueEmpty:
                break
        async with self._lock:
            self._created_connections = 0


def get_connection_pool(db_path: str) -> DatabaseConnectionPool:
    """Get or create a connection pool for a database"""
    global _connection_pools
    if db_path not in _connection_pools:
        _connection_pools[db_path] = DatabaseConnectionPool(db_path)
    return _connection_pools[db_path]


class PooledConnection:
    """Context manager for pooled database connections"""
    
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.pool = get_connection_pool(db_path)
        self.connection = None
    
    async def __aenter__(self) -> aiosqlite.Connection:
        try:
            self.connection = await self.pool.get_connection()
            return self.connection
        except Exception as e:
            logger.error(f"Failed to acquire connection from pool for {self.db_path}: {e}")
            raise
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.connection:
            try:
                await self.pool.return_connection(self.connection)
            except Exception as e:
                logger.error(f"Error returning connection to pool: {e}")
                # Attempt to close the connection directly if pool return fails
                try:
                    if not self.connection.is_closed():
                        await self.connection.close()
                except Exception:
                    pass
            finally:
                self.connection = None

async def safe_file_read(file_path: Path) -> Optional[str]:
    """Thread-safe async file reading that doesn't block the event loop."""
    def _read_file():
        try:
            if file_path.exists():
                return file_path.read_text(encoding='utf-8')
            return None
        except PermissionError as e:
            logger.error(f"Permission denied reading file {file_path}: {e}")
            return None
        except OSError as e:
            logger.error(f"OS error reading file {file_path}: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error reading file {file_path}: {e}", exc_info=True)
            return None
    
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(get_file_executor(), _read_file)

async def safe_file_write(file_path: Path, content: str) -> bool:
    """Thread-safe async file writing that doesn't block the event loop."""
    def _write_file():
        try:
            file_path.parent.mkdir(parents=True, exist_ok=True)
            file_path.write_text(content, encoding='utf-8')
            return True
        except PermissionError as e:
            logger.error(f"Permission denied writing file {file_path}: {e}")
            return False
        except OSError as e:
            logger.error(f"OS error writing file {file_path}: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error writing file {file_path}: {e}", exc_info=True)
            return False
    
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(get_file_executor(), _write_file)

async def safe_json_read(file_path: Path) -> Optional[Dict[str, Any]]:
    """Thread-safe async JSON file reading."""
    def _read_json():
        try:
            if file_path.exists():
                content = file_path.read_text(encoding='utf-8')
                return json.loads(content) if content.strip() else {}
            return None
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in file {file_path}: {e}")
            return None
        except PermissionError as e:
            logger.error(f"Permission denied reading JSON file {file_path}: {e}")
            return None
        except OSError as e:
            logger.error(f"OS error reading JSON file {file_path}: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error reading JSON file {file_path}: {e}", exc_info=True)
            return None
    
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(get_file_executor(), _read_json)

async def safe_json_write(file_path: Path, data: Dict[str, Any]) -> bool:
    """Thread-safe async JSON file writing."""
    def _write_json():
        try:
            file_path.parent.mkdir(parents=True, exist_ok=True)
            file_path.write_text(json.dumps(data, indent=2), encoding='utf-8')
            return True
        except TypeError as e:
            logger.error(f"Data not JSON serializable for {file_path}: {e}")
            return False
        except PermissionError as e:
            logger.error(f"Permission denied writing JSON file {file_path}: {e}")
            return False
        except OSError as e:
            logger.error(f"OS error writing JSON file {file_path}: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error writing JSON file {file_path}: {e}", exc_info=True)
            return False
    
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(get_file_executor(), _write_json)


class MemoryInterface(ABC):
    """Abstract interface for all memory operations"""
    
    @abstractmethod
    async def save_conversation(self, conversation_id: str, message: Dict[str, Any]) -> bool:
        """Save a conversation message"""
        pass
    
    @abstractmethod
    async def get_conversation(self, conversation_id: str, limit: int = None) -> List[Dict[str, Any]]:
        """Get conversation history"""
        pass
    
    @abstractmethod
    async def save_project(self, project_name: str, content: str) -> bool:
        """Save project document content"""
        pass
    
    @abstractmethod
    async def get_project(self, project_name: str) -> Optional[str]:
        """Get project document content"""
        pass
    
    @abstractmethod
    async def list_projects(self) -> List[str]:
        """List all available projects"""
        pass
    
    @abstractmethod
    async def save_memory(self, key: str, content: str) -> bool:
        """Save general memory entry"""
        pass
    
    @abstractmethod
    async def load_memory(self, key: str) -> Optional[str]:
        """Load general memory entry"""
        pass


class UnifiedMemoryManager(MemoryInterface):
    """
    Unified memory manager that consolidates all memory operations.
    
    Architecture:
    - SQLite database for structured data (conversations, metadata)
    - File system for human-readable documents (markdown projects)
    - Async-safe operations using ThreadPoolExecutor
    - Single lock coordination to prevent race conditions
    """
    
    def __init__(self, db_path: str = "app/memory/unified.db", memory_dir: str = "app/memory"):
        self.db_path = Path(db_path)
        self.memory_dir = Path(memory_dir)
        self._file_lock = asyncio.Lock()
        self._initialized = False
    
    async def initialize(self) -> bool:
        """Initialize the unified memory system"""
        if self._initialized:
            return True
            
        try:
            # Create directories
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
            self.memory_dir.mkdir(parents=True, exist_ok=True)
            (self.memory_dir / "projects").mkdir(parents=True, exist_ok=True)
            
            # Initialize database using connection pool
            async with PooledConnection(str(self.db_path)) as db:
                await self._create_tables(db)
            
            # Pre-warm connection pool for better performance
            await self._prewarm_connection_pool()
            
            self._initialized = True
            logger.info("Unified memory system initialized successfully")
            return True
            
        except OSError as e:
            logger.error(f"Database access error initializing unified memory: {e}")
            return False
        except PermissionError as e:
            logger.error(f"Permission error initializing unified memory: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error initializing unified memory: {e}", exc_info=True)
            return False
    
    async def _create_tables(self, db: aiosqlite.Connection):
        """Create necessary database tables"""
        
        # Conversations table (replaces ConversationMemory JSON files)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS conversations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                conversation_id TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                user_id TEXT DEFAULT 'anonymous',
                metadata TEXT DEFAULT '{}',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Memory entries table (general key-value storage)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS memory_entries (
                key TEXT PRIMARY KEY,
                content TEXT NOT NULL,
                content_type TEXT DEFAULT 'text',
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                metadata TEXT DEFAULT '{}'
            )
        """)
        
        # Projects metadata table (complements markdown file storage)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS projects (
                name TEXT PRIMARY KEY,
                description TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                file_path TEXT,
                user_id TEXT DEFAULT 'anonymous',
                metadata TEXT DEFAULT '{}'
            )
        """)
        
        # Session tracking table (replaces MarkdownMemory session logic)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_name TEXT NOT NULL,
                user_id TEXT NOT NULL,
                contributor TEXT NOT NULL,
                start_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                end_time TIMESTAMP,
                sections_updated TEXT DEFAULT '[]',
                status TEXT DEFAULT 'active'
            )
        """)
        
        # Create indexes for performance
        await db.execute("CREATE INDEX IF NOT EXISTS idx_conversations_id ON conversations(conversation_id)")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_conversations_timestamp ON conversations(timestamp)")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_projects_updated ON projects(updated_at)")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_sessions_project ON sessions(project_name, user_id)")
        
        await db.commit()
    
    async def _prewarm_connection_pool(self):
        """Pre-warm the connection pool for better performance"""
        try:
            pool = get_connection_pool(str(self.db_path))
            # Create 2 initial connections to speed up first requests
            connections = []
            for _ in range(2):
                conn = await pool.get_connection()
                connections.append(conn)
            
            # Return connections to pool
            for conn in connections:
                await pool.return_connection(conn)
                
            logger.debug("Connection pool pre-warmed successfully")
        except Exception as e:
            logger.warning(f"Failed to pre-warm connection pool: {e}")

    # === Conversation Management (replaces ConversationMemory + ModernConversationMemory) ===
    
    async def save_conversation(self, conversation_id: str, message: Dict[str, Any]) -> bool:
        """Save conversation message to database"""
        try:
            async with PooledConnection(str(self.db_path)) as db:
                    await db.execute("""
                        INSERT INTO conversations (conversation_id, role, content, timestamp, user_id, metadata)
                        VALUES (?, ?, ?, ?, ?, ?)
                    """, (
                        conversation_id,
                        message.get('role', 'user'),
                        message.get('content', ''),
                        message.get('timestamp', datetime.now().isoformat()),
                        message.get('user_id', 'anonymous'),
                        json.dumps(message.get('metadata', {}))
                    ))
                    await db.commit()
            return True
        except Exception as e:
            logger.error(f"Error saving conversation: {e}")
            return False
    
    async def get_conversation(self, conversation_id: str, limit: int = None) -> List[Dict[str, Any]]:
        """Get conversation history from database"""
        try:
            async with PooledConnection(str(self.db_path)) as db:
                    query = """
                        SELECT role, content, timestamp, user_id, metadata 
                        FROM conversations 
                        WHERE conversation_id = ? 
                        ORDER BY created_at ASC
                    """
                    params = [conversation_id]
                    
                    if limit:
                        query += " LIMIT ?"
                        params.append(limit)
                    
                    async with db.execute(query, params) as cursor:
                        rows = await cursor.fetchall()
                        
                    return [
                        {
                            'role': row[0],
                            'content': row[1],
                            'timestamp': row[2],
                            'user_id': row[3],
                            'metadata': json.loads(row[4]) if row[4] else {}
                        }
                        for row in rows
                    ]
        except Exception as e:
            logger.error(f"Error getting conversation: {e}")
            return []
    
    async def add_message(self, conversation_id: str, role: str, content: str, user_id: str = "anonymous", metadata: Dict = None) -> bool:
        """Add message to conversation (compatibility method)"""
        # Validate inputs
        validate_conversation_id(conversation_id, allow_simple=True)
        if role not in ['user', 'assistant', 'system']:
            raise ValueError("Role must be 'user', 'assistant', or 'system'")
        validate_content_size(content)
        sanitized_user_id = validate_user_id(user_id, strict=False)
        
        # Validate metadata if provided
        if metadata:
            validate_json_data(metadata)
        
        message = {
            'role': role,
            'content': content,
            'timestamp': datetime.now().isoformat(),
            'user_id': sanitized_user_id,
            'metadata': metadata or {}
        }
        return await self.save_conversation(conversation_id, message)
    
    async def get_recent_history(self, conversation_id: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Get recent conversation history (compatibility method)"""
        # Validate inputs
        validate_conversation_id(conversation_id, allow_simple=True)
        if limit < 1 or limit > 1000:  # Prevent DoS via excessive limits
            raise ValueError("Limit must be between 1 and 1000")
            
        messages = await self.get_conversation(conversation_id, limit)
        return messages[-limit:] if messages else []

    # === Project Management (replaces MarkdownMemory) ===
    
    async def save_project(self, project_name: str, content: str, user_id: str = "anonymous") -> bool:
        """Save project to both database metadata and file system"""
        # Validate inputs to prevent security vulnerabilities
        sanitized_name = validate_project_name(project_name, normalize=True)
        validate_content_size(content)
        sanitized_user_id = validate_user_id(user_id, strict=False)
        
        async with self._file_lock:
            try:
                # Save to file system (authoritative for content) - now secure
                project_file = self.memory_dir / f"{sanitized_name}.md"
                
                # Enhanced path traversal protection
                if not validate_file_path_security(project_file, self.memory_dir):
                    logger.error(f"Path traversal attempt detected: {project_file}")
                    return False
                
                success = await safe_file_write(project_file, content)
                
                if success:
                    # Update database metadata
                    async with PooledConnection(str(self.db_path)) as db:
                        await db.execute("""
                            INSERT OR REPLACE INTO projects (name, file_path, updated_at, user_id)
                            VALUES (?, ?, ?, ?)
                        """, (
                            sanitized_name,
                            str(project_file),
                            datetime.now().isoformat(),
                            sanitized_user_id
                        ))
                        await db.commit()
                
                return success
            except Exception as e:
                logger.error(f"Error saving project {project_name}: {e}")
                return False
    
    async def get_project(self, project_name: str) -> Optional[str]:
        """Get project content from file system"""
        try:
            # Validate input to prevent path traversal
            sanitized_name = validate_project_name(project_name, normalize=True)
            project_file = self.memory_dir / f"{sanitized_name}.md"
            
            # Enhanced path traversal protection
            if not validate_file_path_security(project_file, self.memory_dir):
                logger.error(f"Path traversal attempt detected: {project_file}")
                return None
            
            return await safe_file_read(project_file)
        except ValueError as e:
            logger.warning(f"Invalid project name '{project_name}': {e}")
            return None
        except Exception as e:
            logger.error(f"Error loading project {project_name}: {e}")
            return None
    
    async def list_projects(self) -> List[str]:
        """List all available projects"""
        try:
            # Use list comprehension for better performance
            projects = [
                md_file.stem for md_file in self.memory_dir.glob("*.md")
                if not md_file.name.startswith('_')  # Skip internal files
            ]
            return sorted(projects)
        except Exception as e:
            logger.error(f"Error listing projects: {e}")
            return []
    
    async def update_project_section(self, project_name: str, section: str, content: str, 
                                   contributor: str = "User", user_id: str = "anonymous") -> bool:
        """Update a specific section of a project document"""
        try:
            # Validate inputs
            sanitized_name = validate_project_name(project_name, normalize=True)
            sanitized_section = validate_section_name(section)
            validate_content_size(content)
            sanitized_user_id = validate_user_id(user_id, strict=False)
            sanitized_contributor = validate_contributor_name(contributor)
            
            current_content = await self.get_project(sanitized_name)
            if current_content is None:
                logger.error(f"Project {project_name} not found")
                return False
            
            # Use the same section update logic from MarkdownMemory
            updated_content = await self._update_markdown_section(
                current_content, sanitized_section, content, sanitized_contributor, sanitized_user_id
            )
            
            return await self.save_project(sanitized_name, updated_content, sanitized_user_id)
        except Exception as e:
            logger.error(f"Error updating project section: {e}")
            return False

    async def _update_markdown_section(self, content: str, section: str, new_content: str, 
                                     contributor: str, user_id: str) -> str:
        """Update a specific section in markdown content (simplified from MarkdownMemory)"""
        import re
        
        # Add timestamp for tracking
        current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        # Simple section update - look for section header and add content
        section_pattern = rf'^## {re.escape(section)}.*?(?=^## |\Z)'
        
        if re.search(section_pattern, content, re.MULTILINE | re.DOTALL):
            # Section exists, append to it
            def replace_section(match):
                existing = match.group(0)
                return f"{existing.rstrip()}\n\n**Added {current_time} by {contributor}:**\n{new_content}\n\n"
            
            updated_content = re.sub(section_pattern, replace_section, content, flags=re.MULTILINE | re.DOTALL)
        else:
            # Section doesn't exist, add it
            updated_content = f"{content}\n\n## {section}\n**Added {current_time} by {contributor}:**\n{new_content}\n\n"
        
        return updated_content

    # === General Memory Operations ===
    
    async def save_memory(self, key: str, content: str) -> bool:
        """Save general memory entry"""
        try:
            async with PooledConnection(str(self.db_path)) as db:
                    await db.execute("""
                        INSERT OR REPLACE INTO memory_entries (key, content, updated_at)
                        VALUES (?, ?, ?)
                    """, (key, content, datetime.now().isoformat()))
                    await db.commit()
            return True
        except sqlite3.OperationalError as e:
            logger.error(f"Database operational error saving memory {key}: {e}")
            return False
        except OSError as e:
            logger.error(f"Database access error saving memory {key}: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error saving memory {key}: {e}", exc_info=True)
            return False
    
    async def load_memory(self, key: str) -> Optional[str]:
        """Load general memory entry"""
        try:
            async with PooledConnection(str(self.db_path)) as db:
                    async with db.execute("SELECT content FROM memory_entries WHERE key = ?", (key,)) as cursor:
                        row = await cursor.fetchone()
                    return row[0] if row else None
        except sqlite3.OperationalError as e:
            logger.error(f"Database operational error loading memory {key}: {e}")
            return None
        except OSError as e:
            logger.error(f"Database access error loading memory {key}: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error loading memory {key}: {e}", exc_info=True)
            return None

    # === Migration Methods ===
    
    async def migrate_from_legacy(self, legacy_memory_dir: str = "app/memory") -> bool:
        """Migrate data from all legacy memory implementations"""
        try:
            logger.info("Starting migration from legacy memory systems...")
            
            await self._migrate_json_conversations(legacy_memory_dir)
            await self._migrate_markdown_projects(legacy_memory_dir) 
            await self._migrate_sqlite_conversations(legacy_memory_dir)
            
            logger.info("Migration completed successfully!")
            return True
        except Exception as e:
            logger.error(f"Error during migration: {e}")
            return False
    
    async def _migrate_json_conversations(self, legacy_dir: str):
        """Migrate JSON conversation files to unified database"""
        legacy_path = Path(legacy_dir)
        
        # Look for conversation JSON files
        for json_file in legacy_path.glob("*_conversations.json"):
            try:
                conversation_id = json_file.stem.replace("_conversations", "")
                
                data = await safe_json_read(json_file)
                if not data:
                    continue
                
                # Handle different JSON formats
                messages = data.get('messages', []) if isinstance(data, dict) else data
                
                for msg in messages:
                    if isinstance(msg, dict):
                        await self.save_conversation(conversation_id, msg)
                        
                logger.info(f"Migrated JSON conversation: {conversation_id}")
                
                # Backup original file
                backup_path = json_file.with_suffix(".json.backup")
                json_file.rename(backup_path)
                
            except Exception as e:
                logger.error(f"Error migrating {json_file}: {e}")
    
    async def _migrate_markdown_projects(self, legacy_dir: str):
        """Migrate existing markdown project files"""
        legacy_path = Path(legacy_dir)
        
        # Find all markdown files that aren't already in our system
        for md_file in legacy_path.glob("*.md"):
            try:
                if md_file.name.startswith('_'):  # Skip internal files
                    continue
                    
                project_name = md_file.stem
                content = await safe_file_read(md_file)
                
                if content:
                    # Save using unified system (will create metadata entry)
                    await self.save_project(project_name, content, "migration")
                    logger.info(f"Migrated project: {project_name}")
                    
            except Exception as e:
                logger.error(f"Error migrating {md_file}: {e}")
    
    async def _migrate_sqlite_conversations(self, legacy_dir: str):
        """Migrate from ModernConversationMemory SQLite database"""
        legacy_db_path = Path(legacy_dir) / "conversations.db"
        
        if not legacy_db_path.exists():
            return
        
        try:
            async with aiosqlite.connect(legacy_db_path) as legacy_db:
                async with legacy_db.execute("""
                    SELECT thread_id, project_slug, user_id, message_type, content, timestamp, metadata
                    FROM conversations ORDER BY id ASC
                """) as cursor:
                    async for row in cursor:
                        thread_id, project_slug, user_id, message_type, content, timestamp, metadata = row
                        
                        # Convert thread_id format if needed
                        conversation_id = thread_id if ":" in thread_id else f"{project_slug}:{user_id}"
                        
                        message = {
                            'role': 'user' if message_type == 'human' else 'assistant',
                            'content': content,
                            'timestamp': timestamp,
                            'user_id': user_id,
                            'metadata': json.loads(metadata) if metadata else {}
                        }
                        
                        await self.save_conversation(conversation_id, message)
            
            logger.info("Migrated ModernConversationMemory SQLite database")
            
            # Backup original database
            backup_path = legacy_db_path.with_suffix(".db.backup")
            legacy_db_path.rename(backup_path)
            
        except Exception as e:
            logger.error(f"Error migrating SQLite conversations: {e}")


# === Global Instance Management ===

_unified_memory: Optional[UnifiedMemoryManager] = None
_memory_lock = asyncio.Lock()
_connection_pools = {}

async def get_unified_memory() -> UnifiedMemoryManager:
    """Get singleton instance of unified memory manager"""
    global _unified_memory
    
    async with _memory_lock:
        if _unified_memory is None:
            _unified_memory = UnifiedMemoryManager()
            await _unified_memory.initialize()
        return _unified_memory

async def reset_unified_memory():
    """Reset the global instance and cleanup resources (useful for testing and shutdown)"""
    global _unified_memory
    async with _memory_lock:
        if _unified_memory is not None:
            logger.info("Cleaning up unified memory resources")
            
            # Close all connection pools
            for db_path in list(_connection_pools.keys()):
                pool = _connection_pools.pop(db_path)
                try:
                    await pool.close_all()
                    logger.info(f"Closed connection pool for {db_path}")
                except Exception as e:
                    logger.warning(f"Error closing connection pool for {db_path}: {e}")
            
            # Shutdown thread pool executor
            await shutdown_file_executor()
            
            _unified_memory = None
            logger.info("Unified memory system reset completed")