#!/usr/bin/env python3
"""Debug what conversation memory the ChatAgent actually receives."""

import asyncio
import sys
import logging
sys.path.append('app')

async def debug_agent_memory():
    """Debug the ChatAgent's actual memory access."""
    
    # Enable debug logging to see conversation message counts
    logging.basicConfig(level=logging.INFO)
    
    print("🔍 Debugging ChatAgent memory access...")
    
    try:
        from app.langgraph_runner import AgentCoordinator
        
        coordinator = AgentCoordinator("debug-memory", "gpt-4o-mini")
        
        print("\n📝 Step 1: Establish conversation history")
        
        response1, updates1 = await coordinator.process_conversation_turn_unified(
            "Here are my security recommendations: 1) Use OAuth 2.0 2) Implement AES-256 encryption 3) Use TLS 1.3",
            "test-user"
        )
        
        print(f"Agent response 1: {response1[:150]}...")
        
        print(f"\n📝 Step 2: Ask about conversation memory access")
        
        response2, updates2 = await coordinator.process_conversation_turn_unified(
            "do you have access to conversation memory?",
            "test-user"
        )
        
        print(f"\nAgent response 2: {response2}")
        
        # Analyze what the agent says about its memory access
        claims_no_memory = any(phrase in response2.lower() for phrase in [
            "don't have access to conversation", "no access to conversation", 
            "can't access conversation", "don't have conversation memory"
        ])
        
        claims_has_memory = any(phrase in response2.lower() for phrase in [
            "i have access", "i can access", "i remember", "i recall",
            "previous conversation", "conversation history"
        ])
        
        references_previous_content = any(phrase in response2.lower() for phrase in [
            "security recommendations", "oauth", "encryption", "tls"
        ])
        
        print(f"\n📊 MEMORY ACCESS ANALYSIS:")
        print(f"  Agent claims NO memory access: {'❌ YES' if claims_no_memory else '✅ NO'}")
        print(f"  Agent claims HAS memory access: {'✅ YES' if claims_has_memory else '❌ NO'}")
        print(f"  Agent references previous content: {'✅ YES' if references_previous_content else '❌ NO'}")
        
        # Look for the key log line about conversation message count
        print(f"\n🔍 Check the logs above for:")
        print(f"  'ChatAgent: Processing message with X conversation messages'")
        print(f"  If X > 0, technical memory works but agent prompt is wrong")
        print(f"  If X = 0, technical memory is broken")
        
        if claims_no_memory:
            print(f"\n❌ MEMORY ACCESS BROKEN")
            print(f"   Agent explicitly denies having conversation memory access")
            if references_previous_content:
                print(f"   BUT agent can reference previous content - contradiction!")
            return False
        else:
            print(f"\n✅ MEMORY ACCESS WORKING")
            print(f"   Agent acknowledges having conversation memory")
            return True
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    result = asyncio.run(debug_agent_memory())
    print(f"\n🔍 AGENT MEMORY ACCESS: {'✅ WORKING' if result else '❌ BROKEN'}")
    sys.exit(0 if result else 1)