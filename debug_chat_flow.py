#!/usr/bin/env python3
"""
Debug the actual chat flow to see why conversations aren't being saved.
"""

import asyncio
import sys
import os
import json

# Add the app directory to the Python path
sys.path.append('app')

async def debug_chat_flow():
    try:
        from app.langgraph_runner import get_conversation_memory_for_project, add_conversation_to_memory
        from app.core.memory_unified import get_unified_memory
        from app.core.conversation_id_manager import ConversationIDManager
        
        project_slug = "ambers-project"
        user_id = "anonymous"  # This is the default used in chat
        
        print("🔍 Debugging chat flow conversation storage...")
        
        # Test 1: Check what conversation ID is being used
        print(f"\n🆔 Step 1: Conversation ID formats")
        
        # Standard format that should be used
        standard_id = ConversationIDManager.generate_standard_id(project_slug, user_id)
        print(f"Standard conversation ID: '{standard_id}'")
        
        # Legacy format (just project slug)  
        legacy_id = project_slug
        print(f"Legacy conversation ID: '{legacy_id}'")
        
        # Test 2: Check all conversation records in database
        print(f"\n💿 Step 2: All conversation records in database")
        unified_memory = await get_unified_memory()
        
        # Get connection using the PooledConnection
        from app.core.memory_unified import PooledConnection
        
        async with PooledConnection(unified_memory.db_path) as db:
            # Get all conversation records
            cursor = await db.execute("""
                SELECT DISTINCT conversation_id, COUNT(*) as message_count
                FROM conversations 
                GROUP BY conversation_id
                ORDER BY message_count DESC
            """)
            
            all_conversations = await cursor.fetchall()
            print(f"Found {len(all_conversations)} conversation threads:")
            
            for conv_id, count in all_conversations:
                print(f"  '{conv_id}': {count} messages")
            
            # Get recent messages from any conversation
            cursor2 = await db.execute("""
                SELECT conversation_id, role, content, timestamp 
                FROM conversations 
                ORDER BY timestamp DESC 
                LIMIT 10
            """)
            
            recent_messages = await cursor2.fetchall()
            print(f"\nRecent {len(recent_messages)} messages:")
            
            for conv_id, role, content, timestamp in recent_messages:
                content_preview = content[:50] + "..." if len(content) > 50 else content
                print(f"  {timestamp} | '{conv_id}' | {role}: {content_preview}")
        
        # Test 3: Test both conversation ID formats
        print(f"\n📄 Step 3: Testing both conversation ID formats")
        
        # Test standard format
        memory_context_standard = await get_conversation_memory_for_project(project_slug, user_id)
        messages_standard = memory_context_standard.get('messages', [])
        print(f"Standard ID ('{standard_id}'): {len(messages_standard)} messages")
        
        # Test 4: Check feature flags
        print(f"\n🎛️  Step 4: Feature flags")
        from app.core.feature_flags import is_feature_enabled
        
        unified_primary = await is_feature_enabled("unified_memory_primary")
        print(f"unified_memory_primary enabled: {unified_primary}")
        
        # Test 5: Try to simulate the exact planning_node flow
        print(f"\n🔄 Step 5: Simulating planning_node flow")
        
        # Create a test message
        from langchain_core.messages import HumanMessage, AIMessage
        
        test_user_message = HumanMessage(content="Hello, do you remember our previous conversation?")
        
        # This should be the exact flow from planning_node
        print("  Creating AgentCoordinator...")
        from app.langgraph_runner import AgentCoordinator
        
        coordinator = AgentCoordinator(project_slug, use_unified_memory=True)
        print("  Initializing coordinator...")
        await coordinator.initialize_unified(user_id)
        
        print("  Processing conversation turn...")
        try:
            ai_response, tokens_used = await coordinator.process_conversation_turn_unified(
                user_message=test_user_message.content,
                user_id=user_id
            )
            print(f"  AI Response: {ai_response[:100]}...")
            print(f"  Tokens used: {tokens_used}")
            
            # This should add the conversation to memory
            print("  Adding conversation to memory...")
            success = await add_conversation_to_memory(project_slug, test_user_message.content, ai_response, user_id)
            print(f"  Add conversation success: {success}")
            
            # Check if it was actually stored
            print("  Checking if conversation was stored...")
            memory_context_after = await get_conversation_memory_for_project(project_slug, user_id)
            messages_after = memory_context_after.get('messages', [])
            print(f"  Messages after processing: {len(messages_after)}")
            
        except Exception as e:
            print(f"  ❌ Error in processing: {e}")
            import traceback
            traceback.print_exc()
        
        return True
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    result = asyncio.run(debug_chat_flow())
    sys.exit(0 if result else 1)