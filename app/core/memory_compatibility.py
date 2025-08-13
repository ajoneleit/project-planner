"""
Compatibility wrappers for existing memory system usage.

These wrappers ensure that existing code can continue to work without changes
while using the new unified memory system under the hood.
"""

import asyncio
import json
from typing import Dict, Any, List, Optional
from datetime import datetime
from pathlib import Path

from langchain_core.messages import BaseMessage, HumanMessage, AIMessage

from .memory_unified import get_unified_memory, UnifiedMemoryManager
import logging

logger = logging.getLogger(__name__)


class CompatibilityConversationMemory:
    """
    Drop-in replacement for the original ConversationMemory class.
    Uses UnifiedMemoryManager under the hood.
    """
    
    def __init__(self, project_slug: str):
        self.project_slug = project_slug
        self.file_path = Path(f"app/memory/{project_slug}_conversations.json")  # For compatibility
        self._lock = asyncio.Lock()
        self._unified_memory: Optional[UnifiedMemoryManager] = None
        
        # Compatibility properties
        self.messages: List[BaseMessage] = []
        self._memory_initialized = False
        self.last_ai_response = None
    
    async def _get_unified_memory(self) -> UnifiedMemoryManager:
        """Get unified memory instance"""
        if self._unified_memory is None:
            self._unified_memory = await get_unified_memory()
        return self._unified_memory
    
    async def _initialize_langchain_memory(self) -> None:
        """Initialize memory from unified system (compatibility method)"""
        if self._memory_initialized:
            return
        
        try:
            memory = await self._get_unified_memory()
            conversation_id = self.project_slug
            
            # Load messages from unified system
            messages_data = await memory.get_conversation(conversation_id)
            
            # Convert to LangChain message format
            self.messages = []
            for msg_data in messages_data:
                if msg_data['role'] == 'user':
                    self.messages.append(HumanMessage(content=msg_data['content']))
                elif msg_data['role'] == 'assistant':
                    self.messages.append(AIMessage(content=msg_data['content']))
                    self.last_ai_response = msg_data['content']
            
            self._memory_initialized = True
            logger.debug(f"Initialized compatibility memory for {self.project_slug} with {len(self.messages)} messages")
            
        except OSError as e:
            logger.error(f"Database access error initializing compatibility memory: {e}")
            self._memory_initialized = False
            raise RuntimeError(f"Memory initialization failed (database access): {e}") from e
        except ImportError as e:
            logger.error(f"Missing dependency initializing compatibility memory: {e}")
            self._memory_initialized = False
            raise RuntimeError(f"Memory initialization failed (missing dependency): {e}") from e
        except Exception as e:
            logger.error(f"Unexpected error initializing compatibility memory: {e}", exc_info=True)
            self._memory_initialized = False
            raise RuntimeError(f"Memory initialization failed: {e}") from e
    
    async def add_conversation(self, user_input: str, ai_response: str, user_id: str = "anonymous") -> None:
        """Add conversation to unified memory system"""
        try:
            await self._initialize_langchain_memory()
            memory = await self._get_unified_memory()
            conversation_id = self.project_slug
            
            messages_added = []
            
            if user_input:
                await memory.add_message(conversation_id, "user", user_input, user_id)
                user_msg = HumanMessage(content=user_input)
                self.messages.append(user_msg)
                messages_added.append(user_msg)
            
            if ai_response:
                await memory.add_message(conversation_id, "assistant", ai_response, user_id)
                ai_msg = AIMessage(content=ai_response)
                self.messages.append(ai_msg)
                self.last_ai_response = ai_response
                messages_added.append(ai_msg)
            
            logger.debug(f"Added {len(messages_added)} messages to {self.project_slug}")
            
        except ValueError as e:
            # Input validation errors should be raised to caller
            logger.warning(f"Invalid input in add_conversation: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error adding conversation: {e}")
            # Re-raise to let caller know the operation failed
            raise RuntimeError(f"Failed to add conversation: {e}") from e
    
    async def add_user_message(self, content: str, user_id: str = "anonymous") -> None:
        """Add user message to unified memory"""
        try:
            await self._initialize_langchain_memory()
            memory = await self._get_unified_memory()
            conversation_id = self.project_slug
            
            await memory.add_message(conversation_id, "user", content, user_id)
            user_msg = HumanMessage(content=content)
            self.messages.append(user_msg)
            
        except Exception as e:
            logger.error(f"Error adding user message: {e}")
    
    async def update_last_ai_response(self, content: str, user_id: str = "anonymous") -> None:
        """Update the last AI response"""
        try:
            await self._initialize_langchain_memory()
            memory = await self._get_unified_memory()
            conversation_id = self.project_slug
            
            await memory.add_message(conversation_id, "assistant", content, user_id)
            
            # Update local state
            if self.messages and isinstance(self.messages[-1], AIMessage):
                self.messages[-1] = AIMessage(content=content)
            else:
                ai_msg = AIMessage(content=content)
                self.messages.append(ai_msg)
            
            self.last_ai_response = content
            
        except Exception as e:
            logger.error(f"Error updating AI response: {e}")
    
    async def get_memory_context(self, limit: int = 10) -> str:
        """Get recent conversation context"""
        try:
            await self._initialize_langchain_memory()
            
            recent_messages = self.messages[-limit:] if self.messages else []
            
            context_parts = []
            for msg in recent_messages:
                if isinstance(msg, HumanMessage):
                    context_parts.append(f"Human: {msg.content}")
                elif isinstance(msg, AIMessage):
                    context_parts.append(f"Assistant: {msg.content}")
            
            return "\n".join(context_parts)
            
        except Exception as e:
            logger.error(f"Error getting memory context: {e}")
            return ""
    
    def get_langchain_messages(self, max_messages: int = 20) -> List[BaseMessage]:
        """Get conversation history as LangChain messages for context."""
        try:
            # If memory is not initialized, log warning and return empty
            if not self._memory_initialized:
                logger.warning(f"Memory not initialized for {self.project_slug}, returning empty messages")
                return []
            
            # Return cached messages (should be loaded during initialization)
            if hasattr(self, 'messages') and self.messages:
                messages = self.messages
                logger.debug(f"Retrieved {len(messages)} cached messages for {self.project_slug}")
                return messages[-max_messages:] if len(messages) > max_messages else messages
            else:
                logger.warning(f"Memory initialized but no cached messages for {self.project_slug}")
                return []
            
        except Exception as e:
            logger.error(f"Error getting langchain messages: {e}")
            return []
    
    async def _reload_messages_from_database(self):
        """Reload messages from database into cache"""
        try:
            memory = await self._get_unified_memory()
            conversation_id = self.project_slug
            
            # Load messages from unified system
            messages_data = await memory.get_conversation(conversation_id)
            
            # Convert to LangChain message format
            self.messages = []
            for msg_data in messages_data:
                if msg_data['role'] == 'user':
                    self.messages.append(HumanMessage(content=msg_data['content']))
                elif msg_data['role'] == 'assistant':
                    self.messages.append(AIMessage(content=msg_data['content']))
                    self.last_ai_response = msg_data['content']
            
            logger.info(f"Reloaded {len(self.messages)} messages from database for {self.project_slug}")
            
        except Exception as e:
            logger.error(f"Error reloading messages from database: {e}")


class CompatibilityMarkdownMemory:
    """
    Drop-in replacement for the original MarkdownMemory class.
    Uses UnifiedMemoryManager under the hood.
    """
    
    def __init__(self, project_slug: str):
        self.project_slug = project_slug
        self.file_path = Path(f"app/memory/{project_slug}.md")  # For compatibility
        self._lock = asyncio.Lock()
        self._unified_memory: Optional[UnifiedMemoryManager] = None
        
        # Session tracking compatibility (simplified)
        self._session_start_time = None
        self._session_user_id = None
        self._session_contributor = None
        self._session_sections_updated = set()
        self._session_timeout = 10 * 60  # 10 minutes
    
    async def _get_unified_memory(self) -> UnifiedMemoryManager:
        """Get unified memory instance"""
        if self._unified_memory is None:
            self._unified_memory = await get_unified_memory()
        return self._unified_memory
    
    async def ensure_file_exists(self) -> None:
        """Ensure project file exists"""
        try:
            memory = await self._get_unified_memory()
            content = await memory.get_project(self.project_slug)
            
            if content is None:
                # Create initial file
                await self._create_initial_file()
                
        except Exception as e:
            logger.error(f"Error ensuring file exists: {e}")
    
    async def _create_initial_file(self, project_description: str = None) -> None:
        """Create initial structured markdown file"""
        try:
            memory = await self._get_unified_memory()
            
            project_name = self.project_slug.replace('-', ' ').title()
            current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            
            if project_description and project_description.strip():
                executive_summary = project_description.strip()
                context_content = project_description.strip()
            else:
                executive_summary = "Please provide more information about this project's purpose, goals, and context. The executive summary will be updated as details are gathered through our conversation."
                context_content = "*Background and motivation for this project*"
            
            content = f"""# {project_name}
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
            
            await memory.save_project(self.project_slug, content)
            logger.info(f"Created initial document for {self.project_slug}")
            
        except Exception as e:
            logger.error(f"Error creating initial file: {e}")
    
    async def read_content(self) -> str:
        """Read the full markdown content"""
        try:
            await self.ensure_file_exists()
            memory = await self._get_unified_memory()
            
            content = await memory.get_project(self.project_slug)
            return content or ""
            
        except Exception as e:
            logger.error(f"Error reading content: {e}")
            return ""
    
    async def update_section(self, section: str, content: str, contributor: str = "User", user_id: str = "anonymous") -> None:
        """Update a specific section of the markdown document"""
        try:
            memory = await self._get_unified_memory()
            
            success = await memory.update_project_section(
                self.project_slug, section, content, contributor, user_id
            )
            
            if success:
                logger.info(f"Successfully updated section '{section}' for {self.project_slug}")
            else:
                logger.error(f"Failed to update section '{section}' for {self.project_slug}")
                
        except Exception as e:
            logger.error(f"Error updating section '{section}': {e}")
    
    async def replace_section(self, section: str, content: str, contributor: str = "User", user_id: str = "anonymous") -> None:
        """Replace entire section content - delegates to update_section for now"""
        # For simplicity, treat replace the same as update in unified system
        await self.update_section(section, content, contributor, user_id)
    
    async def get_document_context(self) -> str:
        """Get current document content for context"""
        return await self.read_content()


class CompatibilityLegacyMemoryWrapper:
    """
    Drop-in replacement for LegacyMemoryWrapper.
    Simplifies to just use compatibility wrappers.
    """
    
    def __init__(self, project_slug: str, modern_memory=None):
        self.project_slug = project_slug
        # Use compatibility conversation memory instead of modern_memory parameter
        self._conversation_memory = CompatibilityConversationMemory(project_slug)
        self.last_ai_response = None
        self._memory_initialized = True
        self._cached_messages = []
    
    async def add_conversation(self, user_input: str, ai_response: str, user_id: str = "anonymous") -> None:
        """Add conversation using compatibility wrapper"""
        await self._conversation_memory.add_conversation(user_input, ai_response, user_id)
        if ai_response:
            self.last_ai_response = ai_response
    
    async def add_user_message(self, content: str, user_id: str = "anonymous") -> None:
        """Add user message"""
        await self._conversation_memory.add_user_message(content, user_id)
    
    async def update_last_ai_response(self, content: str, user_id: str = "anonymous") -> None:
        """Update last AI response"""
        await self._conversation_memory.update_last_ai_response(content, user_id)
        self.last_ai_response = content
    
    async def get_memory_context(self, limit: int = 10) -> str:
        """Get memory context"""
        return await self._conversation_memory.get_memory_context(limit)


class CompatibilityModernConversationMemory:
    """
    Drop-in replacement for ModernConversationMemory.
    Uses UnifiedMemoryManager under the hood.
    """
    
    def __init__(self, db_path: str = "app/memory/conversations.db"):
        self.db_path = Path(db_path)
        self._unified_memory: Optional[UnifiedMemoryManager] = None
    
    async def _get_unified_memory(self) -> UnifiedMemoryManager:
        """Get unified memory instance"""
        if self._unified_memory is None:
            self._unified_memory = await get_unified_memory()
        return self._unified_memory
    
    def get_thread_id(self, project_slug: str, user_id: str = "default") -> str:
        """Generate thread ID for conversation isolation"""
        return f"{project_slug}:{user_id}"
    
    async def add_message(self, project_slug: str, message: BaseMessage, user_id: str = "default") -> None:
        """Add a message to the conversation thread"""
        try:
            memory = await self._get_unified_memory()
            conversation_id = self.get_thread_id(project_slug, user_id)
            
            # Determine message type
            if isinstance(message, HumanMessage):
                role = "user"
            elif isinstance(message, AIMessage):
                role = "assistant"
            else:
                role = "system"
            
            await memory.add_message(conversation_id, role, message.content, user_id)
            
        except Exception as e:
            logger.error(f"Error adding message: {e}")
    
    async def get_messages(self, project_slug: str, user_id: str = "default", limit: Optional[int] = None) -> List[BaseMessage]:
        """Get conversation messages for a thread"""
        try:
            memory = await self._get_unified_memory()
            conversation_id = self.get_thread_id(project_slug, user_id)
            
            messages_data = await memory.get_conversation(conversation_id, limit)
            
            messages = []
            for msg_data in messages_data:
                if msg_data['role'] == 'user':
                    messages.append(HumanMessage(content=msg_data['content']))
                elif msg_data['role'] == 'assistant':
                    messages.append(AIMessage(content=msg_data['content']))
            
            return messages
            
        except Exception as e:
            logger.error(f"Error getting messages: {e}")
            return []
    
    async def clear_conversation(self, project_slug: str, user_id: str = "default") -> None:
        """Clear conversation history - not implemented in unified system yet"""
        logger.warning("Clear conversation not yet implemented in unified memory")


# === Factory Functions for Easy Migration ===

def create_conversation_memory(project_slug: str) -> CompatibilityConversationMemory:
    """Factory function to create conversation memory"""
    return CompatibilityConversationMemory(project_slug)

def create_markdown_memory(project_slug: str) -> CompatibilityMarkdownMemory:
    """Factory function to create markdown memory"""
    return CompatibilityMarkdownMemory(project_slug)

def create_legacy_memory_wrapper(project_slug: str, modern_memory=None) -> CompatibilityLegacyMemoryWrapper:
    """Factory function to create legacy memory wrapper"""
    return CompatibilityLegacyMemoryWrapper(project_slug, modern_memory)

def create_modern_conversation_memory(db_path: str = "app/memory/conversations.db") -> CompatibilityModernConversationMemory:
    """Factory function to create modern conversation memory"""
    return CompatibilityModernConversationMemory(db_path)