#!/usr/bin/env python3
"""Debug the reference context building in the unified system."""

import asyncio
import sys
sys.path.append('app')

async def debug_reference_context():
    """Debug reference context building step by step."""
    
    print("🔍 Debugging reference context building in unified system...")
    
    try:
        from app.langgraph_runner import AgentCoordinator, LLMReferenceAnalyzer
        import logging
        
        # Enable debug logging
        logging.basicConfig(level=logging.INFO)
        
        # Create coordinator
        coordinator = AgentCoordinator("debug-ref-context", "gpt-4o-mini")
        
        # Test the exact scenario with detailed logging
        print("\n📝 Step 1: Agent provides security recommendations")
        
        response1, updates1 = await coordinator.process_conversation_turn_unified(
            "Can you provide security recommendations for this project?",
            "test-user"
        )
        
        print(f"Agent response 1: {response1[:150]}...")
        
        print(f"\n📝 Step 2: User says 'add that to the document' - debugging reference context")
        
        # Manually test the reference analysis part
        analyzer = coordinator.llm_reference_detector
        
        # Build conversation context as the unified system does
        from app.core.memory_unified import get_conversation_memory_for_project
        memory_context = await get_conversation_memory_for_project(coordinator.project_slug, "test-user")
        conversation_messages = memory_context['messages']
        
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
        
        print(f"\n🔍 DEBUGGING REFERENCE ANALYSIS:")
        print(f"  User message: 'add that to the document'")
        print(f"  Conversation context length: {len(conversation_context)}")
        print(f"  Last AI response length: {len(last_ai_response)}")
        
        # Run reference analysis
        reference_analysis = await analyzer.analyze_reference(
            "add that to the document", conversation_context, last_ai_response
        )
        
        print(f"\n📊 REFERENCE ANALYSIS RESULTS:")
        print(f"  has_reference: {reference_analysis.get('has_reference')}")
        print(f"  reference_type: {reference_analysis.get('reference_type')}")
        print(f"  referenced_content: {reference_analysis.get('referenced_content', '')[:200]}...")
        print(f"  action_requested: {reference_analysis.get('action_requested')}")
        print(f"  confidence: {reference_analysis.get('confidence')}")
        
        # Check the unified system's context building logic
        needs_context = reference_analysis.get('has_reference', False)
        
        reference_context_for_chat = None
        if needs_context and reference_analysis:
            referenced_content = reference_analysis.get('referenced_content', '')
            action_requested = reference_analysis.get('action_requested', '')
            print(f"\n🔧 CONTEXT BUILDING:")
            print(f"  needs_context: {needs_context}")
            print(f"  reference_analysis exists: {reference_analysis is not None}")
            print(f"  referenced_content exists: {bool(referenced_content)}")
            print(f"  Building reference context...")
            
            if referenced_content:
                reference_context_for_chat = f"Referenced content: {referenced_content}\nAction requested: {action_requested}"
                print(f"  ✅ Built reference_context_for_chat: {reference_context_for_chat[:200]}...")
            else:
                print(f"  ❌ No referenced_content found in analysis")
        else:
            print(f"\n❌ NOT BUILDING CONTEXT:")
            print(f"  needs_context: {needs_context}")
            print(f"  reference_analysis exists: {reference_analysis is not None}")
        
        # Now test with actual coordination
        print(f"\n📝 Running full coordination with 'add that to the document'")
        response2, updates2 = await coordinator.process_conversation_turn_unified(
            "add that to the document",
            "test-user"
        )
        
        print(f"Agent response 2: {response2}")
        
        # Check if the agent understood the reference
        understands = any(phrase in response2.lower() for phrase in [
            "security", "recommendations", "added", "updated", "document"
        ])
        asks_clarification = any(phrase in response2.lower() for phrase in [
            "what specific", "could you please clarify", "what would you like"
        ])
        
        print(f"\n📊 FINAL ANALYSIS:")
        print(f"  Agent understands reference: {'✅ YES' if understands else '❌ NO'}")
        print(f"  Agent asks for clarification: {'❌ YES' if asks_clarification else '✅ NO'}")
        
        if understands and not asks_clarification:
            print(f"\n✅ REFERENCE CONTEXT WORKING")
            return True
        else:
            print(f"\n❌ REFERENCE CONTEXT NOT WORKING")
            return False
            
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    result = asyncio.run(debug_reference_context())
    print(f"\n🏁 REFERENCE CONTEXT DEBUG: {'✅ SUCCESS' if result else '❌ FAILED'}")
    sys.exit(0 if result else 1)