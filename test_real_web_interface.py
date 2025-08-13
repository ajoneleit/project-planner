#!/usr/bin/env python3
"""Test the exact web interface API that the user is experiencing."""

import asyncio
import aiohttp
import json
import sys

async def test_real_web_interface():
    """Test the real web interface behavior."""
    
    project_slug = "ambers-project"  # Use existing project
    user_id = "AJ"  # Use the actual user ID from the example
    
    print("🌐 Testing REAL web interface behavior...")
    
    try:
        async with aiohttp.ClientSession() as session:
            
            # Step 1: Simulate providing detailed information (like security recommendations)
            print("\n📝 Step 1: User provides detailed content")
            
            detailed_content = """Here are comprehensive security recommendations for the project:

1. **Authentication & Authorization**
   - Implement OAuth 2.0 with PKCE for secure authentication
   - Use role-based access control (RBAC) with principle of least privilege
   - Implement session management with secure cookies and CSRF protection

2. **Data Protection** 
   - Encrypt all data at rest using AES-256 encryption
   - Use TLS 1.3 for all data in transit
   - Implement proper key management with HSM or key vault
   
3. **API Security**
   - Rate limiting to prevent abuse and DoS attacks
   - Input validation and sanitization for all user inputs
   - Implement proper error handling without information disclosure

4. **Monitoring & Compliance**
   - Real-time security monitoring and alerting
   - Regular security audits and penetration testing
   - Compliance with relevant standards (SOC2, GDPR, etc.)"""
            
            chat_payload_1 = {
                "message": detailed_content,
                "model": "gpt-4o-mini", 
                "user_id": user_id
            }
            
            # Make the first request
            async with session.post(
                f"http://localhost:8000/api/projects/{project_slug}/chat",
                json=chat_payload_1,
                headers={"Content-Type": "application/json"}
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
                
                print(f"Agent response 1: {agent_response_1[:200]}...")
            
            # Wait a moment for the conversation to be saved
            await asyncio.sleep(1)
            
            # Step 2: Test the exact user scenario - "add that to the document" 
            print(f"\n📝 Step 2: User says 'add that to the document'")
            
            chat_payload_2 = {
                "message": "add that to the document",
                "model": "gpt-4o-mini",
                "user_id": user_id
            }
            
            async with session.post(
                f"http://localhost:8000/api/projects/{project_slug}/chat",
                json=chat_payload_2,
                headers={"Content-Type": "application/json"}
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
                
                print(f"\n🤖 Agent response 2:")
                print(agent_response_2)
                print()
                
                # Analyze the REAL web interface behavior
                asks_clarification = any(phrase in agent_response_2.lower() for phrase in [
                    "could you please clarify", "what specific details", 
                    "what would you like to include", "please clarify",
                    "what information", "which content"
                ])
                
                understands_reference = any(phrase in agent_response_2.lower() for phrase in [
                    "security recommendations", "added", "updated", "document",
                    "authentication", "encryption", "api security"
                ])
                
                confident_action = any(phrase in agent_response_2.lower() for phrase in [
                    "i've added", "i'll add", "adding", "included", "incorporated"
                ])
                
                print(f"📊 REAL WEB INTERFACE ANALYSIS:")
                print(f"  Asks for clarification (PROBLEM): {'❌ YES' if asks_clarification else '✅ NO'}")
                print(f"  Understands reference content: {'✅ YES' if understands_reference else '❌ NO'}")  
                print(f"  Takes confident action: {'✅ YES' if confident_action else '❌ NO'}")
                
                # This matches the user's experience if it asks for clarification
                user_experience_broken = asks_clarification and not confident_action
                
                if user_experience_broken:
                    print(f"\n❌ CONFIRMED: Real web interface is broken - matches user's experience")
                    print(f"   Agent asks for clarification instead of understanding the reference")
                    return False
                else:
                    print(f"\n✅ Web interface working correctly")
                    return True
                
    except Exception as e:
        print(f"❌ Error testing real web interface: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    result = asyncio.run(test_real_web_interface())
    print(f"\n🌐 REAL WEB INTERFACE: {'✅ WORKING' if result else '❌ BROKEN (matches user experience)'}")
    sys.exit(0 if result else 1)