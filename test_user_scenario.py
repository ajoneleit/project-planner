#!/usr/bin/env python3
"""Test the exact user scenario that was failing."""

import asyncio
import sys
sys.path.append('app')

async def test_user_scenario():
    """Test the user's exact security recommendations scenario."""
    
    print("🔍 Testing exact user scenario...")
    
    try:
        from app.langgraph_runner import AgentCoordinator
        
        coordinator = AgentCoordinator("test-user-scenario", "gpt-4o-mini")
        
        print("\n📝 Step 1: User asks for security recommendations")
        
        response1, updates1 = await coordinator.process_conversation_turn_unified(
            "Here are some security recommendations tailored for the \"Agentic System\" project. These recommendations focus on the unique security considerations for AI-powered conversational systems that manage project data and user interactions.",
            "test-user"
        )
        
        print(f"Agent response 1: {response1[:200]}...")
        
        print(f"\n📝 Step 2: User says 'add that to the document'")
        
        response2, updates2 = await coordinator.process_conversation_turn_unified(
            "add that to the document",
            "test-user"
        )
        
        print(f"Agent response 2: {response2}")
        print(f"Updates made: {updates2}")
        
        # Check if the agent properly understands and acts
        understands_security = "security" in response2.lower()
        mentions_adding = any(word in response2.lower() for word in ["add", "added", "update", "document"])
        asks_clarification = any(phrase in response2.lower() for phrase in [
            "what specific", "could you clarify", "what would you like"
        ])
        
        print(f"\n📊 SCENARIO ANALYSIS:")
        print(f"  Agent understands security context: {'✅ YES' if understands_security else '❌ NO'}")
        print(f"  Agent mentions adding/updating: {'✅ YES' if mentions_adding else '❌ NO'}")
        print(f"  Agent asks for clarification: {'❌ YES' if asks_clarification else '✅ NO'}")
        print(f"  Document updates made: {updates2}")
        
        success = not asks_clarification and (understands_security or mentions_adding)
        
        if success:
            print(f"\n✅ USER SCENARIO FIXED: Agent understands reference without asking for clarification")
        else:
            print(f"\n❌ USER SCENARIO STILL BROKEN: Agent behavior not improved")
        
        return success
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    result = asyncio.run(test_user_scenario())
    print(f"\n🏁 USER SCENARIO TEST: {'✅ FIXED' if result else '❌ BROKEN'}")
    sys.exit(0 if result else 1)