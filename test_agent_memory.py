#!/usr/bin/env python3
"""
Test if agents can now see conversation history after the fix.
"""

import asyncio
import sys
import os

# Add the app directory to the Python path
sys.path.append('app')

async def test_agent_memory():
    try:
        from app.langgraph_runner import AgentCoordinator
        from app.langgraph_runner import get_conversation_memory_for_project, add_conversation_to_memory
        
        project_slug = "ambers-project"
        user_id = "anonymous"
        
        print("🧠 Testing agent conversation memory...")
        
        # Step 1: Add a clear test conversation
        print(f"\n💾 Step 1: Adding test conversation")
        await add_conversation_to_memory(
            project_slug, 
            "What's the first rule of project planning?", 
            "The first rule of project planning is to clearly define your objectives and success criteria before starting any work.",
            user_id
        )
        
        # Step 2: Check that conversation was stored
        print(f"\n📄 Step 2: Verify conversation storage")
        memory_context = await get_conversation_memory_for_project(project_slug, user_id)
        messages = memory_context.get('messages', [])
        print(f"Total messages in history: {len(messages)}")
        
        if len(messages) > 0:
            # Show last few messages
            print("Recent conversation:")
            for i, msg in enumerate(messages[-4:]):
                msg_type = "User" if hasattr(msg, '__class__') and 'Human' in msg.__class__.__name__ else "Assistant" 
                print(f"  {i+1}. {msg_type}: {msg.content[:80]}...")
        
        # Step 3: Test agent with question referencing previous conversation
        print(f"\n🤖 Step 3: Testing agent memory with reference question")
        
        coordinator = AgentCoordinator(project_slug, use_unified_memory=True)
        await coordinator.initialize_unified(user_id)
        
        # Ask a question that references the previous conversation
        test_question = "What was the first rule I asked about?"
        
        print(f"Asking agent: '{test_question}'")
        
        ai_response, tokens_used = await coordinator.process_conversation_turn_unified(
            user_message=test_question,
            user_id=user_id
        )
        
        print(f"\nAgent response:")
        print(f"'{ai_response}'")
        print(f"Tokens used: {tokens_used}")
        
        # Check if the response references the previous conversation
        if "project planning" in ai_response.lower() and ("first rule" in ai_response.lower() or "objectives" in ai_response.lower() or "criteria" in ai_response.lower()):
            print("\n✅ SUCCESS: Agent correctly referenced previous conversation!")
            return True
        elif "don't have access" in ai_response.lower() or "don't see" in ai_response.lower() or "can't see" in ai_response.lower():
            print("\n❌ FAILURE: Agent still claims no access to conversation history")
            return False
        else:
            print(f"\n⚠️  UNCLEAR: Agent response doesn't clearly indicate memory access")
            print(f"Response: {ai_response}")
            return False
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    result = asyncio.run(test_agent_memory())
    sys.exit(0 if result else 1)