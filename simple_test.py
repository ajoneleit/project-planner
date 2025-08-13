#!/usr/bin/env python3
"""Simple direct test of the exact user issue."""

import asyncio
import json
import sys

# Add the app directory to the Python path
sys.path.append('app')

async def test_direct():
    """Test the conversation system directly without HTTP."""
    
    print("🔍 Direct test of conversation memory issue...")
    
    try:
        from app.langgraph_runner import AgentCoordinator
        
        # Create coordinator
        coordinator = AgentCoordinator("test-direct", "gpt-4o-mini")
        
        # Test the exact scenario
        print("\n📝 Step 1: Agent provides detailed information")
        
        response1, updates1 = await coordinator.process_conversation_turn_unified(
            "Can you provide security recommendations for this project?",
            "test-user"
        )
        
        print(f"Agent response 1: {response1[:200]}...")
        print(f"Updates made: {updates1}")
        
        print(f"\n📝 Step 2: User references agent's response")
        
        response2, updates2 = await coordinator.process_conversation_turn_unified(
            "add that to the document",
            "test-user"
        )
        
        print(f"Agent response 2: {response2}")
        print(f"Updates made: {updates2}")
        
        # Check if agent asks for clarification (the problem)
        asks_clarification = any(phrase in response2.lower() for phrase in [
            "could you please clarify", "what specific information", 
            "what would you like", "which details", "what content"
        ])
        
        # Check if agent understands the reference  
        understands_reference = any(phrase in response2.lower() for phrase in [
            "security recommendations", "added", "updated", "document"
        ])
        
        print(f"\n📊 ANALYSIS:")
        print(f"  Asks for clarification (bad): {'❌ YES' if asks_clarification else '✅ NO'}")
        print(f"  Understands reference (good): {'✅ YES' if understands_reference else '❌ NO'}")
        
        if asks_clarification:
            print(f"\n❌ CONFIRMED: Agent cannot reference its own previous response")
            print(f"Issue reproduced - agent asks for clarification instead of understanding 'that'")
            return False
        elif understands_reference:
            print(f"\n✅ Agent correctly understands reference to its previous response")
            return True
        else:
            print(f"\n⚠️ Unclear result")
            return False
            
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    result = asyncio.run(test_direct())
    print(f"\n🏁 DIRECT TEST: {'✅ WORKS' if result else '❌ BROKEN'}")
    sys.exit(0 if result else 1)