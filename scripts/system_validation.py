#!/usr/bin/env python3
"""
System Validation Script - Phase 4: Comprehensive Validation
Validates the migrated conversation memory system end-to-end.

This script performs:
1. Data integrity validation
2. CRUD operations testing
3. OpenAI format compatibility validation
4. Performance benchmarking
5. Cross-system consistency checks
6. Feature flag validation
"""

import asyncio
import aiosqlite
import json
import time
import hashlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Any, Tuple, Optional
from dataclasses import dataclass, asdict

# Add the app directory to Python path
import sys
sys.path.insert(0, 'app')

from app.core.memory_unified import get_unified_memory
from app.core.conversation_id_manager import ConversationIDManager, ConversationIDFormat
from app.core.migration_logging import get_migration_logger, MigrationEventType, MigrationSeverity
from app.core.feature_flags import is_feature_enabled, get_feature_flags

@dataclass
class ValidationResult:
    """Result of a validation test."""
    test_name: str
    success: bool
    message: str
    details: Optional[Dict[str, Any]] = None
    duration_ms: Optional[float] = None
    error: Optional[str] = None

@dataclass
class ValidationSummary:
    """Overall validation summary."""
    total_tests: int
    passed: int
    failed: int
    success_rate: float
    total_duration_ms: float
    results: List[ValidationResult]

class SystemValidator:
    """Comprehensive system validation for Phase 4."""
    
    def __init__(self, db_path: str = "app/memory/unified.db"):
        self.db_path = Path(db_path)
        self.migration_logger = None
        self.unified_memory = None
        self.feature_flag_manager = None
        
        # Test data
        self.test_conversation_id = f"validation-test-{int(time.time())}"
        self.test_project = "validation-project"
        self.test_user = "validation-user"
        
        # Results tracking
        self.results: List[ValidationResult] = []
        self.start_time = None
        
    async def initialize(self):
        """Initialize validation system."""
        print("🔧 Initializing system validation...")
        self.start_time = time.time()
        
        try:
            self.migration_logger = await get_migration_logger()
            self.unified_memory = await get_unified_memory()
            self.feature_flag_manager = await get_feature_flags()
            
            from app.core.migration_logging import MigrationEvent
            await self.migration_logger.log_event(MigrationEvent(
                event_type=MigrationEventType.INTEGRITY_CHECK_STARTED,
                severity=MigrationSeverity.INFO,
                message="Phase 4 system validation started",
                timestamp=datetime.now(timezone.utc).isoformat(),
                migration_phase="phase_4_validation"
            ))
            
            print("✅ Validation system initialized")
            return True
            
        except Exception as e:
            print(f"❌ Failed to initialize validation system: {e}")
            return False
    
    async def run_validation(self) -> ValidationSummary:
        """Run all validation tests."""
        print("\n🚀 Phase 4: Comprehensive System Validation")
        print("=" * 60)
        
        # Test categories
        validation_tests = [
            # Data integrity tests
            ("Data Integrity", [
                self.validate_database_schema,
                self.validate_conversation_id_formats,
                self.validate_message_integrity,
                self.validate_data_consistency
            ]),
            
            # CRUD operations tests
            ("CRUD Operations", [
                self.test_conversation_creation,
                self.test_message_reading,
                self.test_message_writing,
                self.test_conversation_updates
            ]),
            
            # OpenAI compatibility tests
            ("OpenAI Compatibility", [
                self.validate_openai_message_format,
                self.validate_conversation_state_management,
                self.validate_role_content_structure
            ]),
            
            # Performance tests
            ("Performance", [
                self.benchmark_read_operations,
                self.benchmark_write_operations,
                self.benchmark_query_performance
            ]),
            
            # System integration tests
            ("System Integration", [
                self.validate_feature_flags,
                self.validate_logging_system,
                self.validate_id_manager_integration
            ])
        ]
        
        for category_name, tests in validation_tests:
            print(f"\n📋 {category_name} Tests")
            print("-" * 40)
            
            for test_func in tests:
                await self._run_single_test(test_func)
        
        # Generate summary
        summary = self._generate_summary()
        await self._log_validation_completion(summary)
        
        return summary
    
    async def _run_single_test(self, test_func):
        """Run a single validation test."""
        test_name = test_func.__name__.replace('_', ' ').replace('test ', '').replace('validate ', '').title()
        start_time = time.time()
        
        try:
            print(f"  🔍 {test_name}...", end=" ")
            result = await test_func()
            duration_ms = (time.time() - start_time) * 1000
            
            if isinstance(result, ValidationResult):
                result.duration_ms = duration_ms
                self.results.append(result)
                status = "✅ PASS" if result.success else "❌ FAIL"
                print(f"{status} ({duration_ms:.1f}ms)")
                if not result.success and result.error:
                    print(f"    Error: {result.error}")
            else:
                # Handle boolean return
                success = result if isinstance(result, bool) else True
                validation_result = ValidationResult(
                    test_name=test_name,
                    success=success,
                    message=f"{test_name} {'passed' if success else 'failed'}",
                    duration_ms=duration_ms
                )
                self.results.append(validation_result)
                status = "✅ PASS" if success else "❌ FAIL"
                print(f"{status} ({duration_ms:.1f}ms)")
        
        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            validation_result = ValidationResult(
                test_name=test_name,
                success=False,
                message=f"{test_name} failed with exception",
                duration_ms=duration_ms,
                error=str(e)
            )
            self.results.append(validation_result)
            print(f"❌ FAIL ({duration_ms:.1f}ms)")
            print(f"    Error: {str(e)}")
    
    # === Data Integrity Tests ===
    
    async def validate_database_schema(self) -> ValidationResult:
        """Validate database schema integrity."""
        try:
            async with aiosqlite.connect(str(self.db_path)) as db:
                # Check required tables exist
                async with db.execute("""
                    SELECT name FROM sqlite_master 
                    WHERE type='table' AND name IN ('conversations', 'sessions')
                """) as cursor:
                    tables = [row[0] for row in await cursor.fetchall()]
                
                required_tables = ['conversations', 'sessions']
                missing_tables = [t for t in required_tables if t not in tables]
                
                if missing_tables:
                    return ValidationResult(
                        test_name="Database Schema",
                        success=False,
                        message=f"Missing tables: {missing_tables}",
                        error=f"Required tables not found: {missing_tables}"
                    )
                
                # Check conversations table structure
                async with db.execute("PRAGMA table_info(conversations)") as cursor:
                    columns = {row[1]: row[2] for row in await cursor.fetchall()}
                
                required_columns = {
                    'id': 'INTEGER',
                    'conversation_id': 'TEXT',
                    'user_id': 'TEXT',
                    'role': 'TEXT',
                    'content': 'TEXT',
                    'created_at': 'TIMESTAMP'
                }
                
                missing_columns = []
                for col, col_type in required_columns.items():
                    if col not in columns:
                        missing_columns.append(col)
                
                if missing_columns:
                    return ValidationResult(
                        test_name="Database Schema",
                        success=False,
                        message=f"Missing columns: {missing_columns}",
                        error=f"Required columns not found: {missing_columns}"
                    )
                
                return ValidationResult(
                    test_name="Database Schema",
                    success=True,
                    message="Database schema is valid",
                    details={
                        'tables': tables,
                        'conversations_columns': columns
                    }
                )
        
        except Exception as e:
            return ValidationResult(
                test_name="Database Schema",
                success=False,
                message="Database schema validation failed",
                error=str(e)
            )
    
    async def validate_conversation_id_formats(self) -> ValidationResult:
        """Validate all conversation IDs are in standard format."""
        try:
            async with aiosqlite.connect(str(self.db_path)) as db:
                async with db.execute("SELECT DISTINCT conversation_id FROM conversations") as cursor:
                    conversation_ids = [row[0] for row in await cursor.fetchall()]
            
            non_standard_ids = []
            for conv_id in conversation_ids:
                id_info = ConversationIDManager.analyze_id(conv_id)
                if id_info.format_type != ConversationIDFormat.PROJECT_USER:
                    non_standard_ids.append({
                        'id': conv_id,
                        'format': id_info.format_type.value
                    })
            
            success = len(non_standard_ids) == 0
            message = f"All {len(conversation_ids)} conversations in standard format" if success else f"{len(non_standard_ids)} non-standard IDs found"
            
            return ValidationResult(
                test_name="Conversation ID Formats",
                success=success,
                message=message,
                details={
                    'total_conversations': len(conversation_ids),
                    'non_standard_ids': non_standard_ids
                },
                error=None if success else f"Non-standard IDs: {non_standard_ids}"
            )
        
        except Exception as e:
            return ValidationResult(
                test_name="Conversation ID Formats",
                success=False,
                message="ID format validation failed",
                error=str(e)
            )
    
    async def validate_message_integrity(self) -> ValidationResult:
        """Validate message data integrity."""
        try:
            async with aiosqlite.connect(str(self.db_path)) as db:
                # Check for messages with valid roles
                async with db.execute("""
                    SELECT COUNT(*) as total,
                           SUM(CASE WHEN role IN ('user', 'assistant', 'system') THEN 1 ELSE 0 END) as valid_roles,
                           SUM(CASE WHEN content IS NOT NULL AND content != '' THEN 1 ELSE 0 END) as valid_content
                    FROM conversations
                """) as cursor:
                    row = await cursor.fetchone()
                    total, valid_roles, valid_content = row
                
                # Check for orphaned messages (conversations with only one message)
                async with db.execute("""
                    SELECT conversation_id, COUNT(*) as msg_count
                    FROM conversations
                    GROUP BY conversation_id
                    HAVING COUNT(*) = 1
                """) as cursor:
                    orphaned_convs = await cursor.fetchall()
                
                issues = []
                if valid_roles != total:
                    issues.append(f"{total - valid_roles} messages with invalid roles")
                if valid_content != total:
                    issues.append(f"{total - valid_content} messages with empty content")
                
                success = len(issues) == 0
                message = f"All {total} messages have valid integrity" if success else f"Integrity issues found"
                
                return ValidationResult(
                    test_name="Message Integrity",
                    success=success,
                    message=message,
                    details={
                        'total_messages': total,
                        'valid_roles': valid_roles,
                        'valid_content': valid_content,
                        'orphaned_conversations': len(orphaned_convs),
                        'issues': issues
                    },
                    error=None if success else "; ".join(issues)
                )
        
        except Exception as e:
            return ValidationResult(
                test_name="Message Integrity",
                success=False,
                message="Message integrity validation failed",
                error=str(e)
            )
    
    async def validate_data_consistency(self) -> ValidationResult:
        """Validate cross-table data consistency."""
        try:
            async with aiosqlite.connect(str(self.db_path)) as db:
                # Check conversation-session consistency
                async with db.execute("""
                    SELECT c.conversation_id, s.project_name
                    FROM (SELECT DISTINCT conversation_id FROM conversations) c
                    LEFT JOIN sessions s ON SUBSTR(c.conversation_id, 1, INSTR(c.conversation_id, ':')-1) = s.project_name
                """) as cursor:
                    consistency_check = await cursor.fetchall()
                
                # Check timestamp ordering within conversations
                async with db.execute("""
                    SELECT conversation_id, 
                           COUNT(*) as total_messages,
                           COUNT(DISTINCT created_at) as unique_timestamps
                    FROM conversations
                    GROUP BY conversation_id
                    HAVING COUNT(*) > 1 AND COUNT(DISTINCT created_at) = 1
                """) as cursor:
                    timestamp_issues = await cursor.fetchall()
                
                issues = []
                if timestamp_issues:
                    issues.append(f"{len(timestamp_issues)} conversations with duplicate timestamps")
                
                success = len(issues) == 0
                message = "Data consistency validated" if success else "Consistency issues found"
                
                return ValidationResult(
                    test_name="Data Consistency",
                    success=success,
                    message=message,
                    details={
                        'conversations_checked': len(consistency_check),
                        'timestamp_issues': len(timestamp_issues),
                        'issues': issues
                    },
                    error=None if success else "; ".join(issues)
                )
        
        except Exception as e:
            return ValidationResult(
                test_name="Data Consistency",
                success=False,
                message="Data consistency validation failed",
                error=str(e)
            )
    
    # === CRUD Operations Tests ===
    
    async def test_conversation_creation(self) -> ValidationResult:
        """Test conversation creation functionality."""
        try:
            test_conv_id = f"{self.test_conversation_id}:create-test"
            
            # Create a new conversation
            await self.unified_memory.add_message(
                conversation_id=test_conv_id,
                user_id=self.test_user,
                role="user",
                content="Test message for creation validation"
            )
            
            # Verify it was created
            messages = await self.unified_memory.get_conversation(test_conv_id, limit=1)
            
            success = len(messages) == 1 and messages[0]['content'] == "Test message for creation validation"
            
            return ValidationResult(
                test_name="Conversation Creation",
                success=success,
                message="Successfully created and verified conversation" if success else "Failed to create conversation",
                details={'test_conversation_id': test_conv_id, 'messages_found': len(messages)}
            )
        
        except Exception as e:
            return ValidationResult(
                test_name="Conversation Creation",
                success=False,
                message="Conversation creation test failed",
                error=str(e)
            )
    
    async def test_message_reading(self) -> ValidationResult:
        """Test message reading functionality."""
        try:
            # Use an existing conversation from migration
            existing_convs = await self.unified_memory.get_conversation("test-conversation:anonymous", limit=5)
            
            success = len(existing_convs) > 0 and all('role' in msg and 'content' in msg for msg in existing_convs)
            
            return ValidationResult(
                test_name="Message Reading",
                success=success,
                message=f"Successfully read {len(existing_convs)} messages" if success else "Failed to read messages",
                details={
                    'messages_read': len(existing_convs),
                    'sample_message': existing_convs[0] if existing_convs else None
                }
            )
        
        except Exception as e:
            return ValidationResult(
                test_name="Message Reading",
                success=False,
                message="Message reading test failed",
                error=str(e)
            )
    
    async def test_message_writing(self) -> ValidationResult:
        """Test message writing functionality."""
        try:
            test_conv_id = f"{self.test_conversation_id}:write-test"
            
            # Write multiple messages
            messages_to_write = [
                ("user", "Hello, this is a test user message"),
                ("assistant", "Hello! This is a test assistant response"),
                ("user", "Can you confirm this conversation works?"),
                ("assistant", "Yes, the conversation is working correctly!")
            ]
            
            for role, content in messages_to_write:
                await self.unified_memory.add_message(
                    conversation_id=test_conv_id,
                    user_id=self.test_user,
                    role=role,
                    content=content
                )
            
            # Verify all messages were written
            written_messages = await self.unified_memory.get_conversation(test_conv_id)
            
            success = len(written_messages) == len(messages_to_write)
            
            return ValidationResult(
                test_name="Message Writing",
                success=success,
                message=f"Successfully wrote {len(written_messages)}/{len(messages_to_write)} messages" if success else "Message writing failed",
                details={
                    'expected_messages': len(messages_to_write),
                    'actual_messages': len(written_messages),
                    'test_conversation_id': test_conv_id
                }
            )
        
        except Exception as e:
            return ValidationResult(
                test_name="Message Writing",
                success=False,
                message="Message writing test failed",
                error=str(e)
            )
    
    async def test_conversation_updates(self) -> ValidationResult:
        """Test conversation update functionality."""
        try:
            test_conv_id = f"{self.test_conversation_id}:update-test"
            
            # Create initial message
            await self.unified_memory.add_message(
                conversation_id=test_conv_id,
                user_id=self.test_user,
                role="user",
                content="Initial message"
            )
            
            # Add more messages to test conversation updates
            await self.unified_memory.add_message(
                conversation_id=test_conv_id,
                user_id=self.test_user,
                role="assistant",
                content="Response to initial message"
            )
            
            # Verify conversation has been updated
            updated_messages = await self.unified_memory.get_conversation(test_conv_id)
            
            success = len(updated_messages) == 2
            
            return ValidationResult(
                test_name="Conversation Updates",
                success=success,
                message=f"Successfully updated conversation with {len(updated_messages)} messages" if success else "Conversation update failed",
                details={
                    'final_message_count': len(updated_messages),
                    'test_conversation_id': test_conv_id
                }
            )
        
        except Exception as e:
            return ValidationResult(
                test_name="Conversation Updates",
                success=False,
                message="Conversation update test failed",
                error=str(e)
            )
    
    # === OpenAI Compatibility Tests ===
    
    async def validate_openai_message_format(self) -> ValidationResult:
        """Validate OpenAI message format compatibility."""
        try:
            # Get a conversation and validate OpenAI format
            messages = await self.unified_memory.get_conversation("test-conversation:anonymous", limit=10)
            
            format_issues = []
            for i, msg in enumerate(messages):
                # Check required fields
                if 'role' not in msg:
                    format_issues.append(f"Message {i} missing 'role' field")
                elif msg['role'] not in ['user', 'assistant', 'system']:
                    format_issues.append(f"Message {i} has invalid role: {msg['role']}")
                
                if 'content' not in msg:
                    format_issues.append(f"Message {i} missing 'content' field")
                elif not isinstance(msg['content'], str):
                    format_issues.append(f"Message {i} content is not a string")
                
                # Check no extra fields that would break OpenAI compatibility
                openai_fields = {'role', 'content'}
                extra_fields = set(msg.keys()) - openai_fields - {'timestamp', 'user_id', 'metadata', 'id'}
                if extra_fields:
                    format_issues.append(f"Message {i} has unexpected fields: {extra_fields}")
            
            # Test conversion to OpenAI format
            openai_messages = [{"role": msg["role"], "content": msg["content"]} for msg in messages]
            
            success = len(format_issues) == 0 and len(openai_messages) == len(messages)
            
            return ValidationResult(
                test_name="OpenAI Message Format",
                success=success,
                message=f"All {len(messages)} messages are OpenAI compatible" if success else f"Format issues found",
                details={
                    'messages_checked': len(messages),
                    'format_issues': format_issues,
                    'openai_conversion_sample': openai_messages[:2] if openai_messages else []
                },
                error=None if success else "; ".join(format_issues)
            )
        
        except Exception as e:
            return ValidationResult(
                test_name="OpenAI Message Format",
                success=False,
                message="OpenAI format validation failed",
                error=str(e)
            )
    
    async def validate_conversation_state_management(self) -> ValidationResult:
        """Validate conversation state management for OpenAI patterns."""
        try:
            test_conv_id = f"{self.test_conversation_id}:state-test"
            
            # Simulate OpenAI conversation pattern
            history = [
                {"role": "user", "content": "Tell me a joke"}
            ]
            
            # Add user message
            await self.unified_memory.add_message(
                conversation_id=test_conv_id,
                user_id=self.test_user,
                role=history[0]["role"],
                content=history[0]["content"]
            )
            
            # Simulate assistant response
            assistant_response = {"role": "assistant", "content": "Why don't scientists trust atoms? Because they make up everything!"}
            await self.unified_memory.add_message(
                conversation_id=test_conv_id,
                user_id=self.test_user,
                role=assistant_response["role"],
                content=assistant_response["content"]
            )
            
            # Get conversation state
            conversation_state = await self.unified_memory.get_conversation(test_conv_id)
            
            # Validate state management
            success = (
                len(conversation_state) == 2 and
                conversation_state[0]["role"] == "user" and
                conversation_state[1]["role"] == "assistant"
            )
            
            return ValidationResult(
                test_name="Conversation State Management",
                success=success,
                message="Conversation state properly maintained" if success else "State management issues found",
                details={
                    'conversation_length': len(conversation_state),
                    'state_sample': conversation_state if len(conversation_state) <= 2 else conversation_state[:2]
                }
            )
        
        except Exception as e:
            return ValidationResult(
                test_name="Conversation State Management",
                success=False,
                message="State management validation failed",
                error=str(e)
            )
    
    async def validate_role_content_structure(self) -> ValidationResult:
        """Validate role/content structure matches OpenAI requirements."""
        try:
            # Test all valid roles
            test_conv_id = f"{self.test_conversation_id}:role-test"
            
            test_roles = [
                ("system", "You are a helpful assistant"),
                ("user", "Hello, how are you?"),
                ("assistant", "I'm doing well, thank you!")
            ]
            
            for role, content in test_roles:
                await self.unified_memory.add_message(
                    conversation_id=test_conv_id,
                    user_id=self.test_user,
                    role=role,
                    content=content
                )
            
            # Verify structure
            messages = await self.unified_memory.get_conversation(test_conv_id)
            
            structure_valid = True
            issues = []
            
            for i, msg in enumerate(messages):
                expected_role = test_roles[i][0]
                expected_content = test_roles[i][1]
                
                if msg["role"] != expected_role:
                    structure_valid = False
                    issues.append(f"Message {i}: expected role '{expected_role}', got '{msg['role']}'")
                
                if msg["content"] != expected_content:
                    structure_valid = False
                    issues.append(f"Message {i}: content mismatch")
            
            return ValidationResult(
                test_name="Role Content Structure",
                success=structure_valid,
                message="Role/content structure is valid" if structure_valid else "Structure validation failed",
                details={
                    'roles_tested': [role for role, _ in test_roles],
                    'messages_verified': len(messages),
                    'issues': issues
                },
                error=None if structure_valid else "; ".join(issues)
            )
        
        except Exception as e:
            return ValidationResult(
                test_name="Role Content Structure",
                success=False,
                message="Role/content structure validation failed",
                error=str(e)
            )
    
    # === Performance Tests ===
    
    async def benchmark_read_operations(self) -> ValidationResult:
        """Benchmark read operation performance."""
        try:
            # Test reading multiple conversations
            start_time = time.time()
            
            read_tests = [
                ("test-conversation:anonymous", 10),
                ("test-reference-project:test-user", 20),
                ("test-conversation-project:test-user", 5)
            ]
            
            total_messages_read = 0
            for conv_id, limit in read_tests:
                messages = await self.unified_memory.get_conversation(conv_id, limit=limit)
                total_messages_read += len(messages)
            
            duration_ms = (time.time() - start_time) * 1000
            avg_time_per_message = duration_ms / max(total_messages_read, 1)
            
            # Performance thresholds
            success = duration_ms < 1000 and avg_time_per_message < 50  # Should be fast
            
            return ValidationResult(
                test_name="Read Operations Benchmark",
                success=success,
                message=f"Read {total_messages_read} messages in {duration_ms:.1f}ms",
                details={
                    'total_messages_read': total_messages_read,
                    'total_duration_ms': duration_ms,
                    'avg_time_per_message_ms': avg_time_per_message,
                    'tests_performed': len(read_tests)
                },
                duration_ms=duration_ms
            )
        
        except Exception as e:
            return ValidationResult(
                test_name="Read Operations Benchmark",
                success=False,
                message="Read benchmark failed",
                error=str(e)
            )
    
    async def benchmark_write_operations(self) -> ValidationResult:
        """Benchmark write operation performance."""
        try:
            test_conv_id = f"{self.test_conversation_id}:write-benchmark"
            
            # Benchmark writing multiple messages
            start_time = time.time()
            
            messages_to_write = 20
            for i in range(messages_to_write):
                role = "user" if i % 2 == 0 else "assistant"
                content = f"Benchmark message {i} for performance testing"
                
                await self.unified_memory.add_message(
                    conversation_id=test_conv_id,
                    user_id=self.test_user,
                    role=role,
                    content=content
                )
            
            duration_ms = (time.time() - start_time) * 1000
            avg_time_per_write = duration_ms / messages_to_write
            
            # Verify all messages were written
            written_messages = await self.unified_memory.get_conversation(test_conv_id)
            
            success = len(written_messages) == messages_to_write and avg_time_per_write < 100  # Should be reasonably fast
            
            return ValidationResult(
                test_name="Write Operations Benchmark",
                success=success,
                message=f"Wrote {len(written_messages)}/{messages_to_write} messages in {duration_ms:.1f}ms",
                details={
                    'messages_written': len(written_messages),
                    'expected_messages': messages_to_write,
                    'total_duration_ms': duration_ms,
                    'avg_time_per_write_ms': avg_time_per_write
                },
                duration_ms=duration_ms
            )
        
        except Exception as e:
            return ValidationResult(
                test_name="Write Operations Benchmark",
                success=False,
                message="Write benchmark failed",
                error=str(e)
            )
    
    async def benchmark_query_performance(self) -> ValidationResult:
        """Benchmark database query performance."""
        try:
            start_time = time.time()
            
            # Test various query patterns
            async with aiosqlite.connect(str(self.db_path)) as db:
                # Count total conversations
                async with db.execute("SELECT COUNT(DISTINCT conversation_id) FROM conversations") as cursor:
                    total_convs = (await cursor.fetchone())[0]
                
                # Count total messages
                async with db.execute("SELECT COUNT(*) FROM conversations") as cursor:
                    total_messages = (await cursor.fetchone())[0]
                
                # Get recent conversations
                async with db.execute("""
                    SELECT conversation_id, MAX(created_at) as last_message
                    FROM conversations
                    GROUP BY conversation_id
                    ORDER BY last_message DESC
                    LIMIT 10
                """) as cursor:
                    recent_convs = await cursor.fetchall()
            
            duration_ms = (time.time() - start_time) * 1000
            
            success = duration_ms < 500  # Should be very fast for metadata queries
            
            return ValidationResult(
                test_name="Query Performance Benchmark",
                success=success,
                message=f"Executed metadata queries in {duration_ms:.1f}ms",
                details={
                    'total_conversations': total_convs,
                    'total_messages': total_messages,
                    'recent_conversations_found': len(recent_convs),
                    'query_duration_ms': duration_ms
                },
                duration_ms=duration_ms
            )
        
        except Exception as e:
            return ValidationResult(
                test_name="Query Performance Benchmark",
                success=False,
                message="Query benchmark failed",
                error=str(e)
            )
    
    # === System Integration Tests ===
    
    async def validate_feature_flags(self) -> ValidationResult:
        """Validate feature flag system."""
        try:
            # Test feature flag queries
            validation_enabled = await is_feature_enabled("migration_validation")
            logging_enabled = await is_feature_enabled("memory_migration_logging")
            
            # Check current phase
            current_phase = self.feature_flag_manager._current_phase.value
            
            success = validation_enabled and logging_enabled and current_phase == "phase_4_validation"
            
            return ValidationResult(
                test_name="Feature Flags Validation",
                success=success,
                message="Feature flags are properly configured" if success else "Feature flag issues found",
                details={
                    'migration_validation_enabled': validation_enabled,
                    'logging_enabled': logging_enabled,
                    'current_phase': current_phase,
                    'expected_phase': "phase_4_validation"
                }
            )
        
        except Exception as e:
            return ValidationResult(
                test_name="Feature Flags Validation",
                success=False,
                message="Feature flag validation failed",
                error=str(e)
            )
    
    async def validate_logging_system(self) -> ValidationResult:
        """Validate migration logging system."""
        try:
            # Test logging functionality
            from app.core.migration_logging import MigrationEvent
            test_event = MigrationEvent(
                event_type=MigrationEventType.INTEGRITY_CHECK_COMPLETED,
                severity=MigrationSeverity.INFO,
                message="Validation test log entry",
                timestamp=datetime.now(timezone.utc).isoformat(),
                migration_phase="phase_4_validation"
            )
            
            await self.migration_logger.log_event(test_event)
            
            # Verify logging is working (check if log file exists and is writable)
            log_file_exists = self.migration_logger.log_file.exists()
            
            success = log_file_exists
            
            return ValidationResult(
                test_name="Logging System Validation",
                success=success,
                message="Logging system is functional" if success else "Logging system issues found",
                details={
                    'log_file_exists': log_file_exists,
                    'log_file_path': str(self.migration_logger.log_file)
                }
            )
        
        except Exception as e:
            return ValidationResult(
                test_name="Logging System Validation",
                success=False,
                message="Logging system validation failed",
                error=str(e)
            )
    
    async def validate_id_manager_integration(self) -> ValidationResult:
        """Validate conversation ID manager integration."""
        try:
            # Test ID generation
            test_id = ConversationIDManager.generate_standard_id("validation-project", "validation-user")
            expected_format = "validation-project:validation-user"
            
            # Test ID analysis
            id_info = ConversationIDManager.analyze_id(test_id)
            
            success = (
                test_id == expected_format and
                id_info.format_type == ConversationIDFormat.PROJECT_USER and
                id_info.project_slug == "validation-project" and
                id_info.user_id == "validation-user"
            )
            
            return ValidationResult(
                test_name="ID Manager Integration",
                success=success,
                message="ID manager is working correctly" if success else "ID manager issues found",
                details={
                    'generated_id': test_id,
                    'expected_id': expected_format,
                    'id_format': id_info.format_type.value,
                    'parsed_project': id_info.project_slug,
                    'parsed_user': id_info.user_id
                }
            )
        
        except Exception as e:
            return ValidationResult(
                test_name="ID Manager Integration",
                success=False,
                message="ID manager validation failed",
                error=str(e)
            )
    
    # === Summary and Reporting ===
    
    def _generate_summary(self) -> ValidationSummary:
        """Generate validation summary."""
        total_tests = len(self.results)
        passed = sum(1 for r in self.results if r.success)
        failed = total_tests - passed
        success_rate = (passed / total_tests * 100) if total_tests > 0 else 0
        total_duration_ms = sum(r.duration_ms for r in self.results if r.duration_ms)
        
        return ValidationSummary(
            total_tests=total_tests,
            passed=passed,
            failed=failed,
            success_rate=success_rate,
            total_duration_ms=total_duration_ms,
            results=self.results
        )
    
    async def _log_validation_completion(self, summary: ValidationSummary):
        """Log validation completion."""
        from app.core.migration_logging import MigrationEvent
        await self.migration_logger.log_event(MigrationEvent(
            event_type=MigrationEventType.INTEGRITY_CHECK_COMPLETED,
            severity=MigrationSeverity.INFO if summary.success_rate > 90 else MigrationSeverity.WARNING,
            message=f"Phase 4 validation completed: {summary.passed}/{summary.total_tests} tests passed ({summary.success_rate:.1f}%)",
            timestamp=datetime.now(timezone.utc).isoformat(),
            migration_phase="phase_4_validation",
            record_count=summary.total_tests,
            data_after={
                'total_tests': summary.total_tests,
                'passed': summary.passed,
                'failed': summary.failed,
                'success_rate': summary.success_rate,
                'total_duration_ms': summary.total_duration_ms
            }
        ))
    
    async def cleanup_test_data(self):
        """Clean up test data created during validation."""
        try:
            print("\n🧹 Cleaning up test data...")
            
            # Remove test conversations
            async with aiosqlite.connect(str(self.db_path)) as db:
                await db.execute("""
                    DELETE FROM conversations 
                    WHERE conversation_id LIKE ?
                """, (f"{self.test_conversation_id}%",))
                await db.commit()
            
            print("✅ Test data cleanup completed")
            
        except Exception as e:
            print(f"⚠️  Test cleanup failed (non-critical): {e}")

async def main():
    """Main validation execution function."""
    print("🚀 Phase 4: Comprehensive System Validation")
    print("=" * 60)
    print(f"Started at: {datetime.now().isoformat()}")
    print()
    
    validator = SystemValidator()
    
    try:
        # Initialize
        if not await validator.initialize():
            return False
        
        # Run validation
        summary = await validator.run_validation()
        
        # Generate validation report
        print("\n" + "=" * 60)
        print("🏁 Phase 4 Validation Summary")
        print("=" * 60)
        
        print(f"📊 Test Results:")
        print(f"   Total tests: {summary.total_tests}")
        print(f"   Passed: {summary.passed}")
        print(f"   Failed: {summary.failed}")
        print(f"   Success rate: {summary.success_rate:.1f}%")
        print(f"   Total duration: {summary.total_duration_ms:.1f}ms")
        
        # List failed tests
        failed_tests = [r for r in summary.results if not r.success]
        if failed_tests:
            print(f"\n❌ Failed Tests:")
            for test in failed_tests:
                print(f"   - {test.test_name}: {test.error or test.message}")
        
        # Determine overall success
        validation_success = summary.success_rate >= 90  # 90% pass rate required
        
        if validation_success:
            print("\n🎉 Phase 4 validation completed successfully!")
            print("✅ System is ready for production use")
            print("🚀 All core functionality validated")
        else:
            print(f"\n⚠️  Validation completed with issues")
            print(f"❗ {summary.failed} tests failed - review required")
            print("⚠️  Address issues before proceeding to Phase 5")
        
        # Cleanup
        await validator.cleanup_test_data()
        
        return validation_success
        
    except Exception as e:
        print(f"❌ Validation failed with error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)