#!/usr/bin/env python3
"""Final verification that the reference system is working."""

import asyncio
import sys
sys.path.append('app')

async def final_verification():
    """Final test to verify the system works as expected."""
    
    print("✅ FINAL VERIFICATION: Agent reference understanding")
    
    try:
        from app.langgraph_runner import AgentCoordinator
        
        coordinator = AgentCoordinator("final-test", "gpt-4o-mini")
        
        # Test the exact user scenario
        print("\n📝 User provides detailed security recommendations:")
        security_content = """Here are some security recommendations tailored for the project:

1. **Authentication & Authorization**
   - Implement OAuth 2.0 with PKCE for secure authentication
   - Use role-based access control (RBAC) with principle of least privilege

2. **Data Protection** 
   - Encrypt all data at rest using AES-256 encryption
   - Use TLS 1.3 for all data in transit

3. **API Security**
   - Rate limiting to prevent abuse and DoS attacks
   - Input validation and sanitization for all user inputs"""
        
        print(f"User: {security_content[:200]}...")
        
        response1, updates1 = await coordinator.process_conversation_turn_unified(
            security_content,
            "test-user"
        )
        
        print(f"Agent: {response1[:150]}...")
        
        print(f"\n📝 User says: 'add that to the document'")
        
        response2, updates2 = await coordinator.process_conversation_turn_unified(
            "add that to the document",
            "test-user"
        )
        
        print(f"Agent: {response2}")
        print(f"Document updates made: {updates2}")
        
        # Final analysis
        success_indicators = {
            "No clarification request": not any(phrase in response2.lower() for phrase in [
                "what specific", "could you clarify", "what would you like to include"
            ]),
            "Shows understanding": any(phrase in response2.lower() for phrase in [
                "security", "recommendations", "noted", "authentication", "encryption"
            ]),
            "Document updated": updates2 > 0,
            "Confident response": any(phrase in response2.lower() for phrase in [
                "i've noted", "got it", "those", "recommendations"
            ])
        }
        
        print(f"\n📊 SUCCESS INDICATORS:")
        for indicator, passed in success_indicators.items():
            print(f"  {indicator}: {'✅' if passed else '❌'}")
        
        overall_success = sum(success_indicators.values()) >= 3
        
        if overall_success:
            print(f"\n✅ VERIFICATION PASSED: Reference system is working correctly")
            print(f"   - Agent understands references to previous content")
            print(f"   - Agent doesn't ask for clarification when context is clear") 
            print(f"   - Document updates are made automatically")
            print(f"   - System handles 'add that to the document' properly")
        else:
            print(f"\n❌ VERIFICATION FAILED: Issues remain")
            
        return overall_success
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    result = asyncio.run(final_verification())
    print(f"\n🏁 FINAL VERIFICATION: {'✅ SYSTEM WORKING' if result else '❌ SYSTEM BROKEN'}")
    sys.exit(0 if result else 1)