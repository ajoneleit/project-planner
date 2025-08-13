#!/usr/bin/env python3
"""
Debug the exact timing issue with message context retrieval.
"""

import asyncio
import aiohttp
import json
import sys
import time

async def debug_message_timing():
    """Test the exact timing issue with immediate previous message access"""
    
    project_slug = "ambers-project"
    user_id = "debug-timing-user"
    
    print("🕐 Debugging message timing issue...")
    
    try:
        async with aiohttp.ClientSession() as session:
            
            # Step 1: Send a detailed message (like the security recommendations)
            print("\n📝 Step 1: Sending detailed message")
            
            detailed_message = """Here are security recommendations for the project:
1. Access Control with RBAC
2. Data Encryption (AES-256 and TLS)
3. Regular Security Audits
4. Secure Coding Practices
5. Incident Response Plan"""
            
            print(f"User: {detailed_message}")
            
            chat_payload = {
                "message": detailed_message,
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
                
                # Get the agent's response
                agent_response = ""
                token_count = 0
                
                async for line in response.content:
                    line_text = line.decode('utf-8').strip()
                    if line_text.startswith('data: '):
                        try:
                            data = json.loads(line_text[6:])
                            if 'token' in data:
                                agent_response += data['token']
                                token_count += 1
                            elif 'done' in data and data['done']:
                                break
                        except json.JSONDecodeError:
                            continue
                
                print(f"Agent: {agent_response[:100]}...")
                print(f"Tokens: {token_count}")
            
            # Small delay to ensure the conversation is saved
            await asyncio.sleep(1)
            
            # Step 2: Immediately send a follow-up referencing the previous message
            print(f"\n📝 Step 2: Immediately referencing previous message")
            
            followup_message = "add that to the document"
            print(f"User: {followup_message}")
            
            chat_payload_2 = {
                "message": followup_message,
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
                
                # Get the agent's response
                agent_response_2 = ""
                token_count_2 = 0
                
                async for line in response2.content:
                    line_text = line.decode('utf-8').strip()
                    if line_text.startswith('data: '):
                        try:
                            data = json.loads(line_text[6:])
                            if 'token' in data:
                                agent_response_2 += data['token']
                                token_count_2 += 1
                            elif 'done' in data and data['done']:
                                break
                        except json.JSONDecodeError:
                            continue
                
                print(f"Agent: {agent_response_2}")
                print(f"Tokens: {token_count_2}")
                
                # Check if the agent shows awareness of the security recommendations
                response_lower = agent_response_2.lower()
                
                # Positive indicators - agent references the previous message
                positive_indicators = [
                    "security" in response_lower,
                    "recommendations" in response_lower, 
                    "access control" in response_lower,
                    "encryption" in response_lower,
                    "audit" in response_lower,
                    "rbac" in response_lower,
                    "added" in response_lower and "document" in response_lower,
                    "updating" in response_lower
                ]
                
                # Negative indicators - agent doesn't see the previous message
                negative_indicators = [
                    "clarify" in response_lower,
                    "what would you like" in response_lower,
                    "which details" in response_lower,
                    "what specific" in response_lower,
                    "could you please" in response_lower,
                    "what information" in response_lower
                ]
                
                has_positive = any(indicator for indicator in positive_indicators)
                has_negative = any(indicator for indicator in negative_indicators)
                
                print(f"\n📊 ANALYSIS:")
                print(f"  Agent references previous content: {'✅ YES' if has_positive else '❌ NO'}")
                print(f"  Agent asks for clarification: {'❌ YES' if has_negative else '✅ NO'}")
                print(f"  Tokens used: {token_count_2} {'✅' if token_count_2 > 0 else '❌'}")
                
                if has_positive and not has_negative:
                    print(f"\n✅ MESSAGE TIMING WORKS - Agent sees previous message")
                    return True
                elif has_negative:
                    print(f"\n❌ MESSAGE TIMING ISSUE - Agent doesn't see previous message content")
                    print(f"   Agent is asking for clarification instead of using previous context")
                    return False
                else:
                    print(f"\n⚠️ UNCLEAR RESULT - Need more testing")
                    return False
    
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    result = asyncio.run(debug_message_timing())
    print(f"\n🏁 MESSAGE TIMING TEST: {'✅ WORKS' if result else '❌ BROKEN'}")
    sys.exit(0 if result else 1)