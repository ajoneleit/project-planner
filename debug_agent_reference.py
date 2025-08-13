#!/usr/bin/env python3
"""
Debug the exact user scenario: agent gives detailed response, user says "add that to the document"
"""

import asyncio
import aiohttp
import json
import sys

async def test_agent_reference_issue():
    """Test the exact scenario user reported."""
    
    project_slug = "ambers-project"
    user_id = "debug-agent-ref"
    
    print("🔍 Testing agent's ability to reference its own previous responses...")
    
    try:
        async with aiohttp.ClientSession() as session:
            
            # Step 1: Ask agent to provide detailed recommendations
            print("\n📝 Step 1: Ask agent for detailed information")
            
            message_1 = "Can you provide some recommendations for database optimization?"
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
                
                print(f"Agent: {agent_response_1[:200]}...")
                print(f"Full response length: {len(agent_response_1)} characters")
            
            await asyncio.sleep(2)  # Ensure message is saved
            
            # Step 2: Ask agent to add "that" to the document
            print(f"\n📝 Step 2: User references agent's previous response")
            
            message_2 = "add that to the document"
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
                
                # Analyze the response for the exact user issue
                response_lower = agent_response_2.lower()
                
                # Positive indicators - agent understands the reference
                understands_reference = any(phrase in response_lower for phrase in [
                    "database optimization", "recommendations", "added", "updated", 
                    "document", "included", "incorporat"
                ])
                
                # Negative indicators - agent asks for clarification (the problem)
                asks_clarification = any(phrase in response_lower for phrase in [
                    "could you please clarify", "what specific information", 
                    "what would you like", "which details", "what content",
                    "please share", "what are you referring to"
                ])
                
                print(f"\n📊 REFERENCE ANALYSIS:")
                print(f"  Understands reference to previous response: {'✅ YES' if understands_reference else '❌ NO'}")
                print(f"  Asks for clarification (problematic): {'❌ YES' if asks_clarification else '✅ NO'}")
                
                if understands_reference and not asks_clarification:
                    print(f"\n✅ AGENT CAN REFERENCE ITS OWN RESPONSES")
                    return True
                else:
                    print(f"\n❌ AGENT CANNOT REFERENCE ITS OWN RESPONSES")
                    return False
                
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    result = asyncio.run(test_agent_reference_issue())
    print(f"\n🏁 AGENT REFERENCE TEST: {'✅ WORKS' if result else '❌ BROKEN'}")
    sys.exit(0 if result else 1)