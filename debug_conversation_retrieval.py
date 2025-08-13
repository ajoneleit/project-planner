#!/usr/bin/env python3
"""Debug why conversation messages aren't being retrieved properly."""

import asyncio
import sys
sys.path.append('app')

async def debug_conversation_retrieval():
    """Debug the conversation message retrieval for agentic-system project."""
    
    print("🔍 Debugging conversation retrieval for agentic-system...")
    
    try:
        from app.langgraph_runner import get_conversation_memory_for_project
        
        # Check what conversation messages exist for agentic-system
        print("\n📝 Checking conversation memory for 'agentic-system' project")
        
        memory_context = await get_conversation_memory_for_project("agentic-system", "AJ")
        conversation_messages = memory_context['messages']
        
        print(f"Number of conversation messages found: {len(conversation_messages)}")
        
        if conversation_messages:
            print(f"\n📋 Conversation messages:")
            for i, msg in enumerate(conversation_messages[-5:]):  # Last 5 messages
                role = "User" if hasattr(msg, '__class__') and 'Human' in msg.__class__.__name__ else "Assistant"
                print(f"  {i+1}. {role}: {msg.content[:200]}...")
        else:
            print(f"\n❌ NO CONVERSATION MESSAGES FOUND")
            print(f"   This explains why the agent can't reference previous conversations")
        
        # Also check if the project document exists and what it contains
        print(f"\n📄 Checking project document...")
        
        from app.langgraph_runner import get_project_document_memory
        doc_context = await get_project_document_memory("agentic-system")
        
        print(f"Document content length: {len(doc_context.get('content', ''))}")
        if doc_context.get('content'):
            print(f"Document preview: {doc_context['content'][:300]}...")
        
        # The issue is likely that:
        # 1. Conversation messages aren't being saved properly for this project, OR
        # 2. Conversation messages exist but aren't being retrieved properly, OR  
        # 3. The web interface isn't using the same user_id or project_slug
        
        print(f"\n🔍 DIAGNOSIS:")
        if len(conversation_messages) == 0:
            print(f"❌ ROOT CAUSE: No conversation messages stored for agentic-system:AJ")
            print(f"   Either messages aren't being saved or wrong project/user combination")
        elif len(conversation_messages) < 5:
            print(f"⚠️ LIMITED HISTORY: Only {len(conversation_messages)} messages stored")
            print(f"   Agent has some history but may not have recent conversations")
        else:
            print(f"✅ CONVERSATION HISTORY EXISTS: {len(conversation_messages)} messages")
            print(f"   Technical storage works, issue must be elsewhere")
            
        return len(conversation_messages) > 0
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    result = asyncio.run(debug_conversation_retrieval())
    print(f"\n🔍 CONVERSATION RETRIEVAL: {'✅ HAS MESSAGES' if result else '❌ NO MESSAGES'}")
    sys.exit(0 if result else 1)