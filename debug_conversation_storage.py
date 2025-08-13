#!/usr/bin/env python3
"""Debug what's actually being stored in conversation memory."""

import asyncio
import sys
sys.path.append('app')

async def debug_conversation_storage():
    """Check what's in conversation memory."""
    
    print("🔍 Debugging conversation storage...")
    
    try:
        from app.langgraph_runner import AgentCoordinator, get_conversation_memory_for_project
        
        coordinator = AgentCoordinator("debug-storage", "gpt-4o-mini")
        
        print("\n📝 Step 1: Agent provides response")
        
        response1, updates1 = await coordinator.process_conversation_turn_unified(
            "Can you provide security recommendations?",
            "test-user"
        )
        
        print(f"Response 1: {response1[:100]}...")
        
        # Check what's stored in memory immediately after
        print(f"\n🔍 Checking conversation memory after first message...")
        
        memory_context = await get_conversation_memory_for_project("debug-storage", "test-user")
        conversation_messages = memory_context['messages']
        
        print(f"Number of messages stored: {len(conversation_messages)}")
        
        for i, msg in enumerate(conversation_messages):
            print(f"  Message {i}: {type(msg).__name__} - {msg.content[:100]}...")
        
        # Now check what last_ai_response would be extracted
        last_ai_response = ""
        for msg in reversed(conversation_messages):
            if hasattr(msg, '__class__') and 'AI' in msg.__class__.__name__:
                last_ai_response = msg.content
                break
        
        print(f"\nExtracted last_ai_response: {len(last_ai_response)} chars")
        if last_ai_response:
            print(f"Content: {last_ai_response[:200]}...")
        else:
            print("❌ No AI response found!")
        
        # Test second message
        print(f"\n📝 Step 2: Test 'add that to the document'")
        
        response2, updates2 = await coordinator.process_conversation_turn_unified(
            "add that to the document",
            "test-user"
        )
        
        print(f"Response 2: {response2}")
        
        return "AI" in response2 or "add" in response2.lower()
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    result = asyncio.run(debug_conversation_storage())
    print(f"\n🏁 STORAGE DEBUG: {'✅ HAS AI RESPONSE' if result else '❌ NO AI RESPONSE'}")