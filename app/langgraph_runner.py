"""
LangGraph workflow and memory management for the Project Planner Bot.
Handles conversation state, markdown file operations, and LangGraph execution.
"""

import asyncio
import os
from pathlib import Path
from typing import Dict, Any, Optional
import yaml
from datetime import datetime

class MarkdownMemory:
    """Manages markdown file-based memory for project conversations."""
    
    def __init__(self, memory_dir: str = "app/memory"):
        self.memory_dir = Path(memory_dir)
        self.memory_dir.mkdir(exist_ok=True)
        self._locks: Dict[str, asyncio.Lock] = {}
    
    def _get_lock(self, project_slug: str) -> asyncio.Lock:
        """Get or create a lock for a specific project file."""
        if project_slug not in self._locks:
            self._locks[project_slug] = asyncio.Lock()
        return self._locks[project_slug]
    
    async def create_project(self, project_slug: str, metadata: Dict[str, Any]) -> Path:
        """Create a new project markdown file with metadata."""
        file_path = self.memory_dir / f"{project_slug}.md"
        
        async with self._get_lock(project_slug):
            if file_path.exists():
                raise ValueError(f"Project {project_slug} already exists")
            
            # Create initial markdown content
            content = f"""# Project: {metadata.get('title', project_slug)}

## Metadata
- **Created**: {datetime.now().isoformat()}
- **Slug**: {project_slug}
- **Description**: {metadata.get('description', 'No description provided')}

## Conversation History

"""
            file_path.write_text(content)
            return file_path
    
    async def append_conversation(self, project_slug: str, question: str, answer: str):
        """Append a Q&A pair to the project's conversation history."""
        file_path = self.memory_dir / f"{project_slug}.md"
        
        async with self._get_lock(project_slug):
            if not file_path.exists():
                raise FileNotFoundError(f"Project {project_slug} not found")
            
            # Append Q&A to the file
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            qa_content = f"""
### Q: {question}
*Asked on {timestamp}*

{answer}

---

"""
            with open(file_path, 'a', encoding='utf-8') as f:
                f.write(qa_content)
    
    async def read_project_file(self, project_slug: str) -> str:
        """Read the entire project markdown file."""
        file_path = self.memory_dir / f"{project_slug}.md"
        
        async with self._get_lock(project_slug):
            if not file_path.exists():
                raise FileNotFoundError(f"Project {project_slug} not found")
            
            return file_path.read_text(encoding='utf-8')
    
    async def list_projects(self) -> list[str]:
        """List all project slugs."""
        return [f.stem for f in self.memory_dir.glob("*.md")]


def make_graph(md_path: str, model: str = "gpt-4o-mini"):
    """
    Create a LangGraph conversation graph for a specific project.
    
    Args:
        md_path: Path to the project's markdown file
        model: LLM model to use (o3, gpt-4o-mini, etc.)
    
    Returns:
        Compiled LangGraph workflow
    """
    # TODO: Implement LangGraph workflow
    # This will include:
    # 1. Load project context from markdown
    # 2. Set up conversation state
    # 3. Configure LLM with project planner prompts
    # 4. Return compiled graph for streaming execution
    
    class ProjectPlannerGraph:
        def __init__(self, md_path: str, model: str):
            self.md_path = md_path
            self.model = model
        
        async def stream_response(self, message: str):
            """Stream a response for the given message."""
            # TODO: Implement actual LangGraph streaming
            yield f"[{self.model}] Processing: {message}"
            yield f"[{self.model}] This is a placeholder response for project planning."
            yield f"[{self.model}] Model: {self.model}, Context: {self.md_path}"
    
    return ProjectPlannerGraph(md_path, model)


async def initialize_memory() -> MarkdownMemory:
    """Initialize the markdown memory system."""
    memory = MarkdownMemory()
    return memory