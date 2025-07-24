"""
LangGraph workflow and memory management for the Project Planner Bot.
Handles conversation state, markdown file operations, and LangGraph execution.
"""

import asyncio
import aiofiles
import json
import os
from datetime import datetime
from typing import Dict, Any, AsyncGenerator, Optional
from pathlib import Path
import logging

from langgraph.graph import StateGraph, END
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from typing import TypedDict, List

logger = logging.getLogger(__name__)

MEMORY_DIR = Path("app/memory")
INDEX_FILE = MEMORY_DIR / "index.json"

# State structure for LangGraph
class GraphState(TypedDict):
    messages: List[HumanMessage | AIMessage | SystemMessage]

class MarkdownMemory:
    """Handles async reading/writing of project markdown files with proper locking."""
    
    def __init__(self, project_slug: str):
        self.project_slug = project_slug
        self.file_path = MEMORY_DIR / f"{project_slug}.md"
        self._lock = asyncio.Lock()
    
    async def ensure_file_exists(self) -> None:
        """Create markdown file if it doesn't exist."""
        if not self.file_path.exists():
            await self._create_initial_file()
    
    async def _create_initial_file(self) -> None:
        """Create initial markdown file with metadata."""
        async with self._lock:
            content = f"""# {self.project_slug.replace('-', ' ').title()}

**Created:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
**Status:** Active
**Type:** Project Planning

## Project Overview
This project was created through the Project Planner Bot.

## Conversation History

"""
            async with aiofiles.open(self.file_path, 'w', encoding='utf-8') as f:
                await f.write(content)
    
    async def read_content(self) -> str:
        """Read the full markdown content."""
        await self.ensure_file_exists()
        async with aiofiles.open(self.file_path, 'r', encoding='utf-8') as f:
            return await f.read()
    
    async def append_qa(self, question: str, answer: str) -> None:
        """Append a Q&A pair to the markdown file."""
        async with self._lock:
            await self.ensure_file_exists()
            
            qa_content = f"""### Q: {question}
**A:** {answer}

"""
            async with aiofiles.open(self.file_path, 'a', encoding='utf-8') as f:
                await f.write(qa_content)
    
    async def get_conversation_history(self) -> str:
        """Extract conversation history for context."""
        content = await self.read_content()
        
        # Find the "Conversation History" section
        if "## Conversation History" in content:
            history_start = content.find("## Conversation History")
            return content[history_start:]
        
        return ""

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

def make_graph(project_slug: str, model: str = "gpt-4o-mini") -> StateGraph:
    """Create a LangGraph workflow for the project planner."""
    
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
        prompt_file = Path("prompts/project_planner.md")
        if prompt_file.exists():
            async with aiofiles.open(prompt_file, 'r', encoding='utf-8') as f:
                return await f.read()
        
        # Fallback system prompt
        return """You are a helpful project planning assistant. You help users break down complex projects into manageable tasks, set priorities, and track progress.

Key capabilities:
- Analyze project requirements and scope
- Break down large projects into smaller tasks
- Suggest timelines and milestones
- Identify potential risks and dependencies
- Provide project management best practices

Always be practical, actionable, and focused on helping users make real progress on their projects."""
    
    async def planning_node(state: GraphState) -> Dict[str, Any]:
        """Main planning node that processes user input and generates responses."""
        
        # Get conversation history for context
        history = await memory.get_conversation_history()
        
        # Load system prompt
        system_prompt = await load_system_prompt()
        
        # Build context-aware system message
        context_prompt = f"""{system_prompt}

CONVERSATION CONTEXT:
{history}

Remember to maintain consistency with previous discussions and build upon the established project context."""
        
        messages = [SystemMessage(content=context_prompt)] + state["messages"]
        
        # Generate response
        response = await llm.ainvoke(messages)
        
        # Save to markdown memory
        if state["messages"]:
            last_message = state["messages"][-1]
            if isinstance(last_message, HumanMessage):
                await memory.append_qa(
                    question=last_message.content,
                    answer=response.content
                )
        
        return {"messages": state["messages"] + [response]}
    
    # Build the graph
    workflow = StateGraph(GraphState)
    workflow.add_node("planner", planning_node)
    workflow.set_entry_point("planner")
    workflow.add_edge("planner", END)
    
    return workflow.compile()

async def stream_chat_response(
    project_slug: str, 
    message: str, 
    model: str = "gpt-4o-mini"
) -> AsyncGenerator[str, None]:
    """Stream a chat response for a given project."""
    
    try:
        # Create the graph
        graph = make_graph(project_slug, model)
        
        # Prepare the input
        input_data = {
            "messages": [HumanMessage(content=message)]
        }
        
        # Stream the response
        async for chunk in graph.astream(input_data, stream_mode="messages"):
            if chunk and len(chunk) > 0:
                message_chunk = chunk[-1]
                if hasattr(message_chunk, 'content') and message_chunk.content:
                    # Stream the entire content as individual tokens
                    content = str(message_chunk.content)
                    for token in content:
                        yield f"data: {json.dumps({'token': token})}\n\n"
                        await asyncio.sleep(0.01)  # Small delay for smoother streaming
        
        # End the stream
        yield f"data: {json.dumps({'done': True})}\n\n"
        
    except Exception as e:
        logger.error(f"Error in stream_chat_response: {e}")
        yield f"data: {json.dumps({'error': str(e)})}\n\n"

async def initialize_memory() -> MarkdownMemory:
    """Initialize the markdown memory system."""
    memory = MarkdownMemory("default")
    return memory