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
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage, BaseMessage
from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel

# Import modern memory system
from app.memory.modern_memory import ModernConversationMemory, ConversationMigrator
from app.memory.llm_reference_detector import LLMReferenceDetector, ConversationContextBuilder

logger = logging.getLogger(__name__)

MEMORY_DIR = Path("app/memory")
INDEX_FILE = MEMORY_DIR / "index.json"

# Global modern memory instance
_modern_memory = None

async def get_modern_memory() -> ModernConversationMemory:
    """Get or create the modern memory system instance."""
    global _modern_memory
    if _modern_memory is None:
        _modern_memory = ModernConversationMemory(db_path="app/memory/conversations.db")
        logger.info("Initialized modern conversation memory system")
    return _modern_memory

# Legacy function for backward compatibility during migration
async def get_conversation_memory(project_slug: str) -> 'ConversationMemory':
    """Legacy function - use get_modern_memory() for new code."""
    # For now, return a compatibility wrapper
    modern_memory = await get_modern_memory()
    return LegacyMemoryWrapper(project_slug, modern_memory)

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
            except Exception as e:
                logger.error(f"Failed to initialize LLM for reference analysis: {e}")
                raise
    
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

IMPORTANT: Only return TRUE if the user is clearly referring to something specific from the AI's recent response or the conversation. General responses like "yes", "ok", or new questions should return FALSE.

Return ONLY valid JSON in this exact format:
{{
    "has_reference": true or false,
    "reference_type": "explicit" or "implicit" or "pronoun" or "contextual" or "none",
    "referenced_content": "the specific content they're referring to, or empty string if no reference",
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
    
    async def initialize(self, conversation_memory, markdown_memory):
        """Initialize agent with memory instances."""
        self.conversation_memory = conversation_memory
        self.markdown_memory = markdown_memory
        
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
        """Get specialized system prompt for chat agent."""
        try:
            # Load base prompt from file
            base_prompt_file = Path("prompts/project_planner.md")
            if base_prompt_file.exists():
                async with aiofiles.open(base_prompt_file, 'r', encoding='utf-8') as f:
                    base_prompt = await f.read()
            else:
                base_prompt = "You are a helpful project planning assistant."
        except Exception as e:
            logger.error(f"Error loading base prompt: {e}")
            base_prompt = "You are a helpful project planning assistant."
        
        try:
            # Load specialized chat agent prompt from file
            chat_prompt_file = Path("prompts/chat_agent.md")
            if chat_prompt_file.exists():
                async with aiofiles.open(chat_prompt_file, 'r', encoding='utf-8') as f:
                    chat_agent_prompt = await f.read()
                    # Combine base prompt with specialized prompt
                    return f"{base_prompt}\n\n{chat_agent_prompt}"
            else:
                logger.warning("Chat agent prompt file not found, using fallback")
        except Exception as e:
            logger.error(f"Error loading chat agent prompt: {e}")
        
        # Fallback prompt if file loading fails
        return f"{base_prompt}\n\nROLE: You are the CHAT AGENT - focused on intelligent conversation with users about their NAI projects."
    
    async def process_message(self, user_message: str, conversation_context: str, 
                            document_context: str, reference_context: str = "") -> str:
        """Process user message and generate conversational response."""
        try:
            # If no LLM is available, provide a fallback response
            if self.llm is None:
                return self._generate_fallback_response(user_message, reference_context)
            
            # Get system prompt
            system_prompt = await self.get_system_prompt()
            
            # Build context for chat agent
            reference_section = ""
            if reference_context:
                reference_section = f"""

REFERENCE CONTEXT DETECTED:
The user is referring to specific content from previous messages. Use this context to understand their reference:
{reference_context}
"""
            
            full_context = f"""{system_prompt}

PROJECT: {self.project_slug.replace('-', ' ').title()}

CURRENT PROJECT DOCUMENT:
{document_context}

CONVERSATION HISTORY:
{conversation_context}{reference_section}

You are continuing this conversation. Provide a helpful, natural response that builds on the conversation context."""
            
            # Prepare messages for LLM
            messages = [
                SystemMessage(content=full_context),
                HumanMessage(content=user_message)
            ]
            
            # Generate response
            response = await self.llm.ainvoke(messages)
            
            logger.info(f"Chat agent generated response for {self.project_slug}")
            return response.content
            
        except Exception as e:
            logger.error(f"Error in chat agent processing: {e}", exc_info=True)
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

class InfoAgent:
    """Specialized agent for extracting information and updating documents."""
    
    def __init__(self, project_slug: str, model: str = "gpt-4o-mini"):
        self.project_slug = project_slug
        self.model = model
        self.llm = None  # Lazy initialization
        self.conversation_memory = None
        self.markdown_memory = None
        self.llm_analyzer = None
    
    async def initialize(self, conversation_memory, markdown_memory):
        """Initialize agent with memory instances."""
        self.conversation_memory = conversation_memory
        self.markdown_memory = markdown_memory
        
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
        """Get specialized system prompt for info agent."""
        try:
            # Load info agent prompt from file
            info_prompt_file = Path("prompts/info_agent.md")
            if info_prompt_file.exists():
                async with aiofiles.open(info_prompt_file, 'r', encoding='utf-8') as f:
                    return await f.read()
            else:
                logger.warning("Info agent prompt file not found, using fallback")
        except Exception as e:
            logger.error(f"Error loading info agent prompt: {e}")
        
        # Fallback prompt if file loading fails
        return """ROLE: You are the INFO AGENT - responsible for extracting important information from conversations and updating project documents with comprehensive detail.

Your job is to quietly analyze conversations and ADD comprehensive, detailed information to documents."""
    
    async def analyze_and_extract(self, user_input: str, ai_response: str, 
                                conversation_context: str) -> Dict[str, Any]:
        """Analyze conversation and extract information for document updates."""
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
            
            logger.info(f"Info agent analyzing conversation for {self.project_slug}")
            
            # Use LLM reference analyzer to understand what user is referring to (if available)
            if self.llm_analyzer:
                reference_analysis = await self.llm_analyzer.analyze_reference(
                    user_input, conversation_context, ai_response
                )
            else:
                # Fallback when no LLM analyzer available
                reference_analysis = {
                    "has_reference": False,
                    "reference_type": "none",
                    "referenced_content": "",
                    "action_requested": "",
                    "confidence": "low"
                }
            
            # Get current document context
            current_document = await self.markdown_memory.get_document_context()
            
            # Build extraction prompt
            system_prompt = await self.get_system_prompt()
            
            extraction_prompt = f"""{system_prompt}

CURRENT DOCUMENT:
{current_document}

CONVERSATION CONTEXT:
{conversation_context}

LATEST EXCHANGE:
User: {user_input}
Assistant: {ai_response}

REFERENCE ANALYSIS:
{json.dumps(reference_analysis, indent=2)}

TASK: Analyze this conversation exchange and determine what DETAILED information should be extracted and ADDED to the project document.

CRITICAL INSTRUCTIONS:
- If the user is referencing something from the AI's response (like "add that", "those details", "what you suggested"), extract the COMPLETE referenced content with ALL details
- NEVER create summaries - extract FULL detailed information as provided
- PRESERVE all technical specifications, frameworks, tools, metrics, numbers, names
- ADD comprehensive context and supporting details
- Structure information with detailed bullet points and sub-bullets
- Include explanatory context where beneficial

DOCUMENT UPDATE APPROACH:
- Content will be APPENDED to existing sections, not replaced
- Focus on adding comprehensive, detailed information
- Preserve existing content while adding new detailed information
- Use hierarchical bullet structures for complex information

Return JSON with sections to update:
{{
    "updates": {{
        "Objective": "detailed content to ADD (with comprehensive bullet points) or empty string if no updates needed",
        "Context": "detailed content to ADD (with comprehensive bullet points) or empty string if no updates needed",
        "Constraints & Risks": "detailed content to ADD (with comprehensive bullet points) or empty string if no updates needed",
        "Stakeholders & Collaborators": "detailed content to ADD (with comprehensive bullet points) or empty string if no updates needed",
        "Systems & Data Sources": "detailed content to ADD (with comprehensive bullet points) or empty string if no updates needed",
        "Next Actions": "detailed content to ADD (with comprehensive bullet points) or empty string if no updates needed",
        "Glossary": "detailed content to ADD (with comprehensive bullet points) or empty string if no updates needed"
    }},
    "reasoning": "explanation of what detailed information was extracted and why it was selected for addition",
    "reference_resolved": "if user referenced something, what specific detailed content was identified and will be added"
}}

CONTENT FORMAT EXAMPLES:
- Use detailed bullet points: "• Framework Analysis and Recommendations:"
- Include sub-bullets: "  - Next.js 14 with App Router for improved performance and SEO"
- Add explanatory context: "  - Reasoning: Provides better developer experience and built-in optimizations"
- Preserve specifics: "  - Implementation timeline: 2-3 weeks for migration"

Only include sections that have new DETAILED information to add."""
            
            # Get extraction response
            messages = [SystemMessage(content=extraction_prompt)]
            response = await self.llm.ainvoke(messages)
            
            # Parse response
            try:
                extraction_data = json.loads(response.content)
                logger.info(f"Info agent extracted data: {extraction_data.get('reasoning', 'No reasoning provided')}")
                return extraction_data
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse info agent response: {e}")
                return {"updates": {}, "reasoning": "Failed to parse extraction response"}
                
        except Exception as e:
            logger.error(f"Error in info agent analysis: {e}", exc_info=True)
            return {"updates": {}, "reasoning": f"Error in analysis: {str(e)}"}
    
    async def update_document(self, extraction_data: Dict[str, Any], user_id: str = "anonymous") -> int:
        """Update document with extracted information."""
        try:
            updates = extraction_data.get("updates", {})
            updates_made = 0
            
            # Get contributor name
            try:
                from .user_registry import get_user_display_name
                contributor = await get_user_display_name(user_id)
            except:
                contributor = user_id
            
            # Apply updates to document
            for section, content in updates.items():
                if content and content.strip():
                    await self.markdown_memory.update_section(section, content.strip(), contributor, user_id)
                    updates_made += 1
                    logger.info(f"Info agent updated section '{section}'")
            
            return updates_made
            
        except Exception as e:
            logger.error(f"Error updating document: {e}", exc_info=True)
            return 0

class AgentCoordinator:
    """Coordinates interaction between Chat and Info agents."""
    
    def __init__(self, project_slug: str = "default", model: str = "gpt-4o-mini", use_modern_memory: bool = True):
        self.project_slug = project_slug
        self.use_modern_memory = use_modern_memory
        self.chat_agent = ChatAgent(project_slug, model)
        self.info_agent = InfoAgent(project_slug, model)
        
        # Initialize modern LLM reference detector if we have an API key
        api_key = os.getenv("OPENAI_API_KEY", "")
        if api_key:
            self.llm_reference_detector = LLMReferenceDetector(model_name=model)
            self.context_builder = ConversationContextBuilder()
        else:
            self.llm_reference_detector = None
            self.context_builder = None
    
    async def initialize(self, conversation_memory, markdown_memory):
        """Initialize both agents with memory instances."""
        await self.chat_agent.initialize(conversation_memory, markdown_memory)
        await self.info_agent.initialize(conversation_memory, markdown_memory)
    
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
                    from .memory.llm_reference_detector import LLMReferenceDetector
                    temp_detector = LLMReferenceDetector()  # This will not have LLM but has fallback
                    reference_analysis = temp_detector._fallback_reference_detection(
                        user_message, conversation_messages
                    )
                    logger.info(f"DEBUG: Basic reference analysis: {reference_analysis.explanation}")
                    
                    if reference_analysis.has_reference and reference_analysis.confidence in ["high", "medium"]:
                        from .memory.llm_reference_detector import ConversationContextBuilder
                        context_builder = ConversationContextBuilder()
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
                else:
                    logger.debug("Agent coordinator: Chat agent responded, no document updates needed")
                    
            except Exception as e:
                logger.error(f"Info agent processing failed: {e}", exc_info=True)
            
            return ai_response, updates_made
            
        except Exception as e:
            logger.error(f"Error in agent coordination: {e}", exc_info=True)
            return "I apologize, but I encountered an error processing your request. Could you please try again?", 0


class LegacyMemoryWrapper:
    """Wrapper to provide legacy ConversationMemory interface using ModernConversationMemory."""
    
    def __init__(self, project_slug: str, modern_memory: ModernConversationMemory):
        self.project_slug = project_slug
        self.modern_memory = modern_memory
        self.last_ai_response = None
        self._memory_initialized = True  # Always initialized for modern system
        self._cached_messages = []  # Cache for sync access
    
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
    """Enhanced conversation storage with LangChain memory integration."""
    
    def __init__(self, project_slug: str):
        self.project_slug = project_slug
        self.file_path = MEMORY_DIR / f"{project_slug}_conversations.json"
        self._lock = asyncio.Lock()
        self._file_lock = FileLock(f"{self.file_path}.lock")
        
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
        with self._file_lock:
            async with self._lock:
                initial_data = {
                    "project_slug": self.project_slug,
                    "created": datetime.now().isoformat(),
                    "conversations": []
                }
                async with aiofiles.open(self.file_path, 'w', encoding='utf-8') as f:
                    await f.write(json.dumps(initial_data, indent=2))
                logger.info(f"Created conversation storage for {self.project_slug}")
    
    async def add_conversation(self, user_input: str, ai_response: str, user_id: str = "anonymous") -> None:
        """Add a complete conversation exchange to both JSON and LangChain storage."""
        try:
            with self._file_lock:
                async with self._lock:
                    await self.ensure_file_exists()
                    
                    # Read current conversations
                    async with aiofiles.open(self.file_path, 'r', encoding='utf-8') as f:
                        data = json.loads(await f.read())
                    
                    # Add new conversation
                    conversation_entry = {
                        "timestamp": datetime.now().isoformat(),
                        "user_id": user_id,
                        "user_input": user_input,
                        "ai_response": ai_response
                    }
                    data["conversations"].append(conversation_entry)
                    
                    # Write back to file
                    async with aiofiles.open(self.file_path, 'w', encoding='utf-8') as f:
                        await f.write(json.dumps(data, indent=2))
                    
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
            with self._file_lock:
                async with self._lock:
                    await self.ensure_file_exists()
                    
                    # Read current conversations
                    async with aiofiles.open(self.file_path, 'r', encoding='utf-8') as f:
                        data = json.loads(await f.read())
                    
                    # Add user message (AI response will be empty for now)
                    conversation_entry = {
                        "timestamp": datetime.now().isoformat(),
                        "user_id": user_id,
                        "user_input": user_input,
                        "ai_response": ""  # Will be updated later
                    }
                    data["conversations"].append(conversation_entry)
                    
                    # Write back to file
                    async with aiofiles.open(self.file_path, 'w', encoding='utf-8') as f:
                        await f.write(json.dumps(data, indent=2))
                    
                    # Add to message list immediately  
                    if self._memory_initialized:
                        self.messages.append(HumanMessage(content=user_input))
                    
                    logger.info(f"Added user message to {self.project_slug}")
        except Exception as e:
            logger.error(f"Error adding user message: {e}", exc_info=True)
    
    async def update_last_ai_response(self, ai_response: str) -> None:
        """Update the AI response for the most recent conversation entry."""
        try:
            with self._file_lock:
                async with self._lock:
                    await self.ensure_file_exists()
                    
                    # Read current conversations
                    async with aiofiles.open(self.file_path, 'r', encoding='utf-8') as f:
                        data = json.loads(await f.read())
                    
                    if data["conversations"]:
                        # Update the last conversation entry
                        data["conversations"][-1]["ai_response"] = ai_response
                        
                        # Write back to file
                        async with aiofiles.open(self.file_path, 'w', encoding='utf-8') as f:
                            await f.write(json.dumps(data, indent=2))
                        
                        # Add to message list immediately
                        if self._memory_initialized:
                            self.messages.append(AIMessage(content=ai_response))
                        
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
            async with aiofiles.open(self.file_path, 'r', encoding='utf-8') as f:
                data = json.loads(await f.read())
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

## Recent Updates
*Latest changes and additions to this document*

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
            logger.info(f"Adding to section '{section}' for {self.project_slug} by {contributor} ({user_id})")
            
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
                    
                    logger.info(f"Successfully added to section '{section}' for {self.project_slug}")
        except Exception as e:
            logger.error(f"Error updating section '{section}': {e}")
            # Don't let document update errors break the user experience
    
    async def replace_section(self, section: str, content: str, contributor: str = "User", user_id: str = "anonymous") -> None:
        """Replace entire section content - only use when explicitly requested for deletion/replacement."""
        try:
            logger.info(f"REPLACING section '{section}' for {self.project_slug} by {contributor} ({user_id}) - EXPLICIT REPLACEMENT")
            
            # Use file lock for multi-process safety
            with self._file_lock:
                async with self._lock:
                    await self.ensure_file_exists()
                    
                    # Read content directly without calling read_content() to avoid recursion
                    async with aiofiles.open(self.file_path, 'r', encoding='utf-8') as f:
                        current_content = await f.read()
                    
                    updated_content = await self._replace_markdown_section(
                        current_content, section, content, contributor, user_id
                    )
                    
                    async with aiofiles.open(self.file_path, 'w', encoding='utf-8') as f:
                        await f.write(updated_content)
                    
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
        
        # Update Change Log
        change_entry = f"| {current_time} | {contributor} | {user_id} | REPLACED {section} |"
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

class InformationProcessingAgent:
    """LangChain agent dedicated to analyzing conversations and extracting structured information."""
    
    def __init__(self, project_slug: str):
        self.project_slug = project_slug
        self.conversation_memory = None  # Will be set by async init
        self.markdown_memory = MarkdownMemory(project_slug)
        
        # Initialize LLM for information processing
        self.llm = ChatOpenAI(
            model="gpt-4o-mini", 
            temperature=0.1, 
            api_key=self.get_openai_api_key()
        )
    
    async def ensure_conversation_memory(self):
        """Ensure conversation memory is initialized."""
        if self.conversation_memory is None:
            self.conversation_memory = await get_conversation_memory(self.project_slug)
    
    def get_openai_api_key(self):
        """Parse OpenAI API key - handle AWS App Runner Secrets Manager format."""
        api_key = os.getenv("OPENAI_API_KEY", "")
        if not api_key:
            return ""
        
        # If key looks like JSON (AWS App Runner sometimes wraps secrets in JSON)
        if api_key.startswith("{") and api_key.endswith("}"):
            try:
                secrets = json.loads(api_key)
                return secrets.get("OPENAI_API_KEY", api_key)
            except json.JSONDecodeError:
                logger.warning(f"Failed to parse JSON API key format: {api_key[:20]}...")
                return api_key
        
        return api_key
    
    async def get_extraction_system_prompt(self) -> str:
        """Get the specialized system prompt for information extraction."""
        return """You are an expert information extraction agent specialized in capturing important user-provided information from NAI Problem-Definition Assistant conversations. Your role is to identify and preserve valuable project information that users share during structured questioning sessions.

FOCUS: EXTRACT IMPORTANT USER INFORMATION
- Focus on factual information, data, and specifics provided by users
- Capture technical details, system names, process descriptions, metrics, constraints
- Extract stakeholder names, roles, organizational details, contact information  
- Preserve specific examples, use cases, failure scenarios, success criteria
- Record quantitative data: budgets, timelines, KPIs, performance metrics, costs
- Document regulatory/compliance requirements (ITAR, CUI, export control, etc.)

WHAT TO EXTRACT FROM USER RESPONSES:
- Project objectives, goals, and success definitions
- Business context, pain points, and current state problems
- Technical systems, tools, software (ERP, PLM, MES, CAD, EDA, CAM, etc.)
- Stakeholder names, roles, departments, responsibilities
- Constraints: budget, timeline, regulatory, technical limitations
- Risk factors and potential failure modes
- Metrics, KPIs, measurable outcomes
- Attachments mentioned (BOMs, schematics, screenshots, files)
- Glossary terms, acronyms, technical jargon with definitions
- Opposing viewpoints and conflicting perspectives

DOCUMENT SECTIONS AVAILABLE:
- Objective: Project goals, success criteria, deliverables, outcomes
- Context: Background, business rationale, current pain points, motivation
- Constraints & Risks: Budget/timeline limits, regulatory requirements, technical constraints, risk factors
- Stakeholders & Collaborators: Names, roles, departments, responsibilities, contact info
- Systems & Data Sources: Technical systems, tools, databases, files, integration points
- Glossary: Technical terms, acronyms, NAI-specific jargon with plain-English definitions
- Attachments & Examples: Files, documents, screenshots, samples mentioned by users
- Open Questions & Conflicts: Opposing views, unresolved conflicts, different perspectives
- Next Actions: Tasks, deadlines, owners, milestones

EXTRACTION PRINCIPLES:
- Extract FACTUAL USER-PROVIDED information, not AI assistant questions
- Prioritize specific, concrete details over general statements
- Preserve technical nuance and domain-specific terminology
- Capture quantitative data and metrics whenever provided
- Record regulatory/compliance flags (ITAR, CUI, export control)
- Extract stakeholder details with roles and organizational context
- Focus on information that advances project definition and understanding

OUTPUT FORMAT:
Return JSON with section names as keys and extracted content as values.
Only include sections with new substantive information from the user.
Use structured formatting: bullet points, tables, or lists as appropriate.
Preserve user's specific language for technical terms and system names."""

    async def analyze_conversation_and_extract(self, user_input: str, ai_response: str, user_id: str = "anonymous") -> Dict[str, str]:
        """Analyze the latest conversation and extract structured information."""
        try:
            logger.info(f"Starting information extraction for {self.project_slug}")
            
            # Get current document state
            current_document = await self.markdown_memory.get_document_context()
            
            # Get recent conversation context (last 5 exchanges for context)
            recent_conversations = await self.conversation_memory.get_recent_conversations(5)
            
            # Build context for the extraction agent
            conversation_context = ""
            for conv in recent_conversations[-4:]:  # Previous 4 for context
                conversation_context += f"User: {conv['user_input']}\nAssistant: {conv['ai_response']}\n\n"
            
            # Add the current conversation
            conversation_context += f"User: {user_input}\nAssistant: {ai_response}"
            
            extraction_prompt = f"""CURRENT PROJECT DOCUMENT:
{current_document}

RECENT CONVERSATION HISTORY:
{conversation_context}

TASK: Analyze the conversation and extract information that should be added to the project document. Focus especially on the most recent exchange, but use the conversation history for context.

Consider:
- What new project information was discussed?
- Which document sections would benefit from this information?
- What technical details, objectives, constraints, or stakeholder info emerged?
- What terminology or concepts need to be captured?

Return JSON with section updates:"""

            # Get system prompt
            system_prompt = await self.get_extraction_system_prompt()
            
            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=extraction_prompt)
            ]
            
            logger.info(f"Invoking information processing LLM for {self.project_slug}")
            response = await self.llm.ainvoke(messages)
            
            # Parse JSON response
            try:
                extracted_updates = json.loads(response.content.strip())
                logger.info(f"Successfully extracted {len(extracted_updates)} section updates: {list(extracted_updates.keys())}")
                return extracted_updates if isinstance(extracted_updates, dict) else {}
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse extraction response: {e}. Response: {response.content}")
                return {}
                
        except Exception as e:
            logger.error(f"Error in information extraction: {e}", exc_info=True)
            return {}
    
    async def process_and_update_document(self, user_input: str, ai_response: str, user_id: str = "anonymous") -> None:
        """Complete workflow: save conversation, extract information, update document."""
        try:
            logger.info(f"Starting complete information processing workflow for {self.project_slug}")
            
            # Ensure conversation memory is initialized
            await self.ensure_conversation_memory()
            
            # Step 1: Save complete conversation to invisible memory
            await self.conversation_memory.add_conversation(user_input, ai_response, user_id)
            
            # Step 2: Extract structured information
            extracted_info = await self.analyze_conversation_and_extract(user_input, ai_response, user_id)
            
            # Step 3: Update visible document with extracted information
            updates_made = 0
            from .user_registry import get_user_display_name
            contributor = await get_user_display_name(user_id)
            
            for section, content in extracted_info.items():
                if content and content.strip():
                    logger.info(f"Updating section '{section}' with extracted content")
                    await self.markdown_memory.update_section(section, content.strip(), contributor, user_id)
                    updates_made += 1
            
            # Step 4: Update Recent Updates section with summary
            if updates_made > 0:
                current_time = datetime.now().strftime('%Y-%m-%d %H:%M')
                recent_update = f"**{current_time}**: Updated {updates_made} section(s) based on latest conversation - {', '.join(extracted_info.keys())}"
                await self.markdown_memory.update_section("Recent Updates", recent_update, contributor, user_id)
            
            logger.info(f"Completed information processing: {updates_made} document updates made")
            
        except Exception as e:
            logger.error(f"Error in complete information processing workflow: {e}", exc_info=True)

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
                    logger.warning(f"Failed to parse JSON API key format: {api_key[:20]}...")
                    return api_key
            
            return api_key
        
        # Initialize a lightweight LLM for extraction
        extraction_llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.1, api_key=get_openai_api_key())
        
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
    """Process user input asynchronously using the new InformationProcessingAgent."""
    
    try:
        logger.info(f"Starting information processing workflow for {project_slug} by user {user_id}")
        
        # Create and use the InformationProcessingAgent
        info_agent = InformationProcessingAgent(project_slug)
        await info_agent.process_and_update_document(user_input, ai_response, user_id)
        
        logger.info(f"Completed information processing workflow for {project_slug}")
        
    except Exception as e:
        logger.error(f"Error in information processing workflow: {e}", exc_info=True)
        # Fallback: save conversation to persistent memory at minimum
        try:
            conversation_memory = await get_conversation_memory(project_slug)
            await conversation_memory.add_conversation(user_input, ai_response, user_id)
            logger.info(f"Fallback: Saved conversation to persistent memory for {project_slug}")
        except Exception as fallback_error:
            logger.error(f"Even conversation fallback failed: {fallback_error}", exc_info=True)

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
                logger.warning(f"Failed to parse JSON API key format: {api_key[:20]}...")
                return api_key
        
        return api_key
    
    # Initialize the LLM
    llm = ChatOpenAI(
        model=model,
        temperature=0.1,
        streaming=True,
        api_key=get_openai_api_key()
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
        
        # NAI Problem-Definition Assistant system prompt
        return """You are "NAI Problem-Definition Assistant," a professional, politely persistent coach whose sole mission is to help North Atlantic Industries (NAI) employees turn hazy ideas, pain-points, or requirements into a clear, living Markdown document that any teammate can extend in minutes — not hours. This Markdown "Project Doc" exists to lock in two things early: (1) a rich, shared understanding of the problem and (2) an explicit description of what successful resolution looks like, so every collaborator optimizes toward the same target before proposing or building solutions.

CORE PRINCIPLES:

• Five-Question Cadence: Ask ≈ 5 focused questions at a time. If an answer is vague, immediately drill down with targeted sub-questions. After each bundle, confirm understanding, then send the next bundle.

• Inquisitive by Default: Proactively probe for missing data, examples, metrics, screenshots, file types, and access paths. When a user mentions a file, drawing, or system screen (ERP, PLM, MES, CAD, EDA, CAM, etc.), request a representative attachment or link.

• Perspective-Divergence Module: Early in every session ask, "Who else might see this differently, and why?" Capture opposing views and track them as open questions.

• Glossary Auto-Builder: Whenever an acronym or jargon appears, ask for — or suggest — a plain-English definition.

• Detail Completeness Meter: Internally track progress across core sections. Periodically inform the user: "Depth X/8 achieved—Y to go."

• Risk & Compliance: If ITAR, CUI, export-controlled, or proprietary IP terms surface, briefly flag: "⚠️ Possible sensitive data — consider redaction or consult Tim Campbell."

TONE & DEMEANOR:
• Professional, conversational, coaching
• Persistent but never authoritarian; encourage clarity and completeness
• Avoid overwhelming walls of text—keep bundles digestible
• Focus on QUESTIONS and conversation flow, not information storage

QUESTION STARTERS (pick & adapt):
• Objective clarity: "In two sentences, what outcome defines success?"
• Current pain: "What's the tangible cost or risk today (money, time, quality)?"
• Stakeholders: "Who owns the process now? Who signs off on changes?"
• Systems & Data: "Which systems or tools are involved (e.g., ERP, PLM, MES, SQL reports, EDA/CAD like Vivado or Allegro, CAM software such as MasterCAM, FactoryLogix, custom dashboards)? What tables, logs, or files matter—and can you attach samples?"
• Opposing views: "How might Production or Test Engineering critique this plan?"
• Constraints: "List hard limits—budget ceilings, cycle time, ITAR zones, etc."
• Metrics: "What KPIs will prove the problem is solved?"
• Attachments: "Do you have a BOM excerpt, schematic PDF, or screenshot we can embed?"

Always aim for five questions at a time. Focus on the conversation and questioning process - the information extraction and documentation is handled separately."""
    
    async def planning_node(state: ProjectPlannerState) -> Dict[str, Any]:
        """Dual-agent planning node with separated chat and document processing."""
        
        try:
            logger.info(f"Processing message with dual-agent system for {project_slug}")
            
            # Get modern memory system
            modern_memory = await get_modern_memory()
            
            # For backward compatibility, also get legacy wrapper
            conversation_memory = await get_conversation_memory(project_slug)
            
            # Get current user message
            current_message = state["messages"][-1] if state["messages"] else None
            if not current_message or not isinstance(current_message, HumanMessage):
                logger.warning("No valid user message found in state")
                return {"messages": state["messages"]}
            
            # Get user_id from state
            user_id = state.get("user_id", "anonymous")
            
            # Initialize the Agent Coordinator with modern memory enabled
            coordinator = AgentCoordinator(project_slug, use_modern_memory=True)
            
            # Process the conversation turn using the dual-agent system
            # This will handle adding messages to memory internally
            ai_response, tokens_used = await coordinator.process_conversation_turn(
                user_message=current_message.content,
                conversation_memory=conversation_memory,
                markdown_memory=memory,
                user_id=user_id
            )
            
            logger.info(f"Dual-agent response generated: {len(ai_response)} characters, {tokens_used} tokens used")
            
            # Create AI message response
            response = AIMessage(content=ai_response)
            
            # Build full message history for return - use modern memory when possible
            try:
                modern_messages = await modern_memory.get_messages(project_slug, user_id, limit=20)
                all_messages = modern_messages
            except Exception as e:
                logger.warning(f"Failed to get messages from modern memory, falling back to legacy: {e}")
                conversation_history = conversation_memory.get_langchain_messages(max_messages=20)
                all_messages = conversation_history + [current_message, response]
            
            return {"messages": all_messages}
            
        except Exception as e:
            logger.error(f"Error in dual-agent planning_node: {e}", exc_info=True)
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
        
        # Get document context to check user state
        memory = MarkdownMemory(project_slug)
        document_context = await memory.get_document_context()
        
        # Check if user needs introduction (considering conversation history)
        needs_introduction = should_start_introduction(user_id, document_context) and len(conversation_history) == 0
        
        if needs_introduction:
            project_title = project_slug.replace('-', ' ').title()
            introduction_message = f"""Welcome! I'm the NAI Problem-Definition Assistant. I'll guide you through ~30-60 minutes of structured questions to build a shared problem definition for "{project_title}." You can pause anytime and resume later.

This process creates a living Markdown document that any teammate can extend in minutes — not hours. We'll lock in two things early: (1) a rich, shared understanding of the problem and (2) an explicit description of what successful resolution looks like.

To get started, could you please provide your name, role, and areas of expertise? Additionally, if you have a specific project handle in mind, please share that as well."""
            
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
        
    except Exception as e:
        logger.error(f"Error in context-aware stream_initial_message: {e}", exc_info=True)
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
        
        logger.info(f"Completed context-aware chat stream for {project_slug}")
        
    except Exception as e:
        logger.error(f"Error in context-aware stream_chat_response: {e}", exc_info=True)
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