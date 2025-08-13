#!/usr/bin/env python3
"""Simple debug of the exact reference analysis issue."""

import asyncio
import sys
sys.path.append('app')

async def debug_simple():
    """Test reference analysis for 'add that to the document'."""
    
    print("🔍 Testing reference analysis for 'add that to the document'...")
    
    try:
        from app.langgraph_runner import LLMReferenceAnalyzer
        
        analyzer = LLMReferenceAnalyzer("gpt-4o-mini")
        
        # Simulate a conversation where agent provided security recommendations
        user_message_1 = "Can you provide security recommendations for this project?"
        
        agent_response_1 = """Here are some key security recommendations for your project:

**Core Security Measures:**
- **Access Control**: Implement role-based access control (RBAC)
- **Authentication**: Multi-factor authentication (MFA) for all accounts  
- **Data Encryption**: AES-256 encryption for data at rest, TLS 1.3 for transit
- **Input Validation**: Comprehensive validation of all user inputs
- **Security Monitoring**: Real-time monitoring and logging
- **Regular Updates**: Automated security patches and dependency updates
- **Backup Strategy**: Encrypted, regularly tested backup procedures

Would you like me to expand on any of these areas?"""
        
        # Build conversation context
        conversation_context = f"User: {user_message_1}\n\nAssistant: {agent_response_1}\n\n"
        
        # Test the problematic follow-up
        user_message_2 = "add that to the document"
        
        print(f"Testing: '{user_message_2}'")
        print(f"With conversation context: {len(conversation_context)} chars")
        print(f"Last AI response: {len(agent_response_1)} chars")
        
        # Analyze the reference
        analysis = await analyzer.analyze_reference(
            user_message_2,
            conversation_context,
            agent_response_1
        )
        
        print(f"\n📊 REFERENCE ANALYSIS:")
        print(f"  has_reference: {analysis.get('has_reference')}")
        print(f"  confidence: {analysis.get('confidence')}")
        print(f"  reference_type: {analysis.get('reference_type')}")
        print(f"  action_requested: {analysis.get('action_requested')}")
        print(f"  referenced_content preview: {analysis.get('referenced_content', '')[:200]}...")
        
        # Test the context building logic from unified system
        needs_context = analysis.get('has_reference', False)
        reference_context_for_chat = None
        
        if needs_context and analysis:
            referenced_content = analysis.get('referenced_content', '')
            action_requested = analysis.get('action_requested', '')
            
            if referenced_content:
                reference_context_for_chat = f"Referenced content: {referenced_content}\nAction requested: {action_requested}"
                print(f"\n✅ WOULD BUILD REFERENCE CONTEXT:")
                print(f"  {reference_context_for_chat[:300]}...")
            else:
                print(f"\n❌ NO REFERENCED CONTENT TO BUILD CONTEXT FROM")
        else:
            print(f"\n❌ WOULD NOT BUILD REFERENCE CONTEXT:")
            print(f"  needs_context: {needs_context}")
            print(f"  analysis exists: {analysis is not None}")
        
        # Return whether this would work
        has_reference = analysis.get('has_reference', False)
        high_confidence = analysis.get('confidence') in ['high', 'medium']
        has_content = bool(analysis.get('referenced_content', ''))
        
        success = has_reference and high_confidence and has_content
        
        print(f"\n🏁 ANALYSIS SUCCESS: {success}")
        print(f"  has_reference: {has_reference}")
        print(f"  high_confidence: {high_confidence}")  
        print(f"  has_content: {has_content}")
        
        return success
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    result = asyncio.run(debug_simple())
    print(f"\n🏁 SIMPLE REFERENCE TEST: {'✅ WORKS' if result else '❌ BROKEN'}")
    sys.exit(0 if result else 1)