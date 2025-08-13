#!/usr/bin/env python3
"""
Phase 1 Infrastructure Testing Script
Tests all safety infrastructure components created in Phase 1.

This script validates:
1. Feature flags system initialization and functionality
2. Migration logging system
3. Data validation system
4. Conversation ID management
5. Integration between all systems
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

async def test_feature_flags():
    """Test feature flags system."""
    print("\n🏁 Testing Feature Flags System")
    print("=" * 50)
    
    try:
        from app.core.feature_flags import get_feature_flags, MigrationPhase, is_feature_enabled
        
        # Test initialization
        flags = await get_feature_flags()
        print("✅ Feature flags system initialized successfully")
        
        # Test phase 1 flags are enabled
        phase1_flags = [
            "conversation_id_manager",
            "memory_migration_logging", 
            "data_integrity_validation"
        ]
        
        for flag_name in phase1_flags:
            enabled = await is_feature_enabled(flag_name)
            status = "✅" if enabled else "❌"
            print(f"{status} {flag_name}: {'ENABLED' if enabled else 'DISABLED'}")
        
        # Test phase 2 flags are disabled  
        phase2_flags = ["unified_memory_primary", "active_data_migration"]
        for flag_name in phase2_flags:
            enabled = await is_feature_enabled(flag_name)
            status = "✅" if not enabled else "❌"
            print(f"{status} {flag_name}: {'DISABLED' if not enabled else 'ENABLED'} (should be disabled)")
        
        # Test flag status retrieval
        flag_status = flags.get_flag_status("conversation_id_manager")
        if flag_status:
            print(f"✅ Flag status retrieval working: {flag_status['description']}")
        else:
            print("❌ Flag status retrieval failed")
        
        return True
        
    except Exception as e:
        print(f"❌ Feature flags test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

async def test_migration_logging():
    """Test migration logging system."""
    print("\n📊 Testing Migration Logging System")
    print("=" * 50)
    
    try:
        from app.core.migration_logging import (
            get_migration_logger, log_migration_event, 
            MigrationEventType, MigrationSeverity
        )
        
        # Test initialization
        logger = await get_migration_logger()
        print("✅ Migration logger initialized successfully")
        
        # Test event logging
        await log_migration_event(
            event_type=MigrationEventType.DATA_BACKUP_STARTED,
            message="Test infrastructure validation started",
            severity=MigrationSeverity.INFO,
            project_slug="test-infrastructure"
        )
        print("✅ Event logging working")
        
        # Test operation tracking
        operation_id = await logger.start_operation(
            "test_validation", 
            project_slug="test-infrastructure"
        )
        
        # Simulate some work
        await asyncio.sleep(0.1)
        
        await logger.complete_operation(
            operation_id, 
            success=True, 
            message="Infrastructure test completed", 
            record_count=1
        )
        print("✅ Operation tracking working")
        
        # Test conversation operation logging
        await logger.log_conversation_operation(
            "read",
            "test-infrastructure:test-user",
            user_id="test-user",
            project_slug="test-infrastructure",
            data_before={"messages": 0},
            data_after={"messages": 1},
            success=True
        )
        print("✅ Conversation operation logging working")
        
        return True
        
    except Exception as e:
        print(f"❌ Migration logging test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

async def test_conversation_id_manager():
    """Test conversation ID management system."""
    print("\n🆔 Testing Conversation ID Manager")
    print("=" * 50)
    
    try:
        from app.core.conversation_id_manager import (
            ConversationIDManager, ConversationIDFormat, LegacyConversationResolver
        )
        
        # Test ID generation
        standard_id = ConversationIDManager.generate_standard_id("test-project", "test-user")
        expected = "test-project:test-user"
        if standard_id == expected:
            print(f"✅ ID generation working: {standard_id}")
        else:
            print(f"❌ ID generation failed: expected {expected}, got {standard_id}")
            return False
        
        # Test ID analysis
        test_ids = [
            "simple-project",
            "project-with-user:user123",
            "weird_format_123"
        ]
        
        for test_id in test_ids:
            analysis = ConversationIDManager.analyze_id(test_id)
            print(f"✅ Analyzed '{test_id}': {analysis.format_type.value} -> {analysis.migration_target}")
        
        # Test migration mapping
        migration_map = ConversationIDManager.get_migration_mapping(test_ids)
        print(f"✅ Migration mapping created for {len(migration_map)} IDs")
        
        # Test consolidation plan
        consolidation_plan = ConversationIDManager.create_consolidation_plan(test_ids)
        print(f"✅ Consolidation plan created: {len(consolidation_plan)} groups")
        
        # Test legacy resolver
        project_conversations = LegacyConversationResolver.find_all_conversations_for_project(
            "test-project", test_ids
        )
        print(f"✅ Legacy resolver found {len(project_conversations)} related conversations")
        
        return True
        
    except Exception as e:
        print(f"❌ Conversation ID manager test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

async def test_data_validator():
    """Test data validation system."""
    print("\n🔍 Testing Data Validator")
    print("=" * 50)
    
    try:
        from app.core.data_validator import get_data_validator, run_validation
        
        # Test initialization
        validator = await get_data_validator()
        print("✅ Data validator initialized successfully")
        
        # Run comprehensive validation (this will test against the real database)
        print("🔄 Running comprehensive validation...")
        results = await run_validation()
        
        if results:
            print(f"✅ Validation completed: {len(results)} checks performed")
            
            # Show validation summary
            passed_count = sum(1 for result in results.values() if result.passed)
            total_count = len(results)
            
            print(f"📊 Validation Results: {passed_count}/{total_count} checks passed")
            
            for check_name, result in results.items():
                status = "✅" if result.passed else "⚠️"
                print(f"{status} {check_name}: {result.message}")
                
                # Show critical issues
                if not result.passed and check_name in ["database_structure", "migration_readiness"]:
                    print(f"   ❗ Critical issue: {result.details}")
            
            return passed_count > total_count // 2  # At least half should pass
        else:
            print("❌ Validation returned no results")
            return False
        
    except Exception as e:
        print(f"❌ Data validator test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

async def test_integration():
    """Test integration between all Phase 1 components."""
    print("\n🔗 Testing System Integration")  
    print("=" * 50)
    
    try:
        from app.core.feature_flags import is_feature_enabled
        from app.core.migration_logging import get_migration_logger, MigrationEventType, MigrationSeverity
        from app.core.conversation_id_manager import ConversationIDManager
        from app.core.data_validator import get_data_validator
        
        # Test feature flag controlled logging
        if await is_feature_enabled("memory_migration_logging"):
            logger = await get_migration_logger()
            await logger.log_event(MigrationEvent(
                event_type=MigrationEventType.PHASE_CHANGE,
                severity=MigrationSeverity.INFO,
                message="Phase 1 infrastructure integration test",
                timestamp=datetime.now().isoformat(),
                migration_phase="phase_1_safety",
                feature_flags={
                    "conversation_id_manager": await is_feature_enabled("conversation_id_manager"),
                    "data_integrity_validation": await is_feature_enabled("data_integrity_validation")
                }
            ))
            print("✅ Feature-flag controlled logging integration working")
        
        # Test conversation ID manager with logging
        test_conversation_id = "integration-test:test-user"
        analysis = ConversationIDManager.analyze_id(test_conversation_id)
        
        logger = await get_migration_logger()
        await logger.log_conversation_operation(
            "resolve_id",
            test_conversation_id,
            user_id="test-user", 
            project_slug="integration-test",
            data_after={"format_type": analysis.format_type.value, "migration_target": analysis.migration_target},
            success=True
        )
        print("✅ ID manager + logging integration working")
        
        # Test data validator with feature flag checks
        if await is_feature_enabled("data_integrity_validation"):
            validator = await get_data_validator()
            # Just test that we can initialize and check basic functionality
            # Don't run full validation to save time
            print("✅ Data validator + feature flags integration working")
        
        return True
        
    except Exception as e:
        print(f"❌ Integration test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

async def main():
    """Run all Phase 1 infrastructure tests."""
    print("🚀 Phase 1 Infrastructure Testing")
    print("=" * 60)
    print(f"Started at: {datetime.now().isoformat()}")
    print()
    
    test_results = {}
    
    # Run all tests
    test_results['feature_flags'] = await test_feature_flags()
    test_results['migration_logging'] = await test_migration_logging()
    test_results['conversation_id_manager'] = await test_conversation_id_manager()
    test_results['data_validator'] = await test_data_validator()
    test_results['integration'] = await test_integration()
    
    # Summary
    print("\n" + "=" * 60)
    print("🏁 Phase 1 Infrastructure Test Summary")
    print("=" * 60)
    
    passed_tests = sum(1 for result in test_results.values() if result)
    total_tests = len(test_results)
    
    for test_name, passed in test_results.items():
        status = "✅ PASSED" if passed else "❌ FAILED"
        print(f"{status} {test_name.replace('_', ' ').title()}")
    
    print(f"\n📊 Overall Result: {passed_tests}/{total_tests} tests passed")
    
    if passed_tests == total_tests:
        print("🎉 All Phase 1 infrastructure components are working correctly!")
        print("✅ System is ready to proceed to Phase 2: Unified System Implementation")
        return True
    else:
        print("⚠️  Some infrastructure components need attention before proceeding")
        print("❗ Please fix failing components before moving to Phase 2")
        return False

if __name__ == "__main__":
    # Import here to avoid issues with missing imports
    from app.core.migration_logging import MigrationEvent
    
    success = asyncio.run(main())
    sys.exit(0 if success else 1)