#!/usr/bin/env python3
"""
Debug the exact reference analyzer logic to understand why it fails.
"""

import asyncio
import sys
import os

# Add the app directory to the Python path
sys.path.append('app')

async def debug_reference_analyzer():
    """Debug the LLM reference analyzer directly"""
    
    print("🔍 Debugging LLM Reference Analyzer...")
    
    try:
        from app.langgraph_runner import LLMReferenceAnalyzer
        
        analyzer = LLMReferenceAnalyzer("gpt-4o-mini")
        
        # Simulate the exact scenario from the user's example
        user_message_1 = """Here are security recommendations for the project:
1. Access Control with RBAC
2. Data Encryption (AES-256 and TLS)  
3. Regular Security Audits
4. Secure Coding Practices
5. Incident Response Plan"""
        
        agent_response_1 = """Got it, you've outlined some important security recommendations for the project. 

1. Access Control with RBAC - This is crucial for ensuring only authorized personnel can access sensitive components
2. Data Encryption using AES-256 for data at rest and TLS for data in transit
3. Regular Security Audits to identify and remediate potential vulnerabilities
4. Secure Coding Practices to prevent common vulnerabilities
5. Incident Response Plan for detecting and responding to security incidents

These are excellent foundational security measures. Would you like me to add these to the project document or expand on any particular area?"""

        user_message_2 = "add that to the document"
        
        # Build conversation context like the system does
        conversation_context = f"User: {user_message_1}\n\nAssistant: {agent_response_1}\n\n"
        
        print("📋 Testing Reference Analysis:")
        print(f"User message 1: {user_message_1[:100]}...")
        print(f"Agent response 1: {agent_response_1[:100]}...")
        print(f"User message 2: {user_message_2}")
        print()
        
        # Test the reference analyzer
        analysis_result = await analyzer.analyze_reference(
            user_message_2,
            conversation_context,
            agent_response_1
        )
        
        print("🤖 Reference Analysis Result:")
        print(f"  has_reference: {analysis_result['has_reference']}")
        print(f"  reference_type: {analysis_result['reference_type']}")
        print(f"  referenced_content: {analysis_result['referenced_content']}")
        print(f"  action_requested: {analysis_result['action_requested']}")
        print(f"  confidence: {analysis_result['confidence']}")
        
        # Test different variations to understand the pattern
        print(f"\n🧪 Testing Variations:")
        
        test_cases = [
            "add those security recommendations to the document",
            "please add the security recommendations to the document", 
            "include that in the project document",
            "add the security measures you mentioned to the document",
            "update the document with those recommendations"
        ]
        
        for i, test_message in enumerate(test_cases, 1):
            print(f"\n  Test {i}: '{test_message}'")
            
            test_result = await analyzer.analyze_reference(
                test_message,
                conversation_context,
                agent_response_1
            )
            
            print(f"    Result: {test_result['has_reference']} ({test_result['confidence']})")
            if test_result['has_reference']:
                print(f"    Action: {test_result['action_requested']}")
                print(f"    Content: {test_result['referenced_content'][:50]}...")
        
        # Analyze the issue
        if not analysis_result['has_reference']:
            print(f"\n❌ ISSUE IDENTIFIED:")
            print(f"   The reference analyzer fails to recognize 'add that to the document'")
            print(f"   as referring to the security recommendations from the user's message")
            print(f"\n💡 ROOT CAUSE THEORY:")
            print(f"   The analyzer prompt focuses on references to 'AI's recent response'") 
            print(f"   but 'that' refers to the user's OWN previous content (security list)")
            print(f"   not the agent's acknowledgment response")
            
            return False
        else:
            print(f"\n✅ Reference analyzer working correctly")
            return True
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    result = asyncio.run(debug_reference_analyzer())
    print(f"\n🏁 REFERENCE ANALYZER TEST: {'✅ WORKS' if result else '❌ BROKEN'}")
    sys.exit(0 if result else 1)