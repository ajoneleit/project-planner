#!/usr/bin/env python3
"""Test the LLMReferenceAnalyzer directly to isolate the issue."""

import asyncio
import sys
sys.path.append('app')

async def test_reference_analyzer():
    """Test reference analyzer with the exact failing scenario."""
    
    print("🔍 Testing LLMReferenceAnalyzer directly...")
    
    try:
        from app.langgraph_runner import LLMReferenceAnalyzer
        
        analyzer = LLMReferenceAnalyzer("gpt-4o-mini")
        
        # Simulate the exact failing scenario
        user_message = "Can you provide security recommendations for this project?"
        
        agent_response = """Got it, you're looking for security recommendations for the Test Direct project. To tailor these recommendations effectively, could you clarify a few points?

1. What type of data will the project handle (personal, financial, health records, etc.)?
2. What's the expected scale and user base?
3. Are there specific compliance requirements (GDPR, HIPAA, PCI-DSS, etc.)?

That said, here are some foundational security recommendations that apply to most projects:

**Core Security Measures:**
- **Access Control**: Implement role-based access control (RBAC) with principle of least privilege
- **Authentication**: Multi-factor authentication (MFA) for all user accounts
- **Data Encryption**: AES-256 encryption for data at rest, TLS 1.3 for data in transit
- **Input Validation**: Comprehensive validation and sanitization of all user inputs
- **Security Monitoring**: Real-time monitoring and logging of all security events
- **Regular Updates**: Automated security patches and dependency updates
- **Backup Strategy**: Encrypted, regularly tested backup and recovery procedures

Would you like me to expand on any of these areas or focus on specific aspects based on your project requirements?"""
        
        # Build conversation context
        conversation_context = f"User: {user_message}\n\nAssistant: {agent_response}\n\n"
        
        # Test the problematic follow-up
        followup_message = "add that to the document"
        
        print(f"User message: {user_message}")
        print(f"Agent response: {agent_response[:150]}...")
        print(f"Followup: {followup_message}")
        print()
        
        # Analyze the reference
        analysis = await analyzer.analyze_reference(
            followup_message,
            conversation_context,
            agent_response
        )
        
        print("🤖 Reference Analysis Result:")
        print(f"  has_reference: {analysis.get('has_reference', 'MISSING')}")
        print(f"  reference_type: {analysis.get('reference_type', 'MISSING')}")
        print(f"  referenced_content: {analysis.get('referenced_content', 'MISSING')[:100]}...")
        print(f"  action_requested: {analysis.get('action_requested', 'MISSING')}")
        print(f"  confidence: {analysis.get('confidence', 'MISSING')}")
        
        # Check if it correctly identifies the reference
        has_reference = analysis.get('has_reference', False)
        confidence = analysis.get('confidence', 'low')
        
        if has_reference and confidence in ['high', 'medium']:
            print(f"\n✅ Reference analyzer correctly identifies the reference")
            return True
        else:
            print(f"\n❌ Reference analyzer fails to identify the reference")
            print(f"   This explains why the agent asks for clarification")
            return False
            
    except Exception as e:
        print(f"❌ Error testing reference analyzer: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    result = asyncio.run(test_reference_analyzer())
    print(f"\n🏁 REFERENCE ANALYZER TEST: {'✅ WORKS' if result else '❌ BROKEN'}")
    sys.exit(0 if result else 1)