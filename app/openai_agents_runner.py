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
import re
from pathlib import Path
from typing import Optional, AsyncGenerator, Dict, Any, List
import aiofiles
import logging

from agents import Agent, Runner, SQLiteSession, function_tool, handoff, RunContextWrapper

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
    
    def _load_prompt_sync(self, prompt_file: str) -> str:
        """Load prompt from file synchronously with fallback."""
        try:
            prompt_path = Path(prompt_file)
            if prompt_path.exists():
                with open(prompt_path, 'r', encoding='utf-8') as f:
                    return f.read()
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
    async def update_project_document(
        ctx: RunContextWrapper,
        project_slug: str, 
        section: str, 
        content: str
    ) -> str:
        """Update project markdown document with new information.
        
        Args:
            project_slug: The project identifier
            section: The section name to update
            content: The new content for the section
            
        Returns:
            Confirmation message about the update
        """
        try:
            import re
            from datetime import datetime
            
            file_path = Path(f"app/memory/{project_slug}.md")
            
            # Read existing content
            if file_path.exists():
                async with aiofiles.open(file_path, 'r', encoding='utf-8') as f:
                    existing_content = await f.read()
            else:
                existing_content = f"# {project_slug.replace('-', ' ').title()} Project\n\n"
            
            # Smart section update - append to existing or create new (inline implementation)
            section_pattern = rf'^## {re.escape(section)}\s*\n(.*?)(?=^## |\Z)'
            
            if re.search(section_pattern, existing_content, re.MULTILINE | re.DOTALL):
                # Section exists, append to it
                def replace_section(match):
                    section_header = f"## {section}\n"
                    existing_section_content = match.group(1).strip()
                    # Don't add if content already exists to avoid duplicates
                    if content.strip() in existing_section_content:
                        return f"{section_header}{existing_section_content}\n\n"
                    # Append new content to existing
                    combined_content = f"{existing_section_content}\n\n{content}".strip()
                    return f"{section_header}{combined_content}\n\n"
                
                updated_content = re.sub(section_pattern, replace_section, existing_content, flags=re.MULTILINE | re.DOTALL)
            else:
                # Section doesn't exist, add it at the end
                updated_content = f"{existing_content.rstrip()}\n\n## {section}\n\n{content}\n\n"
            
            # Write updated content
            async with aiofiles.open(file_path, 'w', encoding='utf-8') as f:
                await f.write(updated_content)
            
            return f"Updated section '{section}' in project {project_slug}"
            
        except Exception as e:
            logger.error(f"Error updating project document: {e}")
            return f"Error updating document: {str(e)}"

    @function_tool
    async def read_project_document(
        ctx: RunContextWrapper,
        project_slug: str
    ) -> str:
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

    async def _update_markdown_section(self, content: str, section: str, new_content: str) -> str:
        """Update a specific section in markdown content, appending to existing content.
        
        Args:
            content: The current markdown content
            section: The section name to update
            new_content: The new content to append
            
        Returns:
            Updated markdown content
        """
        import re
        from datetime import datetime
        
        # Add timestamp for tracking
        current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        # Look for existing section header (## Section Name)
        section_pattern = rf'^## {re.escape(section)}\s*\n(.*?)(?=^## |\Z)'
        
        if re.search(section_pattern, content, re.MULTILINE | re.DOTALL):
            # Section exists, append to it
            def replace_section(match):
                section_header = f"## {section}\n"
                existing_content = match.group(1).strip()
                # Don't add if content already exists to avoid duplicates
                if new_content.strip() in existing_content:
                    return f"{section_header}{existing_content}\n\n"
                # Append new content to existing
                combined_content = f"{existing_content}\n\n{new_content}".strip()
                return f"{section_header}{combined_content}\n\n"
            
            updated_content = re.sub(section_pattern, replace_section, content, flags=re.MULTILINE | re.DOTALL)
        else:
            # Section doesn't exist, add it at the end
            updated_content = f"{content.rstrip()}\n\n## {section}\n\n{new_content}\n\n"
        
        return updated_content

    def _setup_agents(self):
        """Initialize the OpenAI Agents SDK agents with proper orchestration."""
        
        # Info Agent - specialized for document operations
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
        
        # Main Agent - handles conversations and delegates to specialized agents
        # Load instructions from the actual prompt file (sync to avoid event loop issues)
        instructions = self._load_prompt_sync("prompts/conversational_nai_agent.md")
        
        # Phase 2.4: Give Main Agent direct access to tools to fix handoff issues
        # The o3 model seems to hallucinate tool calls instead of doing handoffs properly
        self.main_agent = Agent(
            name="NAI Project Planner",
            instructions=f"""{instructions}

IMPORTANT: When users provide project information that should be documented, use the update_project_document tool to save it to the appropriate section.

CRITICAL: When updating existing sections, pass ONLY the new content to the tool, not the complete content. The tool will automatically append new content to existing sections. Do NOT read existing content and combine it - just pass the new items that need to be added.""",
            model=os.getenv("DEFAULT_MODEL", "gpt-4o-mini"),  # Use gpt-4o-mini for more reliable tool usage
            tools=[self.update_project_document, self.read_project_document],  # Direct tool access
            handoffs=[
                handoff(self.info_agent, tool_name_override="update_documentation")  # Keep as backup
            ]
        )
        
        # Keep chat_agent as alias for backward compatibility
        self.chat_agent = self.main_agent

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
            
            # Use model override if provided - start with main agent (orchestrator)
            agent = self.main_agent
            if model and model != agent.model:
                # Create a temporary agent with different model
                agent = Agent(
                    name=self.main_agent.name,
                    instructions=self.main_agent.instructions,
                    model=model,
                    tools=self.main_agent.tools,
                    handoffs=getattr(self.main_agent, 'handoffs', [])
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
            Streaming response chunks formatted for SSE
        """
        try:
            session = self.get_session(project_slug)
            
            # Use model override if provided - start with main agent (orchestrator)
            agent = self.main_agent
            if model and model != agent.model:
                # Create a temporary agent with different model
                agent = Agent(
                    name=self.main_agent.name,
                    instructions=self.main_agent.instructions,
                    model=model,
                    tools=self.main_agent.tools,
                    handoffs=getattr(self.main_agent, 'handoffs', [])
                )
            
            # Run streaming conversation with session memory
            result = Runner.run_streamed(agent, user_message, session=session)
            
            # Track streaming state
            has_started = False
            content_buffer = []
            
            # Stream the response using SDK's built-in event handling
            async for event in result.stream_events():
                if event.type == "raw_response_event":
                    # Handle token-by-token streaming as per SDK documentation
                    if hasattr(event.data, 'delta') and event.data.delta:
                        has_started = True
                        content_buffer.append(event.data.delta)
                        yield event.data.delta
                        
                elif event.type == "run_item_stream_event" and not has_started:
                    # Only handle structured events if we haven't started raw streaming
                    if hasattr(event, 'item') and event.item:
                        item = event.item
                        
                        # Use SDK's built-in item type handling
                        if item.type == "message_output_item":
                            # Extract message content using SDK helper if available
                            try:
                                from agents import ItemHelpers
                                message_output = ItemHelpers.text_message_output(item)
                                if message_output:
                                    for char in str(message_output):
                                        yield char
                                    has_started = True
                            except (ImportError, AttributeError):
                                # Fallback if ItemHelpers not available
                                if hasattr(item, 'content') and item.content:
                                    for char in str(item.content):
                                        yield char
                                    has_started = True
                                        
                elif event.type == "run_item_stream_event":
                    # Handle tool and handoff events regardless of streaming state
                    if hasattr(event, 'item') and event.item:
                        item = event.item
                        
                        if item.type == "tool_call_item":
                            # Indicate tool execution as per SDK patterns
                            tool_indicator = f"\n\n[Tool executing...]\n"
                            for char in tool_indicator:
                                yield char
                                        
                        elif item.type == "handoff_call_item":
                            # Indicate agent handoff
                            handoff_indicator = f"\n\n[Transferring to another agent...]\n"
                            for char in handoff_indicator:
                                yield char
            
            # Ensure we yielded something
            if not has_started and not content_buffer:
                # Fallback: try to get final output
                if hasattr(result, 'final_output'):
                    final_output = await result.final_output if asyncio.iscoroutine(result.final_output) else result.final_output
                    if final_output:
                        for char in str(final_output):
                            yield char
                else:
                    yield "I apologize, but I couldn't generate a response. Please try again."
                    
        except Exception as e:
            error_msg = f"Error: {str(e)}"
            logger.error(f"Error in streaming conversation: {e}")
            for char in error_msg:
                yield char

    async def parse_markdown_conversation(self, md_file: Path) -> List[Dict[str, Any]]:
        """Parse existing markdown conversation into SQLiteSession format.
        
        Args:
            md_file: Path to the markdown file
            
        Returns:
            List of conversation items in OpenAI format
        """
        conversation_items = []
        
        try:
            async with aiofiles.open(md_file, 'r', encoding='utf-8') as f:
                content = await f.read()
            
            if not content.strip():
                return conversation_items
            
            # Add project document as system context
            conversation_items.append({
                "role": "system", 
                "content": f"Project document for {md_file.stem}:\n\n{content}"
            })
            
            # The markdown files in this system are primarily project documents
            # not conversation logs. However, we can extract some conversational
            # context from Change Log entries and Recent Updates
            
            # Look for conversation patterns in Change Log
            change_log_pattern = r'\| (\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) \| ([^|]+) \| ([^|]+) \| ([^|]+) \|'
            matches = re.findall(change_log_pattern, content)
            
            for match in matches:
                timestamp, contributor, user_id, summary = match
                contributor = contributor.strip()
                user_id = user_id.strip()
                summary = summary.strip()
                
                # Skip system entries for now
                if contributor.lower() != 'system':
                    # Create a synthetic conversation based on the change log
                    conversation_items.append({
                        "role": "user",
                        "content": f"Please update the project document: {summary}"
                    })
                    conversation_items.append({
                        "role": "assistant", 
                        "content": f"I've updated the project document as requested. The change has been logged on {timestamp}."
                    })
            
            # Look for Recent Updates section content
            recent_updates_pattern = r'## Recent Updates\s*\n(.*?)(?=\n##|\n---|$)'
            recent_match = re.search(recent_updates_pattern, content, re.DOTALL)
            
            if recent_match and recent_match.group(1).strip() != '*Latest changes and additions to this document*':
                updates_content = recent_match.group(1).strip()
                if updates_content:
                    conversation_items.append({
                        "role": "assistant",
                        "content": f"Recent project updates: {updates_content}"
                    })
            
            return conversation_items
            
        except Exception as e:
            logger.error(f"Error parsing markdown conversation from {md_file}: {e}")
            return []

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
            
            # Check if already migrated by looking for existing items
            existing_items = await session.get_items(limit=1)
            if existing_items:
                logger.info(f"Conversation for project {project_slug} already migrated")
                return True
            
            # Parse existing markdown and add to session
            conversation_items = await self.parse_markdown_conversation(md_file)
            
            if conversation_items:
                await session.add_items(conversation_items)
                logger.info(f"Migrated {len(conversation_items)} conversation items for project {project_slug}")
            else:
                # Even if no conversation items, add project context
                async with aiofiles.open(md_file, 'r', encoding='utf-8') as f:
                    content = await f.read()
                
                if content.strip():
                    await session.add_items([{
                        "role": "system",
                        "content": f"Project document for {project_slug}:\n\n{content}"
                    }])
                    logger.info(f"Added project context for {project_slug}")
            
            return True
            
        except Exception as e:
            logger.error(f"Error migrating conversation for {project_slug}: {e}")
            return False

    async def migrate_from_unified_db(self, project_slug: str) -> bool:
        """Migrate conversation data from unified database to SQLiteSession.
        
        Args:
            project_slug: The project identifier
            
        Returns:
            True if migration successful, False otherwise
        """
        try:
            import aiosqlite
            
            session = self.get_session(project_slug)
            
            # Check if already migrated
            existing_items = await session.get_items(limit=1)
            if existing_items:
                logger.info(f"Conversation for project {project_slug} already migrated from unified DB")
                return True
            
            # Connect to unified database
            unified_db_path = Path("app/memory/unified.db")
            if not unified_db_path.exists():
                logger.info(f"No unified database found for {project_slug}")
                return True
            
            conversation_items = []
            
            async with aiosqlite.connect(str(unified_db_path)) as conn:
                # Query conversations for this project
                cursor = await conn.execute("""
                    SELECT role, content, timestamp, user_id, metadata 
                    FROM conversations 
                    WHERE conversation_id LIKE ? 
                    ORDER BY timestamp ASC
                """, (f"{project_slug}:%",))
                
                rows = await cursor.fetchall()
                
                for row in rows:
                    role, content, timestamp, user_id, metadata = row
                    
                    # Convert to OpenAI format
                    conversation_items.append({
                        "role": role,
                        "content": content
                    })
            
            if conversation_items:
                await session.add_items(conversation_items)
                logger.info(f"Migrated {len(conversation_items)} conversation items from unified DB for project {project_slug}")
                return True
            else:
                logger.info(f"No conversation data found in unified DB for project {project_slug}")
                return True
                
        except Exception as e:
            logger.error(f"Error migrating from unified DB for {project_slug}: {e}")
            return False

    async def migrate_conversations(self) -> Dict[str, Any]:
        """Migration script: Convert existing markdown conversations to SQLiteSession.
        
        This function migrates from both:
        1. Markdown files (project documents)
        2. Unified database (actual conversation history)
        
        Returns:
            Dictionary with migration results
        """
        results = {
            "migrated": [],
            "failed": [],
            "skipped": [],
            "total_processed": 0,
            "markdown_migrated": 0,
            "unified_db_migrated": 0
        }
        
        try:
            memory_dir = Path("app/memory")
            if not memory_dir.exists():
                logger.info("No memory directory found, nothing to migrate")
                return results
            
            # Get list of all projects from markdown files
            project_slugs = set()
            for md_file in memory_dir.glob("*.md"):
                project_slugs.add(md_file.stem)
            
            logger.info(f"Found {len(project_slugs)} projects to migrate")
            
            # Process each project
            for project_slug in project_slugs:
                results["total_processed"] += 1
                logger.info(f"Migrating project: {project_slug}")
                
                try:
                    # First, try to migrate from unified database (actual conversations)
                    unified_success = await self.migrate_from_unified_db(project_slug)
                    if unified_success:
                        results["unified_db_migrated"] += 1
                    
                    # Then, migrate markdown project document as context
                    markdown_success = await self.migrate_existing_conversation(project_slug)
                    if markdown_success:
                        results["markdown_migrated"] += 1
                    
                    if unified_success and markdown_success:
                        results["migrated"].append(project_slug)
                        logger.info(f"✅ Successfully migrated {project_slug} (unified DB + markdown)")
                    else:
                        results["failed"].append(project_slug)
                        logger.warning(f"⚠️  Partial migration failure for {project_slug}")
                        
                except Exception as e:
                    results["failed"].append(project_slug)
                    logger.error(f"❌ Error migrating {project_slug}: {e}")
            
            logger.info(f"""Migration complete: 
                {len(results['migrated'])} projects fully migrated
                {results['unified_db_migrated']} unified DB migrations
                {results['markdown_migrated']} markdown migrations
                {len(results['failed'])} failed""")
                
            return results
            
        except Exception as e:
            logger.error(f"Error in migration process: {e}")
            results["failed"].append("MIGRATION_PROCESS_ERROR")
            return results


# Global instance
openai_runner = OpenAIAgentsRunner()


async def get_openai_runner() -> OpenAIAgentsRunner:
    """Get the global OpenAI Agents runner instance."""
    return openai_runner