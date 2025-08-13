#!/usr/bin/env python3
"""
Debug script to trace exactly what happens during section updates.
"""

import asyncio
import sys
import os
import json

# Add the app directory to the Python path
sys.path.append('app')

async def test_section_replacement_debug():
    try:
        from app.langgraph_runner import InfoAgent
        from app.core.memory_unified import get_unified_memory
        
        print("🔍 Debugging section replacement issue...")
        
        # Step 1: Check current document state
        print("\n📄 Step 1: Current document state")
        unified_memory = await get_unified_memory()
        current_content = await unified_memory.get_project("ambers-project")
        
        print("Current 'Systems & Data Sources' section:")
        import re
        section_pattern = r'^## Systems & Data Sources.*?(?=^## |\Z)'
        match = re.search(section_pattern, current_content, re.MULTILINE | re.DOTALL)
        if match:
            current_section_content = match.group(0)
            print(f"'{current_section_content}'")
        else:
            print("❌ Section not found!")
            return False
            
        # Step 2: Create InfoAgent and test extraction
        print("\n🤖 Step 2: Testing InfoAgent extraction")
        info_agent = InfoAgent("ambers-project")
        await info_agent.initialize("anonymous")
        
        # Simulate the user's input and a mock AI response about adding systems
        user_input = "yes add these systems as well. Include both the current and previous info from the systems section. 5. Task Queue & Dependency Manager"
        
        mock_ai_response = """Let's update the **Systems & Data Sources** section with the new information while retaining the existing details. Here's how the updated section will look:

## Systems & Data Sources
- **Task Manager / Meta-Agent**: Central orchestrator that coordinates all sub-agent activities.
- **Task Queue & Dependency Manager**:
  - `task-queue.json` – Sequential and parallel tasks.
  - `dependencies.json` – Ensures prerequisite tasks are done before dependent ones run."""
        
        conversation_context = f"User: {user_input}\nAssistant: {mock_ai_response}"
        
        # Call the extraction method
        extraction_data = await info_agent.analyze_and_extract(user_input, mock_ai_response, conversation_context)
        
        print(f"📊 Extraction data structure:")
        print(json.dumps(extraction_data, indent=2))
        
        # Step 3: Check what the extraction data contains
        updates = extraction_data.get("updates", {})
        if "Systems & Data Sources" in updates:
            section_update = updates["Systems & Data Sources"]
            print(f"\n📋 Section update details:")
            print(f"  Content: {section_update.get('content', '')[:200]}...")
            print(f"  Replace mode: {section_update.get('replace_existing', False)}")
            print(f"  Is new section: {section_update.get('is_new_section', False)}")
        else:
            print("❌ No 'Systems & Data Sources' section found in updates")
            
        # Step 4: Execute the update and trace what happens
        print(f"\n🔄 Step 4: Executing document update")
        
        # Check if the content is incremental or full section rewrite
        if "Systems & Data Sources" in updates:
            content = updates["Systems & Data Sources"].get("content", "")
            print(f"\n📝 Content analysis:")
            print(f"  Content length: {len(content)} characters")
            print(f"  Contains original content keywords: {'Technical infrastructure' in content}")
            print(f"  Contains new content keywords: {'Task Queue' in content}")
            
            # If it contains both, the LLM is rewriting the entire section instead of providing incremental content
            if "Technical infrastructure" in content and "Task Queue" in content:
                print("⚠️  ISSUE FOUND: LLM is rewriting entire section instead of providing incremental content")
            elif "Task Queue" in content and "Technical infrastructure" not in content:
                print("✅ LLM correctly providing only incremental content")
            else:
                print("🤔 Unclear content pattern")
        
        # Step 5: Test the actual update mechanism
        print(f"\n💾 Step 5: Testing update mechanism")
        updates_made = await info_agent.update_document(extraction_data, "debug_user")
        
        print(f"Updates made: {updates_made}")
        
        # Step 6: Check the result
        print(f"\n📄 Step 6: Checking final result")
        final_content = await unified_memory.get_project("ambers-project")
        
        final_match = re.search(section_pattern, final_content, re.MULTILINE | re.DOTALL)
        if final_match:
            final_section_content = final_match.group(0)
            print("Final 'Systems & Data Sources' section:")
            print(f"'{final_section_content}'")
            
            # Check if original content was preserved
            if "*Technical infrastructure, data sources, tools and platforms*" in final_section_content:
                print("✅ Original content preserved")
            else:
                print("❌ Original content was lost - this is the bug!")
                
        return True
        
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    result = asyncio.run(test_section_replacement_debug())
    sys.exit(0 if result else 1)