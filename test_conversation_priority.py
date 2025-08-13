#!/usr/bin/env python3
"""Test that conversation context is prioritized over document context."""

import asyncio
import sys
sys.path.append('app')

async def test_conversation_priority():
    """Test conversation reference priority over document content."""
    
    print("🔍 Testing conversation context priority...")
    
    try:
        from app.langgraph_runner import AgentCoordinator
        
        coordinator = AgentCoordinator("test-priority", "gpt-4o-mini")
        
        # Step 1: Agent provides specific recommendations
        print("\n📝 Step 1: Agent provides specific recommendations")
        
        response1, updates1 = await coordinator.process_conversation_turn_unified(
            "What are the next steps for improving this project?",
            "test-user"
        )
        
        print(f"Agent response 1: {response1[:300]}...")
        
        # Step 2: User says "add those to next actions" - should refer to agent's recommendations
        print(f"\n📝 Step 2: User says 'add those to next actions'")
        print(f"Expected: Agent should understand 'those' = the recommendations it just provided")
        
        response2, updates2 = await coordinator.process_conversation_turn_unified(
            "add those to next actions",
            "test-user"  
        )
        
        print(f"\nAgent response 2: {response2}")
        print(f"Document updates: {updates2}")
        
        # Analyze if the agent properly understood the conversation reference
        conversation_reference_indicators = [
            "those recommendations", "what I mentioned", "what I suggested",
            "the steps I outlined", "my recommendations"
        ]
        
        document_confusion_indicators = [
            "could you specify", "which items", "what would you like to add",
            "please clarify", "what specific content"
        ]
        
        shows_conversation_understanding = any(indicator in response2.lower() for indicator in conversation_reference_indicators)
        shows_document_confusion = any(indicator in response2.lower() for indicator in document_confusion_indicators)
        
        print(f"\n📊 PRIORITY TEST ANALYSIS:")
        print(f"  Shows conversation understanding: {'✅ YES' if shows_conversation_understanding else '❌ NO'}")
        print(f"  Shows document confusion: {'❌ YES' if shows_document_confusion else '✅ NO'}")
        print(f"  Made document updates: {'✅ YES' if updates2 > 0 else '❌ NO'}")
        
        success = (shows_conversation_understanding or not shows_document_confusion) and updates2 > 0
        
        if success:
            print(f"\n✅ CONVERSATION PRIORITY WORKING")
            print(f"   Agent correctly prioritizes conversation context over document")
        else:
            print(f"\n❌ CONVERSATION PRIORITY BROKEN") 
            print(f"   Agent still confused about what 'those' refers to")
            if shows_document_confusion:
                print(f"   Agent asks for clarification instead of understanding reference")
                
        return success
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    result = asyncio.run(test_conversation_priority())
    print(f"\n🔍 CONVERSATION PRIORITY: {'✅ WORKING' if result else '❌ BROKEN'}")
    sys.exit(0 if result else 1)