"""
Data Validation System - Phase 1: Safety Infrastructure
Part of the unified conversation memory architecture migration.

This module provides:
1. Comprehensive data integrity validation
2. Migration data consistency checks
3. Rollback safety validation
4. Real-time data monitoring
"""

import asyncio
import json
import sqlite3
import hashlib
from typing import Dict, Any, List, Optional, Tuple, Set
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
import aiosqlite
import logging

from .feature_flags import is_feature_enabled
from .migration_logging import get_migration_logger, MigrationEventType, MigrationSeverity

logger = logging.getLogger(__name__)

@dataclass
class ValidationResult:
    """Result of a data validation check."""
    check_name: str
    passed: bool
    message: str
    details: Dict[str, Any]
    timestamp: str
    
    # Metrics
    records_checked: int = 0
    duration_ms: float = 0
    
    # Error information
    error_type: Optional[str] = None
    error_details: Optional[str] = None

@dataclass
class ConversationIntegrityCheck:
    """Result of conversation-specific integrity validation."""
    conversation_id: str
    message_count: int
    user_ids: Set[str]
    date_range: Tuple[str, str]  # (first_message, last_message)
    
    # Integrity checks
    has_orphaned_messages: bool = False
    has_duplicate_content: bool = False
    has_missing_timestamps: bool = False
    has_invalid_roles: bool = False
    
    # Migration-specific checks  
    id_format_consistent: bool = True
    consolidation_needed: bool = False
    potential_duplicates: List[str] = None

class DataValidator:
    """
    Comprehensive data validation system for migration safety.
    
    Features:
    - Pre-migration data integrity validation
    - Real-time migration consistency checking
    - Post-migration verification
    - Rollback safety validation
    """
    
    def __init__(self, db_path: str = "app/memory/unified.db"):
        self.db_path = Path(db_path)
        self._lock = asyncio.Lock()
        self._validation_history: List[ValidationResult] = []
    
    async def run_comprehensive_validation(self) -> Dict[str, ValidationResult]:
        """Run all validation checks and return comprehensive results."""
        async with self._lock:
            start_time = datetime.now()
            
            # Check if validation is enabled
            if not await is_feature_enabled("data_integrity_validation"):
                return {
                    "validation_disabled": ValidationResult(
                        check_name="validation_disabled",
                        passed=True,
                        message="Data integrity validation is disabled via feature flag",
                        details={},
                        timestamp=start_time.isoformat()
                    )
                }
            
            logger.info("Starting comprehensive data validation")
            migration_logger = await get_migration_logger()
            
            results = {}
            
            try:
                # 1. Database connectivity and structure validation
                results["database_structure"] = await self._validate_database_structure()
                
                # 2. Conversation data integrity
                results["conversation_integrity"] = await self._validate_conversation_integrity()
                
                # 3. Conversation ID format consistency
                results["conversation_id_formats"] = await self._validate_conversation_id_formats()
                
                # 4. Data completeness and consistency
                results["data_completeness"] = await self._validate_data_completeness()
                
                # 5. Duplicate detection
                results["duplicate_detection"] = await self._detect_duplicates()
                
                # 6. Migration readiness
                results["migration_readiness"] = await self._validate_migration_readiness()
                
                # 7. Performance baseline
                results["performance_baseline"] = await self._establish_performance_baseline()
                
                duration_ms = (datetime.now() - start_time).total_seconds() * 1000
                
                # Log comprehensive results
                passed_checks = sum(1 for result in results.values() if result.passed)
                total_checks = len(results)
                
                await migration_logger.log_event(MigrationEvent(
                    event_type=MigrationEventType.INTEGRITY_CHECK_COMPLETED,
                    severity=MigrationSeverity.INFO if passed_checks == total_checks else MigrationSeverity.WARNING,
                    message=f"Comprehensive validation completed: {passed_checks}/{total_checks} checks passed",
                    timestamp=datetime.now().isoformat(),
                    duration_ms=duration_ms,
                    record_count=sum(r.records_checked for r in results.values()),
                    data_after={
                        "passed_checks": passed_checks,
                        "total_checks": total_checks,
                        "results_summary": {name: {"passed": r.passed, "message": r.message} for name, r in results.items()}
                    }
                ))
                
                logger.info(f"Comprehensive validation completed: {passed_checks}/{total_checks} checks passed in {duration_ms:.2f}ms")
                
            except Exception as e:
                logger.error(f"Comprehensive validation failed: {e}")
                results["validation_error"] = ValidationResult(
                    check_name="validation_error",
                    passed=False,
                    message=f"Validation failed with error: {str(e)}",
                    details={"error": str(e)},
                    timestamp=datetime.now().isoformat(),
                    error_type=type(e).__name__,
                    error_details=str(e)
                )
            
            # Store results for history
            self._validation_history.extend(results.values())
            
            return results
    
    async def _validate_database_structure(self) -> ValidationResult:
        """Validate database exists and has correct structure."""
        start_time = datetime.now()
        
        try:
            if not self.db_path.exists():
                return ValidationResult(
                    check_name="database_structure",
                    passed=False,
                    message="Database file does not exist",
                    details={"db_path": str(self.db_path)},
                    timestamp=start_time.isoformat()
                )
            
            async with aiosqlite.connect(str(self.db_path)) as db:
                # Check required tables exist
                required_tables = ['conversations', 'projects', 'memory_entries', 'sessions']
                existing_tables = []
                
                async with db.execute("SELECT name FROM sqlite_master WHERE type='table'") as cursor:
                    rows = await cursor.fetchall()
                    existing_tables = [row[0] for row in rows]
                
                missing_tables = [table for table in required_tables if table not in existing_tables]
                
                # Check conversations table structure
                conversation_columns = []
                try:
                    async with db.execute("PRAGMA table_info(conversations)") as cursor:
                        rows = await cursor.fetchall()
                        conversation_columns = [row[1] for row in rows]  # Column names
                except sqlite3.OperationalError:
                    pass
                
                required_columns = ['id', 'conversation_id', 'role', 'content', 'timestamp', 'user_id', 'created_at']
                missing_columns = [col for col in required_columns if col not in conversation_columns]
                
                duration_ms = (datetime.now() - start_time).total_seconds() * 1000
                
                if missing_tables or missing_columns:
                    return ValidationResult(
                        check_name="database_structure",
                        passed=False,
                        message="Database structure validation failed",
                        details={
                            "missing_tables": missing_tables,
                            "missing_columns": missing_columns,
                            "existing_tables": existing_tables,
                            "conversation_columns": conversation_columns
                        },
                        timestamp=start_time.isoformat(),
                        duration_ms=duration_ms
                    )
                
                return ValidationResult(
                    check_name="database_structure",
                    passed=True,
                    message="Database structure validation passed",
                    details={
                        "tables_found": existing_tables,
                        "conversation_columns": conversation_columns
                    },
                    timestamp=start_time.isoformat(),
                    duration_ms=duration_ms
                )
                
        except Exception as e:
            logger.error(f"Database structure validation error: {e}")
            return ValidationResult(
                check_name="database_structure",
                passed=False,
                message=f"Database structure validation error: {str(e)}",
                details={"error": str(e)},
                timestamp=start_time.isoformat(),
                error_type=type(e).__name__,
                error_details=str(e)
            )
    
    async def _validate_conversation_integrity(self) -> ValidationResult:
        """Validate conversation data integrity."""
        start_time = datetime.now()
        
        try:
            async with aiosqlite.connect(str(self.db_path)) as db:
                # Get all conversations
                async with db.execute("""
                    SELECT conversation_id, role, content, timestamp, user_id, created_at
                    FROM conversations 
                    ORDER BY conversation_id, created_at
                """) as cursor:
                    rows = await cursor.fetchall()
                
                total_messages = len(rows)
                issues = []
                conversation_stats = {}
                
                for row in rows:
                    conversation_id, role, content, timestamp, user_id, created_at = row
                    
                    # Track conversation stats
                    if conversation_id not in conversation_stats:
                        conversation_stats[conversation_id] = ConversationIntegrityCheck(
                            conversation_id=conversation_id,
                            message_count=0,
                            user_ids=set(),
                            date_range=(created_at, created_at),
                            potential_duplicates=[]
                        )
                    
                    stats = conversation_stats[conversation_id]
                    stats.message_count += 1
                    stats.user_ids.add(user_id)
                    
                    # Update date range
                    if created_at < stats.date_range[0]:
                        stats.date_range = (created_at, stats.date_range[1])
                    if created_at > stats.date_range[1]:
                        stats.date_range = (stats.date_range[0], created_at)
                    
                    # Check for issues
                    if not role or role not in ['user', 'assistant', 'system']:
                        issues.append(f"Invalid role '{role}' in conversation {conversation_id}")
                        stats.has_invalid_roles = True
                    
                    if not content or content.strip() == '':
                        issues.append(f"Empty content in conversation {conversation_id}")
                    
                    if not created_at:
                        issues.append(f"Missing timestamp in conversation {conversation_id}")
                        stats.has_missing_timestamps = True
                    
                    # Check conversation ID format consistency
                    if ':' in conversation_id:
                        # Should be project:user format
                        parts = conversation_id.split(':')
                        if len(parts) != 2 or not parts[0] or not parts[1]:
                            stats.id_format_consistent = False
                    
                # Check for duplicate content within conversations
                for conv_id, stats in conversation_stats.items():
                    async with db.execute("""
                        SELECT role, content, COUNT(*) as count
                        FROM conversations 
                        WHERE conversation_id = ?
                        GROUP BY role, content
                        HAVING COUNT(*) > 1
                    """, (conv_id,)) as cursor:
                        duplicates = await cursor.fetchall()
                        if duplicates:
                            stats.has_duplicate_content = True
                            for role, content, count in duplicates:
                                issues.append(f"Duplicate content in {conv_id}: {role} message appears {count} times")
                
                duration_ms = (datetime.now() - start_time).total_seconds() * 1000
                
                passed = len(issues) == 0
                
                return ValidationResult(
                    check_name="conversation_integrity",
                    passed=passed,
                    message=f"Conversation integrity: {'PASSED' if passed else 'FAILED'} - {len(issues)} issues found",
                    details={
                        "total_messages": total_messages,
                        "total_conversations": len(conversation_stats),
                        "issues": issues,
                        "conversation_summaries": {
                            conv_id: {
                                "message_count": stats.message_count,
                                "user_count": len(stats.user_ids),
                                "has_issues": any([stats.has_invalid_roles, stats.has_duplicate_content, 
                                                 stats.has_missing_timestamps, not stats.id_format_consistent])
                            }
                            for conv_id, stats in conversation_stats.items()
                        }
                    },
                    timestamp=start_time.isoformat(),
                    records_checked=total_messages,
                    duration_ms=duration_ms
                )
                
        except Exception as e:
            logger.error(f"Conversation integrity validation error: {e}")
            return ValidationResult(
                check_name="conversation_integrity",
                passed=False,
                message=f"Conversation integrity validation error: {str(e)}",
                details={"error": str(e)},
                timestamp=start_time.isoformat(),
                error_type=type(e).__name__,
                error_details=str(e)
            )
    
    async def _validate_conversation_id_formats(self) -> ValidationResult:
        """Validate conversation ID format consistency for migration."""
        start_time = datetime.now()
        
        try:
            async with aiosqlite.connect(str(self.db_path)) as db:
                # Get all unique conversation IDs
                async with db.execute("SELECT DISTINCT conversation_id FROM conversations") as cursor:
                    rows = await cursor.fetchall()
                
                conversation_ids = [row[0] for row in rows]
                
                # Analyze ID formats
                format_analysis = {
                    'simple_project': [],      # just project slug
                    'project_user': [],        # project:user format
                    'other': []               # any other format
                }
                
                consolidation_candidates = {}  # project -> list of conversation_ids
                
                for conv_id in conversation_ids:
                    if ':' in conv_id:
                        format_analysis['project_user'].append(conv_id)
                        project_slug = conv_id.split(':')[0]
                    elif conv_id.count('-') >= 1:  # Likely project slug
                        format_analysis['simple_project'].append(conv_id)
                        project_slug = conv_id
                    else:
                        format_analysis['other'].append(conv_id)
                        project_slug = conv_id
                    
                    # Track potential consolidation candidates
                    if project_slug not in consolidation_candidates:
                        consolidation_candidates[project_slug] = []
                    consolidation_candidates[project_slug].append(conv_id)
                
                # Find conversations that need consolidation
                needs_consolidation = {
                    project: conv_ids 
                    for project, conv_ids in consolidation_candidates.items() 
                    if len(conv_ids) > 1
                }
                
                # Check for potential data loss during consolidation
                consolidation_risks = []
                for project, conv_ids in needs_consolidation.items():
                    # Check if conversations have different user sets
                    user_sets = []
                    for conv_id in conv_ids:
                        async with db.execute("SELECT DISTINCT user_id FROM conversations WHERE conversation_id = ?", (conv_id,)) as cursor:
                            user_rows = await cursor.fetchall()
                            user_sets.append(set(row[0] for row in user_rows))
                    
                    # If user sets don't overlap, consolidation might lose user context
                    if len(user_sets) > 1:
                        all_users = set()
                        for user_set in user_sets:
                            all_users.update(user_set)
                        
                        if len(all_users) > 1:
                            consolidation_risks.append({
                                'project': project,
                                'conversation_ids': conv_ids,
                                'user_sets': [list(s) for s in user_sets],
                                'risk': 'Multiple user contexts may be merged'
                            })
                
                duration_ms = (datetime.now() - start_time).total_seconds() * 1000
                
                # Determine if validation passes
                has_format_inconsistencies = len(format_analysis['other']) > 0
                has_consolidation_needs = len(needs_consolidation) > 0
                has_consolidation_risks = len(consolidation_risks) > 0
                
                passed = not (has_format_inconsistencies and has_consolidation_risks)
                
                return ValidationResult(
                    check_name="conversation_id_formats",
                    passed=passed,
                    message=f"Conversation ID format validation: {'PASSED' if passed else 'NEEDS ATTENTION'} - {len(needs_consolidation)} projects need consolidation",
                    details={
                        "format_distribution": {
                            key: len(values) for key, values in format_analysis.items()
                        },
                        "format_examples": format_analysis,
                        "consolidation_needed": needs_consolidation,
                        "consolidation_risks": consolidation_risks,
                        "total_conversations": len(conversation_ids)
                    },
                    timestamp=start_time.isoformat(),
                    records_checked=len(conversation_ids),
                    duration_ms=duration_ms
                )
                
        except Exception as e:
            logger.error(f"Conversation ID format validation error: {e}")
            return ValidationResult(
                check_name="conversation_id_formats",
                passed=False,
                message=f"Conversation ID format validation error: {str(e)}",
                details={"error": str(e)},
                timestamp=start_time.isoformat(),
                error_type=type(e).__name__,
                error_details=str(e)
            )
    
    async def _validate_data_completeness(self) -> ValidationResult:
        """Validate data completeness and consistency."""
        start_time = datetime.now()
        
        try:
            async with aiosqlite.connect(str(self.db_path)) as db:
                completeness_checks = {}
                
                # Check conversation data completeness
                async with db.execute("SELECT COUNT(*) FROM conversations") as cursor:
                    total_messages = (await cursor.fetchone())[0]
                    completeness_checks['total_messages'] = total_messages
                
                # Check for required fields
                async with db.execute("SELECT COUNT(*) FROM conversations WHERE conversation_id IS NULL OR conversation_id = ''") as cursor:
                    missing_conv_id = (await cursor.fetchone())[0]
                    completeness_checks['missing_conversation_id'] = missing_conv_id
                
                async with db.execute("SELECT COUNT(*) FROM conversations WHERE content IS NULL OR content = ''") as cursor:
                    missing_content = (await cursor.fetchone())[0]
                    completeness_checks['missing_content'] = missing_content
                
                async with db.execute("SELECT COUNT(*) FROM conversations WHERE created_at IS NULL") as cursor:
                    missing_created_at = (await cursor.fetchone())[0]
                    completeness_checks['missing_timestamps'] = missing_created_at
                
                # Check project data completeness
                async with db.execute("SELECT COUNT(*) FROM projects") as cursor:
                    total_projects = (await cursor.fetchone())[0]
                    completeness_checks['total_projects'] = total_projects
                
                # Check for orphaned data
                async with db.execute("""
                    SELECT COUNT(DISTINCT conversation_id) 
                    FROM conversations c
                    WHERE NOT EXISTS (
                        SELECT 1 FROM projects p 
                        WHERE p.name = CASE 
                            WHEN c.conversation_id LIKE '%:%' 
                            THEN SUBSTR(c.conversation_id, 1, INSTR(c.conversation_id, ':') - 1)
                            ELSE c.conversation_id
                        END
                    )
                """) as cursor:
                    orphaned_conversations = (await cursor.fetchone())[0]
                    completeness_checks['orphaned_conversations'] = orphaned_conversations
                
                duration_ms = (datetime.now() - start_time).total_seconds() * 1000
                
                # Calculate completeness score
                total_issues = (missing_conv_id + missing_content + missing_created_at + orphaned_conversations)
                completeness_score = max(0, 100 - (total_issues * 10))  # Penalize 10 points per issue type
                
                passed = total_issues == 0
                
                return ValidationResult(
                    check_name="data_completeness",
                    passed=passed,
                    message=f"Data completeness: {completeness_score:.1f}% - {total_issues} data quality issues found",
                    details={
                        "completeness_score": completeness_score,
                        "checks": completeness_checks,
                        "total_issues": total_issues
                    },
                    timestamp=start_time.isoformat(),
                    records_checked=total_messages,
                    duration_ms=duration_ms
                )
                
        except Exception as e:
            logger.error(f"Data completeness validation error: {e}")
            return ValidationResult(
                check_name="data_completeness",
                passed=False,
                message=f"Data completeness validation error: {str(e)}",
                details={"error": str(e)},
                timestamp=start_time.isoformat(),
                error_type=type(e).__name__,
                error_details=str(e)
            )
    
    async def _detect_duplicates(self) -> ValidationResult:
        """Detect potential duplicate messages and conversations."""
        start_time = datetime.now()
        
        try:
            async with aiosqlite.connect(str(self.db_path)) as db:
                duplicate_analysis = {}
                
                # Find exact duplicate messages (same content, role, conversation)
                async with db.execute("""
                    SELECT conversation_id, role, content, COUNT(*) as count
                    FROM conversations
                    GROUP BY conversation_id, role, content
                    HAVING COUNT(*) > 1
                    ORDER BY count DESC
                """) as cursor:
                    exact_duplicates = await cursor.fetchall()
                
                duplicate_analysis['exact_duplicates'] = len(exact_duplicates)
                duplicate_analysis['exact_duplicate_examples'] = exact_duplicates[:5]  # First 5 examples
                
                # Find near-duplicate messages (similar content length and role)
                async with db.execute("""
                    SELECT conversation_id, role, LENGTH(content) as content_length, COUNT(*) as count
                    FROM conversations
                    GROUP BY conversation_id, role, LENGTH(content)
                    HAVING COUNT(*) > 1 AND LENGTH(content) > 50
                    ORDER BY count DESC
                """) as cursor:
                    near_duplicates = await cursor.fetchall()
                
                duplicate_analysis['near_duplicates'] = len(near_duplicates)
                duplicate_analysis['near_duplicate_examples'] = near_duplicates[:5]
                
                # Find conversations with suspicious similarity
                async with db.execute("""
                    SELECT 
                        conversation_id,
                        COUNT(*) as message_count,
                        COUNT(DISTINCT role) as role_types,
                        MAX(LENGTH(content)) as max_content_length,
                        MIN(LENGTH(content)) as min_content_length
                    FROM conversations
                    GROUP BY conversation_id
                    HAVING COUNT(*) > 1
                """) as cursor:
                    conversation_profiles = await cursor.fetchall()
                
                # Look for conversations with identical profiles (suspicious)
                profile_groups = {}
                for conv_id, msg_count, role_types, max_len, min_len in conversation_profiles:
                    profile_key = (msg_count, role_types, max_len, min_len)
                    if profile_key not in profile_groups:
                        profile_groups[profile_key] = []
                    profile_groups[profile_key].append(conv_id)
                
                suspicious_groups = {k: v for k, v in profile_groups.items() if len(v) > 1}
                duplicate_analysis['suspicious_conversation_groups'] = len(suspicious_groups)
                duplicate_analysis['suspicious_examples'] = dict(list(suspicious_groups.items())[:3])
                
                duration_ms = (datetime.now() - start_time).total_seconds() * 1000
                
                total_duplicate_issues = (duplicate_analysis['exact_duplicates'] + 
                                        duplicate_analysis['near_duplicates'] + 
                                        duplicate_analysis['suspicious_conversation_groups'])
                
                passed = total_duplicate_issues < 5  # Allow some minor duplicates
                
                return ValidationResult(
                    check_name="duplicate_detection",
                    passed=passed,
                    message=f"Duplicate detection: {'PASSED' if passed else 'ATTENTION NEEDED'} - {total_duplicate_issues} potential duplicate issues found",
                    details=duplicate_analysis,
                    timestamp=start_time.isoformat(),
                    records_checked=len(conversation_profiles),
                    duration_ms=duration_ms
                )
                
        except Exception as e:
            logger.error(f"Duplicate detection error: {e}")
            return ValidationResult(
                check_name="duplicate_detection",
                passed=False,
                message=f"Duplicate detection error: {str(e)}",
                details={"error": str(e)},
                timestamp=start_time.isoformat(),
                error_type=type(e).__name__,
                error_details=str(e)
            )
    
    async def _validate_migration_readiness(self) -> ValidationResult:
        """Validate system readiness for migration."""
        start_time = datetime.now()
        
        try:
            readiness_checks = {}
            
            # Check database file permissions and accessibility
            readiness_checks['db_readable'] = self.db_path.exists() and self.db_path.is_file()
            readiness_checks['db_writable'] = os.access(self.db_path, os.W_OK) if self.db_path.exists() else False
            
            # Check backup directory exists and is writable
            backup_dir = Path("migration_backups")
            readiness_checks['backup_dir_exists'] = backup_dir.exists()
            readiness_checks['backup_dir_writable'] = backup_dir.exists() and os.access(backup_dir, os.W_OK)
            
            # Check log directory exists and is writable
            log_dir = Path("logs/migration")
            readiness_checks['log_dir_accessible'] = log_dir.exists() and os.access(log_dir, os.W_OK)
            
            # Check required modules are available
            try:
                from .conversation_id_manager import ConversationIDManager
                readiness_checks['id_manager_available'] = True
            except ImportError:
                readiness_checks['id_manager_available'] = False
            
            try:
                from .feature_flags import get_feature_flags
                readiness_checks['feature_flags_available'] = True
            except ImportError:
                readiness_checks['feature_flags_available'] = False
            
            # Check database connectivity
            try:
                async with aiosqlite.connect(str(self.db_path)) as db:
                    await db.execute("SELECT 1")
                    readiness_checks['db_connectivity'] = True
            except Exception:
                readiness_checks['db_connectivity'] = False
            
            # Check data volume (ensure not too large for safe migration)
            async with aiosqlite.connect(str(self.db_path)) as db:
                async with db.execute("SELECT COUNT(*) FROM conversations") as cursor:
                    message_count = (await cursor.fetchone())[0]
                    readiness_checks['message_count'] = message_count
                    readiness_checks['data_volume_manageable'] = message_count < 100000  # Arbitrary safe limit
            
            duration_ms = (datetime.now() - start_time).total_seconds() * 1000
            
            # Calculate overall readiness score
            critical_checks = ['db_readable', 'db_writable', 'db_connectivity', 'id_manager_available']
            critical_passed = sum(1 for check in critical_checks if readiness_checks.get(check, False))
            
            all_passed = all(readiness_checks.values())
            critical_all_passed = critical_passed == len(critical_checks)
            
            passed = critical_all_passed and readiness_checks.get('data_volume_manageable', False)
            
            return ValidationResult(
                check_name="migration_readiness",
                passed=passed,
                message=f"Migration readiness: {'READY' if passed else 'NOT READY'} - {critical_passed}/{len(critical_checks)} critical checks passed",
                details={
                    "readiness_checks": readiness_checks,
                    "critical_checks_passed": f"{critical_passed}/{len(critical_checks)}",
                    "all_checks_passed": all_passed
                },
                timestamp=start_time.isoformat(),
                records_checked=1,
                duration_ms=duration_ms
            )
            
        except Exception as e:
            logger.error(f"Migration readiness validation error: {e}")
            return ValidationResult(
                check_name="migration_readiness",
                passed=False,
                message=f"Migration readiness validation error: {str(e)}",
                details={"error": str(e)},
                timestamp=start_time.isoformat(),
                error_type=type(e).__name__,
                error_details=str(e)
            )
    
    async def _establish_performance_baseline(self) -> ValidationResult:
        """Establish performance baseline for migration monitoring."""
        start_time = datetime.now()
        
        try:
            performance_metrics = {}
            
            # Time basic database operations
            async with aiosqlite.connect(str(self.db_path)) as db:
                # Time conversation read operation
                read_start = datetime.now()
                async with db.execute("SELECT * FROM conversations LIMIT 100") as cursor:
                    await cursor.fetchall()
                read_duration = (datetime.now() - read_start).total_seconds() * 1000
                performance_metrics['read_100_messages_ms'] = read_duration
                
                # Time conversation count operation
                count_start = datetime.now()
                async with db.execute("SELECT COUNT(*) FROM conversations") as cursor:
                    total_count = (await cursor.fetchone())[0]
                count_duration = (datetime.now() - count_start).total_seconds() * 1000
                performance_metrics['count_all_messages_ms'] = count_duration
                performance_metrics['total_message_count'] = total_count
                
                # Time conversation ID query
                id_query_start = datetime.now()
                async with db.execute("SELECT DISTINCT conversation_id FROM conversations") as cursor:
                    conv_ids = await cursor.fetchall()
                id_query_duration = (datetime.now() - id_query_start).total_seconds() * 1000
                performance_metrics['distinct_conversation_ids_ms'] = id_query_duration
                performance_metrics['unique_conversation_count'] = len(conv_ids)
            
            # Calculate throughput metrics
            if performance_metrics['read_100_messages_ms'] > 0:
                performance_metrics['read_throughput_msg_per_sec'] = 100000 / performance_metrics['read_100_messages_ms']
            
            # Database file size
            performance_metrics['db_file_size_mb'] = self.db_path.stat().st_size / (1024 * 1024)
            
            duration_ms = (datetime.now() - start_time).total_seconds() * 1000
            
            # Performance is acceptable if basic operations complete reasonably quickly
            acceptable_read_time = 1000  # 1 second for 100 messages
            acceptable_count_time = 5000  # 5 seconds for count operation
            
            passed = (performance_metrics['read_100_messages_ms'] < acceptable_read_time and
                     performance_metrics['count_all_messages_ms'] < acceptable_count_time)
            
            return ValidationResult(
                check_name="performance_baseline",
                passed=passed,
                message=f"Performance baseline established: {'ACCEPTABLE' if passed else 'SLOW'} - {performance_metrics['read_100_messages_ms']:.1f}ms/100msg",
                details=performance_metrics,
                timestamp=start_time.isoformat(),
                records_checked=total_count,
                duration_ms=duration_ms
            )
            
        except Exception as e:
            logger.error(f"Performance baseline establishment error: {e}")
            return ValidationResult(
                check_name="performance_baseline",
                passed=False,
                message=f"Performance baseline error: {str(e)}",
                details={"error": str(e)},
                timestamp=start_time.isoformat(),
                error_type=type(e).__name__,
                error_details=str(e)
            )


# === Global Instance Management ===

_data_validator: Optional[DataValidator] = None
_validator_lock = asyncio.Lock()

async def get_data_validator() -> DataValidator:
    """Get singleton instance of data validator."""
    global _data_validator
    
    async with _validator_lock:
        if _data_validator is None:
            _data_validator = DataValidator()
        return _data_validator

async def run_validation() -> Dict[str, ValidationResult]:
    """Convenience function to run comprehensive validation."""
    validator = await get_data_validator()
    return await validator.run_comprehensive_validation()

# Import required modules
import os
from .migration_logging import MigrationEvent