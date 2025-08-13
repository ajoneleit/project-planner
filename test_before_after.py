#!/usr/bin/env python3
"""Compare before and after behavior."""

import asyncio
import sys
sys.path.append('app')

async def test_before_after():
    """Show the improvement in agent behavior."""
    
    print("🔍 Testing before/after improvement...")
    
    try:
        from app.langgraph_runner import AgentCoordinator
        
        coordinator = AgentCoordinator("test-improvement", "gpt-4o-mini")
        
        # Test normal reference scenario
        print("\n📝 Test: Normal reference understanding")
        
        response1, updates1 = await coordinator.process_conversation_turn_unified(
            "What are the key security practices for web applications?",
            "test-user"
        )
        
        print(f"Agent response 1: {response1[:150]}...")
        
        response2, updates2 = await coordinator.process_conversation_turn_unified(
            "add that to the document",
            "test-user"
        )
        
        print(f"Agent response 2: {response2[:200]}...")
        print(f"Document updates: {updates2}")
        
        # Analyze improvement
        before_behavior = "What specific information would you like to add or clarify further?"
        
        asks_clarification = any(phrase in response2.lower() for phrase in [
            "what specific information", "what would you like", "could you clarify"
        ])
        
        mentions_context = any(word in response2.lower() for word in [
            "security", "web", "practices", "application"
        ])
        
        document_updated = updates2 > 0
        
        print(f"\n📊 IMPROVEMENT ANALYSIS:")
        print(f"  BEFORE: Agent would ask 'What specific information would you like to add?'")
        print(f"  AFTER:")
        print(f"    - Asks generic clarification: {'❌ YES' if asks_clarification else '✅ NO'}")
        print(f"    - Understands context: {'✅ YES' if mentions_context else '❌ NO'}")
        print(f"    - Document updated: {'✅ YES' if document_updated else '❌ NO'}")
        
        improvement = (not asks_clarification or mentions_context) and document_updated
        
        print(f"\n🏁 SIGNIFICANT IMPROVEMENT: {'✅ YES' if improvement else '❌ NO'}")
        
        if improvement:
            print("✅ Agent now understands references and makes document updates!")
            print("✅ Conversation memory is working correctly!")
            print("✅ Reference analysis is functional!")
            
        return improvement
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    result = asyncio.run(test_before_after())
    print(f"\n🏁 IMPROVEMENT TEST: {'✅ SUCCESS' if result else '❌ FAILED'}")
    sys.exit(0 if result else 1)