#!/usr/bin/env python3
"""
Test to check if conversation history is being stored and retrieved properly.
"""

import asyncio
import sys
import os

# Add the app directory to the Python path
sys.path.append('app')

async def test_conversation_history():
    try:
        from app.langgraph_runner import get_conversation_memory_for_project, add_conversation_to_memory
        from app.core.memory_unified import get_unified_memory
        
        project_slug = "ambers-project"
        user_id = "test-user"
        
        print("🔍 Testing conversation history storage and retrieval...")
        
        # Test 1: Check current conversation history
        print(f"\n📄 Step 1: Current conversation history for {project_slug}")
        memory_context = await get_conversation_memory_for_project(project_slug, user_id)
        messages = memory_context.get('messages', [])
        print(f"Number of messages found: {len(messages)}")
        
        for i, msg in enumerate(messages):
            msg_type = "User" if hasattr(msg, '__class__') and 'Human' in msg.__class__.__name__ else "Assistant"
            content = msg.content[:100] + "..." if len(msg.content) > 100 else msg.content
            print(f"  Message {i+1}: {msg_type}: {content}")
        
        # Test 2: Add a test conversation
        print(f"\n💾 Step 2: Adding test conversation")
        test_user_input = "What is the main goal of this project?"
        test_ai_response = "The main goal is to develop a project planning system with memory capabilities."
        
        success = await add_conversation_to_memory(project_slug, test_user_input, test_ai_response, user_id)
        print(f"Add conversation success: {success}")
        
        # Test 3: Check conversation history after adding
        print(f"\n📄 Step 3: Conversation history after adding test message")
        memory_context_after = await get_conversation_memory_for_project(project_slug, user_id)
        messages_after = memory_context_after.get('messages', [])
        print(f"Number of messages after adding: {len(messages_after)}")
        
        for i, msg in enumerate(messages_after[-4:]):  # Show last 4 messages
            msg_type = "User" if hasattr(msg, '__class__') and 'Human' in msg.__class__.__name__ else "Assistant"
            content = msg.content[:100] + "..." if len(msg.content) > 100 else msg.content
            print(f"  Message {i+1}: {msg_type}: {content}")
        
        # Test 4: Check direct database content
        print(f"\n💿 Step 4: Direct database query")
        unified_memory = await get_unified_memory()
        
        # Check the conversation table directly
        async with unified_memory._get_db() as db:
            cursor = await db.execute("""
                SELECT conversation_id, role, content, timestamp 
                FROM conversations 
                WHERE conversation_id LIKE ? 
                ORDER BY timestamp DESC 
                LIMIT 10
            """, (f"%{project_slug}%",))
            
            rows = await cursor.fetchall()
            print(f"Direct DB query found {len(rows)} conversation records:")
            
            for row in rows:
                conversation_id, role, content, timestamp = row
                content_preview = content[:50] + "..." if len(content) > 50 else content
                print(f"  {timestamp} | {conversation_id} | {role}: {content_preview}")
        
        return len(messages_after) > len(messages)
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    result = asyncio.run(test_conversation_history())
    sys.exit(0 if result else 1)