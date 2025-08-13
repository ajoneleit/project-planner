"""
Migration Logging System - Phase 1: Safety Infrastructure
Part of the unified conversation memory architecture migration.

This module provides:
1. Structured migration event logging
2. Data integrity tracking
3. Performance monitoring
4. Rollback preparation data
"""

import asyncio
import json
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime, timezone
from pathlib import Path
from dataclasses import dataclass, asdict
from enum import Enum
import traceback

# Configure migration-specific logger
logger = logging.getLogger(__name__)

class MigrationEventType(Enum):
    """Types of migration events to track."""
    # Data operations
    DATA_BACKUP_STARTED = "data_backup_started"
    DATA_BACKUP_COMPLETED = "data_backup_completed"
    DATA_MIGRATION_STARTED = "data_migration_started"
    DATA_MIGRATION_COMPLETED = "data_migration_completed"
    
    # Conversation operations
    CONVERSATION_READ = "conversation_read"
    CONVERSATION_WRITE = "conversation_write"
    CONVERSATION_ID_RESOLVED = "conversation_id_resolved"
    CONVERSATION_CONSOLIDATED = "conversation_consolidated"
    
    # System events
    PHASE_CHANGE = "phase_change"
    FEATURE_FLAG_CHANGE = "feature_flag_change"
    ROLLBACK_STARTED = "rollback_started"
    ROLLBACK_COMPLETED = "rollback_completed"
    
    # Validation events
    INTEGRITY_CHECK_STARTED = "integrity_check_started"
    INTEGRITY_CHECK_COMPLETED = "integrity_check_completed"
    VALIDATION_ERROR = "validation_error"
    
    # Performance events
    PERFORMANCE_BENCHMARK = "performance_benchmark"
    MEMORY_USAGE = "memory_usage"
    
    # Error events
    MIGRATION_ERROR = "migration_error"
    SYSTEM_ERROR = "system_error"

class MigrationSeverity(Enum):
    """Severity levels for migration events."""
    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"

@dataclass
class MigrationEvent:
    """Structured migration event data."""
    event_type: MigrationEventType
    severity: MigrationSeverity
    message: str
    timestamp: str
    
    # Context information
    project_slug: Optional[str] = None
    user_id: Optional[str] = None
    conversation_id: Optional[str] = None
    
    # Migration-specific data
    migration_phase: Optional[str] = None
    feature_flags: Optional[Dict[str, bool]] = None
    
    # Performance metrics
    duration_ms: Optional[float] = None
    memory_usage_mb: Optional[float] = None
    record_count: Optional[int] = None
    
    # Error information
    error_type: Optional[str] = None
    error_details: Optional[str] = None
    stack_trace: Optional[str] = None
    
    # Data integrity
    data_before: Optional[Dict[str, Any]] = None
    data_after: Optional[Dict[str, Any]] = None
    checksum_before: Optional[str] = None
    checksum_after: Optional[str] = None
    
    # Metadata
    component: str = "memory_migration"
    session_id: Optional[str] = None
    request_id: Optional[str] = None

class MigrationLogger:
    """
    Specialized logger for tracking migration events and data integrity.
    
    Features:
    - Structured event logging with rich context
    - Automatic data integrity tracking
    - Performance monitoring
    - Rollback preparation data collection
    """
    
    def __init__(self, log_dir: str = "logs/migration"):
        self.log_dir = Path(log_dir)
        self.log_file = self.log_dir / f"migration_{datetime.now().strftime('%Y%m%d')}.jsonl"
        self._lock = asyncio.Lock()
        self._session_id = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        # Performance tracking
        self._operation_start_times: Dict[str, datetime] = {}
        
        # Data integrity checksums using SHA256 for verification
        
        self._ensure_log_directory()
    
    def _ensure_log_directory(self):
        """Ensure log directory exists."""
        try:
            self.log_dir.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            logger.error(f"Failed to create log directory {self.log_dir}: {e}")
    
    async def log_event(self, event: MigrationEvent):
        """Log a migration event to structured log file."""
        async with self._lock:
            try:
                # Add session ID if not present
                if not event.session_id:
                    event.session_id = self._session_id
                
                # Convert to JSON
                event_dict = asdict(event)
                # Convert enums to strings
                event_dict['event_type'] = event.event_type.value
                event_dict['severity'] = event.severity.value
                
                # Write to JSONL file
                with open(self.log_file, 'a') as f:
                    f.write(json.dumps(event_dict, default=str) + '\n')
                
                # Also log to standard logger based on severity
                log_level = {
                    MigrationSeverity.DEBUG: logging.DEBUG,
                    MigrationSeverity.INFO: logging.INFO,
                    MigrationSeverity.WARNING: logging.WARNING,
                    MigrationSeverity.ERROR: logging.ERROR,
                    MigrationSeverity.CRITICAL: logging.CRITICAL
                }[event.severity]
                
                logger.log(log_level, f"[{event.event_type.value}] {event.message}")
                
            except Exception as e:
                logger.error(f"Failed to log migration event: {e}")
    
    async def start_operation(self, operation_name: str, 
                            project_slug: Optional[str] = None,
                            user_id: Optional[str] = None,
                            conversation_id: Optional[str] = None) -> str:
        """Start tracking an operation and return operation ID."""
        operation_id = f"{operation_name}_{datetime.now().strftime('%H%M%S_%f')}"
        self._operation_start_times[operation_id] = datetime.now(timezone.utc)
        
        await self.log_event(MigrationEvent(
            event_type=MigrationEventType.DATA_MIGRATION_STARTED,
            severity=MigrationSeverity.INFO,
            message=f"Started operation: {operation_name}",
            timestamp=datetime.now(timezone.utc).isoformat(),
            project_slug=project_slug,
            user_id=user_id,
            conversation_id=conversation_id,
            session_id=self._session_id,
            request_id=operation_id
        ))
        
        return operation_id
    
    async def complete_operation(self, operation_id: str, 
                               success: bool = True,
                               message: Optional[str] = None,
                               record_count: Optional[int] = None,
                               error: Optional[Exception] = None):
        """Complete operation tracking with duration and status."""
        start_time = self._operation_start_times.get(operation_id)
        duration_ms = None
        
        if start_time:
            duration_ms = (datetime.now(timezone.utc) - start_time).total_seconds() * 1000
            del self._operation_start_times[operation_id]
        
        event_type = MigrationEventType.DATA_MIGRATION_COMPLETED if success else MigrationEventType.MIGRATION_ERROR
        severity = MigrationSeverity.INFO if success else MigrationSeverity.ERROR
        
        event_message = message or f"{'Completed' if success else 'Failed'} operation: {operation_id}"
        
        event = MigrationEvent(
            event_type=event_type,
            severity=severity,
            message=event_message,
            timestamp=datetime.now(timezone.utc).isoformat(),
            duration_ms=duration_ms,
            record_count=record_count,
            session_id=self._session_id,
            request_id=operation_id
        )
        
        if error:
            event.error_type = type(error).__name__
            event.error_details = str(error)
            event.stack_trace = traceback.format_exc()
        
        await self.log_event(event)
    
    async def log_conversation_operation(self, operation_type: str,
                                       conversation_id: str,
                                       user_id: str = "anonymous",
                                       project_slug: Optional[str] = None,
                                       data_before: Optional[Dict] = None,
                                       data_after: Optional[Dict] = None,
                                       success: bool = True,
                                       error: Optional[Exception] = None):
        """Log conversation-specific operations with data integrity tracking."""
        
        event_type_map = {
            'read': MigrationEventType.CONVERSATION_READ,
            'write': MigrationEventType.CONVERSATION_WRITE,
            'resolve_id': MigrationEventType.CONVERSATION_ID_RESOLVED,
            'consolidate': MigrationEventType.CONVERSATION_CONSOLIDATED
        }
        
        event_type = event_type_map.get(operation_type, MigrationEventType.CONVERSATION_WRITE)
        severity = MigrationSeverity.INFO if success else MigrationSeverity.ERROR
        
        # Calculate data checksums for integrity tracking
        checksum_before = None
        checksum_after = None
        
        if data_before:
            checksum_before = self._calculate_checksum(data_before)
        if data_after:
            checksum_after = self._calculate_checksum(data_after)
        
        event = MigrationEvent(
            event_type=event_type,
            severity=severity,
            message=f"Conversation {operation_type}: {conversation_id}",
            timestamp=datetime.now(timezone.utc).isoformat(),
            project_slug=project_slug,
            user_id=user_id,
            conversation_id=conversation_id,
            data_before=data_before,
            data_after=data_after,
            checksum_before=checksum_before,
            checksum_after=checksum_after,
            session_id=self._session_id
        )
        
        if error:
            event.error_type = type(error).__name__
            event.error_details = str(error)
            event.stack_trace = traceback.format_exc()
        
        await self.log_event(event)
    
    async def log_data_integrity_check(self, check_name: str,
                                     conversation_id: Optional[str] = None,
                                     expected_count: Optional[int] = None,
                                     actual_count: Optional[int] = None,
                                     integrity_valid: bool = True,
                                     details: Optional[Dict] = None):
        """Log data integrity validation results."""
        
        severity = MigrationSeverity.INFO if integrity_valid else MigrationSeverity.ERROR
        message = f"Data integrity check '{check_name}': {'PASSED' if integrity_valid else 'FAILED'}"
        
        if expected_count is not None and actual_count is not None:
            message += f" (expected: {expected_count}, actual: {actual_count})"
        
        event = MigrationEvent(
            event_type=MigrationEventType.INTEGRITY_CHECK_COMPLETED,
            severity=severity,
            message=message,
            timestamp=datetime.now(timezone.utc).isoformat(),
            conversation_id=conversation_id,
            record_count=actual_count,
            data_after=details,
            session_id=self._session_id
        )
        
        await self.log_event(event)
    
    async def log_performance_metrics(self, operation: str,
                                    duration_ms: float,
                                    record_count: Optional[int] = None,
                                    memory_usage_mb: Optional[float] = None,
                                    details: Optional[Dict] = None):
        """Log performance metrics for migration operations."""
        
        message = f"Performance metrics for {operation}: {duration_ms:.2f}ms"
        if record_count:
            message += f", {record_count} records"
        if memory_usage_mb:
            message += f", {memory_usage_mb:.2f}MB memory"
        
        await self.log_event(MigrationEvent(
            event_type=MigrationEventType.PERFORMANCE_BENCHMARK,
            severity=MigrationSeverity.INFO,
            message=message,
            timestamp=datetime.now(timezone.utc).isoformat(),
            duration_ms=duration_ms,
            record_count=record_count,
            memory_usage_mb=memory_usage_mb,
            data_after=details,
            session_id=self._session_id
        ))
    
    async def log_phase_change(self, from_phase: str, to_phase: str,
                             feature_flags: Optional[Dict[str, bool]] = None):
        """Log migration phase changes."""
        
        await self.log_event(MigrationEvent(
            event_type=MigrationEventType.PHASE_CHANGE,
            severity=MigrationSeverity.INFO,
            message=f"Migration phase changed from {from_phase} to {to_phase}",
            timestamp=datetime.now(timezone.utc).isoformat(),
            migration_phase=to_phase,
            feature_flags=feature_flags,
            session_id=self._session_id
        ))
    
    def _calculate_checksum(self, data: Dict[str, Any]) -> str:
        """Calculate a SHA256 checksum for data integrity tracking."""
        try:
            import hashlib
            # Sort keys to ensure consistent checksum
            sorted_json = json.dumps(data, sort_keys=True)
            return hashlib.sha256(sorted_json.encode()).hexdigest()
        except Exception as e:
            logger.warning(f"Failed to calculate checksum: {e}")
            return "checksum_error"
    
    async def get_migration_summary(self, hours: int = 24) -> Dict[str, Any]:
        """Get migration activity summary for the last N hours."""
        try:
            cutoff_time = datetime.now(timezone.utc) - timedelta(hours=hours)
            
            # Read recent events from log file
            events = []
            if self.log_file.exists():
                with open(self.log_file, 'r') as f:
                    for line in f:
                        try:
                            event_data = json.loads(line.strip())
                            event_time = datetime.fromisoformat(event_data['timestamp'].replace('Z', '+00:00'))
                            if event_time >= cutoff_time:
                                events.append(event_data)
                        except (json.JSONDecodeError, KeyError, ValueError):
                            continue
            
            # Analyze events
            summary = {
                'total_events': len(events),
                'time_range_hours': hours,
                'event_types': {},
                'severity_counts': {},
                'error_count': 0,
                'operations_completed': 0,
                'avg_operation_duration_ms': 0,
                'conversations_processed': set(),
                'data_integrity_checks': 0,
                'phase_changes': []
            }
            
            total_duration = 0
            duration_count = 0
            
            for event in events:
                # Count event types
                event_type = event.get('event_type', 'unknown')
                summary['event_types'][event_type] = summary['event_types'].get(event_type, 0) + 1
                
                # Count severity levels
                severity = event.get('severity', 'unknown')
                summary['severity_counts'][severity] = summary['severity_counts'].get(severity, 0) + 1
                
                # Count errors
                if severity in ['error', 'critical']:
                    summary['error_count'] += 1
                
                # Track operations
                if event_type.endswith('_completed'):
                    summary['operations_completed'] += 1
                    
                    duration = event.get('duration_ms')
                    if duration:
                        total_duration += duration
                        duration_count += 1
                
                # Track conversations
                conv_id = event.get('conversation_id')
                if conv_id:
                    summary['conversations_processed'].add(conv_id)
                
                # Track integrity checks
                if event_type == 'integrity_check_completed':
                    summary['data_integrity_checks'] += 1
                
                # Track phase changes
                if event_type == 'phase_change':
                    summary['phase_changes'].append({
                        'timestamp': event['timestamp'],
                        'phase': event.get('migration_phase')
                    })
            
            # Calculate averages
            if duration_count > 0:
                summary['avg_operation_duration_ms'] = total_duration / duration_count
            
            summary['conversations_processed'] = len(summary['conversations_processed'])
            
            return summary
            
        except Exception as e:
            logger.error(f"Failed to generate migration summary: {e}")
            return {'error': str(e)}


# === Global Instance Management ===

_migration_logger: Optional[MigrationLogger] = None
_logger_lock = asyncio.Lock()

async def get_migration_logger() -> MigrationLogger:
    """Get singleton instance of migration logger."""
    global _migration_logger
    
    async with _logger_lock:
        if _migration_logger is None:
            _migration_logger = MigrationLogger()
        return _migration_logger

# === Convenience Functions ===

async def log_migration_event(event_type: MigrationEventType, 
                            message: str,
                            severity: MigrationSeverity = MigrationSeverity.INFO,
                            **kwargs):
    """Convenience function to log migration events."""
    logger_instance = await get_migration_logger()
    event = MigrationEvent(
        event_type=event_type,
        severity=severity,
        message=message,
        timestamp=datetime.now(timezone.utc).isoformat(),
        **kwargs
    )
    await logger_instance.log_event(event)

async def log_conversation_read(conversation_id: str, message_count: int, user_id: str = "anonymous"):
    """Log conversation read operation."""
    logger_instance = await get_migration_logger()
    await logger_instance.log_conversation_operation(
        'read', conversation_id, user_id, data_after={'message_count': message_count}
    )

async def log_conversation_write(conversation_id: str, message: Dict[str, Any], user_id: str = "anonymous"):
    """Log conversation write operation."""
    logger_instance = await get_migration_logger()
    await logger_instance.log_conversation_operation(
        'write', conversation_id, user_id, data_after={'message': message}
    )

# Import here to avoid circular imports
from datetime import timedelta