#!/usr/bin/env python3
"""Debug the actual conversation flow to find where reference context gets lost."""

import asyncio
import sys
import logging
sys.path.append('app')

async def debug_conversation_flow():
    """Test the conversation flow with detailed logging."""
    
    # Enable detailed logging
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)
    
    print("🔍 Debugging conversation flow with reference context...")
    
    try:
        from app.langgraph_runner import AgentCoordinator
        
        coordinator = AgentCoordinator("debug-conversation", "gpt-4o-mini")
        
        print("\n📝 Step 1: Agent provides security recommendations")
        
        response1, updates1 = await coordinator.process_conversation_turn_unified(
            "Can you provide security recommendations for this project?",
            "test-user"
        )
        
        print(f"Response 1: {response1[:200]}...")
        
        print(f"\n📝 Step 2: User says 'add that to the document' - WATCH THE LOGS")
        
        # This should trigger reference analysis and context building
        response2, updates2 = await coordinator.process_conversation_turn_unified(
            "add that to the document",
            "test-user"
        )
        
        print(f"\nResponse 2: {response2}")
        
        # Analyze the response
        asks_clarification = any(phrase in response2.lower() for phrase in [
            "what specific", "could you please clarify", "what would you like",
            "which details", "what content"
        ])
        
        understands_reference = any(phrase in response2.lower() for phrase in [
            "security", "recommendations", "added", "updated", "document"
        ])
        
        print(f"\n📊 RESPONSE ANALYSIS:")
        print(f"  Asks for clarification (bad): {'❌ YES' if asks_clarification else '✅ NO'}")
        print(f"  Understands reference (good): {'✅ YES' if understands_reference else '❌ NO'}")
        
        if asks_clarification:
            print(f"\n❌ ISSUE CONFIRMED: Agent asks for clarification despite working reference analysis")
            print(f"This means the reference context is not reaching ChatAgent properly")
            return False
        elif understands_reference:
            print(f"\n✅ ISSUE FIXED: Agent understands the reference correctly")
            return True
        else:
            print(f"\n⚠️ UNCLEAR: Agent doesn't ask for clarification but doesn't clearly understand reference")
            return False
            
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    result = asyncio.run(debug_conversation_flow())
    print(f"\n🏁 CONVERSATION FLOW TEST: {'✅ WORKS' if result else '❌ BROKEN'}")
    sys.exit(0 if result else 1)