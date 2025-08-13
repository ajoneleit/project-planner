#!/usr/bin/env python3
"""
Debug the actual conversation context that ChatAgent receives.
"""

import asyncio
import aiohttp
import json
import sys

async def test_conversation_context():
    """Test what conversation context ChatAgent actually receives."""
    
    project_slug = "ambers-project"
    user_id = "debug-context-user"
    
    print("🔍 Debugging ChatAgent conversation context...")
    
    try:
        async with aiohttp.ClientSession() as session:
            
            # Step 1: Send a message with specific content
            print("\n📝 Step 1: Sending message with specific content")
            
            message_1 = "My name is Alice and I work on machine learning projects"
            print(f"User: {message_1}")
            
            chat_payload = {
                "message": message_1,
                "model": "gpt-4o-mini",
                "user_id": user_id
            }
            
            async with session.post(
                f"http://localhost:8000/api/projects/{project_slug}/chat",
                json=chat_payload,
                headers={"Content-Type": "application/json"}
            ) as response:
                
                if response.status != 200:
                    print(f"❌ First message failed: {response.status}")
                    return False
                
                agent_response_1 = ""
                async for line in response.content:
                    line_text = line.decode('utf-8').strip()
                    if line_text.startswith('data: '):
                        try:
                            data = json.loads(line_text[6:])
                            if 'token' in data:
                                agent_response_1 += data['token']
                            elif 'done' in data and data['done']:
                                break
                        except json.JSONDecodeError:
                            continue
                
                print(f"Agent: {agent_response_1[:150]}...")
            
            await asyncio.sleep(1)  # Ensure message is saved
            
            # Step 2: Ask agent to reference the previous conversation
            print(f"\n📝 Step 2: Testing conversation memory")
            
            message_2 = "What is my name and what do I work on?"
            print(f"User: {message_2}")
            
            chat_payload_2 = {
                "message": message_2,
                "model": "gpt-4o-mini",
                "user_id": user_id
            }
            
            async with session.post(
                f"http://localhost:8000/api/projects/{project_slug}/chat",
                json=chat_payload_2,
                headers={"Content-Type": "application/json"}
            ) as response2:
                
                if response2.status != 200:
                    print(f"❌ Second message failed: {response2.status}")
                    return False
                
                agent_response_2 = ""
                async for line in response2.content:
                    line_text = line.decode('utf-8').strip()
                    if line_text.startswith('data: '):
                        try:
                            data = json.loads(line_text[6:])
                            if 'token' in data:
                                agent_response_2 += data['token']
                            elif 'done' in data and data['done']:
                                break
                        except json.JSONDecodeError:
                            continue
                
                print(f"Agent: {agent_response_2}")
                
                # Analyze the response
                response_lower = agent_response_2.lower()
                
                # Check if agent remembered the specific details
                remembers_name = "alice" in response_lower
                remembers_work = "machine learning" in response_lower or "ml" in response_lower
                
                # Check for problematic responses
                asks_clarification = any(phrase in response_lower for phrase in [
                    "don't have access", "can't recall", "don't remember", 
                    "what's your name", "tell me about", "could you remind"
                ])
                
                print(f"\n📊 MEMORY ANALYSIS:")
                print(f"  Remembers name (Alice): {'✅ YES' if remembers_name else '❌ NO'}")
                print(f"  Remembers work (ML): {'✅ YES' if remembers_work else '❌ NO'}")
                print(f"  Asks for clarification: {'❌ YES' if asks_clarification else '✅ NO'}")
                
                if remembers_name and remembers_work and not asks_clarification:
                    print(f"\n✅ CONVERSATION MEMORY WORKS")
                    return True
                else:
                    print(f"\n❌ CONVERSATION MEMORY BROKEN")
                    return False
                
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    result = asyncio.run(test_conversation_context())
    print(f"\n🏁 CONVERSATION CONTEXT TEST: {'✅ WORKS' if result else '❌ BROKEN'}")
    sys.exit(0 if result else 1)