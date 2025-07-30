"""
Modern LLM-based reference detection using LangChain chatbot techniques.
Replaces rule-based reference detection with LLM evaluation.
"""

import logging
from typing import List, Dict, Any, Optional, Tuple
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, SystemMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_openai import ChatOpenAI
from langchain_core.output_parsers import PydanticOutputParser
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class ReferenceAnalysis(BaseModel):
    """Structure for LLM reference analysis results."""
    has_reference: bool = Field(description="Whether the message contains a reference to previous content")
    confidence: str = Field(description="Confidence level: high, medium, low")
    reference_type: str = Field(description="Type of reference: specific_content, previous_response, document, unclear")
    referenced_content: str = Field(description="The specific content being referenced")
    action_requested: str = Field(description="What action the user is requesting with the referenced content")
    explanation: str = Field(description="Brief explanation of the reference detected")


class LLMReferenceDetector:
    """LLM-based reference detection using modern LangChain patterns."""
    
    def __init__(self, model_name: str = "gpt-4o-mini"):
        """Initialize the LLM reference detector."""
        import os
        import json
        
        # Check if API key is available using same logic as rest of application
        api_key = self._get_openai_api_key()
        if not api_key:
            logger.warning("No OpenAI API key found - LLM reference detection will use fallback")
            self.model = None
        else:
            logger.info(f"Initializing LLM Reference Detector with model {model_name}")
            self.model = ChatOpenAI(
                model=model_name,
                temperature=0.1,  # Low temperature for consistent analysis
                max_tokens=500,
                api_key=api_key
            )
        
        # Output parser for structured response
        self.output_parser = PydanticOutputParser(pydantic_object=ReferenceAnalysis)
        
        # Create the reference detection prompt and chain only if model is available
        if self.model:
            self.prompt_template = ChatPromptTemplate.from_messages([
                ("system", self._get_system_prompt()),
                MessagesPlaceholder(variable_name="conversation_history"),
                ("human", "Current user message: {current_message}\n\nAnalyze this message for references to previous content.\n\n{format_instructions}")
            ])
            
            # Create the chain
            self.chain = self.prompt_template | self.model | self.output_parser
        else:
            self.prompt_template = None
            self.chain = None
    
    def _get_openai_api_key(self) -> str:
        """Parse OpenAI API key using same logic as existing system."""
        import os
        import json
        
        api_key = os.getenv("OPENAI_API_KEY", "")
        if not api_key:
            return ""
        
        # Handle AWS App Runner JSON format
        if api_key.startswith("{") and api_key.endswith("}"):
            try:
                secrets = json.loads(api_key)
                return secrets.get("OPENAI_API_KEY", api_key)
            except json.JSONDecodeError:
                logger.warning("Failed to parse JSON API key format")
                return api_key
        
        return api_key
        
    def _get_system_prompt(self) -> str:
        """Get the system prompt for reference detection."""
        return """You are an expert at analyzing conversational context and detecting when users reference previous messages or content.

Your task is to analyze a user's current message in the context of the conversation history and determine:

1. WHETHER the message contains references to previous content (like "that", "it", "those details", "add that", etc.)
2. WHAT specific content is being referenced 
3. WHAT action the user wants to take with the referenced content

Key indicators of references:
- Pronouns: "that", "it", "those", "this", "these"
- Demonstrative phrases: "the information above", "what you just said", "your recommendation"
- Action phrases: "add that", "include it", "use those", "implement that"
- Context-dependent requests: "please add all that information to the document"
- CONFIRMATION RESPONSES: "yes", "yes do that", "yes document that", "correct", "exactly" when answering a previous question
- QUESTION-ANSWER PAIRS: When the AI asked a question and user responds with confirmation or reference

CRITICAL: Pay special attention to QUESTION-ANSWER patterns:
- If the AI recently asked "Should we document this tech stack?" and user says "yes document that"  
- If the AI asked "Would you like to add X?" and user says "yes add it" or "yes add those"
- If the AI provided suggestions/metrics/recommendations and asked for input, and user says "yes add those"
- If the AI proposed something and asked for confirmation, and user confirms with reference words

For CONFIRMATION responses:
- Look for the most recent AI question or proposal in the conversation
- Identify what specific content or action was being proposed
- Understand that "yes document that" means "yes, document the content you just proposed"
- Understand that "yes add those" means "yes, add the suggestions/metrics/items you just listed"
- "Those" typically refers to multiple items, suggestions, or recommendations from the previous AI response

Be very precise in identifying WHAT is being referenced. Look at the conversation history to find the most recent relevant content that matches the reference.

Confidence levels:
- HIGH: 
  * Clear pronoun/demonstrative with obvious referent in recent messages
  * Confirmation response to a recent AI question with clear context
  * "yes document that" following AI proposal with question
- MEDIUM: Implied reference with likely referent
- LOW: Possible reference but ambiguous

Reference types:
- specific_content: References specific information, frameworks, recommendations, etc.
- previous_response: References the entire previous AI response
- document: References adding something to a document
- confirmation: User confirming/agreeing to a previous AI proposal or question
- unclear: Reference detected but unclear what it refers to"""

    async def analyze_reference(
        self, 
        current_message: str, 
        conversation_history: List[BaseMessage],
        max_history: int = 10
    ) -> ReferenceAnalysis:
        """
        Analyze a message for references to previous conversation content.
        
        Args:
            current_message: The current user message to analyze
            conversation_history: List of previous messages in the conversation
            max_history: Maximum number of previous messages to consider
            
        Returns:
            ReferenceAnalysis object with detection results
        """
        try:
            # If no model available, use simple fallback detection
            if not self.model or not self.chain:
                return self._fallback_reference_detection(current_message, conversation_history)
            
            # Limit conversation history for context window
            recent_history = conversation_history[-max_history:] if conversation_history else []
            
            # Get format instructions
            format_instructions = self.output_parser.get_format_instructions()
            
            # Invoke the chain
            logger.info(f"LLM Reference Detector: Invoking chain for message: '{current_message[:50]}...'")
            result = await self.chain.ainvoke({
                "current_message": current_message,
                "conversation_history": recent_history,
                "format_instructions": format_instructions
            })
            
            logger.info(f"LLM Reference analysis successful: {result.explanation}")
            logger.info(f"LLM Reference result: has_reference={result.has_reference}, confidence={result.confidence}")
            return result
            
        except Exception as e:
            logger.error(f"Error in LLM reference analysis: {e}")
            # Return safe fallback
            return ReferenceAnalysis(
                has_reference=False,
                confidence="low",
                reference_type="unclear",
                referenced_content="",
                action_requested="",
                explanation=f"Analysis failed: {str(e)}"
            )
    
    def analyze_reference_sync(
        self, 
        current_message: str, 
        conversation_history: List[BaseMessage],
        max_history: int = 10
    ) -> ReferenceAnalysis:
        """
        Synchronous version of reference analysis.
        
        Args:
            current_message: The current user message to analyze
            conversation_history: List of previous messages in the conversation
            max_history: Maximum number of previous messages to consider
            
        Returns:
            ReferenceAnalysis object with detection results
        """
        try:
            # Limit conversation history for context window
            recent_history = conversation_history[-max_history:] if conversation_history else []
            
            # Get format instructions
            format_instructions = self.output_parser.get_format_instructions()
            
            # Invoke the chain synchronously
            result = self.chain.invoke({
                "current_message": current_message,
                "conversation_history": recent_history,
                "format_instructions": format_instructions
            })
            
            logger.info(f"Reference analysis: {result.explanation}")
            return result
            
        except Exception as e:
            logger.error(f"Error in LLM reference analysis: {e}")
            # Return safe fallback
            return ReferenceAnalysis(
                has_reference=False,
                confidence="low",
                reference_type="unclear",
                referenced_content="",
                action_requested="",
                explanation=f"Analysis failed: {str(e)}"
            )
    
    def _fallback_reference_detection(self, current_message: str, conversation_history: List[BaseMessage]) -> ReferenceAnalysis:
        """Simple rule-based fallback when LLM is not available."""
        message_lower = current_message.lower()
        
        # Common reference indicators
        reference_words = [
            "that", "it", "this", "these", "those", 
            "add that", "include that", "use that", "add those", "include those",
            "add all that", "please add that", "add it", "use those",
            "the information", "the details", "the recommendation", "those suggestions"
        ]
        
        # Confirmation indicators
        confirmation_patterns = [
            "yes", "yes document that", "yes add that", "yes do that", "yes add those",
            "correct", "exactly", "right", "document that", "add that", "add those",
            "yes please", "yes go ahead", "sounds good", "looks good", "that works"
        ]
        
        has_reference = any(word in message_lower for word in reference_words)
        has_confirmation = any(pattern in message_lower for pattern in confirmation_patterns)
        
        # Check for question-answer pattern in recent conversation
        is_answer_to_question = False
        last_ai_message = ""
        
        if conversation_history:
            for msg in reversed(conversation_history):
                if isinstance(msg, AIMessage):
                    last_ai_message = msg.content
                    # Check if the last AI message contained a question
                    if "?" in last_ai_message or "should we" in last_ai_message.lower() or "would you like" in last_ai_message.lower():
                        is_answer_to_question = True
                    break
        
        if has_reference or (has_confirmation and is_answer_to_question):
            # Try to find what might be referenced
            referenced_content = ""
            if last_ai_message:
                # Don't truncate - we need the full content for proper reference resolution
                # The context builder will handle length limits appropriately
                referenced_content = last_ai_message
            
            reference_type = "confirmation" if (has_confirmation and is_answer_to_question) else "previous_response"
            confidence = "high" if (has_confirmation and is_answer_to_question) else "medium"
            
            return ReferenceAnalysis(
                has_reference=True,
                confidence=confidence,
                reference_type=reference_type,
                referenced_content=referenced_content,
                action_requested="add to document" if ("add" in message_lower or "document" in message_lower) else "use information",
                explanation=f"Fallback detection: Found {'confirmation response to AI question' if is_answer_to_question else 'reference indicators'} in message"
            )
        else:
            return ReferenceAnalysis(
                has_reference=False,
                confidence="low",
                reference_type="none",
                referenced_content="",
                action_requested="",
                explanation="No reference indicators detected"
            )


class ConversationContextBuilder:
    """Builds rich conversation context for reference resolution."""
    
    @staticmethod
    def build_context_for_reference(
        current_message: str,
        conversation_history: List[BaseMessage],
        reference_analysis: ReferenceAnalysis,
        max_context_length: int = 2000
    ) -> str:
        """
        Build enriched context when a reference is detected.
        
        Args:
            current_message: Current user message
            conversation_history: Full conversation history
            reference_analysis: Results from reference detection
            max_context_length: Maximum length of context to return
            
        Returns:
            Rich context string for the LLM
        """
        if not reference_analysis.has_reference:
            return ""
        
        context_parts = []
        
        # Add reference analysis summary
        context_parts.append(f"REFERENCE DETECTED: {reference_analysis.explanation}")
        context_parts.append(f"Referenced content: {reference_analysis.referenced_content}")
        context_parts.append(f"Requested action: {reference_analysis.action_requested}")
        context_parts.append("")
        
        # Add relevant conversation history
        context_parts.append("CONVERSATION CONTEXT:")
        
        # Get last few exchanges for context
        recent_messages = conversation_history[-6:] if len(conversation_history) > 6 else conversation_history
        
        for msg in recent_messages:
            if isinstance(msg, HumanMessage):
                context_parts.append(f"User: {msg.content}")
            elif isinstance(msg, AIMessage):
                context_parts.append(f"Assistant: {msg.content}")
        
        context_parts.append(f"User: {current_message}")
        context_parts.append("")
        
        # Build final context
        full_context = "\n".join(context_parts)
        
        # Truncate if too long
        if len(full_context) > max_context_length:
            full_context = full_context[:max_context_length] + "...[truncated]"
        
        return full_context


# Factory function for easy integration
def create_llm_reference_detector(model_name: str = "gpt-4o-mini") -> LLMReferenceDetector:
    """Create an LLM reference detector instance."""
    return LLMReferenceDetector(model_name=model_name)