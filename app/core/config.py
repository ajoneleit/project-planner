"""
Configuration settings for the unified memory system.
"""

from pathlib import Path
from typing import Optional
import os


class MemoryConfig:
    """Configuration for the unified memory system"""
    
    # Database settings
    UNIFIED_DB_PATH: str = os.getenv("MEMORY_DB_PATH", "app/memory/unified.db")
    LEGACY_DB_PATH: str = os.getenv("LEGACY_DB_PATH", "app/memory/conversations.db")
    
    # Directory settings
    MEMORY_DIR: Path = Path(os.getenv("MEMORY_DIR", "app/memory"))
    BACKUP_DIR: Path = Path(os.getenv("BACKUP_DIR", "app/memory_backup"))
    
    # Migration settings
    AUTO_MIGRATE: bool = os.getenv("AUTO_MIGRATE", "true").lower() == "true"
    MIGRATION_BACKUP: bool = os.getenv("MIGRATION_BACKUP", "true").lower() == "true"
    
    # Performance settings
    THREAD_POOL_SIZE: int = int(os.getenv("MEMORY_THREAD_POOL_SIZE", "4"))
    DB_CONNECTION_TIMEOUT: int = int(os.getenv("DB_CONNECTION_TIMEOUT", "30"))
    
    # Logging settings
    ENABLE_MEMORY_DEBUG: bool = os.getenv("ENABLE_MEMORY_DEBUG", "false").lower() == "true"
    
    @classmethod
    def get_unified_db_path(cls) -> Path:
        """Get the path to the unified database"""
        return Path(cls.UNIFIED_DB_PATH)
    
    @classmethod
    def get_legacy_db_path(cls) -> Path:
        """Get the path to the legacy database"""
        return Path(cls.LEGACY_DB_PATH)
    
    @classmethod
    def ensure_directories(cls) -> None:
        """Ensure all required directories exist"""
        cls.MEMORY_DIR.mkdir(parents=True, exist_ok=True)
        cls.BACKUP_DIR.mkdir(parents=True, exist_ok=True)
        (cls.MEMORY_DIR / "projects").mkdir(parents=True, exist_ok=True)