#!/usr/bin/env python3
"""Debug to verify that the fix is actually being applied."""

import asyncio
import sys
sys.path.append('app')

async def debug_fix():
    """Debug the actual fix implementation."""
    
    print("🔍 Debugging fix implementation...")
    
    try:
        from app.langgraph_runner import AgentCoordinator
        
        # Create coordinator
        coordinator = AgentCoordinator("debug-fix", "gpt-4o-mini")
        
        # Test with verbose logging
        print("\n📝 Testing fix with detailed logging")
        
        # First provide content
        print("Step 1: Providing security recommendations")
        response1, updates1 = await coordinator.process_conversation_turn_unified(
            "What are some key security measures for this project?",
            "test-user"
        )
        
        print(f"Response 1: {response1[:200]}...")
        
        # Then test the reference
        print("\nStep 2: Testing reference to agent's response")
        response2, updates2 = await coordinator.process_conversation_turn_unified(
            "add that to the document",
            "test-user"
        )
        
        print(f"Response 2: {response2}")
        
        # Check the response characteristics
        asks_clarification = any(phrase in response2.lower() for phrase in [
            "what specific", "could you please clarify", "which details",
            "what would you like", "what information"
        ])
        
        mentions_security = "security" in response2.lower()
        mentions_added = any(word in response2.lower() for word in ["added", "updating", "included"])
        
        print(f"\n📊 RESPONSE ANALYSIS:")
        print(f"  Asks for clarification: {'❌ YES' if asks_clarification else '✅ NO'}")
        print(f"  Mentions security: {'✅ YES' if mentions_security else '❌ NO'}")  
        print(f"  Indicates action taken: {'✅ YES' if mentions_added else '❌ NO'}")
        
        if asks_clarification:
            print(f"\n❌ FIX NOT WORKING: Agent still asks for clarification")
            return False
        elif mentions_security and mentions_added:
            print(f"\n✅ FIX WORKING: Agent understands reference and takes action")
            return True
        else:
            print(f"\n⚠️ PARTIAL FIX: Agent doesn't ask for clarification but unclear if it fully understands")
            return False
            
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    result = asyncio.run(debug_fix())
    print(f"\n🏁 FIX VERIFICATION: {'✅ SUCCESS' if result else '❌ FAILED'}")
    sys.exit(0 if result else 1)