"""
Conversation ID Manager - Phase 1: Standardization Strategy
Part of the unified conversation memory architecture.

This module provides:
1. Unified conversation ID generation
2. Legacy ID format resolution
3. Migration mapping strategies
4. ID validation and normalization
"""

import re
from typing import List, Set, Dict, Tuple, Optional
from dataclasses import dataclass
from enum import Enum

# Import centralized validation functions
from .validation import (
    validate_project_name, 
    validate_user_id, 
    DEFAULT_USER_ID
)

class ConversationIDFormat(Enum):
    """Supported conversation ID formats."""
    SIMPLE_PROJECT = "simple_project"      # e.g., "test-project"
    PROJECT_USER = "project_user"          # e.g., "test-project:user123"
    LEGACY_MIXED = "legacy_mixed"          # Mixed or inconsistent format

@dataclass
class ConversationIDInfo:
    """Information about a conversation ID."""
    original_id: str
    format_type: ConversationIDFormat
    project_slug: str
    user_id: Optional[str] = None
    is_valid: bool = True
    migration_target: Optional[str] = None

class ConversationIDManager:
    """
    Unified conversation ID management system.
    
    Handles:
    - ID generation in standardized format
    - Legacy format resolution and migration mapping
    - Validation and normalization
    - Migration strategy coordination
    """
    
    # Standard format: project_slug:user_id
    STANDARD_FORMAT = "{project_slug}:{user_id}"
    # DEFAULT_USER_ID moved to validation module
    
    # Regex patterns for ID format detection
    PATTERNS = {
        ConversationIDFormat.PROJECT_USER: re.compile(r'^([a-zA-Z0-9_-]+):([a-zA-Z0-9_-]+)$'),
        ConversationIDFormat.SIMPLE_PROJECT: re.compile(r'^([a-zA-Z0-9_-]+)$'),
    }
    
    @classmethod
    def generate_standard_id(cls, project_slug: str, user_id: str = DEFAULT_USER_ID) -> str:
        """
        Generate conversation ID in standard format.
        
        Args:
            project_slug: Project identifier (e.g., "my-web-app")
            user_id: User identifier (defaults to "anonymous")
            
        Returns:
            Standard format conversation ID: "project-slug:user-id"
        """
        # Validate inputs
        project_slug = validate_project_name(project_slug, normalize=True)
        user_id = validate_user_id(user_id, strict=False)
        
        return cls.STANDARD_FORMAT.format(project_slug=project_slug, user_id=user_id)
    
    @classmethod
    def analyze_id(cls, conversation_id: str) -> ConversationIDInfo:
        """
        Analyze a conversation ID and determine its format and components.
        
        Args:
            conversation_id: The conversation ID to analyze
            
        Returns:
            ConversationIDInfo with analysis results
        """
        if not conversation_id or not isinstance(conversation_id, str):
            return ConversationIDInfo(
                original_id=conversation_id or "",
                format_type=ConversationIDFormat.LEGACY_MIXED,
                project_slug="",
                is_valid=False
            )
        
        # Try project:user format first
        match = cls.PATTERNS[ConversationIDFormat.PROJECT_USER].match(conversation_id)
        if match:
            project_slug, user_id = match.groups()
            return ConversationIDInfo(
                original_id=conversation_id,
                format_type=ConversationIDFormat.PROJECT_USER,
                project_slug=project_slug,
                user_id=user_id,
                migration_target=conversation_id  # Already in standard format
            )
        
        # Try simple project format
        match = cls.PATTERNS[ConversationIDFormat.SIMPLE_PROJECT].match(conversation_id)
        if match:
            project_slug = match.group(1)
            return ConversationIDInfo(
                original_id=conversation_id,
                format_type=ConversationIDFormat.SIMPLE_PROJECT,
                project_slug=project_slug,
                user_id=DEFAULT_USER_ID,  # Assume anonymous user
                migration_target=cls.generate_standard_id(project_slug, DEFAULT_USER_ID)
            )
        
        # Unknown format
        return ConversationIDInfo(
            original_id=conversation_id,
            format_type=ConversationIDFormat.LEGACY_MIXED,
            project_slug=conversation_id,  # Best guess
            is_valid=False
        )
    
    @classmethod
    def get_migration_mapping(cls, conversation_ids: List[str]) -> Dict[str, ConversationIDInfo]:
        """
        Create migration mapping for a list of conversation IDs.
        
        Args:
            conversation_ids: List of existing conversation IDs
            
        Returns:
            Dictionary mapping original IDs to their analysis and migration targets
        """
        migration_map = {}
        
        for conv_id in conversation_ids:
            analysis = cls.analyze_id(conv_id)
            migration_map[conv_id] = analysis
            
        return migration_map
    
    @classmethod
    def resolve_legacy_ids_for_project(cls, project_slug: str, user_id: str = DEFAULT_USER_ID) -> List[str]:
        """
        Generate all possible legacy conversation ID formats for a project.
        Used during migration to find all conversations that should be consolidated.
        
        Args:
            project_slug: Project identifier
            user_id: User identifier
            
        Returns:
            List of all possible conversation ID formats for this project/user
        """
        possible_ids = [
            # Standard format (target)
            cls.generate_standard_id(project_slug, user_id),
            # Simple project format (legacy)
            project_slug,
            # Handle default user variations
            cls.generate_standard_id(project_slug, "anonymous"),
            cls.generate_standard_id(project_slug, "default"),
        ]
        
        # Remove duplicates while preserving order
        seen = set()
        unique_ids = []
        for conv_id in possible_ids:
            if conv_id not in seen:
                seen.add(conv_id)
                unique_ids.append(conv_id)
                
        return unique_ids
    
    @classmethod
    def create_consolidation_plan(cls, conversation_ids: List[str]) -> Dict[str, List[str]]:
        """
        Create a consolidation plan that groups conversations by their target unified ID.
        
        Args:
            conversation_ids: All existing conversation IDs
            
        Returns:
            Dictionary mapping target unified IDs to lists of source IDs to consolidate
        """
        consolidation_plan = {}
        
        for conv_id in conversation_ids:
            analysis = cls.analyze_id(conv_id)
            
            if analysis.migration_target:
                target = analysis.migration_target
                if target not in consolidation_plan:
                    consolidation_plan[target] = []
                consolidation_plan[target].append(conv_id)
        
        # Return all consolidation mappings (even single sources need mapping)
        return consolidation_plan
    
    # Validation functions moved to centralized validation module

class LegacyConversationResolver:
    """
    Helper class for resolving legacy conversation ID formats during migration.
    """
    
    @staticmethod
    def find_all_conversations_for_project(project_slug: str, 
                                         existing_conversation_ids: List[str]) -> List[str]:
        """
        Find all existing conversation IDs that belong to a specific project.
        
        This handles the case where conversations for the same project might be
        stored under different ID formats due to system evolution.
        """
        project_conversations = []
        
        for conv_id in existing_conversation_ids:
            analysis = ConversationIDManager.analyze_id(conv_id)
            if analysis.project_slug.lower() == project_slug.lower():
                project_conversations.append(conv_id)
                
        return project_conversations
    
    @staticmethod
    def create_sql_query_for_project(project_slug: str, user_id: str = "anonymous") -> Tuple[str, List[str]]:
        """
        Create SQL query to find all conversations for a project across all ID formats.
        
        Returns:
            Tuple of (SQL query string, list of parameters)
        """
        possible_ids = ConversationIDManager.resolve_legacy_ids_for_project(project_slug, user_id)
        
        # Create SQL IN clause
        placeholders = ','.join('?' * len(possible_ids))
        query = f"""
            SELECT conversation_id, role, content, timestamp, user_id, created_at
            FROM conversations 
            WHERE conversation_id IN ({placeholders})
            ORDER BY created_at ASC
        """
        
        return query, possible_ids