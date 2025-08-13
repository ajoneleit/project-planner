"""
LangGraph workflow and memory management for the Project Planner Bot.
Handles conversation state, markdown file operations, and LangGraph execution with intelligent information filtering.
"""

import asyncio
import aiofiles
import json
import os
import re
import concurrent.futures
from datetime import datetime
from typing import Dict, Any, AsyncGenerator, Optional, List, Tuple
from pathlib import Path
import logging
from .core.logging_config import get_secure_logger

from langgraph.graph import StateGraph, END
from langgraph.graph.message import MessagesState
from typing_extensions import TypedDict
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage, BaseMessage
from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel

# Phase 2: Import unified memory system directly
from app.core.memory_unified import get_unified_memory, UnifiedMemoryManager
from app.core.feature_flags import is_feature_enabled
from app.core.migration_logging import get_migration_logger, log_conversation_read, log_conversation_write
from app.core.conversation_id_manager import ConversationIDManager

# Keep compatibility imports for transition period
from app.core.memory_compatibility import (
    CompatibilityConversationMemory,
    CompatibilityMarkdownMemory
)

# Use secure logger that sanitizes sensitive data
logger = get_secure_logger(__name__)

MEMORY_DIR = Path("app/memory")
INDEX_FILE = MEMORY_DIR / "index.json"

# Global unified memory instance
_unified_memory = None

# Global thread executor for file operations
_file_executor = None

# Cleanup flag to prevent memory leaks
_cleanup_registered = False

def get_file_executor() -> concurrent.futures.ThreadPoolExecutor:
    """Get or create the thread executor for file operations."""
    global _file_executor
    if _file_executor is None:
        max_workers = min(4, (os.cpu_count() or 1) + 2)
        _file_executor = concurrent.futures.ThreadPoolExecutor(
            max_workers=max_workers,
            thread_name_prefix="file_io"
        )
        logger.info(f"Initialized file operations thread executor with {max_workers} workers")
    return _file_executor

async def safe_file_read(file_path: Path) -> Optional[str]:
    """Thread-safe async file reading that doesn't block the event loop."""
    def _read_file():
        try:
            if file_path.exists():
                return file_path.read_text(encoding='utf-8')
            return None
        except FileNotFoundError:
            # File doesn't exist, return None as expected
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

async def safe_json_read(file_path: Path) -> Optional[Dict]:
    """Thread-safe async JSON reading that doesn't block the event loop."""
    def _read_json():
        try:
            if file_path.exists():
                content = file_path.read_text(encoding='utf-8')
                if content.strip():
                    return json.loads(content)
            return None
        except FileNotFoundError:
            # File doesn't exist, return None as expected
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

async def safe_json_write(file_path: Path, data: Dict) -> bool:
    """Thread-safe async JSON writing that doesn't block the event loop."""
    def _write_json():
        try:
            file_path.parent.mkdir(parents=True, exist_ok=True)
            content = json.dumps(data, indent=2, ensure_ascii=False, default=str)
            file_path.write_text(content, encoding='utf-8')
            return True
        except PermissionError as e:
            logger.error(f"Permission denied writing JSON file {file_path}: {e}")
            return False
        except OSError as e:
            logger.error(f"OS error writing JSON file {file_path}: {e}")
            return False
        except TypeError as e:
            logger.error(f"Data not serializable to JSON for {file_path}: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error writing JSON file {file_path}: {e}", exc_info=True)
            return False
    
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(get_file_executor(), _write_json)

async def get_unified_memory_instance() -> UnifiedMemoryManager:
    """Get or create the unified memory system instance (Phase 2 implementation)."""
    global _unified_memory, _cleanup_registered
    if _unified_memory is None:
        # Direct use of unified memory system
        _unified_memory = await get_unified_memory()
        logger.info("Initialized unified memory system directly (Phase 2)")
        
        # Register cleanup on first use
        if not _cleanup_registered:
            import atexit
            import signal
            atexit.register(cleanup_global_resources)
            signal.signal(signal.SIGTERM, lambda sig, frame: cleanup_global_resources())
            signal.signal(signal.SIGINT, lambda sig, frame: cleanup_global_resources())
            _cleanup_registered = True
            logger.info("Registered cleanup handlers for global resources")
    
    return _unified_memory


def cleanup_global_resources():
    """Clean up global resources to prevent memory leaks"""
    global _unified_memory, _file_executor
    
    try:
        # Clean up thread executor
        if _file_executor is not None:
            logger.info("Shutting down file executor thread pool")
            _file_executor.shutdown(wait=True)
            _file_executor = None
        
        # Clean up unified memory instance
        if _unified_memory is not None:
            logger.info("Cleaning up unified memory instance")
            _unified_memory = None
        
        # Clean up unified memory system
        from .core.memory_unified import reset_unified_memory
        import asyncio
        try:
            # Try to clean up async resources safely
            loop = asyncio.get_event_loop()
            if loop.is_running():
                asyncio.create_task(reset_unified_memory())
            else:
                loop.run_until_complete(reset_unified_memory())
        except RuntimeError:
            # No event loop running, skip async cleanup
            pass
        
        logger.info("Global resource cleanup completed")
    
    except ImportError as e:
        logger.error(f"Import error during cleanup (system may not be fully initialized): {e}")
    except AttributeError as e:
        logger.error(f"Attribute error during cleanup (resource already cleaned): {e}")
    except Exception as e:
        logger.error(f"Unexpected error during resource cleanup: {e}", exc_info=True)


async def get_conversation_memory_for_project(project_slug: str, user_id: str = "anonymous") -> Dict[str, Any]:
    """Get conversation memory context for a project using unified memory system (Phase 2)."""
    try:
        if not await is_feature_enabled("unified_memory_primary"):
            # Phase 2: Use compatibility layer during transition
            memory = CompatibilityConversationMemory(project_slug)
            await memory._initialize_langchain_memory()
            return {
                'messages': memory.get_langchain_messages(max_messages=20),
                'last_ai_response': memory.last_ai_response,
                'conversation_id': project_slug
            }
        else:
            # Direct unified memory access
            unified_memory = await get_unified_memory_instance()
            conversation_id = ConversationIDManager.generate_standard_id(project_slug, user_id)
            
            # Get conversation history
            messages_data = await unified_memory.get_conversation(conversation_id, limit=20)
            
            # Convert to LangChain messages
            messages = []
            last_ai_response = None
            for msg_data in messages_data:
                if msg_data['role'] == 'user':
                    messages.append(HumanMessage(content=msg_data['content']))
                elif msg_data['role'] == 'assistant':
                    ai_msg = AIMessage(content=msg_data['content'])
                    messages.append(ai_msg)
                    last_ai_response = msg_data['content']
            
            # Log conversation read
            await log_conversation_read(conversation_id, len(messages), user_id)
            
            return {
                'messages': messages,
                'last_ai_response': last_ai_response,
                'conversation_id': conversation_id
            }
            
    except Exception as e:
        logger.error(f"Error getting conversation memory for {project_slug}: {e}")
        return {
            'messages': [],
            'last_ai_response': None,
            'conversation_id': project_slug
        }

async def add_conversation_to_memory(project_slug: str, user_input: str, ai_response: str, user_id: str = "anonymous") -> bool:
    """Add conversation to memory using unified system (Phase 2)."""
    try:
        if not await is_feature_enabled("unified_memory_primary"):
            # Phase 2: Use compatibility layer during transition
            memory = CompatibilityConversationMemory(project_slug)
            await memory.add_conversation(user_input, ai_response, user_id)
            return True
        else:
            # Direct unified memory access
            unified_memory = await get_unified_memory_instance()
            conversation_id = ConversationIDManager.generate_standard_id(project_slug, user_id)
            
            # Add messages
            if user_input:
                await unified_memory.add_message(conversation_id, "user", user_input, user_id)
                await log_conversation_write(conversation_id, {"role": "user", "content": user_input}, user_id)
                
            if ai_response:
                await unified_memory.add_message(conversation_id, "assistant", ai_response, user_id)
                await log_conversation_write(conversation_id, {"role": "assistant", "content": ai_response}, user_id)
            
            return True
            
    except Exception as e:
        logger.error(f"Error adding conversation to memory for {project_slug}: {e}")
        return False

async def get_project_document_memory(project_slug: str) -> Dict[str, Any]:
    """Get project document memory using unified system (Phase 2)."""
    try:
        if not await is_feature_enabled("unified_memory_primary"):
            # Phase 2: Use compatibility layer during transition
            memory = CompatibilityMarkdownMemory(project_slug)
            await memory.ensure_file_exists()
            content = await memory.read_content()
            return {
                'content': content,
                'project_slug': project_slug,
                'file_path': f"app/memory/{project_slug}.md"
            }
        else:
            # Direct unified memory access
            unified_memory = await get_unified_memory_instance()
            content = await unified_memory.get_project(project_slug)
            
            if content is None:
                # Create initial project file
                await unified_memory.save_project(project_slug, "", "system")
                content = ""
            
            return {
                'content': content,
                'project_slug': project_slug,
                'file_path': f"app/memory/{project_slug}.md"
            }
            
    except Exception as e:
        logger.error(f"Error getting project document memory for {project_slug}: {e}")
        return {
            'content': "",
            'project_slug': project_slug,
            'file_path': f"app/memory/{project_slug}.md"
        }

async def update_project_document(project_slug: str, section: str, content: str, contributor: str = "User", user_id: str = "anonymous") -> bool:
    """Update project document using unified system (Phase 2)."""
    try:
        if not await is_feature_enabled("unified_memory_primary"):
            # Phase 2: Use compatibility layer during transition
            memory = CompatibilityMarkdownMemory(project_slug)
            await memory.update_section(section, content, contributor, user_id)
            return True
        else:
            # Direct unified memory access
            unified_memory = await get_unified_memory_instance()
            success = await unified_memory.update_project_section(project_slug, section, content, contributor, user_id)
            return success
            
    except Exception as e:
        logger.error(f"Error updating project document for {project_slug}: {e}")
        return False

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

class LLMReferenceAnalyzer:
    """LLM-powered reference detection system that understands conversational context."""
    
    def __init__(self, model: str = "gpt-4o-mini"):
        self.model = model
        self.llm = None  # Lazy initialization to avoid API key issues during import
        self._analysis_cache = {}  # Simple cache for repeated analyses
        self._performance_metrics = {
            "total_requests": 0,
            "cache_hits": 0,
            "total_response_time": 0.0,
            "total_tokens_used": 0,
            "total_cost": 0.0,
            "accuracy_samples": []
        }
    
    def _initialize_llm(self):
        """Lazy initialization of LLM to handle API key timing."""
        if self.llm is None:
            try:
                # Use the same key parsing logic as existing system
                api_key = self._get_openai_api_key()
                self.llm = ChatOpenAI(
                    model=self.model, 
                    temperature=0.1,
                    api_key=api_key
                )
            except ValueError as e:
                logger.error(f"Invalid model configuration for reference analysis: {e}")
                raise
            except ImportError as e:
                logger.error(f"OpenAI dependency missing for reference analysis: {e}")
                raise RuntimeError(f"LLM initialization failed: {e}") from e
            except Exception as e:
                logger.error(f"Unexpected error initializing LLM for reference analysis: {e}", exc_info=True)
                raise RuntimeError(f"LLM initialization failed: {e}") from e
    
    def _get_openai_api_key(self) -> str:
        """Parse OpenAI API key using same logic as existing system."""
        api_key = os.getenv("OPENAI_API_KEY", "")
        if not api_key:
            return ""
        
        # Handle AWS App Runner JSON format
        if api_key.startswith("{") and api_key.endswith("}"):
            try:
                secrets = json.loads(api_key)
                return secrets.get("OPENAI_API_KEY", api_key)
            except json.JSONDecodeError:
                logger.warning(f"Failed to parse JSON API key format")
                return api_key
        
        return api_key
    
    async def analyze_reference(self, 
                               user_message: str, 
                               conversation_context: str, 
                               last_ai_response: str) -> Dict[str, Any]:
        """
        Analyze if user message contains references to previous conversation content.
        
        Returns:
            Dict with keys:
            - has_reference: bool
            - reference_type: str (explicit/implicit/pronoun/contextual)  
            - referenced_content: str (what they're referring to)
            - action_requested: str (what they want done)
            - confidence: str (high/medium/low)
        """
        import time
        start_time = time.time()
        
        try:
            # Track total requests
            self._performance_metrics["total_requests"] += 1
            
            # Initialize LLM if needed
            self._initialize_llm()
            
            # Create cache key for repeated analyses
            cache_key = hash(f"{user_message}_{last_ai_response[:100]}")
            if cache_key in self._analysis_cache:
                self._performance_metrics["cache_hits"] += 1
                logger.debug("Using cached reference analysis")
                return self._analysis_cache[cache_key]
            
            # Build analysis prompt
            analysis_prompt = self._build_analysis_prompt(
                user_message, conversation_context, last_ai_response
            )
            
            # Get LLM analysis
            messages = [SystemMessage(content=analysis_prompt)]
            response = await self.llm.ainvoke(messages)
            
            # Parse JSON response
            try:
                result = json.loads(response.content)
                
                # Validate response structure
                required_keys = ['has_reference', 'reference_type', 'referenced_content', 'action_requested', 'confidence']
                if not all(key in result for key in required_keys):
                    logger.warning("LLM response missing required keys, using fallback")
                    result = self._create_fallback_response()
                
                # Cache successful analysis
                self._analysis_cache[cache_key] = result
                
                # Track performance metrics
                response_time = time.time() - start_time
                self._track_performance(response_time, user_message, conversation_context, last_ai_response)
                
                logger.info(f"LLM reference analysis: {result['has_reference']} ({result['confidence']} confidence) - {response_time:.3f}s")
                return result
                
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse LLM reference analysis JSON: {e}")
                response_time = time.time() - start_time
                self._track_performance(response_time, user_message, conversation_context, last_ai_response, failed=True)
                return self._create_fallback_response()
                
        except Exception as e:
            logger.error(f"Error in LLM reference analysis: {e}", exc_info=True)
            response_time = time.time() - start_time
            self._track_performance(response_time, user_message, conversation_context, last_ai_response, failed=True)
            return self._create_fallback_response()
    
    def _build_analysis_prompt(self, user_message: str, context: str, last_response: str) -> str:
        """Build optimized prompt for reference detection."""
        
        # Limit context to essential information for cost optimization
        limited_context = context[-1500:] if len(context) > 1500 else context
        limited_response = last_response[-800:] if len(last_response) > 800 else last_response
        
        return f"""You are analyzing a user message to determine if they're referencing something from the previous conversation.

CONVERSATION CONTEXT (recent):
{limited_context}

MOST RECENT AI RESPONSE:
{limited_response}

CURRENT USER MESSAGE:
{user_message}

Analyze if the user is referencing something from the conversation, particularly the most recent AI response.

Look for:
- Explicit references: "add that", "include those", "use what you suggested", "implement that"
- Implicit references: "add it", "include them", "that's good", "perfect"
- Pronoun references: "that", "those", "it", "them" referring to previous content
- Contextual references: "the metrics", "your recommendation", "what you mentioned"

CRITICAL: When extracting referenced_content, focus on the MOST RECENT AI RESPONSE above.
- If the AI provided numbered recommendations/steps, extract those specific items
- If the user says "those" or "items 1-5", extract the numbered list from the AI's response
- If the AI provided advice/suggestions, extract the specific advice given
- Prioritize content from the AI's immediate previous response over older conversation context

IMPORTANT: Only return TRUE if the user is clearly referring to something specific from the AI's recent response or the conversation. General responses like "yes", "ok", or new questions should return FALSE.

Return ONLY valid JSON in this exact format:
{{
    "has_reference": true or false,
    "reference_type": "explicit" or "implicit" or "pronoun" or "contextual" or "none",
    "referenced_content": "the specific content they're referring to from the AI's response, or empty string if no reference",
    "action_requested": "what they want done with the referenced content, or empty string if no reference", 
    "confidence": "high" or "medium" or "low"
}}

Do not include any other text or explanation, only the JSON response."""
    
    def _create_fallback_response(self) -> Dict[str, Any]:
        """Create safe fallback response when LLM analysis fails."""
        return {
            "has_reference": False,
            "reference_type": "none",
            "referenced_content": "",
            "action_requested": "",
            "confidence": "low"
        }
    
    def _track_performance(self, response_time: float, user_message: str, context: str, last_response: str, failed: bool = False):
        """Track performance metrics for analysis and optimization."""
        try:
            # Update response time tracking
            self._performance_metrics["total_response_time"] += response_time
            
            # Estimate token usage (rough approximation)
            prompt_tokens = len(user_message.split()) + len(context.split()) + len(last_response.split()) + 200  # prompt overhead
            completion_tokens = 50 if not failed else 0  # JSON response estimate
            total_tokens = prompt_tokens + completion_tokens
            
            self._performance_metrics["total_tokens_used"] += total_tokens
            
            # Estimate cost (gpt-4o-mini pricing: $0.15/1M input, $0.60/1M output)
            input_cost = (prompt_tokens / 1_000_000) * 0.15
            output_cost = (completion_tokens / 1_000_000) * 0.60
            request_cost = input_cost + output_cost
            
            self._performance_metrics["total_cost"] += request_cost
            
            # Log performance data periodically
            if self._performance_metrics["total_requests"] % 10 == 0:
                self._log_performance_summary()
                
        except Exception as e:
            logger.error(f"Error tracking performance: {e}")
    
    def _log_performance_summary(self):
        """Log performance summary for monitoring."""
        try:
            metrics = self._performance_metrics
            total_requests = metrics["total_requests"]
            
            if total_requests == 0:
                return
            
            avg_response_time = metrics["total_response_time"] / total_requests
            cache_hit_rate = (metrics["cache_hits"] / total_requests) * 100
            
            logger.info(f"LLM Reference Analyzer Performance Summary:")
            logger.info(f"  Total Requests: {total_requests}")
            logger.info(f"  Cache Hit Rate: {cache_hit_rate:.1f}%")
            logger.info(f"  Avg Response Time: {avg_response_time:.3f}s")
            logger.info(f"  Total Tokens Used: {metrics['total_tokens_used']:,}")
            logger.info(f"  Estimated Total Cost: ${metrics['total_cost']:.4f}")
            logger.info(f"  Cost Per Request: ${metrics['total_cost']/total_requests:.4f}")
            
        except Exception as e:
            logger.error(f"Error logging performance summary: {e}")
    
    def get_performance_metrics(self) -> Dict[str, Any]:
        """Get current performance metrics for monitoring."""
        metrics = self._performance_metrics.copy()
        
        if metrics["total_requests"] > 0:
            metrics["avg_response_time"] = metrics["total_response_time"] / metrics["total_requests"]
            metrics["cache_hit_rate"] = (metrics["cache_hits"] / metrics["total_requests"]) * 100
            metrics["cost_per_request"] = metrics["total_cost"] / metrics["total_requests"]
        else:
            metrics["avg_response_time"] = 0.0
            metrics["cache_hit_rate"] = 0.0
            metrics["cost_per_request"] = 0.0
        
        return metrics
    
    def should_use_llm_analysis(self) -> bool:
        """Check if LLM analysis should be used based on feature flags."""
        use_llm = os.getenv("USE_LLM_REFERENCE_DETECTION", "true").lower() == "true"
        
        # Gradual rollout support
        rollout_percentage = int(os.getenv("LLM_REFERENCE_ROLLOUT_PERCENTAGE", "100"))
        if rollout_percentage < 100:
            import random
            if random.randint(1, 100) > rollout_percentage:
                return False
        
        return use_llm

class ChatAgent:
    """Specialized agent for natural conversation and user interaction."""
    
    def __init__(self, project_slug: str, model: str = "gpt-4o-mini"):
        self.project_slug = project_slug
        self.model = model
        self.llm = None  # Lazy initialization
        self.conversation_memory = None
        self.markdown_memory = None
    
    async def initialize(self, user_id: str = "anonymous"):
        """Initialize agent with unified memory system (Phase 2)."""
        
        # Get conversation memory context using unified system
        memory_context = await get_conversation_memory_for_project(self.project_slug, user_id)
        self.conversation_memory = memory_context  # Store as dict rather than object
        
        # Get document memory context
        doc_context = await get_project_document_memory(self.project_slug)
        self.markdown_memory = doc_context  # Store as dict rather than object
        
        logger.info(f"ChatAgent initialized for {self.project_slug} with {len(memory_context['messages'])} conversation messages")
        
        # Initialize LLM only if we have an API key
        if self.llm is None:
            api_key = self._get_openai_api_key()
            if api_key:
                self.llm = ChatOpenAI(
                    model=self.model,
                    temperature=0.1,
                    streaming=True,
                    api_key=api_key
                )
                logger.info(f"Initialized ChatOpenAI with model {self.model}")
            else:
                logger.warning(f"No API key available, ChatAgent will use fallback responses")
    
    def _get_openai_api_key(self) -> str:
        """Parse OpenAI API key using same logic as existing system."""
        api_key = os.getenv("OPENAI_API_KEY", "")
        if not api_key:
            return ""
        
        # Handle AWS App Runner JSON format
        if api_key.startswith("{") and api_key.endswith("}"):
            try:
                secrets = json.loads(api_key)
                return secrets.get("OPENAI_API_KEY", api_key)
            except json.JSONDecodeError:
                logger.warning(f"Failed to parse JSON API key format")
                return api_key
        
        return api_key
    
    async def get_system_prompt(self) -> str:
        """Get enhanced system prompt for refined conversational agent."""
        try:
            # Load combined conversational NAI agent prompt from file
            combined_prompt_file = Path("prompts/conversational_nai_agent.md")
            if combined_prompt_file.exists():
                async with aiofiles.open(combined_prompt_file, 'r', encoding='utf-8') as f:
                    base_prompt = await f.read()
            else:
                logger.warning("Conversational NAI agent prompt file not found, using fallback")
                base_prompt = """# Conversational NAI Problem-Definition Assistant

You are the "Conversational NAI Problem-Definition Assistant," a professional, politely persistent coach whose mission is to help North Atlantic Industries (NAI) employees turn hazy ideas, pain-points, or requirements into clear, living Markdown documents that any teammate can extend efficiently."""
        except Exception as e:
            logger.error(f"Error loading conversational NAI agent prompt: {e}")
            base_prompt = """# Conversational NAI Problem-Definition Assistant

You are the "Conversational NAI Problem-Definition Assistant," a professional, politely persistent coach whose mission is to help North Atlantic Industries (NAI) employees turn hazy ideas, pain-points, or requirements into clear, living Markdown documents that any teammate can extend efficiently."""
        
        # Enhanced chat agent prompt for refined behavior
        enhanced_prompt = f"""{base_prompt}

ROLE: You are the CHAT AGENT - focused on intelligent conversation and guidance about NAI projects.

CORE RESPONSIBILITIES:
- Have natural, helpful conversations about project planning
- Ask targeted questions to understand requirements and scope
- Provide expert guidance and recommendations
- Help users think through project challenges and solutions
- Reference project information without displaying full document content

CONVERSATION GUIDELINES:
1. **Conversational Focus**: Engage in natural dialogue about the project
2. **Targeted Questions**: Ask specific questions to gather detailed information
3. **Expert Guidance**: Provide recommendations based on project management best practices
4. **Reference, Don't Display**: Reference document sections without showing full content
5. **Progressive Understanding**: Build understanding through conversation

WHAT NOT TO DO:
- DO NOT display the entire project document in your responses
- DO NOT copy large sections of the document into chat
- DO NOT provide document summaries unless specifically requested
- DO NOT overwhelm users with process details

WHAT TO DO:
- Ask specific, targeted questions about project details
- Provide expert recommendations and guidance
- Reference relevant sections: "I see in your technical requirements..." 
- Help users think through challenges and solutions
- Guide project development through conversation

EXAMPLE RESPONSES:
❌ "Here's what I captured: [long document content]"
✅ "Based on your technical requirements, have you considered how you'll handle the type inference challenges you mentioned?"

❌ "Let me update these sections: [document display]"
✅ "I've noted those specific requirements. What's your biggest concern about the conversion accuracy?"

Focus on being a knowledgeable project planning consultant who guides through conversation."""
        
        return enhanced_prompt
    
    async def process_message(self, user_message: str, conversation_context: str, 
                            document_context: str, reference_context: str = "") -> str:
        """Enhanced process message with full conversation history and better memory."""
        try:
            # If no LLM is available, provide a fallback response
            if self.llm is None:
                return self._generate_fallback_response(user_message, reference_context)
            
            logger.info(f"MEMORY DEBUG: Processing message for {self.project_slug}")
            logger.info(f"MEMORY DEBUG: User message: {user_message[:100]}...")
            logger.info(f"MEMORY DEBUG: Conversation context length: {len(conversation_context)} chars")
            logger.info(f"MEMORY DEBUG: Reference context: {reference_context[:200] if reference_context else 'None'}...")
            
            # Get enhanced system prompt
            system_prompt = await self.get_system_prompt()
            
            # Get full conversation history from memory
            conversation_messages = []
            if self.conversation_memory:
                try:
                    # Try to get the full conversation history as LangChain messages
                    conversation_messages = self.conversation_memory.get_langchain_messages(max_messages=20)
                    logger.info(f"MEMORY DEBUG: Retrieved {len(conversation_messages)} messages from memory")
                    
                    # Log the last few messages for debugging
                    for i, msg in enumerate(conversation_messages[-4:]):
                        role = "User" if hasattr(msg, '__class__') and 'Human' in msg.__class__.__name__ else "Assistant"
                        logger.info(f"MEMORY DEBUG: Recent message {i}: {role}: {msg.content[:100]}...")
                        
                except Exception as e:
                    logger.error(f"MEMORY DEBUG: Error getting conversation messages: {e}")
                    conversation_messages = []
            
            # Build enhanced context for chat agent
            reference_section = ""
            if reference_context:
                reference_section = f"""

REFERENCE CONTEXT DETECTED:
The user is referring to specific content from previous messages. Use this context to understand their reference:
{reference_context}
"""
            
            enhanced_context = f"""{system_prompt}

PROJECT: {self.project_slug.replace('-', ' ').title()}

CURRENT PROJECT DOCUMENT (Preview):
{document_context[:1000]}{"..." if len(document_context) > 1000 else ""}

CONVERSATION HISTORY:
{conversation_context}{reference_section}

CRITICAL MEMORY INSTRUCTIONS FOR THIS CONVERSATION:
- You MUST remember what you said in your previous responses
- When user references "those metrics" or "what you mentioned", recall your specific recommendations
- When user says "yes add all" or similar, know exactly what items you recommended
- Maintain perfect continuity with your previous responses in this conversation
- Never ask for permission to make document changes - they happen automatically in the background
- Do NOT ask "Should I update the document?" or "Shall I go ahead and add this?" 
- Simply acknowledge information provided and continue the conversation naturally
- Document extraction and updates are handled automatically by the Info Agent

You are continuing this conversation with full awareness of previous exchanges. Provide a helpful, natural response that builds on the conversation context."""
            
            # Prepare enhanced messages for LLM - include conversation history
            messages = [SystemMessage(content=enhanced_context)]
            
            # Add conversation history messages if available
            if conversation_messages:
                # Add recent conversation history (last 10 messages to manage context window)
                recent_messages = conversation_messages[-10:] if len(conversation_messages) > 10 else conversation_messages
                messages.extend(recent_messages)
                logger.info(f"MEMORY DEBUG: Including {len(recent_messages)} conversation history messages in context")
            
            # Add current user message
            messages.append(HumanMessage(content=user_message))
            
            logger.info(f"MEMORY DEBUG: Sending {len(messages)} total messages to LLM")
            
            # Generate response
            response = await self.llm.ainvoke(messages)
            
            logger.info(f"MEMORY DEBUG: Generated response: {response.content[:200]}...")
            logger.info(f"Chat agent generated response for {self.project_slug}")
            return response.content
            
        except Exception as e:
            logger.error(f"Error in enhanced chat agent processing: {e}", exc_info=True)
            return "I apologize, but I encountered an error processing your message. Could you please try rephrasing your question?"
    
    def _generate_fallback_response(self, user_message: str, reference_context: str) -> str:
        """Generate a fallback response when LLM is not available."""
        
        # Check if this looks like a reference to add something to document
        user_lower = user_message.lower()
        reference_keywords = [
            "add that", "add those", "include that", "include those", 
            "use that", "apply that", "implement that", "add this",
            "those metrics", "that information", "the metrics", "the details",
            "what you mentioned", "what you suggested", "your recommendation"
        ]
        
        if any(keyword in user_lower for keyword in reference_keywords):
            if reference_context:
                return f"I understand you'd like to add the information we just discussed to the document. I've noted your request and the relevant information will be processed for document updates."
            else:
                return "I understand you'd like to add something to the document. Could you please specify what information you'd like me to include?"
        
        # Generic helpful response
        return f"Thank you for your message about '{user_message[:50]}...'. I'm currently running in limited mode but I've noted your input and will do my best to help with your project planning needs."
    
    async def chat_with_context(self, user_message: str, conversation_messages: List, document_context: str = None, reference_context: str = None) -> str:
        """Chat method that takes conversation messages, document context, and reference context directly."""
        try:
            # If no LLM is available, provide a fallback response
            if self.llm is None:
                return self._generate_fallback_response(user_message, "")
            
            logger.info(f"ChatAgent: Processing message with {len(conversation_messages)} conversation messages")
            
            # Get enhanced system prompt
            system_prompt = await self.get_system_prompt()
            
            # Build context string from conversation messages
            conversation_context = ""
            if conversation_messages:
                for msg in conversation_messages[-10:]:  # Last 10 messages
                    role = "User" if hasattr(msg, '__class__') and 'Human' in msg.__class__.__name__ else "Assistant"
                    conversation_context += f"{role}: {msg.content[:500]}...\n\n"
            
            # Build enhanced context for chat agent
            reference_section = ""
            if reference_context:
                reference_section = f"""

REFERENCE CONTEXT DETECTED:
The user is referencing specific content from the conversation. Here's what they're referring to:
{reference_context}

CRITICAL INSTRUCTION: The user's current message (like "add that to the document") references the above content. 
DO NOT ask for clarification - you have all the information needed. 
Respond confidently that you understand what they're referring to and that the information will be/has been added to the document.
Example: "I'll add those security recommendations to the document" or "I've noted those details and they'll be included in the project documentation."
DO NOT say things like "What specific details would you like to include?" - you already have the details from the reference context above."""

            enhanced_context = f"""{system_prompt}

PROJECT: {self.project_slug.replace('-', ' ').title()}

CONVERSATION HISTORY:
{conversation_context}{reference_section}

CURRENT PROJECT DOCUMENT (Preview):
{document_context[:1000] if document_context else "No document context available"}{"..." if document_context and len(document_context) > 1000 else ""}

{'⚠️ CRITICAL PRIORITY: Reference context detected above. The user is referring to content from the CONVERSATION (the numbered recommendations you just provided), NOT from the project document. Use the conversation reference context, not document content. When they say "add those" they mean the items from your previous response.' if reference_context else ''}

CRITICAL MEMORY INSTRUCTIONS FOR THIS CONVERSATION:
- You MUST remember what you said in your previous responses
- When user references previous messages, recall your specific content
- Maintain perfect continuity with your previous responses in this conversation
- Document extraction and updates are handled automatically by the Info Agent

You are continuing this conversation with full awareness of previous exchanges. Provide a helpful, natural response that builds on the conversation context."""
            
            # Prepare messages for LLM
            messages = [SystemMessage(content=enhanced_context)]
            
            # Add recent conversation history
            if conversation_messages:
                recent_messages = conversation_messages[-10:] if len(conversation_messages) > 10 else conversation_messages
                messages.extend(recent_messages)
            
            # Add current user message
            messages.append(HumanMessage(content=user_message))
            
            logger.info(f"ChatAgent: Sending {len(messages)} messages to LLM")
            
            # Generate response
            response = await self.llm.ainvoke(messages)
            
            logger.info(f"ChatAgent: Generated response ({len(response.content)} chars)")
            return response.content
            
        except Exception as e:
            logger.error(f"Error in chat_with_context: {e}", exc_info=True)
            return "I apologize, but I encountered an error processing your message. Could you please try rephrasing your question?"
    
class InfoAgent:
    """Specialized agent for extracting information and updating documents."""
    
    def __init__(self, project_slug: str, model: str = "gpt-4o-mini"):
        self.project_slug = project_slug
        self.model = model
        self.llm = None  # Lazy initialization
        self.conversation_memory = None
        self.markdown_memory = None
        self.llm_analyzer = None
    
    async def initialize(self, conversation_memory_or_user_id=None, markdown_memory=None):
        """Initialize agent with memory instances (supports both legacy and unified)."""
        
        # Check if this is unified memory call (single string parameter)
        if isinstance(conversation_memory_or_user_id, str) and markdown_memory is None:
            # Phase 2: Unified memory initialization
            user_id = conversation_memory_or_user_id
            
            # Get memory contexts using unified system
            memory_context = await get_conversation_memory_for_project(self.project_slug, user_id)
            
            # Store conversation memory as dictionary for reading
            self.conversation_memory = memory_context
            
            # Create proper CompatibilityMarkdownMemory object for document updates
            from .core.memory_compatibility import CompatibilityMarkdownMemory
            self.markdown_memory = CompatibilityMarkdownMemory(self.project_slug)
            
            logger.info(f"InfoAgent initialized with unified memory system for {self.project_slug}")
        else:
            # Legacy initialization
            self.conversation_memory = conversation_memory_or_user_id
            self.markdown_memory = markdown_memory
            
            logger.info(f"InfoAgent initialized with legacy memory system for {self.project_slug}")
        
        # Common initialization for both paths
        # Only initialize LLM analyzer if we have an API key
        api_key = self._get_openai_api_key() 
        if api_key:
            self.llm_analyzer = LLMReferenceAnalyzer(self.model)
        else:
            self.llm_analyzer = None
        
        # Initialize LLM only if we have an API key
        if self.llm is None:
            api_key = self._get_openai_api_key()
            if api_key:
                self.llm = ChatOpenAI(
                    model=self.model,
                    temperature=0.1,
                    api_key=api_key
                )
                logger.info(f"Initialized InfoAgent LLM with model {self.model}")
            else:
                logger.warning(f"No API key available, InfoAgent will skip document extraction")
    
    def _get_openai_api_key(self) -> str:
        """Parse OpenAI API key using same logic as existing system."""
        api_key = os.getenv("OPENAI_API_KEY", "")
        if not api_key:
            return ""
        
        # Handle AWS App Runner JSON format
        if api_key.startswith("{") and api_key.endswith("}"):
            try:
                secrets = json.loads(api_key)
                return secrets.get("OPENAI_API_KEY", api_key)
            except json.JSONDecodeError:
                logger.warning(f"Failed to parse JSON API key format")
                return api_key
        
        return api_key
    
    async def get_system_prompt(self) -> str:
        """Get enhanced system prompt for detailed info agent."""
        try:
            # Load info agent prompt from file
            info_prompt_file = Path("prompts/info_agent.md")
            if info_prompt_file.exists():
                async with aiofiles.open(info_prompt_file, 'r', encoding='utf-8') as f:
                    return await f.read()
            else:
                logger.warning("Info agent prompt file not found, using enhanced fallback")
        except Exception as e:
            logger.error(f"Error loading info agent prompt: {e}")
        
        # Enhanced fallback prompt if file loading fails
        return """ROLE: You are the INFO AGENT - responsible for capturing detailed, specific project information.

CORE RESPONSIBILITIES:
- Extract comprehensive, detailed information from conversations
- Preserve exact technical specifications and requirements
- Create appropriate document structure for different project types
- Capture granular details that enable project execution
- Maintain information accuracy and completeness

EXTRACTION PRINCIPLES:
1. **Capture Exact Details**: Preserve specific numbers, technologies, processes, constraints
2. **Technical Precision**: Maintain technical language and specifications
3. **Comprehensive Coverage**: Extract all relevant project information
4. **Dynamic Structure**: Create new sections when information doesn't fit existing categories
5. **Implementation Focus**: Capture details needed for actual project execution

INFORMATION PRIORITIES:
- Technical specifications and requirements
- Exact processes and methodologies
- Specific metrics and success criteria
- Detailed constraints and limitations
- Implementation approaches and technologies
- Quality assurance and testing strategies
- Timeline details and dependencies
- Resource requirements and allocations

You capture the detailed information that makes projects executable, not just understandable."""
    
    async def analyze_and_extract(self, user_input: str, ai_response: str, 
                                conversation_context: str) -> Dict[str, Any]:
        """Enhanced analyze_and_extract - captures detailed, specific information and creates appropriate document structure."""
        try:
            # If no LLM is available, return empty extraction data
            if self.llm is None:
                logger.info(f"Info agent skipping extraction - no LLM available for {self.project_slug}")
                return {
                    "has_extractable_info": False,
                    "extraction_confidence": "low",
                    "extracted_data": {},
                    "reason": "No LLM available for extraction"
                }
            
            logger.info(f"Enhanced info agent analyzing conversation for {self.project_slug}")
            
            # Enhanced reference analyzer
            if self.llm_analyzer:
                reference_analysis = await self._enhanced_reference_analyzer(
                    user_input, conversation_context, ai_response
                )
            else:
                # Fallback when no LLM analyzer available
                reference_analysis = {
                    "has_reference": False,
                    "reference_type": "none",
                    "referenced_content": "",
                    "action_requested": "",
                    "confidence": "low",
                    "extraction_priority": "low"
                }
            
            # Get current document context
            current_document = await self.markdown_memory.get_document_context()
            
            # Enhanced extraction prompt for detailed information capture
            extraction_prompt = f"""You are an expert information extraction agent responsible for capturing detailed, specific project information from conversations.

CRITICAL INSTRUCTIONS:
1. **ADDITIVE BEHAVIOR**: When updating existing sections, provide ONLY new/additional content to ADD, not full section rewrites
2. Capture EXACT details, specifications, technical requirements, and specific information  
3. Preserve user's exact language when it contains important technical details
4. Do NOT summarize or abbreviate - capture comprehensive, detailed information including ALL context and explanations
5. Include user's reasoning, examples, analogies, and detailed explanations - these provide crucial context
6. When users explain problems or challenges, capture the FULL explanation including why it's a problem, how it manifests, and what the implications are
7. Create new document sections if information doesn't fit existing categories
8. Store granular details that would be valuable for project execution including user's thought process and reasoning
9. NEVER reduce detailed explanations to brief summaries - expand and elaborate while preserving all original meaning

CURRENT DOCUMENT:
{current_document}

CONVERSATION CONTEXT:
{conversation_context}

LATEST EXCHANGE:
User: {user_input}
Assistant: {ai_response}

REFERENCE ANALYSIS:
{json.dumps(reference_analysis, indent=2)}

EXTRACTION TASK:
Analyze the conversation for detailed project information. For each piece of information:

1. **Capture Specific Details**: Extract exact specifications, technical requirements, metrics, constraints, processes, tools, technologies, methodologies, etc. Include ALL context, reasoning, examples, and explanations provided by the user.

2. **Preserve and Expand Technical Language**: Keep technical terms, specific numbers, exact requirements, and precise descriptions. When users provide detailed explanations of problems, challenges, or implementations, preserve the ENTIRE explanation including their reasoning, examples, and context.

3. **Maintain User's Thought Process**: If users explain WHY something is a problem, HOW it manifests, WHAT the implications are, or WHAT they've tried, capture all of this contextual information as it's crucial for understanding the full scope.

4. **Determine Appropriate Section**: Map information to existing sections OR create new sections if needed

5. **Document Structure**: Use these guidelines for section mapping:
   - **Objective**: Specific goals, success criteria, deliverables, outcomes
   - **Context**: Background, problem statement, business rationale, motivation
   - **Technical Requirements**: Specifications, technologies, tools, platforms, architectures
   - **Functional Requirements**: Features, capabilities, user stories, workflows
   - **Performance Requirements**: Metrics, benchmarks, performance criteria, SLAs
   - **Implementation Details**: Processes, methodologies, approaches, techniques
   - **Quality Assurance**: Testing strategies, validation methods, quality gates
   - **Security Requirements**: Security specifications, compliance, access controls
   - **Integration Requirements**: System integrations, APIs, data flows
   - **Infrastructure Requirements**: Hardware, software, deployment, scaling
   - **Data Requirements**: Data sources, formats, processing, storage
   - **Timeline & Milestones**: Specific dates, phases, dependencies, deadlines
   - **Resource Requirements**: Personnel, budget, tools, equipment
   - **Constraints & Risks**: Limitations, dependencies, potential issues
   - **Stakeholders & Collaborators**: People, roles, responsibilities, contacts
   - **Glossary**: Technical terms, acronyms, definitions
   - **Success Metrics**: KPIs, measurement criteria, validation methods
   - **Compliance Requirements**: Standards, regulations, certifications
   - **Custom Sections**: Create new sections for information that doesn't fit above

Return JSON with sections to update. Include new sections if needed:

CRITICAL: Default behavior is to INTEGRATE with existing content by ADDING new information. Only use replace_existing=true for explicit replacement requests.

IMPORTANT: When adding to existing sections, provide ONLY the NEW INCREMENTAL content to add, not a rewrite of the entire section. Your content will be APPENDED to existing content.

DO NOT include section headers/titles in your content - only provide the actual content to add.

EXAMPLE:
- If section has: "- Feature A\n- Feature B"  
- And you want to add Feature C
- Provide content: "- Feature C" (NOT "Features for X\n- Feature C" or "Features\n- Feature A\n- Feature B\n- Feature C")

WRONG: "Features for the Chatbox\n- New feature"
CORRECT: "- New feature"

{{
    "updates": {{
        "Section Name": {{
            "content": "NEW content to ADD (bullet points, paragraphs, etc.) - do NOT rewrite existing content",
            "is_new_section": true/false,
            "section_description": "brief description of what this section contains",
            "replace_existing": false  // Only set to true if explicitly replacing content
        }}
    }},
    "extracted_details": [
        "list of specific details captured from the conversation"
    ],
    "reasoning": "explanation of extraction decisions and section mappings"
}}

EXAMPLES OF DETAILED EXTRACTION (PRESERVE ALL CONTEXT AND REASONING):

EXAMPLE 1 - Adding to existing section:
Input: "I also want the ability to make suggestions and provide advice to users"
Existing Features section contains: "- Document view to save information\n- Chatbox interface\n- Ability to add, delete, and archive projects"
Extract: 
- Features: "- **Ability to make suggestions and provide advice to users while they develop their project ideas**"
(NOTE: Provide ONLY the new feature to ADD, no section headers, not the entire features list)

EXAMPLE 2 - New technical requirements:
Input: "We need the system to handle 1000 concurrent users with 99.9% uptime"
Extract: 
- Performance Requirements: "- System must support 1000 concurrent users with 99.9% uptime availability target"
- Success Metrics: "- System performance will be measured by concurrent user capacity (target: 1000 users) and uptime percentage (target: 99.9%)"

Input: "The problems with using the OpenAI API is it doesn't work like in ChatGPT where your last response is automatically recorded and you can reference that in your next message, each message is completely separate"
Extract:
- Technical Challenges: "OpenAI API integration challenges with message continuity: Unlike ChatGPT's conversational interface where responses are automatically recorded and can be referenced in subsequent messages, the OpenAI API treats each message as completely separate. This creates difficulties in maintaining conversation context and continuity across API calls."
- Implementation Details: "API behavior difference: ChatGPT automatically maintains conversation history and context, while OpenAI API requires manual conversation state management since each message is treated as an isolated request"
- Integration Requirements: "Need to implement custom conversation state management to bridge the gap between ChatGPT's automatic context retention and OpenAI API's stateless message handling"

Input: "The Verilog to VHDL converter struggles with HdlTypeAuto inference"
Extract:
- Technical Challenges: "Verilog to VHDL converter encounters difficulties with HdlTypeAuto inference mechanisms"
- Technical Requirements: "Verilog to VHDL conversion capability required with proper type inference handling"
- Implementation Details: "Type inference system needed for HdlTypeAuto conversion, addressing current conversion struggles"

Capture ALL specific details, technical specifications, exact requirements, and granular information."""
            
            # Get extraction response
            messages = [SystemMessage(content=extraction_prompt)]
            response = await self.llm.ainvoke(messages)
            
            # Parse response
            try:
                extraction_data = json.loads(response.content)
                
                # Log extracted details for monitoring
                extracted_details = extraction_data.get("extracted_details", [])
                if extracted_details:
                    logger.info(f"Extracted {len(extracted_details)} specific details: {extracted_details[:3]}...")
                
                logger.info(f"Enhanced info agent extracted data: {extraction_data.get('reasoning', 'No reasoning provided')}")
                return extraction_data
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse enhanced info agent response: {e}")
                return {"updates": {}, "reasoning": "Failed to parse extraction response"}
                
        except Exception as e:
            logger.error(f"Error in enhanced info agent analysis: {e}", exc_info=True)
            return {"updates": {}, "reasoning": f"Error in analysis: {str(e)}"}
    
    async def _enhanced_reference_analyzer(self, user_message: str, conversation_context: str, last_ai_response: str) -> Dict[str, Any]:
        """Enhanced LLM-powered reference detection with detailed analysis."""
        
        analysis_prompt = f"""You are analyzing a user message to determine detailed references and extract specific information.

CONVERSATION CONTEXT:
{conversation_context}

MOST RECENT AI RESPONSE:
{last_ai_response}

CURRENT USER MESSAGE:
{user_message}

Analyze the user's message for:

1. **References to Previous Content**: What specifically are they referring to?
2. **New Technical Information**: Specific details, requirements, specifications
3. **Action Requests**: What do they want done with the information?
4. **Context Clues**: Implicit information that should be captured

Return detailed JSON:
{{
    "has_reference": true/false,
    "reference_type": "explicit/implicit/pronoun/contextual",
    "referenced_content": {{
        "specific_items": ["list of specific items referenced"],
        "technical_details": ["technical specifications mentioned"],
        "requirements": ["specific requirements stated"]
    }},
    "new_information": {{
        "technical_specs": ["new technical information provided"],
        "requirements": ["new requirements mentioned"],
        "constraints": ["limitations or constraints mentioned"],
        "processes": ["processes or methodologies mentioned"],
        "metrics": ["specific numbers, percentages, or measurements"]
    }},
    "action_requested": "what they want done with the information",
    "confidence": "high/medium/low",
    "extraction_priority": "high/medium/low"
}}

Focus on capturing specific, actionable information rather than general statements.
"""
        
        try:
            messages = [SystemMessage(content=analysis_prompt)]
            response = await self.llm.ainvoke(messages)
            return json.loads(response.content)
        except Exception as e:
            logger.error(f"Enhanced reference analysis error: {e}")
            return {"has_reference": False, "extraction_priority": "low"}
    
    async def update_document(self, extraction_data: Dict[str, Any], user_id: str = "anonymous") -> int:
        """Enhanced update document with integration-first approach and automatic summary updates."""
        try:
            updates = extraction_data.get("updates", {})
            updates_made = 0
            
            # Get contributor name
            try:
                from .user_registry import get_user_display_name
                contributor = await get_user_display_name(user_id)
            except:
                contributor = user_id
            
            # Apply updates to document with integration-first logic
            for section_name, section_data in updates.items():
                if isinstance(section_data, dict):
                    content = section_data.get("content", "")
                    is_new = section_data.get("is_new_section", False)
                    section_description = section_data.get("section_description", "")
                    replace_mode = section_data.get("replace_existing", False)  # Only replace if explicitly requested
                else:
                    content = str(section_data)
                    is_new = False
                    section_description = ""
                    replace_mode = False
                
                if content and content.strip():
                    # Use integration by default, replacement only when explicitly requested
                    if replace_mode:
                        await self.markdown_memory.replace_section(section_name, content.strip(), contributor, user_id)
                        logger.info(f"Enhanced info agent REPLACED section '{section_name}' (explicit request)")
                    else:
                        # Default behavior: integrate with existing content
                        await self.markdown_memory.update_section(section_name, content.strip(), contributor, user_id)
                        logger.info(f"Enhanced info agent INTEGRATED into section '{section_name}'")
                    
                    updates_made += 1
                    
                    if is_new:
                        logger.info(f"Enhanced info agent created new section: {section_name} - {section_description}")
            
            # Update Executive Summary with comprehensive project overview
            if updates_made > 0:
                await self._update_executive_summary(contributor, user_id)
                logger.info(f"Enhanced info agent updated Executive Summary based on {updates_made} changes")
            
            # Log extracted details for monitoring
            extracted_details = extraction_data.get("extracted_details", [])
            if extracted_details:
                logger.info(f"Enhanced info agent captured {len(extracted_details)} specific details")
            
            return updates_made
            
        except Exception as e:
            logger.error(f"Error in enhanced document update: {e}", exc_info=True)
            return 0
    
    async def _update_executive_summary(self, contributor: str, user_id: str) -> None:
        """Generate and update comprehensive executive summary based on all project content."""
        try:
            if self.llm is None:
                logger.debug("Skipping executive summary update - no LLM available")
                return
            
            # Get full document context
            current_document = await self.markdown_memory.get_document_context()
            
            # Check if current summary is a generic placeholder
            is_placeholder_summary = ("Project documentation is being developed through conversation with the AI assistant" in current_document or
                                    "Please provide more information about this project's purpose, goals, and context" in current_document)
            
            # Generate comprehensive summary
            summary_prompt = f"""You are an expert project documentation analyst. Create a comprehensive Executive Summary that synthesizes ALL the project information below.

CURRENT PROJECT DOCUMENT:
{current_document}

INSTRUCTIONS:
1. Create a concise but comprehensive Executive Summary (2-4 paragraphs)
2. Capture the project's purpose, scope, key requirements, and current status
3. Highlight critical success factors, main challenges, and next steps
4. Include key technical details and business context
5. Make it standalone - someone reading only the summary should understand the project
6. Focus on what matters most for stakeholders and decision-makers

Generate ONLY the Executive Summary content (no headers, no formatting - just the content):"""

            try:
                response = await self.llm.ainvoke([
                    {"role": "user", "content": summary_prompt}
                ])
                
                summary_content = response.content.strip()
                
                if summary_content and len(summary_content) > 50:  # Ensure meaningful content
                    # Always replace placeholder summaries, otherwise only update if substantial content exists
                    should_update = is_placeholder_summary or (len(current_document) > 1000)
                    
                    if should_update:
                        # Replace the Executive Summary section entirely with the new comprehensive summary
                        await self.markdown_memory.replace_section("Executive Summary", summary_content, contributor, user_id)
                        if is_placeholder_summary:
                            logger.info(f"Enhanced info agent replaced placeholder Executive Summary with actual project overview")
                        else:
                            logger.info(f"Enhanced info agent updated Executive Summary with comprehensive overview")
                    else:
                        logger.debug("Document still too sparse for meaningful summary update")
                else:
                    logger.debug("Generated summary too short, keeping existing summary")
                    
            except Exception as e:
                logger.error(f"Error generating executive summary: {e}")
                
        except Exception as e:
            logger.error(f"Error in executive summary update: {e}")
    
    async def should_update_document(self, user_message: str, ai_response: str) -> bool:
        """Determine if document updates are needed based on the conversation."""
        try:
            # Use analyze_and_extract to determine if updates are needed
            extraction_data = await self.analyze_and_extract(
                user_message, ai_response, ""
            )
            
            # Check if there are any updates to be made (the actual return format)
            updates = extraction_data.get("updates", {})
            extracted_details = extraction_data.get("extracted_details", [])
            reasoning = extraction_data.get("reasoning", "")
            
            # Return True if there are updates to be made OR extracted details
            has_updates = len(updates) > 0 or len(extracted_details) > 0
            
            # Also return True if the reasoning suggests document updates are needed
            update_keywords = ["add", "update", "document", "section", "include", "insert"]
            reasoning_suggests_updates = any(keyword in reasoning.lower() for keyword in update_keywords)
            
            should_update = has_updates or reasoning_suggests_updates
            
            logger.info(f"InfoAgent should_update_document: {should_update} (updates: {len(updates)}, details: {len(extracted_details)}, reasoning_match: {reasoning_suggests_updates})")
            return should_update
            
        except Exception as e:
            logger.error(f"Error in should_update_document: {e}")
            return False
    
    async def extract_and_update_information(self, user_message: str, ai_response: str, user_id: str = "anonymous") -> List[str]:
        """Extract information and update document, returning list of updates made."""
        try:
            # Get conversation context (empty for unified system call)
            conversation_context = ""
            
            # Analyze and extract information
            extraction_data = await self.analyze_and_extract(
                user_message, ai_response, conversation_context
            )
            
            # Update document using existing method
            updates_made = await self.update_document(extraction_data, user_id)
            
            # Return list of updates (simulate list for compatibility)
            if updates_made > 0:
                update_list = [f"Updated {updates_made} section(s) in document"]
                logger.info(f"InfoAgent extract_and_update_information: {updates_made} updates made")
                return update_list
            else:
                logger.info(f"InfoAgent extract_and_update_information: No updates made")
                return []
                
        except Exception as e:
            logger.error(f"Error in extract_and_update_information: {e}")
            return []
    
    async def generate_clarifying_questions(self, user_input: str, ai_response: str, conversation_context: str) -> str:
        """Generate relevant clarifying questions based on the information just processed."""
        try:
            if self.llm is None:
                return ""
            
            # Get current document for context
            current_document = await self.markdown_memory.get_document_context()
            
            questions_prompt = f"""You are an expert project planning consultant. Based on the information just added to this project, generate 3-5 specific, actionable clarifying questions that would help gather more details or resolve potential ambiguities.

CURRENT PROJECT DOCUMENT:
{current_document}

LATEST CONVERSATION:
User Input: {user_input}
AI Response: {ai_response}
Context: {conversation_context}

INSTRUCTIONS:
1. Generate questions that are specific and actionable
2. Focus on technical details, requirements, constraints, or implementation specifics
3. Address potential gaps or ambiguities in the information just added
4. Help clarify scope, priorities, timelines, or dependencies
5. Only generate questions that would genuinely help improve the project documentation

Format as a simple bulleted list. If no meaningful questions can be generated, return an empty string.

Example format:
- What specific performance benchmarks are expected for the API response times?
- Who will be responsible for the security audit and when should it be completed?
- Are there any existing systems that need to integrate with this solution?"""

            try:
                response = await self.llm.ainvoke([
                    {"role": "user", "content": questions_prompt}
                ])
                
                questions = response.content.strip()
                
                # Only return questions if they're meaningful
                if questions and len(questions) > 20 and not questions.lower().startswith("no meaningful"):
                    return questions
                else:
                    return ""
                    
            except Exception as e:
                logger.error(f"Error generating clarifying questions: {e}")
                return ""
                
        except Exception as e:
            logger.error(f"Error in clarifying questions generation: {e}")
            return ""
    
    async def migrate_placeholder_summary(self, contributor: str = "System", user_id: str = "system") -> bool:
        """Migrate old placeholder Executive Summary to use actual project description."""
        try:
            current_document = await self.markdown_memory.get_document_context()
            
            # Check if this is a placeholder summary that needs migration
            if ("Project documentation is being developed through conversation with the AI assistant" in current_document or
                "Please provide more information about this project's purpose, goals, and context" in current_document):
                # Try to get the original project description
                try:
                    projects = await ProjectRegistry.list_projects()
                    if self.project_slug in projects:
                        project_info = projects[self.project_slug]
                        project_description = project_info.get("description", "")
                        
                        if project_description and project_description.strip():
                            # Replace the placeholder with the actual project description
                            await self.markdown_memory.replace_section("Executive Summary", project_description.strip(), contributor, user_id)
                            logger.info(f"Migrated placeholder Executive Summary to actual project description for {self.project_slug}")
                            return True
                        else:
                            logger.debug(f"No project description available for migration: {self.project_slug}")
                except Exception as e:
                    logger.error(f"Error accessing project registry during migration: {e}")
            
            return False
            
        except Exception as e:
            logger.error(f"Error migrating placeholder summary: {e}")
            return False

class AgentCoordinator:
    """Coordinates interaction between Chat and Info agents."""
    
    def __init__(self, project_slug: str = "default", model: str = "gpt-4o-mini", use_modern_memory: bool = True, use_unified_memory: bool = False):
        self.project_slug = project_slug
        self.use_modern_memory = use_modern_memory
        self.use_unified_memory = use_unified_memory  # Phase 2: Support for unified memory
        self.chat_agent = ChatAgent(project_slug, model)
        self.info_agent = InfoAgent(project_slug, model)
        
        # Initialize modern LLM reference detector if we have an API key
        api_key = os.getenv("OPENAI_API_KEY", "")
        if api_key:
            self.llm_reference_detector = LLMReferenceAnalyzer(model=model)
            self.context_builder = None  # Functionality integrated into LLMReferenceAnalyzer
        else:
            self.llm_reference_detector = None
            self.context_builder = None
    
    async def initialize(self, conversation_memory, markdown_memory):
        """Initialize both agents with memory instances (legacy method)."""
        await self.chat_agent.initialize(conversation_memory, markdown_memory)
        await self.info_agent.initialize(conversation_memory, markdown_memory)
        
    async def initialize_unified(self, user_id: str = "anonymous"):
        """Initialize both agents with unified memory system (Phase 2)."""
        await self.chat_agent.initialize(user_id)
        await self.info_agent.initialize(user_id)
    
    async def process_conversation_turn(self, user_message: str, conversation_memory, 
                                      markdown_memory, user_id: str = "anonymous") -> Tuple[str, int]:
        """
        Process a complete conversation turn with both agents.
        
        Returns:
            Tuple of (ai_response, updates_made_count)
        """
        try:
            # Initialize agents with memory instances
            await self.initialize(conversation_memory, markdown_memory)
            
            # Check for and migrate placeholder Executive Summary if needed
            try:
                migrated = await self.info_agent.migrate_placeholder_summary("System", "system")
                if migrated:
                    logger.info("Migrated placeholder Executive Summary during conversation processing")
            except Exception as migration_error:
                logger.error(f"Error during summary migration: {migration_error}")
            
            # Get conversation context
            conversation_context = conversation_memory.get_formatted_context(max_exchanges=5)
            document_context = await markdown_memory.get_document_context()
            
            # Get conversation messages for modern reference detection
            conversation_messages = conversation_memory.get_langchain_messages(max_messages=10)
            
            # Modern LLM-based reference detection
            reference_context = ""
            reference_analysis = None
            
            if os.getenv("USE_LLM_REFERENCE_DETECTION", "true").lower() == "true" and self.llm_reference_detector:
                try:
                    logger.info(f"DEBUG: Processing LLM reference detection for: '{user_message[:100]}...'")
                    logger.info(f"DEBUG: Conversation history: {len(conversation_messages)} messages")
                    
                    # Use new LLM-based reference detection
                    reference_analysis = await self.llm_reference_detector.analyze_reference(
                        current_message=user_message,
                        conversation_history=conversation_messages,
                        max_history=8
                    )
                    
                    logger.info(f"DEBUG: LLM Reference analysis: {reference_analysis.explanation}")
                    logger.info(f"DEBUG: Has reference: {reference_analysis.has_reference}, Confidence: {reference_analysis.confidence}")
                    
                    if reference_analysis.has_reference and reference_analysis.confidence in ["high", "medium"]:
                        # Build rich context using the detected reference
                        reference_context = self.context_builder.build_context_for_reference(
                            current_message=user_message,
                            conversation_history=conversation_messages,
                            reference_analysis=reference_analysis,
                            max_context_length=1500
                        )
                        logger.info(f"DEBUG: Built reference context: {len(reference_context)} characters")
                        logger.info(f"Agent coordinator detected {reference_analysis.reference_type} reference with {reference_analysis.confidence} confidence")
                    else:
                        logger.info(f"DEBUG: No strong reference detected (confidence: {reference_analysis.confidence})")
                        
                except Exception as e:
                    logger.error(f"LLM reference detection failed: {e}", exc_info=True)
                    # Fall back to rule-based detection when LLM fails
                    logger.info("DEBUG: Falling back to rule-based reference detection")
                    try:
                        reference_analysis = self.llm_reference_detector._fallback_reference_detection(
                            user_message, conversation_messages
                        )
                        logger.info(f"DEBUG: Fallback reference analysis: {reference_analysis.explanation}")
                        
                        if reference_analysis.has_reference and reference_analysis.confidence in ["high", "medium"]:
                            reference_context = self.context_builder.build_context_for_reference(
                                current_message=user_message,
                                conversation_history=conversation_messages,
                                reference_analysis=reference_analysis,
                                max_context_length=1500
                            )
                            logger.info(f"DEBUG: Built fallback reference context: {len(reference_context)} characters")
                            logger.info(f"Agent coordinator detected {reference_analysis.reference_type} reference with {reference_analysis.confidence} confidence (fallback)")
                    except Exception as fallback_error:
                        logger.error(f"Fallback reference detection also failed: {fallback_error}")
            else:
                # No LLM reference detector available, use basic rule-based detection
                logger.info("DEBUG: No LLM reference detector available, using basic rule-based detection")
                try:
                    # Use the LLMReferenceAnalyzer that's already defined in this file
                    temp_detector = LLMReferenceAnalyzer(model="gpt-4o-mini")  # Fallback analyzer
                    reference_analysis = temp_detector._fallback_reference_detection(
                        user_message, conversation_messages
                    )
                    logger.info(f"DEBUG: Basic reference analysis: {reference_analysis.explanation}")
                    
                    if reference_analysis.has_reference and reference_analysis.confidence in ["high", "medium"]:
                        # Context building is now integrated into LLMReferenceAnalyzer
                        context_builder = None  # Not needed - functionality integrated
                        reference_context = context_builder.build_context_for_reference(
                            current_message=user_message,
                            conversation_history=conversation_messages,
                            reference_analysis=reference_analysis,
                            max_context_length=1500
                        )
                        logger.info(f"DEBUG: Built basic reference context: {len(reference_context)} characters")
                        logger.info(f"Agent coordinator detected {reference_analysis.reference_type} reference with {reference_analysis.confidence} confidence (basic)")
                except Exception as basic_error:
                    logger.error(f"Basic reference detection failed: {basic_error}")
            
            # Step 1: Generate conversational response with Chat Agent
            ai_response = await self.chat_agent.process_message(
                user_message, conversation_context, document_context, reference_context
            )
            
            # Step 2: Update conversation memory
            logger.info(f"DEBUG: Storing conversation - User: '{user_message[:50]}...', AI: '{ai_response[:50]}...'")
            await conversation_memory.add_conversation(user_message, ai_response, user_id)
            
            # Step 3: Extract information and update document with Info Agent (background)
            updates_made = 0
            try:
                # Pass the reference context to the info agent for better extraction
                enriched_context = conversation_context
                if reference_context:
                    enriched_context = f"{conversation_context}\n\nREFERENCE CONTEXT:\n{reference_context}"
                    logger.info(f"DEBUG: Passing enriched context with reference to Info Agent")
                
                extraction_data = await self.info_agent.analyze_and_extract(
                    user_message, ai_response, enriched_context
                )
                
                updates_made = await self.info_agent.update_document(extraction_data, user_id)
                
                if updates_made > 0:
                    logger.info(f"Agent coordinator: Chat agent responded, Info agent made {updates_made} document updates")
                    
                    # Generate clarifying questions after making changes
                    try:
                        clarifying_questions = await self.info_agent.generate_clarifying_questions(
                            user_message, ai_response, enriched_context
                        )
                        
                        if clarifying_questions:
                            # Append clarifying questions to the AI response
                            questions_section = f"\n\n### Questions for Clarification:\n{clarifying_questions}"
                            ai_response += questions_section
                            logger.info(f"Agent coordinator: Added clarifying questions to response")
                            
                    except Exception as q_error:
                        logger.error(f"Error generating clarifying questions: {q_error}")
                        # Don't fail the whole process if questions fail
                else:
                    logger.debug("Agent coordinator: Chat agent responded, no document updates needed")
                    
            except Exception as e:
                logger.error(f"Info agent processing failed: {e}", exc_info=True)
            
            return ai_response, updates_made
            
        except Exception as e:
            logger.error(f"Error in agent coordination: {e}", exc_info=True)
            return "I apologize, but I encountered an error processing your request. Could you please try again?", 0


    async def process_conversation_turn_unified(self, user_message: str, user_id: str = "anonymous") -> Tuple[str, int]:
        """
        Process a complete conversation turn using unified memory system (Phase 2).
        
        Returns:
            Tuple of (ai_response, tokens_used)
        """
        try:
            # Initialize agents with unified memory
            await self.initialize_unified(user_id)
            
            # Get conversation context from unified memory
            memory_context = await get_conversation_memory_for_project(self.project_slug, user_id)
            conversation_messages = memory_context['messages']
            
            # Get document context from unified memory
            doc_context = await get_project_document_memory(self.project_slug)
            
            # Use LLM reference detector for context awareness if available
            if self.llm_reference_detector:
                # Get conversation context string
                conversation_context = ""
                if conversation_messages:
                    for msg in conversation_messages[-5:]:  # Last 5 messages for context
                        role = "User" if hasattr(msg, '__class__') and 'Human' in msg.__class__.__name__ else "Assistant"
                        conversation_context += f"{role}: {msg.content}\n\n"
                
                # Get last AI response
                last_ai_response = ""
                for msg in reversed(conversation_messages):
                    if hasattr(msg, '__class__') and 'AI' in msg.__class__.__name__:
                        last_ai_response = msg.content
                        break
                
                reference_analysis = await self.llm_reference_detector.analyze_reference(
                    user_message, conversation_context, last_ai_response
                )
                needs_context = reference_analysis.get('has_reference', False)
                
                if needs_context:
                    logger.info("Message needs document context - will include relevant sections")
                else:
                    logger.info("Message is conversational - will focus on chat response")
            else:
                # Fallback: assume context needed for project-specific queries
                needs_context = any(word in user_message.lower() for word in 
                                  ['project', 'document', 'section', 'update', 'what', 'how', 'when', 'where'])
            
            # Build reference context from analysis results
            reference_context_for_chat = None
            if needs_context and reference_analysis:
                referenced_content = reference_analysis.get('referenced_content', '')
                action_requested = reference_analysis.get('action_requested', '')
                logger.info(f"Building reference context: needs_context={needs_context}, has_reference={reference_analysis.get('has_reference')}, referenced_content='{referenced_content[:100]}...'")
                if referenced_content:
                    reference_context_for_chat = f"Referenced content: {referenced_content}\nAction requested: {action_requested}"
                    logger.info(f"Built reference_context_for_chat: {reference_context_for_chat[:200]}...")
                else:
                    logger.info("No referenced_content found in analysis")
            else:
                logger.info(f"Not building reference context: needs_context={needs_context}, reference_analysis={reference_analysis is not None}")

            # Generate response using ChatAgent with appropriate context
            if hasattr(self.chat_agent, 'chat_with_context'):
                # Use chat method if available
                ai_response = await self.chat_agent.chat_with_context(
                    user_message, 
                    conversation_messages,
                    doc_context['content'] if needs_context else None,
                    reference_context_for_chat
                )
            else:
                # Fallback to basic chat
                ai_response = f"I understand you're asking about: {user_message}. Let me help you with your project."
            
            # Check if document update is needed using InfoAgent
            updates_made = 0
            if needs_context and hasattr(self.info_agent, 'should_update_document'):
                should_update = await self.info_agent.should_update_document(user_message, ai_response)
                
                if should_update:
                    # Extract information and update document
                    info_updates = await self.info_agent.extract_and_update_information(
                        user_message, ai_response, user_id
                    )
                    updates_made = len(info_updates)
                    
                    if updates_made > 0:
                        logger.info(f"Made {updates_made} document updates based on conversation")
            
            # Save conversation to memory (this was missing!)
            logger.info(f"Saving conversation to memory: User: '{user_message[:50]}...', AI: '{ai_response[:50]}...'")
            await add_conversation_to_memory(self.project_slug, user_message, ai_response, user_id)
            
            logger.info(f"Processed conversation turn: {len(ai_response)} chars response, {updates_made} updates")
            return ai_response, updates_made
            
        except Exception as e:
            logger.error(f"Error in unified conversation turn processing: {e}")
            # Return fallback response
            return f"I apologize, but I encountered an error processing your request. Could you please try again?", 0


# Phase 2: Legacy classes kept for compatibility during migration
# These will be removed in Phase 5: Cleanup

class LegacyMemoryWrapper:
    """DEPRECATED: Wrapper to provide legacy ConversationMemory interface. Use unified memory system instead."""
    
    def __init__(self, project_slug: str, modern_memory):
        self.project_slug = project_slug
        self.modern_memory = modern_memory
        self.last_ai_response = None
        self._memory_initialized = False  # Need to initialize from database
        self._cached_messages = []  # Cache for sync access
    
    async def _initialize_langchain_memory(self) -> None:
        """Load existing messages from modern memory system."""
        if self._memory_initialized:
            return
        
        try:
            # Load existing messages from database using the same conversation ID format as storage
            # Storage uses just project_slug, so we need to get messages directly from unified memory
            unified_memory = await self.modern_memory._get_unified_memory() 
            messages_data = await unified_memory.get_conversation(self.project_slug, limit=50)
            
            # Convert to LangChain message format
            messages = []
            for msg_data in messages_data:
                if msg_data['role'] == 'user':
                    messages.append(HumanMessage(content=msg_data['content']))
                elif msg_data['role'] == 'assistant':
                    messages.append(AIMessage(content=msg_data['content']))
            
            self._cached_messages = messages
            self._memory_initialized = True
            
            # Set last AI response if available
            for msg in reversed(messages):
                if isinstance(msg, AIMessage):
                    self.last_ai_response = msg.content
                    break
            
            logger.info(f"LegacyMemoryWrapper initialized for {self.project_slug} with {len(messages)} messages")
            
        except Exception as e:
            logger.error(f"Failed to initialize LegacyMemoryWrapper: {e}")
            self._memory_initialized = True  # Prevent repeated failures
    
    async def add_conversation(self, user_input: str, ai_response: str, user_id: str = "anonymous") -> None:
        """Add conversation using modern memory system."""
        try:
            messages_to_add = []
            if user_input:
                user_msg = HumanMessage(content=user_input)
                await self.modern_memory.add_message(self.project_slug, user_msg, user_id)
                messages_to_add.append(user_msg)
            if ai_response:
                ai_msg = AIMessage(content=ai_response)
                await self.modern_memory.add_message(self.project_slug, ai_msg, user_id)
                messages_to_add.append(ai_msg)
                self.last_ai_response = ai_response
            
            # Update cache
            self._cached_messages.extend(messages_to_add)
            # Keep cache size reasonable
            if len(self._cached_messages) > 40:
                self._cached_messages = self._cached_messages[-40:]
                
            logger.info(f"Added conversation to {self.project_slug} via modern memory")
        except Exception as e:
            logger.error(f"Error adding conversation via wrapper: {e}")
    
    def _sync_last_ai_response(self):
        """Synchronize last_ai_response from cached messages or modern memory."""
        try:
            # First try cache
            for msg in reversed(self._cached_messages):
                if isinstance(msg, AIMessage):
                    self.last_ai_response = msg.content
                    return
            
            # Fallback to modern memory (only if no running loop)
            import asyncio
            try:
                asyncio.get_running_loop()
                logger.debug("Event loop already running, using empty last AI response")
                return
            except RuntimeError:
                # No running loop, safe to create one
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    messages = loop.run_until_complete(
                        self.modern_memory.get_messages(self.project_slug, limit=10)
                    )
                    
                    # Find the last AI message and update cache
                    self._cached_messages = messages[-20:] if len(messages) > 20 else messages
                    for msg in reversed(messages):
                        if isinstance(msg, AIMessage):
                            self.last_ai_response = msg.content
                            break
                finally:
                    loop.close()
                    
        except Exception as e:
            logger.error(f"Error syncing last AI response: {e}")
    
    async def get_all_conversations(self) -> List[Dict[str, Any]]:
        """Get conversations in legacy format from modern memory."""
        try:
            messages = await self.modern_memory.get_messages(self.project_slug)
            conversations = []
            
            # Convert message pairs to legacy format
            for i in range(0, len(messages), 2):
                user_msg = messages[i] if i < len(messages) else None
                ai_msg = messages[i + 1] if i + 1 < len(messages) else None
                
                conversations.append({
                    "timestamp": datetime.now().isoformat(),
                    "user_id": "anonymous",
                    "user_input": user_msg.content if user_msg else "",
                    "ai_response": ai_msg.content if ai_msg else ""
                })
            
            return conversations
        except Exception as e:
            logger.error(f"Error getting conversations via wrapper: {e}")
            return []
    
    async def get_context_for_llm(self, limit: int = 10) -> str:
        """Get conversation context in string format."""
        try:
            messages = await self.modern_memory.get_messages(self.project_slug, limit=limit * 2)
            context_parts = []
            
            for msg in messages:
                if isinstance(msg, HumanMessage):
                    context_parts.append(f"User: {msg.content}")
                elif isinstance(msg, AIMessage):
                    context_parts.append(f"Assistant: {msg.content}")
            
            return "\n\n".join(context_parts)
        except Exception as e:
            logger.error(f"Error getting context via wrapper: {e}")
            return ""
    
    def get_last_ai_response(self) -> str:
        """Get the last AI response for reference by user."""
        if not self.last_ai_response:
            self._sync_last_ai_response()
        return self.last_ai_response or ""
    
    def get_formatted_context(self, max_exchanges: int = 5) -> str:
        """Format conversation history for LLM analysis."""
        try:
            # Use cached messages first
            messages = self._cached_messages[-(max_exchanges * 2):] if self._cached_messages else []
            
            # If cache is empty, try to sync from modern memory (only if no running loop)
            if not messages:
                import asyncio
                try:
                    asyncio.get_running_loop()
                    logger.debug("Event loop running, using empty context")
                    return "No conversation history available."
                except RuntimeError:
                    # Safe to create new loop
                    try:
                        loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(loop)
                        messages = loop.run_until_complete(
                            self.modern_memory.get_messages(self.project_slug, limit=max_exchanges * 2)
                        )
                        # Update cache
                        self._cached_messages = messages[-20:] if len(messages) > 20 else messages
                        loop.close()
                    except Exception as e:
                        logger.error(f"Error syncing messages for context: {e}")
                        return "Error retrieving conversation context."
                
            if not messages:
                return "No conversation history available."
            
            formatted_context = ""
            for msg in messages:
                if isinstance(msg, HumanMessage):
                    formatted_context += f"User: {msg.content}\n"
                elif isinstance(msg, AIMessage):
                    formatted_context += f"Assistant: {msg.content}\n"
                formatted_context += "\n"
            
            return formatted_context.strip()
            
        except Exception as e:
            logger.error(f"Error formatting conversation context via wrapper: {e}")
            return "Error retrieving conversation context."
    
    def get_langchain_messages(self, max_messages: int = 20) -> List[BaseMessage]:
        """Get conversation history as LangChain messages for context."""
        try:
            # Use cached messages first
            messages = self._cached_messages[-max_messages:] if self._cached_messages else []
            
            # If cache is empty, try modern memory (only if no running loop)
            if not messages:
                import asyncio
                try:
                    asyncio.get_running_loop()
                    logger.debug("Event loop running, returning empty messages")
                    return []
                except RuntimeError:
                    # Safe to create new loop
                    try:
                        loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(loop)
                        messages = loop.run_until_complete(
                            self.modern_memory.get_messages(self.project_slug, limit=max_messages)
                        )
                        # Update cache
                        self._cached_messages = messages[-20:] if len(messages) > 20 else messages
                        loop.close()
                    except Exception as e:
                        logger.error(f"Error syncing messages: {e}")
                        return []
            
            return messages
            
        except Exception as e:
            logger.error(f"Error getting langchain messages via wrapper: {e}")
            return []


class ConversationMemory:
    """DEPRECATED: Enhanced conversation storage with LangChain memory integration. Use unified memory system instead."""
    
    def __init__(self, project_slug: str):
        self.project_slug = project_slug
        self.file_path = MEMORY_DIR / f"{project_slug}_conversations.json"
        self._lock = asyncio.Lock()
        # Removed FileLock - now using async-safe file operations
        
        # Use simple message list instead of deprecated ConversationBufferMemory
        self.messages: List[BaseMessage] = []
        
        # Initialize flag to track if memory has been loaded
        self._memory_initialized = False
        
        # Store last AI response for easy reference
        self.last_ai_response = None
    
    async def _initialize_langchain_memory(self) -> None:
        """Initialize message list from existing JSON conversations."""
        if self._memory_initialized:
            return  # Already initialized
            
        try:
            conversations = await self.get_all_conversations()
            for conv in conversations:
                if conv["user_input"]:  # Only add if user input exists
                    self.messages.append(HumanMessage(content=conv["user_input"]))
                if conv["ai_response"]:  # Only add if AI response exists
                    self.messages.append(AIMessage(content=conv["ai_response"]))
                    # Keep track of the most recent AI response
                    self.last_ai_response = conv["ai_response"]
            
            self._memory_initialized = True
            logger.info(f"Initialized message list with {len(conversations)} conversations for {self.project_slug}")
        except Exception as e:
            logger.error(f"Error initializing message list: {e}")
    
    async def ensure_file_exists(self) -> None:
        """Create conversation file if it doesn't exist."""
        if not self.file_path.exists():
            logger.info(f"Creating conversation file: {self.file_path}")
            await self._create_initial_file()
        else:
            logger.debug(f"Conversation file exists: {self.file_path}")
    
    async def _create_initial_file(self) -> None:
        """Create initial conversation storage file."""
        async with self._lock:
            initial_data = {
                "project_slug": self.project_slug,
                "created": datetime.now().isoformat(),
                "conversations": []
            }
            await safe_json_write(self.file_path, initial_data)
            logger.info(f"Created conversation storage for {self.project_slug}")
    
    async def add_conversation(self, user_input: str, ai_response: str, user_id: str = "anonymous") -> None:
        """Add a complete conversation exchange to both JSON and LangChain storage."""
        try:
            async with self._lock:
                await self.ensure_file_exists()
                
                # Read current conversations
                data = await safe_json_read(self.file_path)
                if data is None:
                    data = {
                        "project_slug": self.project_slug,
                        "created": datetime.now().isoformat(),
                        "conversations": []
                    }
                
                # Add new conversation
                conversation_entry = {
                    "timestamp": datetime.now().isoformat(),
                    "user_id": user_id,
                    "user_input": user_input,
                    "ai_response": ai_response
                }
                data["conversations"].append(conversation_entry)
                
                # Write back to file
                await safe_json_write(self.file_path, data)
                
                # Also add to message list immediately
                if self._memory_initialized:
                    self.messages.append(HumanMessage(content=user_input))
                    if ai_response:  # Only add if AI response exists
                        self.messages.append(AIMessage(content=ai_response))
                
                # Update last AI response for easy reference
                if ai_response:
                    self.last_ai_response = ai_response
                
                logger.info(f"Added conversation to {self.project_slug}: {len(user_input)} chars input, {len(ai_response)} chars response")
        except Exception as e:
            logger.error(f"Error adding conversation: {e}", exc_info=True)
    
    async def add_user_message(self, user_input: str, user_id: str = "anonymous") -> None:
        """Add only user message (for when AI response comes later)."""
        try:
            async with self._lock:
                await self.ensure_file_exists()
                
                # Read current conversations
                data = await safe_json_read(self.file_path)
                if data is None:
                    data = {
                        "project_slug": self.project_slug,
                        "created": datetime.now().isoformat(),
                        "conversations": []
                    }
                
                # Add user message (AI response will be empty for now)
                conversation_entry = {
                    "timestamp": datetime.now().isoformat(),
                    "user_id": user_id,
                    "user_input": user_input,
                    "ai_response": ""  # Will be updated later
                }
                data["conversations"].append(conversation_entry)
                
                # Write back to file
                await safe_json_write(self.file_path, data)
                
                # Add to message list immediately  
                if self._memory_initialized:
                    self.messages.append(HumanMessage(content=user_input))
                
                logger.info(f"Added user message to {self.project_slug}")
        except Exception as e:
            logger.error(f"Error adding user message: {e}", exc_info=True)
    
    async def update_last_ai_response(self, ai_response: str) -> None:
        """Update the AI response for the most recent conversation entry."""
        try:
            async with self._lock:
                await self.ensure_file_exists()
                
                # Read current conversations
                data = await safe_json_read(self.file_path)
                if data is None or not data.get("conversations"):
                    logger.warning(f"No conversations found to update for {self.project_slug}")
                    return
                
                # Update the last conversation entry
                data["conversations"][-1]["ai_response"] = ai_response
                
                # Write back to file
                await safe_json_write(self.file_path, data)
                
                # Add to message list immediately
                if self._memory_initialized:
                    self.messages.append(AIMessage(content=ai_response))
                
                # Update last AI response for easy reference
                self.last_ai_response = ai_response
                
                logger.info(f"Updated AI response for {self.project_slug}")
        except Exception as e:
            logger.error(f"Error updating AI response: {e}", exc_info=True)
    
    def get_langchain_messages(self, max_messages: int = 20) -> List[BaseMessage]:
        """Get conversation history as LangChain messages for context."""
        messages = self.messages
        # Return recent messages within limit
        return messages[-max_messages:] if len(messages) > max_messages else messages
    
    async def get_all_conversations(self) -> List[Dict[str, Any]]:
        """Get all conversations for this project."""
        try:
            await self.ensure_file_exists()
            data = await safe_json_read(self.file_path)
            if data is None:
                return []
            return data.get("conversations", [])
        except Exception as e:
            logger.error(f"Error reading conversations: {e}")
            return []
    
    async def get_recent_conversations(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get recent conversations for context."""
        conversations = await self.get_all_conversations()
        return conversations[-limit:] if conversations else []
    
    def get_last_ai_response(self) -> str:
        """Get the last AI response for reference by user."""
        return self.last_ai_response or ""
    
    def get_formatted_context(self, max_exchanges: int = 5) -> str:
        """Format conversation history for LLM analysis."""
        try:
            messages = self.get_langchain_messages(max_messages=max_exchanges * 2)
            
            if not messages:
                return "No conversation history available."
            
            formatted_context = ""
            for msg in messages:
                if hasattr(msg, '__class__') and 'Human' in msg.__class__.__name__:
                    formatted_context += f"User: {msg.content}\n"
                elif hasattr(msg, '__class__') and 'AI' in msg.__class__.__name__:
                    formatted_context += f"Assistant: {msg.content}\n"
                formatted_context += "\n"
            
            return formatted_context.strip()
            
        except Exception as e:
            logger.error(f"Error formatting conversation context: {e}")
            return "Error retrieving conversation context."
    
    def get_last_ai_response_detailed(self) -> Dict[str, str]:
        """Return AI response with metadata for better context."""
        try:
            last_response = self.get_last_ai_response()
            if not last_response:
                return {
                    "content": "",
                    "length": "0",
                    "has_content": "false",
                    "preview": ""
                }
            
            return {
                "content": last_response,
                "length": str(len(last_response)),
                "has_content": "true",
                "preview": last_response[:200] + "..." if len(last_response) > 200 else last_response
            }
            
        except Exception as e:
            logger.error(f"Error getting detailed AI response: {e}")
            return {
                "content": "",
                "length": "0", 
                "has_content": "false",
                "preview": "Error retrieving response"
            }
    
    async def get_conversation_summary(self, focus_area: str = None) -> str:
        """Get summarized context for efficient LLM processing."""
        try:
            recent_conversations = await self.get_recent_conversations(limit=3)
            
            if not recent_conversations:
                return "No recent conversation to summarize."
            
            summary = "Recent conversation summary:\n"
            for i, conv in enumerate(recent_conversations[-3:], 1):
                user_preview = conv.get('user_input', '')[:100]
                ai_preview = conv.get('ai_response', '')[:150]
                
                summary += f"{i}. User: {user_preview}{'...' if len(conv.get('user_input', '')) > 100 else ''}\n"
                summary += f"   AI: {ai_preview}{'...' if len(conv.get('ai_response', '')) > 150 else ''}\n\n"
            
            if focus_area:
                summary += f"Focus: {focus_area}\n"
            
            return summary.strip()
            
        except Exception as e:
            logger.error(f"Error creating conversation summary: {e}")
            return "Error creating conversation summary."
    
    def clear_memory(self) -> None:
        """Clear LangChain memory (for testing or reset)."""
        self.messages.clear()
        logger.info(f"Cleared LangChain memory for {self.project_slug}")

class MarkdownMemory:
    """DEPRECATED: Handles intelligent markdown document management with structured sections. Use unified memory system instead."""
    
    def __init__(self, project_slug: str):
        self.project_slug = project_slug
        self.file_path = MEMORY_DIR / f"{project_slug}.md"
        self._lock = asyncio.Lock()
        # Removed FileLock - now using async-safe file operations
        
        # Session-based changelog tracking
        self._session_start_time = None
        self._session_user_id = None
        self._session_contributor = None
        self._session_sections_updated = set()
        self._session_timeout = 10 * 60  # 10 minutes
    
    async def ensure_file_exists(self) -> None:
        """Create structured markdown file if it doesn't exist, but don't overwrite existing files."""
        if not self.file_path.exists():
            logger.info(f"File does not exist, creating: {self.file_path}")
            
            # Get project description from registry
            project_description = None
            try:
                # Access ProjectRegistry without circular import
                projects = await ProjectRegistry.list_projects()
                if self.project_slug in projects:
                    project_info = projects[self.project_slug]
                    project_description = project_info.get("description", "")
                    logger.info(f"Found project description: {project_description[:100]}...")
            except KeyError as e:
                logger.warning(f"Project description not found in index: {e}")
                project_description = None
            except OSError as e:
                logger.error(f"Database error getting project description: {e}")
                project_description = None
            except Exception as e:
                logger.error(f"Unexpected error getting project description: {e}", exc_info=True)
                project_description = None
            
            await self._create_initial_file(project_description)
        else:
            logger.info(f"File exists: {self.file_path}")
            # File exists, no need to read it just to verify - just log that it exists
            logger.debug(f"Existing file preserved: {self.file_path}")
    
    async def _create_initial_file(self, project_description: str = None) -> None:
        """Create initial structured markdown file with actual project description."""
        async with self._lock:
                project_name = self.project_slug.replace('-', ' ').title()
                current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                
                # Create executive summary from project description or prompt for more information
                if project_description and project_description.strip():
                    executive_summary = project_description.strip()
                    context_content = project_description.strip()
                else:
                    executive_summary = "Please provide more information about this project's purpose, goals, and context. The executive summary will be updated as details are gathered through our conversation."
                    context_content = "*Background and motivation for this project will be captured through conversation*"
                
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
                await safe_file_write(self.file_path, content)
                
                logger.info(f"Created new structured document for {self.project_slug}")
    
    async def read_content(self) -> str:
        """Read the full markdown content from the actual file."""
        await self.ensure_file_exists()
        
        content = await safe_file_read(self.file_path)
        if content is None:
            raise RuntimeError(f"Failed to read file {self.file_path}")
        
        logger.debug(f"Read {len(content)} characters from {self.file_path}")
        return content
    
    async def update_section(self, section: str, content: str, contributor: str = "User", user_id: str = "anonymous") -> None:
        """Update a specific section of the markdown document with async-safe file operations."""
        try:
            logger.info(f"Adding to section '{section}' for {self.project_slug} by {contributor} ({user_id})")
            
            # Use async lock for coordination
            async with self._lock:
                await self.ensure_file_exists()
                
                # Read content using async-safe utility
                current_content = await safe_file_read(self.file_path)
                if current_content is None:
                    current_content = ""
                logger.debug(f"Current content length before update: {len(current_content)}")
                
                updated_content = await self._update_markdown_section(
                    current_content, section, content, contributor, user_id
                )
                
                logger.debug(f"Updated content length after update: {len(updated_content)}")
                
                # Check if we need to finalize an expired session before writing
                if self._session_start_time and self._session_sections_updated:
                    session_duration = datetime.now().timestamp() - self._session_start_time
                    if session_duration > self._session_timeout:
                        logger.info("Session timeout reached, finalizing changelog")
                        updated_content = await self._finalize_session_changelog(updated_content)
                
                await safe_file_write(self.file_path, updated_content)
                
                logger.info(f"Successfully added to section '{section}' for {self.project_slug}")
        except Exception as e:
            logger.error(f"Error updating section '{section}': {e}")
            # Don't let document update errors break the user experience
    
    def _is_session_active(self, user_id: str, contributor: str) -> bool:
        """Check if current user session is still active."""
        if not self._session_start_time or not self._session_user_id:
            return False
        
        # Check if session has timed out
        session_duration = datetime.now().timestamp() - self._session_start_time
        if session_duration > self._session_timeout:
            return False
        
        # Check if same user
        return self._session_user_id == user_id and self._session_contributor == contributor
    
    def _start_new_session(self, user_id: str, contributor: str):
        """Start a new user session for changelog tracking."""
        self._session_start_time = datetime.now().timestamp()
        self._session_user_id = user_id
        self._session_contributor = contributor
        self._session_sections_updated = set()
        logger.info(f"Started new session for {contributor} ({user_id})")
    
    async def _finalize_session_changelog(self, content: str) -> str:
        """Add session summary to changelog and clear session."""
        if not self._session_start_time or not self._session_sections_updated:
            return content
        
        # Create session summary
        session_start = datetime.fromtimestamp(self._session_start_time).strftime('%Y-%m-%d %H:%M:%S')
        current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        sections_list = ', '.join(sorted(self._session_sections_updated))
        
        if len(self._session_sections_updated) == 1:
            summary = f"Updated {sections_list}"
        else:
            summary = f"Updated {len(self._session_sections_updated)} sections: {sections_list}"
        
        # Add session entry to Change Log
        change_entry = f"| {session_start} - {current_time} | {self._session_contributor} | {self._session_user_id} | {summary} |"
        change_log_pattern = r'(## Change Log.*?\n\|.*?\n\|.*?\n)'
        if re.search(change_log_pattern, content, re.DOTALL):
            content = re.sub(
                change_log_pattern,
                rf'\1{change_entry}\n',
                content,
                flags=re.DOTALL
            )
        
        logger.info(f"Finalized session changelog for {self._session_contributor}: {summary}")
        
        # Clear session
        self._session_start_time = None
        self._session_user_id = None
        self._session_contributor = None
        self._session_sections_updated = set()
        
        return content
    
    async def replace_section(self, section: str, content: str, contributor: str = "User", user_id: str = "anonymous") -> None:
        """Replace entire section content - only use when explicitly requested for deletion/replacement."""
        try:
            logger.info(f"REPLACING section '{section}' for {self.project_slug} by {contributor} ({user_id}) - EXPLICIT REPLACEMENT")
            
            # Use async lock for coordination
            async with self._lock:
                await self.ensure_file_exists()
                
                # Read content using async-safe utility
                current_content = await safe_file_read(self.file_path)
                if current_content is None:
                    current_content = ""
                
                updated_content = await self._replace_markdown_section(
                    current_content, section, content, contributor, user_id
                )
                
                # Check if we need to finalize an expired session before writing
                if self._session_start_time and self._session_sections_updated:
                    session_duration = datetime.now().timestamp() - self._session_start_time
                    if session_duration > self._session_timeout:
                        logger.info("Session timeout reached during replace, finalizing changelog")
                        updated_content = await self._finalize_session_changelog(updated_content)
                
                await safe_file_write(self.file_path, updated_content)
                
                logger.info(f"Successfully REPLACED section '{section}' for {self.project_slug}")
        except Exception as e:
            logger.error(f"Error replacing section '{section}': {e}")
            # Don't let document update errors break the user experience
    
    async def _update_markdown_section(self, content: str, section: str, new_content: str, contributor: str, user_id: str = "anonymous") -> str:
        """Update a specific section in the markdown content by appending new information."""
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
            # Section exists - APPEND new content instead of replacing
            def replace_section(match):
                section_header = match.group(1)
                existing_content = match.group(2).strip()
                
                # Remove trailing --- if present
                if existing_content.endswith('---'):
                    existing_content = existing_content[:-3].strip()
                
                # Skip empty or placeholder content
                placeholder_patterns = [
                    r'^\*[^*]*\*$',  # *placeholder text*
                    r'^- \[ \].*$',   # - [ ] placeholder tasks
                    r'^_[^_]*_$'      # _placeholder text_
                ]
                
                lines = existing_content.split('\n')
                filtered_lines = []
                
                for line in lines:
                    line = line.strip()
                    if line and not any(re.match(p, line) for p in placeholder_patterns):
                        filtered_lines.append(line)
                
                # Combine existing content with new content
                if filtered_lines:
                    combined_content = '\n'.join(filtered_lines) + '\n\n' + new_content.strip()
                else:
                    combined_content = new_content.strip()
                
                return f"{section_header}\n{combined_content}\n\n---\n\n"
            
            content = re.sub(section_pattern, replace_section, content, flags=re.DOTALL)
            logger.debug(f"Appended to existing section '{section}'")
        else:
            # Section doesn't exist, add it before Change Log (Enhanced dynamic section creation)
            change_log_pattern = r'(## Change Log.*)'
            if re.search(change_log_pattern, content, re.DOTALL):
                new_section = f"## {section}\n{new_content.strip()}\n\n---\n\n"
                content = re.sub(change_log_pattern, new_section + r'\1', content, flags=re.DOTALL)
                logger.debug(f"Added new section '{section}' with enhanced dynamic creation")
            else:
                # No change log found, append to end
                content += f"\n\n## {section}\n{new_content.strip()}\n\n---\n\n"
                logger.debug(f"Appended new section '{section}' to end of document")
        
        # Session-based changelog tracking
        if not self._is_session_active(user_id, contributor):
            # Finalize previous session if exists
            if self._session_start_time and self._session_sections_updated:
                content = await self._finalize_session_changelog(content)
            # Start new session
            self._start_new_session(user_id, contributor)
        
        # Track section update in current session
        self._session_sections_updated.add(section)
        
        return content
    
    async def _replace_markdown_section(self, content: str, section: str, new_content: str, contributor: str, user_id: str = "anonymous") -> str:
        """Replace entire section content - only for explicit replacement requests."""
        # Update the "Last updated" timestamp
        current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        content = re.sub(
            r'_Last updated: .*?_',
            f'_Last updated: {current_time}_',
            content
        )
        
        # Find and replace the section
        section_pattern = rf'(## {re.escape(section)})(.*?)(?=## |\Z)'
        
        if re.search(section_pattern, content, re.DOTALL):
            # Section exists - REPLACE entire content (explicit replacement)
            replacement = f"## {section}\n{new_content.strip()}\n\n---\n\n"
            content = re.sub(section_pattern, replacement, content, flags=re.DOTALL)
            logger.debug(f"REPLACED entire section '{section}' content")
        else:
            # Section doesn't exist, add it before Change Log
            change_log_pattern = r'(## Change Log.*)'
            if re.search(change_log_pattern, content, re.DOTALL):
                new_section = f"## {section}\n{new_content.strip()}\n\n---\n\n"
                content = re.sub(change_log_pattern, new_section + r'\1', content, flags=re.DOTALL)
                logger.debug(f"Added new section '{section}'")
        
        # Session-based changelog tracking
        if not self._is_session_active(user_id, contributor):
            # Finalize previous session if exists
            if self._session_start_time and self._session_sections_updated:
                content = await self._finalize_session_changelog(content)
            # Start new session
            self._start_new_session(user_id, contributor)
        
        # Track section update in current session
        self._session_sections_updated.add(section)
        
        return content
    
    async def finalize_current_session(self) -> None:
        """Manually finalize the current session and write changelog entry."""
        try:
            if not self._session_start_time or not self._session_sections_updated:
                logger.debug("No active session to finalize")
                return
            
            logger.info(f"Manually finalizing session for {self._session_contributor}")
            
            # Use async lock for coordination
            async with self._lock:
                await self.ensure_file_exists()
                
                # Read current content using async-safe utility
                current_content = await safe_file_read(self.file_path)
                if current_content is None:
                    current_content = ""
                
                # Finalize session changelog
                updated_content = await self._finalize_session_changelog(current_content)
                
                # Write updated content using async-safe utility
                await safe_file_write(self.file_path, updated_content)
                
                logger.info("Session successfully finalized")
                
        except Exception as e:
            logger.error(f"Error finalizing session: {e}")
    
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

class ProjectRegistry:
    """Manages the index.json file that tracks all projects."""
    
    @staticmethod
    async def load_index() -> Dict[str, Any]:
        """Load the project index."""
        content = await safe_json_read(INDEX_FILE)
        return content if content is not None else {}
    
    @staticmethod
    async def save_index(index: Dict[str, Any]) -> None:
        """Save the project index."""
        INDEX_FILE.parent.mkdir(exist_ok=True)
        await safe_json_write(INDEX_FILE, index)
    
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
    
    # Check if user's name appears in the change log (indicating they've contributed before)
    change_log_section = document_context.split('## Change Log')[-1] if '## Change Log' in document_context else ""
    
    # For anonymous users, check if we can find any existing contributors
    if user_id == "anonymous":
        # If there are existing contributors in the changelog, this might be a returning user with session issues
        # Look for any user entries in changelog
        has_existing_contributors = (
            "| user_" in change_log_section or 
            "| 2025-" in change_log_section or  # Date pattern indicating existing entries
            len(change_log_section.strip()) > 100  # Non-empty changelog
        )
        # Only start intro for truly new projects with anonymous users
        return not has_existing_contributors
    
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
    
    # Parse OpenAI API key - handle AWS App Runner Secrets Manager format
    def get_openai_api_key():
        api_key = os.getenv("OPENAI_API_KEY", "")
        if not api_key:
            return ""
        
        # If key looks like JSON (AWS App Runner sometimes wraps secrets in JSON)
        if api_key.startswith("{") and api_key.endswith("}"):
            try:
                secrets = json.loads(api_key)
                return secrets.get("OPENAI_API_KEY", api_key)
            except json.JSONDecodeError:
                logger.warning("Failed to parse JSON API key format: [API_KEY_REDACTED]")
                return api_key
        
        return api_key
    
    # Initialize the LLM
    llm = ChatOpenAI(
        model=model,
        temperature=0.1,
        streaming=True,
        api_key=get_openai_api_key()
    )
    
    # Phase 2: Memory will be initialized dynamically in planning_node
    
    
    async def planning_node(state: ProjectPlannerState) -> Dict[str, Any]:
        """Phase 2: Unified memory planning node with conversation and document processing."""
        
        try:
            logger.info(f"Processing message with unified memory system for {project_slug}")
            
            # Get current user message
            current_message = state["messages"][-1] if state["messages"] else None
            if not current_message or not isinstance(current_message, HumanMessage):
                logger.warning("No valid user message found in state")
                return {"messages": state["messages"]}
            
            # Get user_id from state
            user_id = state.get("user_id", "anonymous")
            
            # Initialize the Agent Coordinator with unified memory system
            coordinator = AgentCoordinator(project_slug, use_unified_memory=True)
            
            # Process the conversation turn using the unified memory system
            ai_response, tokens_used = await coordinator.process_conversation_turn_unified(
                user_message=current_message.content,
                user_id=user_id
            )
            
            logger.info(f"Unified memory response generated: {len(ai_response)} characters, {tokens_used} tokens used")
            
            # Create AI message response
            response = AIMessage(content=ai_response)
            
            # Add conversation to unified memory system
            await add_conversation_to_memory(project_slug, current_message.content, ai_response, user_id)
            
            # Build full message history using unified memory
            memory_context = await get_conversation_memory_for_project(project_slug, user_id)
            all_messages = memory_context['messages'] + [response]  # Include the current response
            
            return {"messages": all_messages}
            
        except ValueError as e:
            logger.error(f"Invalid input in dual-agent planning_node: {e}")
            return state
        except OSError as e:
            logger.error(f"Database/file error in dual-agent planning_node: {e}")
            return state
        except ImportError as e:
            logger.error(f"Missing dependency in dual-agent planning_node: {e}")
            return state
        except Exception as e:
            logger.error(f"Unexpected error in dual-agent planning_node: {e}", exc_info=True)
            return state
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
    """Stream an initial message with conversation memory awareness."""
    
    try:
        logger.info(f"Starting context-aware initial message stream for {project_slug} by user {user_id}")
        
        # Get persistent conversation memory instance
        conversation_memory = await get_conversation_memory(project_slug)
        conversation_history = conversation_memory.get_langchain_messages()
        
        # Get document context to check user state (Phase 2: using compatibility layer)
        doc_context = await get_project_document_memory(project_slug)
        document_context = doc_context['content'][:200] + "..." if len(doc_context['content']) > 200 else doc_context['content']
        
        # Check if user needs introduction (considering conversation history)
        needs_introduction = should_start_introduction(user_id, document_context) and len(conversation_history) == 0
        logger.info(f"DEBUG: user_id='{user_id}', conversation_history_length={len(conversation_history)}, should_start_intro={should_start_introduction(user_id, document_context)}, needs_introduction={needs_introduction}")
        
        if needs_introduction:
            project_title = project_slug.replace('-', ' ').title()
            introduction_message = f"""Welcome! I'm the NAI Problem-Definition Assistant. I'll guide you through ~30-60 minutes of structured questions to build a shared problem definition for "{project_title}." You can pause anytime and resume later.

This process creates a living Markdown document that any teammate can extend in minutes — not hours. We'll lock in two things early: (1) a rich, shared understanding of the problem and (2) an explicit description of what successful resolution looks like.

To get started, could you please provide your name, role, and areas of expertise?"""
            
            # Stream the introduction message token by token
            for token in introduction_message:
                yield f"data: {json.dumps({'token': token})}\n\n"
                await asyncio.sleep(0.01)  # Small delay for smoother streaming
                
            # Store the initial message in conversation memory
            await conversation_memory.add_conversation("", introduction_message, "system")
            
        else:
            # For returning users or continuing conversations, provide contextual welcome
            if len(conversation_history) > 0:
                welcome_message = f"Welcome back to {project_slug.replace('-', ' ').title()}! I remember our previous conversation. How can I help you continue developing this project?"
            else:
                welcome_message = f"Welcome back to {project_slug.replace('-', ' ').title()}! How can I help you continue developing this project?"
            
            for token in welcome_message:
                yield f"data: {json.dumps({'token': token})}\n\n"
                await asyncio.sleep(0.01)
        
        # End the stream
        yield f"data: {json.dumps({'done': True})}\n\n"
        
        logger.info(f"Completed context-aware initial message stream for {project_slug}")
        
    except ValueError as e:
        logger.warning(f"Invalid input for stream_initial_message: {e}")
        error_message = "Welcome! I'm here to help you develop your project. Please tell me about what you'd like to work on."
        for token in error_message:
            yield f"data: {json.dumps({'token': token})}\n\n"
    except OSError as e:
        logger.error(f"Database/file error in stream_initial_message: {e}")
        error_message = "Welcome! I'm here to help you develop your project. Please tell me about what you'd like to work on."
        for token in error_message:
            yield f"data: {json.dumps({'token': token})}\n\n"
    except Exception as e:
        logger.error(f"Unexpected error in context-aware stream_initial_message: {e}", exc_info=True)
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
    """Stream a chat response with enhanced conversation memory management."""
    
    try:
        logger.info(f"Starting context-aware chat stream for {project_slug}")
        
        # Create the graph with conversation memory support
        graph = make_graph(project_slug, model)
        
        # Prepare the input with user message
        input_data = {
            "messages": [HumanMessage(content=message)],
            "user_id": user_id
        }
        
        # Execute the graph with full conversation context
        final_result = await graph.ainvoke(input_data)
        
        # Extract and stream the final message
        if final_result and "messages" in final_result and len(final_result["messages"]) > 0:
            final_message = final_result["messages"][-1]
            if hasattr(final_message, 'content') and final_message.content:
                # Stream the content as individual tokens
                content = str(final_message.content)
                logger.info(f"Streaming context-aware response: {len(content)} characters")
                
                # Stream token by token
                for token in content:
                    yield f"data: {json.dumps({'token': token})}\n\n"
                    await asyncio.sleep(0.01)  # Small delay for smoother streaming
                    
                logger.info(f"Successfully streamed conversation-aware response for {project_slug}")
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
        
        # Schedule session finalization after a delay (for session cleanup)
        try:
            asyncio.create_task(_delayed_session_cleanup(project_slug, user_id))
        except Exception as cleanup_error:
            logger.error(f"Error scheduling session cleanup: {cleanup_error}")
        
        logger.info(f"Completed context-aware chat stream for {project_slug}")
        
    except ValueError as e:
        logger.warning(f"Invalid input for stream_chat_response: {e}")
        error_message = "I apologize, but there was an issue with your request. Please check your input and try again."
        for token in error_message:
            yield f"data: {json.dumps({'token': token})}\n\n"
    except OSError as e:
        logger.error(f"Database/file error in stream_chat_response: {e}")
        error_message = "I apologize, but I'm having trouble accessing project data. Please try again in a moment."
        for token in error_message:
            yield f"data: {json.dumps({'token': token})}\n\n"
    except ImportError as e:
        logger.error(f"Missing dependency for stream_chat_response: {e}")
        error_message = "I apologize, but I'm experiencing a system error. Please contact support if this continues."
        for token in error_message:
            yield f"data: {json.dumps({'token': token})}\n\n"
    except Exception as e:
        logger.error(f"Unexpected error in context-aware stream_chat_response: {e}", exc_info=True)
        # Always provide some response to the user
        error_message = "I apologize, but I encountered an error. Please try your request again."
        for token in error_message:
            yield f"data: {json.dumps({'token': token})}\n\n"
            await asyncio.sleep(0.01)
        yield f"data: {json.dumps({'done': True})}\n\n"

async def _delayed_session_cleanup(project_slug: str, user_id: str, delay_seconds: int = 60):
    """Delayed session cleanup - finalize sessions after user inactivity."""
    try:
        logger.info(f"Scheduling session cleanup for {project_slug} in {delay_seconds} seconds")
        await asyncio.sleep(delay_seconds)
        
        # Phase 2: Session cleanup using unified memory system
        # Note: Session tracking is handled by unified memory system automatically
        logger.info(f"Session cleanup for {project_slug} - unified memory handles session tracking automatically")
            
    except Exception as e:
        logger.error(f"Error in delayed session cleanup for {project_slug}: {e}")

# Phase 2: initialize_memory function removed - use get_unified_memory_instance() instead