#!/usr/bin/env python3
"""Test reference extraction with the exact user scenario."""

import asyncio
import sys
sys.path.append('app')

async def test_reference_extraction():
    """Test the reference analyzer with the exact user scenario."""
    
    print("🔍 Testing reference extraction with user's exact scenario...")
    
    try:
        from app.langgraph_runner import LLMReferenceAnalyzer
        
        analyzer = LLMReferenceAnalyzer("gpt-4o-mini")
        
        # Simulate the exact scenario from the user
        user_message_1 = "please give me advice on how to proceed with next steps for this project"
        
        # Simulate the agent's response that provided recommendations
        agent_response = """Here's a recap of the current state of the "Agentic System" project to help guide your next steps:

### Current Project State:
- **Objective**: Add metrics for success to measure project effectiveness.
- **Status**: The project is addressing challenges such as template evolution gaps, system complexity, performance optimization, and integration stability.

### Recommendations for Next Steps:
1. **Focus on Documentation**: Start developing the detailed documentation for migration steps as outlined in the Next Actions section. This should include:
   - Pre-migration checks
   - Data migration strategies
   - Rollback procedures
   - Testing framework

2. **Address Open Questions**: Identify the key stakeholders who can provide insights into the unresolved questions. Schedule discussions or meetings to clarify integration requirements and address any team concerns.

3. **Review Metrics for Success**: Ensure that the metrics for success are aligned with the project's objectives. Consider gathering feedback from stakeholders to refine these metrics further.

4. **Risk Mitigation Planning**: Develop a risk mitigation strategy for the identified risks, particularly focusing on compatibility and performance impacts during migration.

5. **Engage Stakeholders**: Keep stakeholders informed about progress and involve them in key decisions, especially regarding integration and migration strategies.

Would you like to dive deeper into any specific area or need assistance with a particular task?"""
        
        # Build conversation context
        conversation_context = f"User: {user_message_1}\n\nAssistant: {agent_response}\n\n"
        
        # Test the problematic follow-up - this should extract the 5 recommendations
        followup_message = "Add those to next actions"
        
        print(f"User's original message: {user_message_1}")
        print(f"Agent provided 5 recommendations (items 1-5)")
        print(f"User's follow-up: '{followup_message}'")
        print(f"Expected: Should extract the 5 recommendations as referenced content")
        
        # Analyze the reference
        analysis = await analyzer.analyze_reference(
            followup_message,
            conversation_context,
            agent_response
        )
        
        print(f"\n📊 REFERENCE ANALYSIS RESULTS:")
        print(f"  has_reference: {analysis.get('has_reference')}")
        print(f"  confidence: {analysis.get('confidence')}")
        print(f"  reference_type: {analysis.get('reference_type')}")
        print(f"  action_requested: {analysis.get('action_requested')}")
        print(f"  referenced_content: {analysis.get('referenced_content', '')[:500]}...")
        
        # Check if it correctly identified the 5 recommendations
        referenced_content = analysis.get('referenced_content', '')
        has_reference = analysis.get('has_reference', False)
        confidence = analysis.get('confidence', 'low')
        
        # Look for the numbered recommendations in the referenced content
        has_recommendations = any(item in referenced_content.lower() for item in [
            'focus on documentation', 'address open questions', 'review metrics', 
            'risk mitigation', 'engage stakeholders'
        ])
        
        has_numbered_items = any(num in referenced_content for num in ['1.', '2.', '3.', '4.', '5.'])
        
        print(f"\n🔍 EXTRACTION QUALITY CHECK:")
        print(f"  Detected reference: {'✅ YES' if has_reference else '❌ NO'}")
        print(f"  High confidence: {'✅ YES' if confidence in ['high', 'medium'] else '❌ NO'}")
        print(f"  Contains recommendations: {'✅ YES' if has_recommendations else '❌ NO'}")
        print(f"  Contains numbered items: {'✅ YES' if has_numbered_items else '❌ NO'}")
        
        success = has_reference and confidence in ['high', 'medium'] and (has_recommendations or has_numbered_items)
        
        if success:
            print(f"\n✅ REFERENCE EXTRACTION WORKING")
            print(f"   Correctly identified and extracted the 5 recommendations")
        else:
            print(f"\n❌ REFERENCE EXTRACTION BROKEN")
            print(f"   Failed to extract the correct content that user was referencing")
            
        return success
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    result = asyncio.run(test_reference_extraction())
    print(f"\n🔍 REFERENCE EXTRACTION: {'✅ WORKING' if result else '❌ BROKEN'}")
    sys.exit(0 if result else 1)