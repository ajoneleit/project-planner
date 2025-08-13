#!/usr/bin/env python3
"""Test the exact user scenario to reproduce the reference issue."""

import asyncio
import aiohttp
import json
import sys

async def test_exact_scenario():
    """Reproduce the exact user scenario."""
    
    project_slug = "agentic-system"
    user_id = "AJ"
    
    print("🔍 Testing EXACT user scenario...")
    
    try:
        async with aiohttp.ClientSession() as session:
            
            # Step 1: Agent provides recommendations (simulated)
            print("\n📝 Step 1: Ask for advice on next steps")
            
            chat_payload_1 = {
                "message": "please give me advice on how to proceed with next steps for this project",
                "model": "gpt-4o-mini",
                "user_id": user_id
            }
            
            async with session.post(
                f"http://localhost:8000/api/projects/{project_slug}/chat",
                json=chat_payload_1,
                headers={"Content-Type": "application/json"},
                timeout=aiohttp.ClientTimeout(total=120)
            ) as response:
                
                if response.status != 200:
                    print(f"❌ First request failed: {response.status}")
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
                
                print(f"Agent response 1: {agent_response_1[:300]}...")
            
            # Brief pause for conversation to be saved
            await asyncio.sleep(1)
            
            # Step 2: User says "Add those to next actions"
            print(f"\n📝 Step 2: User says 'Add those to next actions'")
            
            chat_payload_2 = {
                "message": "Add those to next actions",
                "model": "gpt-4o-mini",
                "user_id": user_id
            }
            
            async with session.post(
                f"http://localhost:8000/api/projects/{project_slug}/chat",
                json=chat_payload_2,
                headers={"Content-Type": "application/json"},
                timeout=aiohttp.ClientTimeout(total=120)
            ) as response2:
                
                if response2.status != 200:
                    print(f"❌ Second request failed: {response2.status}")
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
                
                print(f"\nAgent response 2:")
                print(agent_response_2)
                
                # Analyze the response for the exact user issue
                asks_clarification = any(phrase in agent_response_2.lower() for phrase in [
                    "could you please specify", "which items", "what would you like to add",
                    "please clarify", "which specific", "what exactly"
                ])
                
                understands_reference = any(phrase in agent_response_2.lower() for phrase in [
                    "recommendations", "next steps", "i'll add", "adding those"
                ])
                
                print(f"\n📊 EXACT SCENARIO ANALYSIS:")
                print(f"  Asks for clarification (PROBLEM): {'❌ YES' if asks_clarification else '✅ NO'}")
                print(f"  Understands reference: {'✅ YES' if understands_reference else '❌ NO'}")
                
                if asks_clarification:
                    print(f"\n❌ CONFIRMED: Agent asks for clarification instead of understanding 'those'")
                    print(f"   This matches the exact user experience")
                    return False
                else:
                    print(f"\n✅ Agent correctly understands the reference")
                    return True
                
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    result = asyncio.run(test_exact_scenario())
    print(f"\n🔍 EXACT SCENARIO: {'✅ WORKING' if result else '❌ BROKEN (matches user experience)'}")
    sys.exit(0 if result else 1)