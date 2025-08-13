#!/usr/bin/env python3
"""
Test conversation continuity across multiple real chat sessions with different users.
"""

import asyncio
import aiohttp
import json
import time
import sys

async def chat_with_api(session, project_slug, message, user_id, model="gpt-4o-mini"):
    """Helper function to make a chat API call and return the response"""
    
    chat_payload = {
        "message": message,
        "model": model, 
        "user_id": user_id
    }
    
    print(f"User {user_id}: {message}")
    
    async with session.post(
        f"http://localhost:8000/api/projects/{project_slug}/chat",
        json=chat_payload,
        headers={"Content-Type": "application/json"}
    ) as response:
        
        if response.status != 200:
            print(f"❌ API call failed with status {response.status}")
            response_text = await response.text()
            print(f"Response: {response_text}")
            return "", 0
        
        # Stream the response
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
        print()
        
        return full_response, token_count

async def test_multiple_sessions():
    """Test conversation continuity across multiple chat sessions"""
    
    project_slug = "ambers-project"
    
    print("🔄 Testing conversation continuity across multiple chat sessions...")
    
    try:
        async with aiohttp.ClientSession() as session:
            
            # Session A: User Bob
            print("📱 SESSION A: User Bob")
            print("=" * 50)
            
            response_a1, tokens_a1 = await chat_with_api(
                session, project_slug, 
                "Hi, I'm Bob. I need help with user authentication for this project.",
                "bob-user"
            )
            
            await asyncio.sleep(1)  # Allow conversation to be saved
            
            response_a2, tokens_a2 = await chat_with_api(
                session, project_slug,
                "Do you remember my name and what I need help with?",
                "bob-user"
            )
            
            # Check if Bob's session has memory
            bob_memory_works = (
                "Bob" in response_a2 and 
                ("authentication" in response_a2.lower() or "auth" in response_a2.lower()) and
                tokens_a2 > 0
            )
            
            print(f"Bob's session memory: {'✅ WORKS' if bob_memory_works else '❌ FAILED'}")
            
            # Session B: User Carol (should not see Bob's conversation)
            print("\n📱 SESSION B: User Carol")
            print("=" * 50)
            
            response_b1, tokens_b1 = await chat_with_api(
                session, project_slug,
                "Hello, I'm Carol. I'm working on the database design.",
                "carol-user"
            )
            
            await asyncio.sleep(1)
            
            response_b2, tokens_b2 = await chat_with_api(
                session, project_slug,
                "What did Bob ask me about earlier?",
                "carol-user" 
            )
            
            # Carol should NOT know about Bob's conversation
            carol_isolation_works = (
                "Bob" not in response_b2 and
                "authentication" not in response_b2.lower() and
                tokens_b2 > 0
            )
            
            print(f"Carol's session isolation: {'✅ WORKS' if carol_isolation_works else '❌ FAILED'}")
            
            # Session C: Bob returns (should remember his previous conversation)
            print("\n📱 SESSION C: Bob Returns") 
            print("=" * 50)
            
            response_c1, tokens_c1 = await chat_with_api(
                session, project_slug,
                "I'm back. What was I asking about before?",
                "bob-user"
            )
            
            # Bob should remember his previous authentication question
            bob_continuity_works = (
                ("authentication" in response_c1.lower() or "auth" in response_c1.lower()) and
                tokens_c1 > 0
            )
            
            print(f"Bob's session continuity: {'✅ WORKS' if bob_continuity_works else '❌ FAILED'}")
            
            # Session D: Carol continues her session
            print("\n📱 SESSION D: Carol Continues")
            print("=" * 50)
            
            response_d1, tokens_d1 = await chat_with_api(
                session, project_slug,
                "What was I working on when we last talked?",
                "carol-user"
            )
            
            # Carol should remember her database design work
            carol_continuity_works = (
                "database" in response_d1.lower() and
                tokens_d1 > 0
            )
            
            print(f"Carol's session continuity: {'✅ WORKS' if carol_continuity_works else '❌ FAILED'}")
            
            # Overall test results
            all_tests_pass = (
                bob_memory_works and
                carol_isolation_works and 
                bob_continuity_works and
                carol_continuity_works
            )
            
            print(f"\n🏁 MULTI-SESSION TEST RESULTS:")
            print(f"  Bob's memory: {'✅' if bob_memory_works else '❌'}")
            print(f"  Session isolation: {'✅' if carol_isolation_works else '❌'}")
            print(f"  Bob's continuity: {'✅' if bob_continuity_works else '❌'}")
            print(f"  Carol's continuity: {'✅' if carol_continuity_works else '❌'}")
            print(f"  Overall: {'✅ PASSED' if all_tests_pass else '❌ FAILED'}")
            
            return all_tests_pass
            
    except Exception as e:
        print(f"❌ Error testing multiple sessions: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    result = asyncio.run(test_multiple_sessions())
    sys.exit(0 if result else 1)