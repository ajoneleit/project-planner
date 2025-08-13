#!/usr/bin/env python3
"""Debug what reference context is actually reaching the ChatAgent."""

import asyncio
import sys
import logging
sys.path.append('app')

async def debug_reference_context_flow():
    """Debug the complete reference context flow."""
    
    # Enable debug logging to see what's happening
    logging.basicConfig(level=logging.INFO)
    
    print("🔍 Debugging reference context flow to ChatAgent...")
    
    try:
        from app.langgraph_runner import AgentCoordinator
        
        coordinator = AgentCoordinator("debug-ref-flow", "gpt-4o-mini")
        
        print("\n📝 Step 1: Agent provides detailed content")
        
        response1, updates1 = await coordinator.process_conversation_turn_unified(
            "Here are detailed security recommendations: Use OAuth 2.0 authentication, implement AES-256 encryption, and use TLS 1.3 for transport security.",
            "test-user"
        )
        
        print(f"Agent response 1: {response1[:150]}...")
        
        print(f"\n📝 Step 2: Test 'add that to the document' - WATCH FOR REFERENCE CONTEXT LOGS")
        
        # This should show reference context building and passing
        response2, updates2 = await coordinator.process_conversation_turn_unified(
            "add that to the document",
            "test-user"
        )
        
        print(f"\nAgent response 2: {response2}")
        print(f"Updates made: {updates2}")
        
        # Check if the response shows the agent understood the reference
        asks_clarification = any(phrase in response2.lower() for phrase in [
            "what specific", "could you clarify", "what would you like",
            "which details", "what content", "please specify"
        ])
        
        confident_response = any(phrase in response2.lower() for phrase in [
            "i'll add", "i've added", "got it", "security", "recommendations",
            "authentication", "encryption"
        ])
        
        print(f"\n📊 REFERENCE CONTEXT FLOW ANALYSIS:")
        print(f"  Agent asks for clarification: {'❌ YES' if asks_clarification else '✅ NO'}")
        print(f"  Agent shows understanding: {'✅ YES' if confident_response else '❌ NO'}")
        
        # Look for the specific log lines about reference context
        print(f"\n🔍 Check the logs above for these key indicators:")
        print(f"  - 'Building reference context: needs_context=True'")
        print(f"  - 'Built reference_context_for_chat'") 
        print(f"  - 'ChatAgent: Processing message with X conversation messages'")
        
        success = not asks_clarification and confident_response
        
        if success:
            print(f"\n✅ REFERENCE CONTEXT FLOW WORKING")
        else:
            print(f"\n❌ REFERENCE CONTEXT FLOW BROKEN")
            if asks_clarification:
                print(f"   Agent still asks for clarification despite reference context")
            if not confident_response:
                print(f"   Agent doesn't show understanding of the referenced content")
        
        return success
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    result = asyncio.run(debug_reference_context_flow())
    print(f"\n🔍 REFERENCE CONTEXT FLOW: {'✅ WORKING' if result else '❌ BROKEN'}")
    sys.exit(0 if result else 1)