#!/usr/bin/env python3
"""
Test the actual chat API endpoint to verify conversation memory works end-to-end.
"""

import asyncio
import aiohttp
import json
import time
import sys

async def test_real_chat_api():
    """Test the actual /api/projects/{slug}/chat endpoint"""
    
    base_url = "http://localhost:8000"
    project_slug = "ambers-project"
    user_id = "test-api-user"
    
    print("🌐 Testing REAL chat API endpoint...")
    
    try:
        async with aiohttp.ClientSession() as session:
            
            # Test 1: First chat message
            print(f"\n💬 Test 1: First conversation turn")
            
            chat_payload = {
                "message": "Hello, my name is Alice. What is the main purpose of this project?",
                "model": "gpt-4o-mini", 
                "user_id": user_id
            }
            
            print(f"Sending: {chat_payload['message']}")
            
            async with session.post(
                f"{base_url}/api/projects/{project_slug}/chat",
                json=chat_payload,
                headers={"Content-Type": "application/json"}
            ) as response:
                
                if response.status != 200:
                    print(f"❌ API call failed with status {response.status}")
                    response_text = await response.text()
                    print(f"Response: {response_text}")
                    return False
                
                print(f"✅ API call successful (status {response.status})")
                
                # Stream the response
                full_response = ""
                token_count = 0
                
                async for line in response.content:
                    line_text = line.decode('utf-8').strip()
                    if line_text.startswith('data: '):
                        try:
                            data = json.loads(line_text[6:])  # Remove 'data: ' prefix
                            if 'token' in data:
                                full_response += data['token']
                                token_count += 1
                            elif 'done' in data and data['done']:
                                break
                        except json.JSONDecodeError:
                            continue
                
                print(f"Response: {full_response}")
                print(f"Tokens streamed: {token_count}")
                
                if token_count == 0:
                    print("⚠️ WARNING: Zero tokens received - LLM may not have processed request")
                
                # Wait a moment for the conversation to be saved
                await asyncio.sleep(2)
            
            # Test 2: Second chat message referencing the first
            print(f"\n💬 Test 2: Follow-up conversation referencing previous")
            
            chat_payload_2 = {
                "message": "Do you remember my name from the previous message?",
                "model": "gpt-4o-mini",
                "user_id": user_id
            }
            
            print(f"Sending: {chat_payload_2['message']}")
            
            async with session.post(
                f"{base_url}/api/projects/{project_slug}/chat", 
                json=chat_payload_2,
                headers={"Content-Type": "application/json"}
            ) as response2:
                
                if response2.status != 200:
                    print(f"❌ Second API call failed with status {response2.status}")
                    response_text = await response2.text()
                    print(f"Response: {response_text}")
                    return False
                
                print(f"✅ Second API call successful (status {response2.status})")
                
                # Stream the response
                full_response_2 = ""
                token_count_2 = 0
                
                async for line in response2.content:
                    line_text = line.decode('utf-8').strip()
                    if line_text.startswith('data: '):
                        try:
                            data = json.loads(line_text[6:])
                            if 'token' in data:
                                full_response_2 += data['token']
                                token_count_2 += 1
                            elif 'done' in data and data['done']:
                                break
                        except json.JSONDecodeError:
                            continue
                
                print(f"Response: {full_response_2}")
                print(f"Tokens streamed: {token_count_2}")
                
                # Check if the agent remembered the name "Alice"
                if "Alice" in full_response_2:
                    print("✅ SUCCESS: Agent remembered the name from previous conversation!")
                    memory_works = True
                elif "don't have access" in full_response_2.lower() or "can't see" in full_response_2.lower() or "don't see" in full_response_2.lower():
                    print("❌ FAILURE: Agent still claims no access to conversation history")
                    memory_works = False
                elif token_count_2 == 0:
                    print("❌ FAILURE: Zero tokens suggests LLM not processing")
                    memory_works = False
                else:
                    print(f"⚠️ UNCLEAR: Response doesn't clearly show memory access")
                    print(f"Looking for 'Alice' in: {full_response_2}")
                    memory_works = False
                
                # Test 3: Third message to confirm continuity
                print(f"\n💬 Test 3: Third message to confirm conversation continuity")
                
                chat_payload_3 = {
                    "message": "What was the first question I asked you?",
                    "model": "gpt-4o-mini",
                    "user_id": user_id
                }
                
                print(f"Sending: {chat_payload_3['message']}")
                
                async with session.post(
                    f"{base_url}/api/projects/{project_slug}/chat",
                    json=chat_payload_3,
                    headers={"Content-Type": "application/json"}
                ) as response3:
                    
                    if response3.status != 200:
                        print(f"❌ Third API call failed with status {response3.status}")
                        return memory_works
                    
                    print(f"✅ Third API call successful (status {response3.status})")
                    
                    # Stream the response
                    full_response_3 = ""
                    token_count_3 = 0
                    
                    async for line in response3.content:
                        line_text = line.decode('utf-8').strip()
                        if line_text.startswith('data: '):
                            try:
                                data = json.loads(line_text[6:])
                                if 'token' in data:
                                    full_response_3 += data['token']
                                    token_count_3 += 1
                                elif 'done' in data and data['done']:
                                    break
                            except json.JSONDecodeError:
                                continue
                    
                    print(f"Response: {full_response_3}")
                    print(f"Tokens streamed: {token_count_3}")
                    
                    # Check if agent can recall the first question
                    if ("purpose" in full_response_3.lower() or "main" in full_response_3.lower()) and "project" in full_response_3.lower():
                        print("✅ SUCCESS: Agent recalled the first question content!")
                        continuity_works = True
                    elif token_count_3 == 0:
                        print("❌ FAILURE: Zero tokens in third response")
                        continuity_works = False
                    else:
                        print("⚠️ UNCLEAR: Third response doesn't show clear memory of first question")
                        continuity_works = False
                
                return memory_works and continuity_works
                
    except Exception as e:
        print(f"❌ Error testing real chat API: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    result = asyncio.run(test_real_chat_api())
    print(f"\n🏁 FINAL RESULT: Real chat API memory test {'PASSED' if result else 'FAILED'}")
    sys.exit(0 if result else 1)