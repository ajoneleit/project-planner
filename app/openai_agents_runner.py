"""
OpenAI Agents SDK implementation to replace LangGraph workflow.

This module provides the new agent system using OpenAI Agents SDK with:
- SQLiteSession for automatic conversation memory management
- Streaming support for real-time responses
- Tool integration for markdown file operations
- Agent handoffs for multi-agent workflows
"""

import os
import asyncio
from pathlib import Path
from typing import Optional, AsyncGenerator, Dict, Any
import aiofiles
import logging

from agents import Agent, Runner, SQLiteSession, function_tool

logger = logging.getLogger(__name__)


class OpenAIAgentsRunner:
    """OpenAI Agents SDK runner that replaces LangGraph workflow."""
    
    def __init__(self):
        self.conversations_db = Path("app/memory/conversations.db")
        self.conversations_db.parent.mkdir(parents=True, exist_ok=True)
        
        # Initialize agents
        self.chat_agent = None
        self.info_agent = None
        self._setup_agents()
    
    async def _load_prompt(self, prompt_file: str) -> str:
        """Load prompt from file with fallback."""
        try:
            prompt_path = Path(prompt_file)
            if prompt_path.exists():
                async with aiofiles.open(prompt_path, 'r', encoding='utf-8') as f:
                    return await f.read()
            else:
                logger.warning(f"Prompt file {prompt_file} not found, using fallback")
                return self._get_fallback_prompt()
        except Exception as e:
            logger.error(f"Error loading prompt from {prompt_file}: {e}")
            return self._get_fallback_prompt()
    
    def _get_fallback_prompt(self) -> str:
        """Fallback prompt if file loading fails."""
        return """# Conversational NAI Problem-Definition Assistant

You are the "Conversational NAI Problem-Definition Assistant," a professional, politely persistent coach whose mission is to help North Atlantic Industries (NAI) employees turn hazy ideas, pain-points, or requirements into clear, living Markdown documents that any teammate can extend efficiently."""

    @function_tool
    async def update_project_document(self, project_slug: str, section: str, content: str) -> str:
        """Update project markdown document with new information.
        
        Args:
            project_slug: The project identifier
            section: The section name to update
            content: The new content for the section
            
        Returns:
            Confirmation message about the update
        """
        try:
            file_path = Path(f"app/memory/{project_slug}.md")
            
            # Read existing content
            if file_path.exists():
                async with aiofiles.open(file_path, 'r', encoding='utf-8') as f:
                    existing_content = await f.read()
            else:
                existing_content = f"# {project_slug.replace('-', ' ').title()} Project\n\n"
            
            # Simple section update logic - append new content
            updated_content = f"{existing_content}\n\n## {section}\n\n{content}\n"
            
            # Write updated content
            async with aiofiles.open(file_path, 'w', encoding='utf-8') as f:
                await f.write(updated_content)
            
            return f"Updated section '{section}' in project {project_slug}"
            
        except Exception as e:
            logger.error(f"Error updating project document: {e}")
            return f"Error updating document: {str(e)}"

    @function_tool
    async def read_project_document(self, project_slug: str) -> str:
        """Read the current project document content.
        
        Args:
            project_slug: The project identifier
            
        Returns:
            The current document content or error message
        """
        try:
            file_path = Path(f"app/memory/{project_slug}.md")
            
            if file_path.exists():
                async with aiofiles.open(file_path, 'r', encoding='utf-8') as f:
                    content = await f.read()
                return content
            else:
                return f"No project document found for {project_slug}"
                
        except Exception as e:
            logger.error(f"Error reading project document: {e}")
            return f"Error reading document: {str(e)}"

    def _setup_agents(self):
        """Initialize the OpenAI Agents SDK agents."""
        
        # Info Agent - handles document updates
        self.info_agent = Agent(
            name="NAI Info Agent",
            instructions="""You are the Info Agent responsible for extracting and documenting project information.

Your responsibilities:
- Extract key project information from conversations
- Update project documents with relevant details
- Organize information into clear sections
- Maintain document consistency and quality

When users provide project information, automatically extract and document it without asking for permission.""",
            model=os.getenv("DEFAULT_MODEL", "gpt-4o-mini"),  # Use cheaper model for document operations
            tools=[self.update_project_document, self.read_project_document]
        )
        
        # Chat Agent - handles conversations and delegates to Info Agent
        self.chat_agent = Agent(
            name="NAI Chat Agent", 
            instructions="""You are the NAI Conversational Assistant focused on intelligent conversation about project planning.

Your responsibilities:
- Have natural, helpful conversations about project planning using NAI methodology
- Answer user questions about their project based on available context
- Make recommendations and provide guidance using NAI principles
- Ask clarifying questions to understand requirements better
- Reference previous conversation naturally when relevant
- When users provide project information that should be documented, use the Info Agent

You do NOT directly update documents - delegate that to the Info Agent when needed.""",
            model=os.getenv("DEFAULT_MODEL", "o3"),
            tools=[],
            handoffs=[self.info_agent] if hasattr(Agent, 'handoffs') else []  # Handle if handoffs not available
        )

    def get_session(self, project_slug: str) -> SQLiteSession:
        """Get or create a SQLiteSession for the project.
        
        Args:
            project_slug: The project identifier
            
        Returns:
            SQLiteSession instance for this project
        """
        return SQLiteSession(f"project_{project_slug}", str(self.conversations_db))

    async def run_conversation(
        self, 
        project_slug: str, 
        user_message: str,
        model: Optional[str] = None
    ) -> Dict[str, Any]:
        """Run a conversation with the agent system.
        
        Args:
            project_slug: The project identifier
            user_message: The user's message
            model: Optional model override
            
        Returns:
            Dictionary with conversation result
        """
        try:
            session = self.get_session(project_slug)
            
            # Use model override if provided
            agent = self.chat_agent
            if model and model != agent.model:
                # Create a temporary agent with different model
                agent = Agent(
                    name=self.chat_agent.name,
                    instructions=self.chat_agent.instructions,
                    model=model,
                    tools=self.chat_agent.tools,
                    handoffs=getattr(self.chat_agent, 'handoffs', [])
                )
            
            # Run the conversation with session memory
            result = await Runner.run(agent, user_message, session=session)
            
            return {
                "success": True,
                "response": result.final_output,
                "agent_used": result.last_agent.name if hasattr(result, 'last_agent') else agent.name
            }
            
        except Exception as e:
            logger.error(f"Error in conversation: {e}")
            return {
                "success": False,
                "error": str(e),
                "response": "I'm sorry, I encountered an error processing your request."
            }

    async def run_conversation_stream(
        self, 
        project_slug: str, 
        user_message: str,
        model: Optional[str] = None
    ) -> AsyncGenerator[str, None]:
        """Run a streaming conversation with the agent system.
        
        Args:
            project_slug: The project identifier
            user_message: The user's message
            model: Optional model override
            
        Yields:
            Streaming response chunks
        """
        try:
            session = self.get_session(project_slug)
            
            # Use model override if provided
            agent = self.chat_agent
            if model and model != agent.model:
                # Create a temporary agent with different model
                agent = Agent(
                    name=self.chat_agent.name,
                    instructions=self.chat_agent.instructions,
                    model=model,
                    tools=self.chat_agent.tools,
                    handoffs=getattr(self.chat_agent, 'handoffs', [])
                )
            
            # Run streaming conversation with session memory
            result = Runner.run_streamed(agent, user_message, session=session)
            
            # Stream the response
            async for event in result.stream_events():
                if event.type == "raw_response_event":
                    if hasattr(event.data, 'delta') and event.data.delta:
                        yield event.data.delta
                elif event.type == "run_item_stream_event":
                    # Handle other event types if needed
                    pass
                    
        except Exception as e:
            logger.error(f"Error in streaming conversation: {e}")
            yield f"Error: {str(e)}"

    async def migrate_existing_conversation(self, project_slug: str) -> bool:
        """Migrate existing markdown conversation to SQLiteSession.
        
        Args:
            project_slug: The project identifier
            
        Returns:
            True if migration successful, False otherwise
        """
        try:
            md_file = Path(f"app/memory/{project_slug}.md")
            if not md_file.exists():
                return True  # No existing conversation to migrate
            
            session = self.get_session(project_slug)
            
            # Simple migration - read existing markdown and add as context
            async with aiofiles.open(md_file, 'r', encoding='utf-8') as f:
                content = await f.read()
            
            # Add existing content as initial context
            if content.strip():
                await session.add_items([{
                    "role": "system",
                    "content": f"Existing project context:\n\n{content}"
                }])
            
            logger.info(f"Migrated conversation for project {project_slug}")
            return True
            
        except Exception as e:
            logger.error(f"Error migrating conversation for {project_slug}: {e}")
            return False


# Global instance
openai_runner = OpenAIAgentsRunner()


async def get_openai_runner() -> OpenAIAgentsRunner:
    """Get the global OpenAI Agents runner instance."""
    return openai_runner