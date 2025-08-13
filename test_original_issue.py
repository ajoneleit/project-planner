#!/usr/bin/env python3
"""
Test the exact original issue: agents claiming "I don't have access to our conversation history"
"""

import asyncio
import aiohttp
import json
import sys

async def test_original_issue():
    """Test the exact scenario the user reported"""
    
    project_slug = "ambers-project" 
    user_id = "anonymous"  # Use same user_id as user likely used
    
    print("🎯 Testing ORIGINAL ISSUE: 'I don't have access to our conversation history'")
    print()
    
    try:
        async with aiohttp.ClientSession() as session:
            
            # First establish some conversation history
            print("📝 Step 1: Establishing conversation history")
            
            messages = [
                "What are the key components of a project plan?",
                "How do you define project success criteria?", 
                "What's the most important first step in project planning?"
            ]
            
            responses = []
            
            for i, message in enumerate(messages, 1):
                print(f"  {i}. User: {message}")
                
                chat_payload = {
                    "message": message,
                    "model": "gpt-4o-mini",
                    "user_id": user_id
                }
                
                async with session.post(
                    f"http://localhost:8000/api/projects/{project_slug}/chat",
                    json=chat_payload,
                    headers={"Content-Type": "application/json"}
                ) as response:
                    
                    if response.status != 200:
                        print(f"❌ API call failed with status {response.status}")
                        return False
                    
                    # Get the response
                    full_response = ""
                    token_count = 0
                    
                    async for line in response.content:
                        line_text = line.decode('utf-8').strip()
                        if line_text.startswith('data: '):
                            try:
                                data = json.loads(line_text[6:])
                                if 'token' in data:
                                    full_response += data['token']
                                    token_count += 1
                                elif 'done' in data and data['done']:
                                    break
                            except json.JSONDecodeError:
                                continue
                    
                    print(f"     Agent: {full_response[:100]}...")
                    print(f"     Tokens: {token_count}")
                    responses.append(full_response)
                
                # Small delay between messages
                await asyncio.sleep(0.5)
            
            print(f"\n✅ Established {len(messages)} conversation turns")
            
            # Now ask the EXACT question that was problematic
            print("\n🎯 Step 2: Testing the original problematic question")
            
            test_question = "do you have access to our conversation history"
            print(f"User: {test_question}")
            
            chat_payload = {
                "message": test_question,
                "model": "gpt-4o-mini", 
                "user_id": user_id
            }
            
            async with session.post(
                f"http://localhost:8000/api/projects/{project_slug}/chat",
                json=chat_payload,
                headers={"Content-Type": "application/json"}
            ) as response:
                
                if response.status != 200:
                    print(f"❌ Final API call failed with status {response.status}")
                    return False
                
                # Get the response
                full_response = ""
                token_count = 0
                
                async for line in response.content:
                    line_text = line.decode('utf-8').strip()
                    if line_text.startswith('data: '):
                        try:
                            data = json.loads(line_text[6:])
                            if 'token' in data:
                                full_response += data['token']
                                token_count += 1
                            elif 'done' in data and data['done']:
                                break
                        except json.JSONDecodeError:
                            continue
                
                print(f"Agent: {full_response}")
                print(f"Tokens: {token_count}")
                
                # Analyze the response for the original issue
                response_lower = full_response.lower()
                
                # Check for the problematic phrases
                problematic_phrases = [
                    "don't have access",
                    "can't see",
                    "don't see", 
                    "no access",
                    "cannot see",
                    "can't access",
                    "don't recall",
                    "no memory"
                ]
                
                has_problematic_phrase = any(phrase in response_lower for phrase in problematic_phrases)
                
                # Check for positive indicators (references to previous conversation)
                positive_indicators = [
                    "project plan" in response_lower,
                    "success criteria" in response_lower,
                    "first step" in response_lower,
                    "yes" in response_lower and "access" in response_lower,
                    "remember" in response_lower,
                    "recall" in response_lower and "ask" in response_lower,
                    "previous" in response_lower,
                    "earlier" in response_lower
                ]
                
                has_positive_indicator = any(indicator for indicator in positive_indicators)
                
                print(f"\n📊 ANALYSIS:")
                print(f"  Tokens used: {token_count} {'✅' if token_count > 0 else '❌'}")
                print(f"  Has problematic phrase: {'❌ YES' if has_problematic_phrase else '✅ NO'}")
                print(f"  Has positive memory indicator: {'✅ YES' if has_positive_indicator else '❌ NO'}")
                
                if has_problematic_phrase:
                    print(f"\n❌ ORIGINAL ISSUE STILL EXISTS")
                    print(f"   Agent still claims: '{full_response}'")
                    return False
                elif has_positive_indicator and token_count > 0:
                    print(f"\n✅ ORIGINAL ISSUE RESOLVED")
                    print(f"   Agent demonstrates conversation memory access")
                    return True
                elif token_count == 0:
                    print(f"\n❌ TECHNICAL ISSUE: Zero tokens suggests LLM not processing")
                    return False
                else:
                    print(f"\n⚠️ UNCLEAR: Response doesn't clearly demonstrate memory access")
                    print(f"   May need more specific testing")
                    return False
                
    except Exception as e:
        print(f"❌ Error testing original issue: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    result = asyncio.run(test_original_issue())
    print(f"\n🏁 ORIGINAL ISSUE TEST: {'✅ RESOLVED' if result else '❌ NOT RESOLVED'}")
    sys.exit(0 if result else 1)