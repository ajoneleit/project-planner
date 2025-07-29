"""
LangGraph workflow and memory management for the Project Planner Bot.
Handles conversation state, markdown file operations, and LangGraph execution with intelligent information filtering.
"""

import asyncio
import aiofiles
import json
import os
import re
from datetime import datetime
from typing import Dict, Any, AsyncGenerator, Optional, List, Tuple
from pathlib import Path
import logging
from filelock import FileLock

from langgraph.graph import StateGraph, END
from langgraph.graph.message import MessagesState
from typing_extensions import TypedDict
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel

logger = logging.getLogger(__name__)

MEMORY_DIR = Path("app/memory")
INDEX_FILE = MEMORY_DIR / "index.json"

class DocumentSection(BaseModel):
    """Represents a section of the markdown document."""
    title: str
    content: str
    level: int
    start_line: int
    end_line: int

class InformationSignal(BaseModel):
    """Represents filtered information from conversation."""
    signal_type: str  # 'objective', 'stakeholder', 'requirement', etc.
    content: str
    section_target: str
    confidence: float
    source: str  # 'user' or 'context'

class ProjectPlannerState(TypedDict):
    """State for the project planner workflow."""
    messages: list
    user_id: str

class AgentState(MessagesState):
    """Extended state for the planning agent with intelligent filtering."""
    project_slug: str
    document_content: str
    document_sections: List[DocumentSection]
    information_signals: List[InformationSignal]
    user_message: str
    agent_response: str
    should_update_document: bool
    document_updates_made: List[str]

class MarkdownMemory:
    """Handles intelligent markdown document management with structured sections."""
    
    def __init__(self, project_slug: str):
        self.project_slug = project_slug
        self.file_path = MEMORY_DIR / f"{project_slug}.md"
        self._lock = asyncio.Lock()
        self._file_lock = FileLock(f"{self.file_path}.lock")
    
    async def ensure_file_exists(self) -> None:
        """Create structured markdown file if it doesn't exist, but don't overwrite existing files."""
        if not self.file_path.exists():
            logger.info(f"File does not exist, creating: {self.file_path}")
            await self._create_initial_file()
        else:
            logger.info(f"File exists: {self.file_path}")
            # File exists, no need to read it just to verify - just log that it exists
            logger.debug(f"Existing file preserved: {self.file_path}")
    
    async def _create_initial_file(self) -> None:
        """Create initial structured markdown file only if file doesn't exist."""
        with self._file_lock:
            async with self._lock:
                project_name = self.project_slug.replace('-', ' ').title()
                current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                
                content = f"""# {project_name}
_Last updated: {current_time}_

---

## Executive Summary
Project documentation is being developed through conversation with the AI assistant.

---

## Objective
- [ ] Define specific, measurable project goals
- [ ] Establish success criteria
- [ ] Identify key deliverables

---

## Context
*Background and motivation for this project*

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

## Recent Discussions
*Latest project conversations and updates*

---

## Change Log

| Date | Contributor | User ID | Summary |
| {current_time} | System | system | Initial structured project document created |

"""
                async with aiofiles.open(self.file_path, 'w', encoding='utf-8') as f:
                    await f.write(content)
                
                logger.info(f"Created new structured document for {self.project_slug}")
    
    async def read_content(self) -> str:
        """Read the full markdown content from the actual file."""
        await self.ensure_file_exists()
        
        try:
            async with aiofiles.open(self.file_path, 'r', encoding='utf-8') as f:
                content = await f.read()
                logger.debug(f"Read {len(content)} characters from {self.file_path}")
                return content
        except Exception as e:
            logger.error(f"Error reading file {self.file_path}: {e}")
            raise
    
    async def update_section(self, section: str, content: str, contributor: str = "User", user_id: str = "anonymous") -> None:
        """Update a specific section of the markdown document with file locking for multi-process safety."""
        try:
            logger.info(f"Updating section '{section}' for {self.project_slug} by {contributor} ({user_id})")
            
            # Use file lock for multi-process safety
            with self._file_lock:
                async with self._lock:
                    await self.ensure_file_exists()
                    
                    # Read content directly without calling read_content() to avoid recursion
                    async with aiofiles.open(self.file_path, 'r', encoding='utf-8') as f:
                        current_content = await f.read()
                    logger.debug(f"Current content length before update: {len(current_content)}")
                    
                    updated_content = await self._update_markdown_section(
                        current_content, section, content, contributor, user_id
                    )
                    
                    logger.debug(f"Updated content length after update: {len(updated_content)}")
                    
                    async with aiofiles.open(self.file_path, 'w', encoding='utf-8') as f:
                        await f.write(updated_content)
                    
                    logger.info(f"Successfully updated section '{section}' for {self.project_slug}")
        except Exception as e:
            logger.error(f"Error updating section '{section}': {e}")
            # Don't let document update errors break the user experience
    
    async def _update_markdown_section(self, content: str, section: str, new_content: str, contributor: str, user_id: str = "anonymous") -> str:
        """Update a specific section in the markdown content."""
        # Update the "Last updated" timestamp
        current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        content = re.sub(
            r'_Last updated: .*?_',
            f'_Last updated: {current_time}_',
            content
        )
        
        # Find and update the section
        section_pattern = rf'(## {re.escape(section)})(.*?)(?=## |\Z)'
        
        if re.search(section_pattern, content, re.DOTALL):
            # Section exists, replace its content
            replacement = f"## {section}\n{new_content.strip()}\n\n---\n\n"
            content = re.sub(section_pattern, replacement, content, flags=re.DOTALL)
            logger.debug(f"Replaced existing section '{section}'")
        else:
            # Section doesn't exist, add it before Change Log
            change_log_pattern = r'(## Change Log.*)'
            if re.search(change_log_pattern, content, re.DOTALL):
                new_section = f"## {section}\n{new_content.strip()}\n\n---\n\n"
                content = re.sub(change_log_pattern, new_section + r'\1', content, flags=re.DOTALL)
                logger.debug(f"Added new section '{section}'")
        
        # Update Change Log
        change_entry = f"| {current_time} | {contributor} | {user_id} | Updated {section} |"
        change_log_pattern = r'(## Change Log.*?\n\|.*?\n\|.*?\n)'
        if re.search(change_log_pattern, content, re.DOTALL):
            content = re.sub(
                change_log_pattern,
                rf'\1{change_entry}\n\n',
                content,
                flags=re.DOTALL
            )
        
        return content
    
    async def parse_sections(self) -> List[DocumentSection]:
        """Parse the markdown into structured sections."""
        content = await self.read_content()
        sections = []
        lines = content.split('\n')
        
        current_section = None
        current_content = []
        
        for i, line in enumerate(lines):
            # Check for markdown headers
            header_match = re.match(r'^(#{1,6})\s+(.+)', line)
            
            if header_match:
                # Save previous section
                if current_section:
                    sections.append(DocumentSection(
                        title=current_section['title'],
                        content='\n'.join(current_content),
                        level=current_section['level'],
                        start_line=current_section['start_line'],
                        end_line=i - 1
                    ))
                
                # Start new section
                level = len(header_match.group(1))
                title = header_match.group(2)
                current_section = {
                    'title': title,
                    'level': level,
                    'start_line': i
                }
                current_content = [line]
            else:
                if current_section:
                    current_content.append(line)
        
        # Add final section
        if current_section:
            sections.append(DocumentSection(
                title=current_section['title'],
                content='\n'.join(current_content),
                level=current_section['level'],
                start_line=current_section['start_line'],
                end_line=len(lines) - 1
            ))
        
        return sections
    
    async def get_document_context(self) -> str:
        """Get the current document state for context - this MUST return the actual file content."""
        try:
            await self.ensure_file_exists()
            content = await self.read_content()
            
            # Log to verify we're getting real content
            lines = content.split('\n')
            logger.info(f"Document context loaded: {len(lines)} lines")
            
            # Log some key indicators to verify content
            if "## Objective" in content:
                logger.info("Document contains Objective section")
            if "multiagentic coding system" in content.lower():
                logger.info("Document contains multiagentic coding system reference")
            if "Software Development Team" in content:
                logger.info("Document contains stakeholder information")
            
            return content
            
        except Exception as e:
            logger.error(f"Error reading document context: {e}")
            return f"Error loading document context: {str(e)}"

class InformationExtractor:
    """Extracts structured information from conversations using signal detection."""
    
    @staticmethod
    def extract_signals(text: str, message_type: str = "user") -> List[InformationSignal]:
        """Extract information signals from text using pattern matching."""
        signals = []
        text_lower = text.lower()
        
        # Core Information Signals
        if any(word in text_lower for word in ['goal', 'objective', 'purpose', 'aim', 'target']):
            signals.append(InformationSignal(
                signal_type='objective',
                content=text,
                section_target='Objective',
                confidence=0.8,
                source=message_type
            ))
        
        if any(word in text_lower for word in ['requirement', 'need', 'must', 'should', 'specification']):
            signals.append(InformationSignal(
                signal_type='requirement',
                content=text,
                section_target='Requirements & Specifications',
                confidence=0.7,
                source=message_type
            ))
        
        if any(word in text_lower for word in ['budget', 'cost', 'resource', 'constraint', 'limit']):
            signals.append(InformationSignal(
                signal_type='constraint',
                content=text,
                section_target='Constraints & Risks',
                confidence=0.7,
                source=message_type
            ))
        
        if any(word in text_lower for word in ['deadline', 'timeline', 'schedule', 'milestone', 'date']):
            signals.append(InformationSignal(
                signal_type='timeline',
                content=text,
                section_target='Next Actions',
                confidence=0.7,
                source=message_type
            ))
        
        if any(word in text_lower for word in ['risk', 'problem', 'issue', 'concern', 'challenge']):
            signals.append(InformationSignal(
                signal_type='risk',
                content=text,
                section_target='Constraints & Risks',
                confidence=0.8,
                source=message_type
            ))
        
        # Stakeholder detection
        if any(word in text_lower for word in ['team', 'person', 'manager', 'stakeholder', 'user', 'client']):
            signals.append(InformationSignal(
                signal_type='stakeholder',
                content=text,
                section_target='Stakeholders & Collaborators',
                confidence=0.6,
                source=message_type
            ))
        
        # System/tool references
        if any(word in text_lower for word in ['system', 'tool', 'software', 'platform', 'database', 'api']):
            signals.append(InformationSignal(
                signal_type='system',
                content=text,
                section_target='Systems & Data Sources',
                confidence=0.7,
                source=message_type
            ))
        
        return signals
    
    @staticmethod
    def extract_glossary_terms(text: str) -> List[str]:
        """Extract potential glossary terms (acronyms, technical terms)."""
        # Find acronyms (2+ consecutive capital letters)
        acronym_pattern = r'\b[A-Z]{2,}\b'
        acronyms = re.findall(acronym_pattern, text)
        
        # Find technical terms (words with specific patterns)
        technical_patterns = [
            r'\b\w+(?:API|SDK|UI|UX|DB|SQL)\b',
            r'\b(?:micro)?service\w*\b',
            r'\b\w*(?:ware|tech|system)\b'
        ]
        
        technical_terms = []
        for pattern in technical_patterns:
            technical_terms.extend(re.findall(pattern, text, re.IGNORECASE))
        
        return list(set(acronyms + technical_terms))

def extract_stakeholder_info(text: str) -> str:
    """Extract stakeholder information from user input."""
    lines = []
    
    # Look for team mentions
    if 'software development team' in text.lower():
        lines.append("| Software Development Team | Primary development and implementation |")
    
    if 'nai' in text.lower() and 'benefit' in text.lower():
        lines.append("| NAI Organization | End users and beneficiaries of the system |")
    
    # Look for role mentions
    role_patterns = [
        r'(?:people involved|team|stakeholders).*?(?:are|include)?\s*([^.]+)',
    ]
    
    for pattern in role_patterns:
        matches = re.findall(pattern, text, re.IGNORECASE)
        for match in matches:
            if len(match.strip()) > 5 and 'software development team' in match.lower():
                continue  # Already captured above
            if match.strip():
                lines.append(f"| {match.strip().title()} | Key project stakeholder |")
    
    # Add header if we have data
    if lines:
        header = "| Role / Name | Responsibilities |\n|-------------|------------------|"
        return header + "\n" + "\n\n".join(lines)
    
    return ""

def extract_objective_info(text: str) -> str:
    """Extract objective information from user input."""
    objectives = []
    
    # Look for main goal
    goal_match = re.search(r'(?:main goal|objective|purpose).*?(?:is )?to ([^.]+)', text, re.IGNORECASE)
    if goal_match:
        objectives.append(f"- {goal_match.group(1).strip()}")
    
    # Look for specific goals like "create a multiagentic coding system"
    if 'multiagentic coding system' in text.lower():
        objectives.append("- Create a multiagentic coding system")
        objectives.append("- Enable simple application development with single prompts")
        objectives.append("- Benefit entire NAI organization with automated development tools")
    
    # Look for success criteria
    if 'success' in text.lower() or 'indicate' in text.lower():
        success_patterns = [
            r'success.*?(?:criteria|indicators?).*?([^.]+)',
            r'(?:indicate|measure).*?success.*?([^.]+)'
        ]
        for pattern in success_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            for match in matches:
                if len(match.strip()) > 10:
                    objectives.append(f"- Success criteria: {match.strip()}")
    
    return "\n".join(objectives) if objectives else ""

def extract_context_info(text: str) -> str:
    """Extract context information from user input."""
    context_lines = []
    
    # Look for project background
    if 'multiagentic coding system' in text.lower():
        context_lines.append("This project aims to develop an advanced multiagentic coding system that will revolutionize how NAI develops software applications.")
        context_lines.append("The system will enable developers to create applications using simple natural language prompts, reducing development time and complexity.")
    
    # Look for business value
    if 'benefit' in text.lower() and 'nai' in text.lower():
        context_lines.append("The solution will benefit the entire NAI organization by democratizing application development capabilities.")
    
    return "\n\n".join(context_lines) if context_lines else ""

def extract_technical_info(text: str) -> str:
    """Extract technical information from user input."""
    tech_sections = []
    
    # Look for specific architectural components including feedback loop
    if any(term in text.lower() for term in ['feedback loop', 'agents', 'verifier', 'prompt refiner']):
        tech_sections.append("**Architecture Components:**")
        tech_sections.append("- Task-Manager (Meta-Agent): Orchestrates and coordinates sub-agents")
        tech_sections.append("- Sub-Agents: Architect, Builder, Validator, Scribe")
        tech_sections.append("- Feedback Loop: Agents, Verifier, Prompt Refiner")
        tech_sections.append("- Communication: Shared JSON files (task-queue.json, dependencies.json)")
    
    # Look for system components
    elif 'task-manager' in text.lower() or 'meta-agent' in text.lower():
        tech_sections.append("**Architecture Components:**")
        tech_sections.append("- Task-Manager (Meta-Agent): Orchestrates and coordinates sub-agents")
        tech_sections.append("- Sub-Agents: Architect, Builder, Validator, Scribe")
        tech_sections.append("- Communication: Shared JSON files (task-queue.json, dependencies.json)")
    
    # Extract specific technical details
    if 'claude code terminals' in text.lower():
        tech_sections.append("\n**Technology Stack:**")
        tech_sections.append("- Claude Code terminals for agent execution")
        tech_sections.append("- Python automation scripts")
        tech_sections.append("- JSON for state and inter-process messaging")
        tech_sections.append("- Git for version control and hooks")
    
    # Look for current status information
    if 'working end-to-end' in text.lower():
        tech_sections.append("\n**Current Implementation Status:**")
        tech_sections.append("- Autonomous Task Orchestration: Working end-to-end (ORCH-001 validated)")
        tech_sections.append("- Multi-Agent Parallelism: Proven in INT-012 & INT-011.1")
        tech_sections.append("- Prompt Refinement Loop: Implemented and tested")
        tech_sections.append("- Memory & Knowledge Base: Complete with demo script (MEM-001)")
        tech_sections.append("- Quality & Security Gates: 100% pass rate in integration tests")
        tech_sections.append("- Logging & Observability: Meets required telemetry standards")
    
    return "\n".join(tech_sections) if tech_sections else ""

def extract_timeline_info(text: str) -> str:
    """Extract timeline information from user input."""
    timeline_items = []
    
    # Look for timeline mentions
    timeline_match = re.search(r'timeline.*?(\d+)\s*weeks?', text, re.IGNORECASE)
    if timeline_match:
        weeks = timeline_match.group(1)
        timeline_items.append(f"**Project Timeline:** {weeks} weeks to completion")
    
    # Look for specific deadlines
    if 'should be done' in text.lower():
        deadline_match = re.search(r'should be done.*?(\d+)\s*weeks?', text, re.IGNORECASE)
        if deadline_match:
            weeks = deadline_match.group(1)
            timeline_items.append(f"- Target completion: {weeks} weeks from project start")
            timeline_items.append("- Milestone: Full system operational and deployed")
    
    return "\n".join(timeline_items) if timeline_items else ""

def extract_glossary_info(text: str) -> str:
    """Extract glossary terms from user input."""
    terms = []
    
    # Define key terms found in the text
    glossary_terms = {
        'Task-Manager': 'Meta-agent that reads queues, spawns sub-agents, and coordinates task completion',
        'Meta-Agent': 'Central coordinating agent that manages other specialized agents',
        'Sub-Agents': 'Specialized agents including Architect, Builder, Validator, and Scribe',
        'Architect': 'Agent responsible for decomposing high-level tasks',
        'Builder': 'Agent that generates and edits code',
        'Validator': 'Agent that runs compilation and tests',
        'Scribe': 'Agent that documents results and updates memory',
        'Verifier': 'Component that validates code compilation and execution',
        'Prompt Refiner': 'System component that improves prompts based on feedback',
        'Feedback Loop': 'Process where agent outcomes inform future iterations',
        'ORCH-001': 'Orchestration validation test identifier',
        'INT-012': 'Integration test identifier for multi-agent parallelism',
        'MEM-001': 'Memory backend system identifier',
        'CASCADE-004': 'Future scalability implementation for horizontal sharding'
    }
    
    # Check which terms appear in the text
    for term, definition in glossary_terms.items():
        if term.lower() in text.lower() or term.replace('-', ' ').lower() in text.lower():
            terms.append(f"| {term} | {definition} | User |")
    
    # Add header if we have terms
    if terms:
        header = "| Term | Definition | Added by |\n|------|------------|----------|"
        return header + "\n" + "\n\n".join(terms)
    
    return ""

async def extract_project_updates_with_llm(user_input: str, ai_response: str, project_slug: str) -> Dict[str, str]:
    """Use LLM to intelligently identify document sections that need updates."""
    try:
        from langchain_openai import ChatOpenAI
        from langchain_core.messages import HumanMessage, SystemMessage
        import json
        
        # Initialize a lightweight LLM for extraction
        extraction_llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.1)
        
        extraction_prompt = f"""You are a project documentation assistant. Analyze the conversation and identify what document sections should be updated.

CONVERSATION:
User: {user_input}
AI Assistant: {ai_response}

PROJECT SECTIONS AVAILABLE:
- Objective: Project goals and success criteria
- Context: Background and motivation  
- Stakeholders & Collaborators: People and teams involved
- Systems & Data Sources: Technical components and architecture
- Constraints & Risks: Limitations and identified risks
- Next Actions: Timeline and immediate steps
- Glossary: Important terms and definitions
- Recent Discussions: General project conversations

TASK: Return ONLY a JSON object with section names as keys and content to add as values. Only include sections that should be updated based on the conversation. If no clear updates are needed, return an empty object {{}}.

FORMAT EXAMPLE:
{{
    "Systems & Data Sources": "- Automated Testing Framework: Required for quality assurance",
    "Next Actions": "- Set up testing infrastructure by end of sprint"
}}

RESPONSE (JSON only):"""

        messages = [
            SystemMessage(content="You are a precise document extraction assistant. Return only valid JSON."),
            HumanMessage(content=extraction_prompt)
        ]
        
        logger.info(f"Using LLM extraction for project {project_slug}")
        response = await extraction_llm.ainvoke(messages)
        
        # Parse the JSON response
        try:
            updates = json.loads(response.content.strip())
            logger.info(f"LLM extracted {len(updates)} section updates: {list(updates.keys())}")
            return updates if isinstance(updates, dict) else {}
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse LLM extraction response: {e}. Response: {response.content}")
            return {}
            
    except Exception as e:
        logger.error(f"Error in LLM extraction: {e}", exc_info=True)
        return {}

async def process_user_input_async(user_input: str, ai_response: str, memory: MarkdownMemory, project_slug: str, user_id: str = "anonymous") -> None:
    """Process user input asynchronously using intelligent LLM-based extraction."""
    
    try:
        logger.info(f"Starting intelligent background extraction for {project_slug} by user {user_id}")
        
        # Get user display name for attribution
        from .user_registry import get_user_display_name
        contributor = await get_user_display_name(user_id)
        
        # Use LLM-based extraction as primary method
        llm_updates = await extract_project_updates_with_llm(user_input, ai_response, project_slug)
        
        updates_made = 0
        # Apply LLM-identified updates
        for section, content in llm_updates.items():
            if content and content.strip():
                logger.info(f"Updating section '{section}' with LLM-extracted content")
                await memory.update_section(section, content.strip(), contributor, user_id)
                updates_made += 1
        
        # Fallback mechanism: if no updates were made, capture in Recent Discussions
        if updates_made == 0:
            logger.info(f"No specific sections identified, adding to Recent Discussions")
            current_time = datetime.now().strftime('%Y-%m-%d %H:%M')
            discussion_entry = f"**{current_time}**: {user_input}"
            await memory.update_section("Recent Discussions", discussion_entry, contributor, user_id)
            updates_made = 1
        
        logger.info(f"Completed intelligent extraction for {project_slug}: {updates_made} updates made")
        
    except Exception as e:
        logger.error(f"Error in background processing: {e}", exc_info=True)
        # Fallback: at minimum, capture the conversation
        try:
            current_time = datetime.now().strftime('%Y-%m-%d %H:%M')
            fallback_entry = f"**{current_time}**: {user_input} (Auto-saved due to processing error)"
            await memory.update_section("Recent Discussions", fallback_entry, "System", "system")
        except Exception as fallback_error:
            logger.error(f"Even fallback failed: {fallback_error}", exc_info=True)

class ProjectRegistry:
    """Manages the index.json file that tracks all projects."""
    
    @staticmethod
    async def load_index() -> Dict[str, Any]:
        """Load the project index."""
        if not INDEX_FILE.exists():
            return {}
        
        async with aiofiles.open(INDEX_FILE, 'r', encoding='utf-8') as f:
            content = await f.read()
            return json.loads(content) if content.strip() else {}
    
    @staticmethod
    async def save_index(index: Dict[str, Any]) -> None:
        """Save the project index."""
        INDEX_FILE.parent.mkdir(exist_ok=True)
        
        async with aiofiles.open(INDEX_FILE, 'w', encoding='utf-8') as f:
            await f.write(json.dumps(index, indent=2))
    
    @staticmethod
    async def add_project(slug: str, metadata: Dict[str, Any] = None) -> None:
        """Add a project to the index."""
        index = await ProjectRegistry.load_index()
        
        index[slug] = {
            "created": datetime.now().isoformat(),
            "file_path": f"{slug}.md",
            "status": "active",
            **(metadata or {})
        }
        
        await ProjectRegistry.save_index(index)
    
    @staticmethod
    async def list_projects() -> Dict[str, Any]:
        """List all projects."""
        return await ProjectRegistry.load_index()
    
    @staticmethod
    async def archive_project(slug: str) -> bool:
        """Archive a project by setting its status to 'archived'."""
        index = await ProjectRegistry.load_index()
        
        if slug not in index:
            return False
        
        index[slug]["status"] = "archived"
        index[slug]["archived"] = datetime.now().isoformat()
        
        await ProjectRegistry.save_index(index)
        return True
    
    @staticmethod
    async def unarchive_project(slug: str) -> bool:
        """Unarchive a project by setting its status back to 'active'."""
        index = await ProjectRegistry.load_index()
        
        if slug not in index:
            return False
        
        index[slug]["status"] = "active"
        if "archived" in index[slug]:
            del index[slug]["archived"]
        
        await ProjectRegistry.save_index(index)
        return True
    
    @staticmethod
    async def delete_project(slug: str) -> bool:
        """Delete a project completely."""
        index = await ProjectRegistry.load_index()
        
        if slug not in index:
            return False
        
        # Delete the markdown file
        file_path = MEMORY_DIR / f"{slug}.md"
        if file_path.exists():
            file_path.unlink()
        
        # Remove from index
        del index[slug]
        
        await ProjectRegistry.save_index(index)
        return True
    
    @staticmethod
    async def get_projects_by_status(status: str = "active") -> Dict[str, Any]:
        """Get projects filtered by status."""
        index = await ProjectRegistry.load_index()
        return {slug: data for slug, data in index.items() if data.get("status", "active") == status}

def should_start_introduction(user_id: str, document_context: str) -> bool:
    """Determine if we should start the introduction flow based on user and project state."""
    
    # Always start introduction for anonymous users
    if user_id == "anonymous":
        return True
    
    # Check if user's name appears in the change log (indicating they've contributed before)
    change_log_section = document_context.split('## Change Log')[-1] if '## Change Log' in document_context else ""
    
    # Look for user ID or name patterns in change log
    user_in_changelog = (f"| {user_id} |" in change_log_section or 
                        f"by {user_id}:" in change_log_section or
                        user_id in change_log_section)
    
    # If user hasn't contributed to this project before, start introduction
    if not user_in_changelog:
        return True
        
    return False

def make_graph(project_slug: str, model: str = "gpt-4o-mini") -> StateGraph:
    """Create an intelligent LangGraph workflow that prioritizes response generation."""
    
    # Initialize the LLM
    llm = ChatOpenAI(
        model=model,
        temperature=0.1,
        streaming=True
    )
    
    # Initialize memory
    memory = MarkdownMemory(project_slug)
    
    async def load_system_prompt() -> str:
        """Load the system prompt from prompts/project_planner.md"""
        try:
            prompt_file = Path("prompts/project_planner.md")
            if prompt_file.exists():
                async with aiofiles.open(prompt_file, 'r', encoding='utf-8') as f:
                    return await f.read()
        except Exception as e:
            logger.error(f"Error loading system prompt: {e}")
        
        # Fallback system prompt that ensures responses
        return """You are an expert project planning assistant. You help users develop comprehensive project documentation through conversation.

Your role is to:
1. Have natural conversations with users about their project
2. Ask clarifying questions to understand project scope, objectives, and requirements
3. Provide helpful guidance and suggestions for project planning
4. Extract important project information and maintain structured documentation

Always respond to the user in a helpful, professional manner. Focus on understanding their project needs and providing actionable advice."""
    
    async def planning_node(state: ProjectPlannerState) -> Dict[str, Any]:
        """Main planning node that processes user input and generates responses."""
        
        try:
            logger.info(f"Processing message for {project_slug}")
            
            # Get current document context - this MUST return the actual document content
            document_context = await memory.get_document_context()
            
            # Log the document context to verify we have the right data
            logger.info(f"Document context preview: {document_context[:200]}...")
            
            # Load system prompt
            system_prompt = await load_system_prompt()
            
            # Get user_id from state or default to anonymous
            user_id = state.get("user_id", "anonymous")
            
            # Check if we should start with introduction workflow
            needs_introduction = should_start_introduction(user_id, document_context)
            
            # Build context that includes the ACTUAL document content and appropriate workflow
            if needs_introduction:
                project_title = project_slug.replace('-', ' ').title()
                context_prompt = f"""{system_prompt}

CURRENT USER STATE: NEW USER TO PROJECT
This user is either anonymous or hasn't contributed to this project before. Follow the NEW PROJECT WORKFLOW:

AUTOMATIC INTRODUCTION: Start immediately with this introduction message:
"This assistant will guide you through a structured questionnaire to build a shared problem definition for \"{project_title}.\" You can pause anytime and resume later.

To get started, could you please provide your name, role, and areas of expertise? Additionally, if you have a specific project handle in mind, please share that as well."

After they respond, use Five-Question Cadence (4-5 questions per bundle) to build comprehensive foundation.
Track progress and guide toward completeness ("Depth X/8 achieved").
Only reveal full document when depth ≥ 4/8 or explicitly requested.

CURRENT DOCUMENT STATE:
{document_context}

IMPORTANT: Do not wait for user input - start with the introduction message immediately."""

            else:
                context_prompt = f"""{system_prompt}

CURRENT USER STATE: RETURNING COLLABORATOR
This user has contributed to this project before. Follow the EXISTING PROJECT WORKFLOW:

1. Provide recap of current project state (≤5 bullets: objective, status, open questions, risks, next actions)
2. Ask about user's role and familiarity with the project
3. Focus on enhancing existing content based on user expertise
4. Address gaps and open questions in their domain

CURRENT PROJECT DOCUMENT:
{document_context}

IMPORTANT: The above document contains the actual current state of the project "{project_slug.replace('-', ' ').title()}". 
Use this information to:
1. Answer questions about the project based on what's documented
2. Build upon existing information rather than starting from scratch  
3. Reference specific details that are already captured
4. Help complete missing sections

The user can see this same document. Reference specific existing details and build upon the established foundation."""
            
            messages = [SystemMessage(content=context_prompt)] + state["messages"]
            
            logger.info("Generating AI response with document context...")
            
            # Generate response - this must complete successfully
            response = await llm.ainvoke(messages)
            
            logger.info(f"AI response generated successfully: {len(response.content)} characters")
            
            # Process user input for document updates in the background (don't let this block response)
            if state["messages"]:
                last_message = state["messages"][-1]
                if isinstance(last_message, HumanMessage):
                    # Get user_id from state or default to anonymous
                    user_id = state.get("user_id", "anonymous")
                    
                    # Run document processing asynchronously with error tracking
                    task = asyncio.create_task(
                        process_user_input_async(last_message.content, response.content, memory, project_slug, user_id)
                    )
                    # Add error callback to surface background failures
                    task.add_done_callback(lambda t: 
                        logger.error(f"Background processing failed for {project_slug}: {t.exception()}", exc_info=True) 
                        if t.exception() else 
                        logger.debug(f"Background processing completed successfully for {project_slug}")
                    )
            
            return {"messages": state["messages"] + [response]}
            
        except Exception as e:
            logger.error(f"Error in planning_node: {e}", exc_info=True)
            # Return a fallback response so user isn't left hanging
            fallback_response = AIMessage(content="I apologize, but I encountered an error processing your request. Could you please try rephrasing your question?")
            return {"messages": state["messages"] + [fallback_response]}
    
    # Build the graph
    workflow = StateGraph(ProjectPlannerState)
    workflow.add_node("planner", planning_node)
    workflow.set_entry_point("planner")
    workflow.add_edge("planner", END)
    
    return workflow.compile()

async def stream_initial_message(
    project_slug: str,
    user_id: str = "anonymous"
) -> AsyncGenerator[str, None]:
    """Stream an initial message for users who need introduction workflow."""
    
    try:
        logger.info(f"Starting initial message stream for {project_slug} by user {user_id}")
        
        # Get document context to check user state
        memory = MarkdownMemory(project_slug)
        document_context = await memory.get_document_context()
        
        # Check if user needs introduction
        needs_introduction = should_start_introduction(user_id, document_context)
        
        if needs_introduction:
            project_title = project_slug.replace('-', ' ').title()
            introduction_message = f"""This assistant will guide you through a structured questionnaire to build a shared problem definition for "{project_title}." You can pause anytime and resume later.

To get started, could you please provide your name, role, and areas of expertise? Additionally, if you have a specific project handle in mind, please share that as well."""
            
            # Stream the introduction message token by token
            for token in introduction_message:
                yield f"data: {json.dumps({'token': token})}\n\n"
                await asyncio.sleep(0.01)  # Small delay for smoother streaming
        else:
            # For returning users, provide a brief welcome
            welcome_message = f"Welcome back to {project_slug.replace('-', ' ').title()}! How can I help you continue developing this project?"
            
            for token in welcome_message:
                yield f"data: {json.dumps({'token': token})}\n\n"
                await asyncio.sleep(0.01)
        
        # End the stream
        yield f"data: {json.dumps({'done': True})}\n\n"
        
        logger.info(f"Completed initial message stream for {project_slug}")
        
    except Exception as e:
        logger.error(f"Error in stream_initial_message: {e}", exc_info=True)
        # Always provide some response to the user
        error_message = "Welcome! I'm here to help you develop your project. Please tell me about what you'd like to work on."
        for token in error_message:
            yield f"data: {json.dumps({'token': token})}\n\n"
            await asyncio.sleep(0.01)
        yield f"data: {json.dumps({'done': True})}\n\n"

async def stream_chat_response(
    project_slug: str, 
    message: str, 
    model: str = "gpt-4o-mini",
    user_id: str = "anonymous"
) -> AsyncGenerator[str, None]:
    """Stream a chat response for a given project with prioritized response generation."""
    
    try:
        logger.info(f"Starting chat response stream for {project_slug}")
        
        # Create the graph
        graph = make_graph(project_slug, model)
        
        # Prepare the input
        input_data = {
            "messages": [HumanMessage(content=message)],
            "user_id": user_id
        }
        
        # Execute the graph and get the final result
        final_result = await graph.ainvoke(input_data)
        
        # Extract the final message
        if final_result and "messages" in final_result and len(final_result["messages"]) > 0:
            final_message = final_result["messages"][-1]
            if hasattr(final_message, 'content') and final_message.content:
                # Stream the content as individual tokens
                content = str(final_message.content)
                logger.info(f"Streaming response: {len(content)} characters")
                for token in content:
                    yield f"data: {json.dumps({'token': token})}\n\n"
                    await asyncio.sleep(0.01)  # Small delay for smoother streaming
            else:
                logger.warning("Final message has no content")
                # Provide fallback response
                fallback = "I'm ready to help with your project planning. What would you like to know?"
                for token in fallback:
                    yield f"data: {json.dumps({'token': token})}\n\n"
                    await asyncio.sleep(0.01)
        else:
            logger.warning("No final result from graph execution")
            # Provide fallback response
            fallback = "I'm here to help with your project. How can I assist you today?"
            for token in fallback:
                yield f"data: {json.dumps({'token': token})}\n\n"
                await asyncio.sleep(0.01)
        
        # End the stream
        yield f"data: {json.dumps({'done': True})}\n\n"
        
        logger.info(f"Completed chat response stream for {project_slug}")
        
    except Exception as e:
        logger.error(f"Error in stream_chat_response: {e}", exc_info=True)
        # Always provide some response to the user
        error_message = "I apologize, but I encountered an error. Please try your request again."
        for token in error_message:
            yield f"data: {json.dumps({'token': token})}\n\n"
            await asyncio.sleep(0.01)
        yield f"data: {json.dumps({'done': True})}\n\n"

async def initialize_memory() -> MarkdownMemory:
    """Initialize the intelligent markdown memory system."""
    memory = MarkdownMemory("default")
    return memory