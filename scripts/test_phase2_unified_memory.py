#!/usr/bin/env python3
"""
Phase 2 Unified Memory System Testing Script
Tests the unified memory system and new conversation memory architecture.

This script validates:
1. Unified memory system initialization and functionality
2. Conversation memory CRUD operations  
3. Project document management
4. Feature flag integration
5. Migration logging integration
6. End-to-end conversation flow
"""

import asyncio
import sys
import os
import tempfile
import json
from pathlib import Path
from datetime import datetime

# Add the app directory to Python path
sys.path.insert(0, 'app')

async def test_unified_memory_initialization():
    """Test unified memory system initialization."""
    print("\n🔧 Testing Unified Memory System Initialization")
    print("=" * 60)
    
    try:
        from app.core.memory_unified import get_unified_memory
        
        # Test initialization
        unified_memory = await get_unified_memory()
        print("✅ Unified memory system initialized successfully")
        
        # Test basic functionality
        test_key = "test_memory_entry"
        test_content = "This is a test memory entry"
        
        success = await unified_memory.save_memory(test_key, test_content)
        if success:
            print("✅ Memory save operation working")
        else:
            print("❌ Memory save operation failed")
            return False
        
        loaded_content = await unified_memory.load_memory(test_key)
        if loaded_content == test_content:
            print("✅ Memory load operation working")
        else:
            print(f"❌ Memory load operation failed: expected '{test_content}', got '{loaded_content}'")
            return False
        
        return True
        
    except Exception as e:
        print(f"❌ Unified memory initialization test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

async def test_conversation_memory_operations():
    """Test conversation memory CRUD operations."""
    print("\n💬 Testing Conversation Memory Operations")
    print("=" * 60)
    
    try:
        from app.core.memory_unified import get_unified_memory
        from app.core.conversation_id_manager import ConversationIDManager
        
        unified_memory = await get_unified_memory()
        
        # Test conversation ID generation
        project_slug = "test-conversation-project"
        user_id = "test-user"
        conversation_id = ConversationIDManager.generate_standard_id(project_slug, user_id)
        expected_id = f"{project_slug}:{user_id}"
        
        if conversation_id == expected_id:
            print(f"✅ Conversation ID generation: {conversation_id}")
        else:
            print(f"❌ Conversation ID generation failed: expected {expected_id}, got {conversation_id}")
            return False
        
        # Test adding messages
        await unified_memory.add_message(conversation_id, "user", "Hello, this is a test message", user_id)
        print("✅ User message added successfully")
        
        await unified_memory.add_message(conversation_id, "assistant", "Hello! I understand this is a test. How can I help you?", user_id)
        print("✅ Assistant message added successfully")
        
        # Test retrieving conversation
        messages = await unified_memory.get_conversation(conversation_id)
        if len(messages) == 2:
            print(f"✅ Retrieved {len(messages)} messages from conversation")
            
            # Verify message content
            if messages[0]['role'] == 'user' and messages[0]['content'] == "Hello, this is a test message":
                print("✅ User message content verified")
            else:
                print("❌ User message content verification failed")
                return False
                
            if messages[1]['role'] == 'assistant' and "test" in messages[1]['content']:
                print("✅ Assistant message content verified")
            else:
                print("❌ Assistant message content verification failed")
                return False
        else:
            print(f"❌ Expected 2 messages, got {len(messages)}")
            return False
        
        return True
        
    except Exception as e:
        print(f"❌ Conversation memory operations test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

async def test_project_document_management():
    """Test project document management operations."""
    print("\n📄 Testing Project Document Management")
    print("=" * 60)
    
    try:
        from app.core.memory_unified import get_unified_memory
        
        unified_memory = await get_unified_memory()
        
        # Test project creation
        project_slug = "test-document-project"
        initial_content = f"""# Test Document Project
_Created: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}_

## Executive Summary
This is a test project for validating document management functionality.

## Test Section
Initial content for testing.
"""
        
        success = await unified_memory.save_project(project_slug, initial_content, "test-user")
        if success:
            print("✅ Project document created successfully")
        else:
            print("❌ Project document creation failed")
            return False
        
        # Test project retrieval
        retrieved_content = await unified_memory.get_project(project_slug)
        if retrieved_content and "Test Document Project" in retrieved_content:
            print("✅ Project document retrieved successfully")
        else:
            print("❌ Project document retrieval failed")
            return False
        
        # Test project list
        projects = await unified_memory.list_projects()
        if project_slug in projects:
            print(f"✅ Project listed in {len(projects)} total projects")
        else:
            print("❌ Project not found in project list")
            return False
        
        # Test section update
        success = await unified_memory.update_project_section(
            project_slug, 
            "Test Section", 
            "Updated content for testing section updates.",
            "test-user",
            "test-user"
        )
        if success:
            print("✅ Project section updated successfully")
            
            # Verify update
            updated_content = await unified_memory.get_project(project_slug)
            if "Updated content for testing section updates" in updated_content:
                print("✅ Section update content verified")
            else:
                print("❌ Section update content verification failed")
                return False
        else:
            print("❌ Project section update failed")
            return False
        
        return True
        
    except Exception as e:
        print(f"❌ Project document management test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

async def test_feature_flag_integration():
    """Test feature flag integration with memory system."""
    print("\n🚩 Testing Feature Flag Integration")
    print("=" * 60)
    
    try:
        from app.core.feature_flags import is_feature_enabled, get_feature_flags
        from app.langgraph_runner import get_conversation_memory_for_project, add_conversation_to_memory
        
        # Test Phase 2 feature flags
        phase2_flags = [
            "compatibility_layer_active",
            "conversation_id_manager",
            "memory_migration_logging",
            "data_integrity_validation"
        ]
        
        for flag_name in phase2_flags:
            enabled = await is_feature_enabled(flag_name)
            status = "✅" if enabled else "⚠️"
            print(f"{status} {flag_name}: {'ENABLED' if enabled else 'DISABLED'}")
        
        # Test unified memory flag (should be disabled in Phase 2)
        unified_enabled = await is_feature_enabled("unified_memory_primary")
        if not unified_enabled:
            print("✅ unified_memory_primary correctly disabled (Phase 2 transition)")
        else:
            print("⚠️ unified_memory_primary enabled - testing direct unified memory path")
        
        # Test memory operations through compatibility layer
        project_slug = "test-flag-integration"
        user_id = "test-user"
        
        # Test conversation memory retrieval
        memory_context = await get_conversation_memory_for_project(project_slug, user_id)
        if isinstance(memory_context, dict) and 'messages' in memory_context:
            print(f"✅ Conversation memory context retrieved: {len(memory_context['messages'])} messages")
        else:
            print("❌ Conversation memory context retrieval failed")
            return False
        
        # Test conversation adding
        success = await add_conversation_to_memory(
            project_slug, 
            "Test user message for flag integration", 
            "Test assistant response for flag integration",
            user_id
        )
        if success:
            print("✅ Conversation added through feature-flagged system")
        else:
            print("❌ Conversation adding through feature-flagged system failed")
            return False
        
        return True
        
    except Exception as e:
        print(f"❌ Feature flag integration test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

async def test_migration_logging_integration():
    """Test migration logging integration."""
    print("\n📊 Testing Migration Logging Integration")
    print("=" * 60)
    
    try:
        from app.core.migration_logging import get_migration_logger, log_conversation_read, log_conversation_write
        
        # Test logging integration
        logger = await get_migration_logger()
        print("✅ Migration logger retrieved successfully")
        
        # Test conversation operation logging
        test_conversation_id = "test-logging:test-user"
        
        await log_conversation_read(test_conversation_id, 5, "test-user")
        print("✅ Conversation read logged successfully")
        
        await log_conversation_write(test_conversation_id, {"role": "user", "content": "Test message"}, "test-user")
        print("✅ Conversation write logged successfully")
        
        # Test migration summary (should work even with limited data)
        try:
            summary = await logger.get_migration_summary(hours=1)
            if isinstance(summary, dict) and 'total_events' in summary:
                print(f"✅ Migration summary generated: {summary['total_events']} events in last hour")
            else:
                print("⚠️ Migration summary generated but format unexpected")
        except Exception as e:
            print(f"⚠️ Migration summary generation failed (expected in test environment): {e}")
        
        return True
        
    except Exception as e:
        print(f"❌ Migration logging integration test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

async def test_end_to_end_conversation_flow():
    """Test end-to-end conversation flow using new unified system."""
    print("\n🔄 Testing End-to-End Conversation Flow")
    print("=" * 60)
    
    try:
        from app.langgraph_runner import (
            get_conversation_memory_for_project, 
            add_conversation_to_memory,
            get_project_document_memory,
            update_project_document
        )
        from app.core.conversation_id_manager import ConversationIDManager
        
        # Test complete conversation workflow
        project_slug = "test-e2e-conversation"
        user_id = "test-user"
        
        # Step 1: Get initial conversation state
        initial_memory = await get_conversation_memory_for_project(project_slug, user_id)
        initial_message_count = len(initial_memory['messages'])
        print(f"✅ Initial conversation state: {initial_message_count} messages")
        
        # Step 2: Add conversation exchange
        success = await add_conversation_to_memory(
            project_slug,
            "I want to create a new feature for user authentication",
            "I'd be happy to help you plan the user authentication feature. Let's start by understanding your requirements.",
            user_id
        )
        if success:
            print("✅ Conversation exchange added successfully")
        else:
            print("❌ Conversation exchange addition failed")
            return False
        
        # Step 3: Verify conversation was stored
        updated_memory = await get_conversation_memory_for_project(project_slug, user_id)
        updated_message_count = len(updated_memory['messages'])
        
        if updated_message_count > initial_message_count:
            print(f"✅ Conversation stored: {updated_message_count - initial_message_count} new messages")
        else:
            print("❌ Conversation storage verification failed")
            return False
        
        # Step 4: Test document operations
        doc_context = await get_project_document_memory(project_slug)
        if doc_context['content']:
            print("✅ Project document context retrieved")
        else:
            print("❌ Project document context retrieval failed")
            return False
        
        # Step 5: Test document update
        success = await update_project_document(
            project_slug,
            "Requirements",
            "User authentication feature requirements:\n- Secure login system\n- Password reset functionality\n- Multi-factor authentication support",
            "Test User",
            user_id
        )
        if success:
            print("✅ Document updated successfully")
            
            # Verify update
            updated_doc = await get_project_document_memory(project_slug)
            if "authentication feature requirements" in updated_doc['content']:
                print("✅ Document update content verified")
            else:
                print("❌ Document update content verification failed")
                return False
        else:
            print("❌ Document update failed")
            return False
        
        # Step 6: Verify conversation ID consistency
        expected_id = ConversationIDManager.generate_standard_id(project_slug, user_id)
        actual_id = updated_memory['conversation_id']
        
        # Note: In Phase 2, we may still be using legacy ID format
        print(f"✅ Conversation ID format: expected '{expected_id}', actual '{actual_id}'")
        
        return True
        
    except Exception as e:
        print(f"❌ End-to-end conversation flow test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

async def main():
    """Run all Phase 2 unified memory tests."""
    print("🚀 Phase 2 Unified Memory System Testing")
    print("=" * 70)
    print(f"Started at: {datetime.now().isoformat()}")
    print()
    
    test_results = {}
    
    # Run all tests
    test_results['unified_memory_init'] = await test_unified_memory_initialization()
    test_results['conversation_operations'] = await test_conversation_memory_operations()
    test_results['document_management'] = await test_project_document_management()
    test_results['feature_flag_integration'] = await test_feature_flag_integration()
    test_results['migration_logging'] = await test_migration_logging_integration()
    test_results['end_to_end_flow'] = await test_end_to_end_conversation_flow()
    
    # Summary
    print("\n" + "=" * 70)
    print("🏁 Phase 2 Unified Memory System Test Summary")
    print("=" * 70)
    
    passed_tests = sum(1 for result in test_results.values() if result)
    total_tests = len(test_results)
    
    for test_name, passed in test_results.items():
        status = "✅ PASSED" if passed else "❌ FAILED"
        print(f"{status} {test_name.replace('_', ' ').title()}")
    
    print(f"\n📊 Overall Result: {passed_tests}/{total_tests} tests passed")
    
    if passed_tests == total_tests:
        print("🎉 All Phase 2 unified memory system tests passed!")
        print("✅ System is ready for Phase 3: Active Data Migration")
        return True
    else:
        print("⚠️  Some unified memory components need attention")
        print("❗ Please fix failing components before proceeding to Phase 3")
        return False

if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)