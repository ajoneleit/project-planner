#!/usr/bin/env python3
"""
Conversation Data Migration Script - Phase 3: Active Data Migration
Migrates conversation data to use standardized conversation ID format.

This script:
1. Analyzes existing conversation data 
2. Creates migration plan for ID format standardization
3. Safely migrates conversations with data integrity checks
4. Consolidates fragmented conversations where appropriate
5. Validates migration results
"""

import asyncio
import sqlite3
import aiosqlite
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Any, Tuple, Set, Optional
from dataclasses import dataclass

# Add the app directory to Python path
import sys
sys.path.insert(0, 'app')

from app.core.conversation_id_manager import ConversationIDManager, ConversationIDFormat
from app.core.migration_logging import get_migration_logger, MigrationEventType, MigrationSeverity
from app.core.feature_flags import is_feature_enabled
from app.core.memory_unified import get_unified_memory

@dataclass
class MigrationPlan:
    """Migration plan for a specific conversation."""
    original_id: str
    target_id: str
    format_type: ConversationIDFormat
    message_count: int
    user_ids: Set[str]
    needs_consolidation: bool = False
    consolidate_with: List[str] = None

class ConversationDataMigrator:
    """Handles conversation data migration with safety checks."""
    
    def __init__(self, db_path: str = "app/memory/unified.db"):
        self.db_path = Path(db_path)
        self.migration_logger = None
        self.unified_memory = None
        
        # Migration tracking
        self.migration_plan: Dict[str, MigrationPlan] = {}
        self.dry_run = False
        
        # Statistics
        self.stats = {
            'conversations_analyzed': 0,
            'conversations_migrated': 0,
            'messages_migrated': 0,
            'consolidations_performed': 0,
            'errors_encountered': 0
        }
    
    async def initialize(self):
        """Initialize migration system."""
        self.migration_logger = await get_migration_logger()
        self.unified_memory = await get_unified_memory()
        
        await self.migration_logger.log_event(MigrationEvent(
            event_type=MigrationEventType.DATA_MIGRATION_STARTED,
            severity=MigrationSeverity.INFO,
            message="Phase 3 conversation data migration initialized",
            timestamp=datetime.now(timezone.utc).isoformat(),
            migration_phase="phase_3_migration"
        ))
    
    async def analyze_migration_needs(self) -> Dict[str, Any]:
        """Analyze current conversation data and create migration plan."""
        print("🔍 Analyzing conversation data for migration needs...")
        
        # Get all conversations from database
        async with aiosqlite.connect(str(self.db_path)) as db:
            async with db.execute("""
                SELECT DISTINCT conversation_id, COUNT(*) as message_count, 
                       GROUP_CONCAT(DISTINCT user_id) as user_ids,
                       MIN(created_at) as first_message,
                       MAX(created_at) as last_message
                FROM conversations 
                GROUP BY conversation_id
                ORDER BY conversation_id
            """) as cursor:
                conversations = await cursor.fetchall()
        
        analysis_results = {
            'total_conversations': len(conversations),
            'needs_migration': 0,
            'already_standard': 0,
            'consolidation_opportunities': 0,
            'migration_plan': {}
        }
        
        consolidation_candidates = {}  # project_slug -> list of conversation_ids
        
        for conv_id, msg_count, user_ids_str, first_msg, last_msg in conversations:
            self.stats['conversations_analyzed'] += 1
            
            # Analyze conversation ID format
            id_info = ConversationIDManager.analyze_id(conv_id)
            user_ids = set(user_ids_str.split(',')) if user_ids_str else set()
            
            # Create migration plan entry
            plan = MigrationPlan(
                original_id=conv_id,
                target_id=id_info.migration_target or conv_id,
                format_type=id_info.format_type,
                message_count=msg_count,
                user_ids=user_ids,
                consolidate_with=[]
            )
            
            if id_info.format_type == ConversationIDFormat.SIMPLE_PROJECT:
                # Needs migration to standard format
                analysis_results['needs_migration'] += 1
                
                # Check for consolidation opportunities
                project_slug = id_info.project_slug
                if project_slug not in consolidation_candidates:
                    consolidation_candidates[project_slug] = []
                consolidation_candidates[project_slug].append(conv_id)
                
                print(f"  📋 {conv_id} → {plan.target_id} ({msg_count} messages)")
                
            elif id_info.format_type == ConversationIDFormat.PROJECT_USER:
                # Already in standard format
                analysis_results['already_standard'] += 1
                print(f"  ✅ {conv_id} (already standard, {msg_count} messages)")
            else:
                # Unknown format - needs investigation
                print(f"  ⚠️  {conv_id} (unknown format, {msg_count} messages)")
            
            self.migration_plan[conv_id] = plan
            analysis_results['migration_plan'][conv_id] = {
                'original_id': plan.original_id,
                'target_id': plan.target_id,
                'format_type': plan.format_type.value,
                'message_count': plan.message_count,
                'user_ids': list(plan.user_ids)
            }
        
        # Identify consolidation opportunities
        for project_slug, conv_ids in consolidation_candidates.items():
            if len(conv_ids) > 1:
                analysis_results['consolidation_opportunities'] += 1
                print(f"  🔗 Consolidation opportunity: {project_slug} ({len(conv_ids)} conversations)")
                
                # Mark for consolidation - choose target based on most recent activity
                target_id = None
                target_plan = None
                
                for conv_id in conv_ids:
                    plan = self.migration_plan[conv_id]
                    if target_id is None or plan.message_count > target_plan.message_count:
                        target_id = conv_id
                        target_plan = plan
                
                # Set consolidation targets
                for conv_id in conv_ids:
                    if conv_id != target_id:
                        self.migration_plan[conv_id].needs_consolidation = True
                        self.migration_plan[conv_id].consolidate_with = [target_id]
        
        print(f"📊 Analysis complete:")
        print(f"   Total conversations: {analysis_results['total_conversations']}")
        print(f"   Need migration: {analysis_results['needs_migration']}")
        print(f"   Already standard: {analysis_results['already_standard']}")
        print(f"   Consolidation opportunities: {analysis_results['consolidation_opportunities']}")
        
        return analysis_results
    
    async def create_migration_backup(self) -> Path:
        """Create backup before migration."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_dir = Path(f"migration_backups/phase3_migration_{timestamp}")
        backup_dir.mkdir(parents=True, exist_ok=True)
        
        # Copy database
        backup_db_path = backup_dir / "unified_pre_migration.db"
        shutil.copy2(self.db_path, backup_db_path)
        
        # Save migration plan
        plan_path = backup_dir / "migration_plan.json"
        plan_data = {
            'timestamp': timestamp,
            'migration_phase': 'phase_3_migration',
            'statistics': self.stats,
            'migration_plan': {
                conv_id: {
                    'original_id': plan.original_id,
                    'target_id': plan.target_id,
                    'format_type': plan.format_type.value,
                    'message_count': plan.message_count,
                    'user_ids': list(plan.user_ids),
                    'needs_consolidation': plan.needs_consolidation,
                    'consolidate_with': plan.consolidate_with or []
                }
                for conv_id, plan in self.migration_plan.items()
            }
        }
        
        with open(plan_path, 'w') as f:
            json.dump(plan_data, f, indent=2)
        
        print(f"✅ Migration backup created: {backup_dir}")
        return backup_dir
    
    async def execute_migration(self, dry_run: bool = True) -> bool:
        """Execute the conversation data migration."""
        self.dry_run = dry_run
        
        if dry_run:
            print("🔄 Executing migration in DRY RUN mode...")
        else:
            print("🔄 Executing LIVE migration...")
            
            # Check feature flag
            if not await is_feature_enabled("active_data_migration"):
                print("❌ Active data migration feature flag not enabled")
                return False
        
        success = True
        
        async with aiosqlite.connect(str(self.db_path)) as db:
            for conv_id, plan in self.migration_plan.items():
                try:
                    if plan.format_type == ConversationIDFormat.PROJECT_USER:
                        # Already in correct format, skip
                        continue
                    
                    if plan.needs_consolidation:
                        # Handle consolidation
                        success &= await self._consolidate_conversation(db, plan)
                    else:
                        # Handle standard migration
                        success &= await self._migrate_conversation(db, plan)
                        
                except Exception as e:
                    print(f"❌ Error migrating {conv_id}: {e}")
                    self.stats['errors_encountered'] += 1
                    success = False
                    
                    if self.migration_logger:
                        await self.migration_logger.log_event(MigrationEvent(
                            event_type=MigrationEventType.MIGRATION_ERROR,
                            severity=MigrationSeverity.ERROR,
                            message=f"Migration error for conversation {conv_id}",
                            timestamp=datetime.now(timezone.utc).isoformat(),
                            conversation_id=conv_id,
                            error_type=type(e).__name__,
                            error_details=str(e)
                        ))
        
        # Log migration completion
        if self.migration_logger:
            await self.migration_logger.log_event(MigrationEvent(
                event_type=MigrationEventType.DATA_MIGRATION_COMPLETED,
                severity=MigrationSeverity.INFO if success else MigrationSeverity.ERROR,
                message=f"Phase 3 migration completed: {'SUCCESS' if success else 'WITH ERRORS'}",
                timestamp=datetime.now(timezone.utc).isoformat(),
                migration_phase="phase_3_migration",
                record_count=self.stats['messages_migrated'],
                data_after=self.stats
            ))
        
        return success
    
    async def _migrate_conversation(self, db: aiosqlite.Connection, plan: MigrationPlan) -> bool:
        """Migrate a single conversation to standard ID format."""
        
        if plan.original_id == plan.target_id:
            # No migration needed
            return True
        
        print(f"  📝 Migrating: {plan.original_id} → {plan.target_id}")
        
        if not self.dry_run:
            # Update conversation_id in database
            await db.execute("""
                UPDATE conversations 
                SET conversation_id = ? 
                WHERE conversation_id = ?
            """, (plan.target_id, plan.original_id))
            
            await db.commit()
        
        self.stats['conversations_migrated'] += 1
        self.stats['messages_migrated'] += plan.message_count
        
        # Log the migration
        if self.migration_logger and not self.dry_run:
            await self.migration_logger.log_conversation_operation(
                'resolve_id',
                plan.target_id,
                user_id=list(plan.user_ids)[0] if plan.user_ids else 'anonymous',
                data_before={'conversation_id': plan.original_id},
                data_after={'conversation_id': plan.target_id},
                success=True
            )
        
        return True
    
    async def _consolidate_conversation(self, db: aiosqlite.Connection, plan: MigrationPlan) -> bool:
        """Consolidate conversation with another conversation."""
        
        if not plan.consolidate_with:
            return True
        
        target_conv_id = plan.consolidate_with[0]
        target_plan = self.migration_plan[target_conv_id]
        
        print(f"  🔗 Consolidating: {plan.original_id} → {target_plan.target_id}")
        
        if not self.dry_run:
            # Move all messages from source to target conversation
            await db.execute("""
                UPDATE conversations 
                SET conversation_id = ? 
                WHERE conversation_id = ?
            """, (target_plan.target_id, plan.original_id))
            
            await db.commit()
        
        self.stats['consolidations_performed'] += 1
        self.stats['messages_migrated'] += plan.message_count
        
        # Log the consolidation
        if self.migration_logger and not self.dry_run:
            await self.migration_logger.log_conversation_operation(
                'consolidate',
                target_plan.target_id,
                user_id=list(plan.user_ids)[0] if plan.user_ids else 'anonymous',
                data_before={
                    'source_conversation': plan.original_id,
                    'source_messages': plan.message_count
                },
                data_after={
                    'target_conversation': target_plan.target_id,
                    'consolidated_messages': plan.message_count
                },
                success=True
            )
        
        return True
    
    async def validate_migration(self) -> Dict[str, Any]:
        """Validate migration results."""
        print("🔍 Validating migration results...")
        
        validation_results = {
            'total_conversations': 0,
            'standard_format_count': 0,
            'legacy_format_count': 0,
            'message_integrity': True,
            'id_format_distribution': {},
            'validation_errors': []
        }
        
        async with aiosqlite.connect(str(self.db_path)) as db:
            # Count conversations by format
            async with db.execute("""
                SELECT DISTINCT conversation_id, COUNT(*) as message_count
                FROM conversations 
                GROUP BY conversation_id
            """) as cursor:
                conversations = await cursor.fetchall()
            
            validation_results['total_conversations'] = len(conversations)
            
            for conv_id, msg_count in conversations:
                id_info = ConversationIDManager.analyze_id(conv_id)
                
                format_key = id_info.format_type.value
                if format_key not in validation_results['id_format_distribution']:
                    validation_results['id_format_distribution'][format_key] = 0
                validation_results['id_format_distribution'][format_key] += 1
                
                if id_info.format_type == ConversationIDFormat.PROJECT_USER:
                    validation_results['standard_format_count'] += 1
                else:
                    validation_results['legacy_format_count'] += 1
                    validation_results['validation_errors'].append(
                        f"Conversation {conv_id} still in legacy format"
                    )
            
            # Validate message integrity
            async with db.execute("SELECT COUNT(*) FROM conversations") as cursor:
                total_messages = (await cursor.fetchone())[0]
            
            expected_messages = sum(plan.message_count for plan in self.migration_plan.values())
            if total_messages != expected_messages:
                validation_results['message_integrity'] = False
                validation_results['validation_errors'].append(
                    f"Message count mismatch: expected {expected_messages}, found {total_messages}"
                )
        
        print(f"📊 Validation results:")
        print(f"   Total conversations: {validation_results['total_conversations']}")
        print(f"   Standard format: {validation_results['standard_format_count']}")
        print(f"   Legacy format: {validation_results['legacy_format_count']}")
        print(f"   Message integrity: {'✅ PASSED' if validation_results['message_integrity'] else '❌ FAILED'}")
        
        if validation_results['validation_errors']:
            print(f"   Validation errors: {len(validation_results['validation_errors'])}")
            for error in validation_results['validation_errors']:
                print(f"     ❌ {error}")
        
        return validation_results

async def main():
    """Main migration execution function."""
    print("🚀 Phase 3: Active Data Migration")
    print("=" * 60)
    print(f"Started at: {datetime.now().isoformat()}")
    print()
    
    migrator = ConversationDataMigrator()
    
    try:
        # Initialize migration system
        await migrator.initialize()
        
        # Step 1: Analyze current data
        analysis = await migrator.analyze_migration_needs()
        
        if analysis['needs_migration'] == 0:
            print("✅ No conversations need migration - all are already in standard format!")
            return True
        
        # Step 2: Create backup
        backup_dir = await migrator.create_migration_backup()
        
        # Step 3: Dry run first
        print("\n" + "=" * 60)
        print("🔄 Phase 3a: Migration Dry Run")
        print("=" * 60)
        
        dry_run_success = await migrator.execute_migration(dry_run=True)
        
        if not dry_run_success:
            print("❌ Dry run failed - aborting migration")
            return False
        
        print("✅ Dry run completed successfully")
        
        # Step 4: Execute live migration
        print("\n" + "=" * 60)
        print("🔄 Phase 3b: Live Migration Execution")
        print("=" * 60)
        
        live_success = await migrator.execute_migration(dry_run=False)
        
        if not live_success:
            print("❌ Live migration failed")
            return False
        
        # Step 5: Validate results
        print("\n" + "=" * 60)
        print("🔍 Phase 3c: Migration Validation")
        print("=" * 60)
        
        validation = await migrator.validate_migration()
        
        # Final summary
        print("\n" + "=" * 60)
        print("🏁 Phase 3 Migration Summary")
        print("=" * 60)
        
        print(f"📊 Migration Statistics:")
        print(f"   Conversations analyzed: {migrator.stats['conversations_analyzed']}")
        print(f"   Conversations migrated: {migrator.stats['conversations_migrated']}")
        print(f"   Messages migrated: {migrator.stats['messages_migrated']}")
        print(f"   Consolidations performed: {migrator.stats['consolidations_performed']}")
        print(f"   Errors encountered: {migrator.stats['errors_encountered']}")
        
        migration_success = (
            live_success and 
            validation['message_integrity'] and 
            validation['legacy_format_count'] == 0
        )
        
        if migration_success:
            print("🎉 Phase 3 migration completed successfully!")
            print("✅ All conversations now use standardized ID format")
            print("✅ Data integrity validated")
            print("🚀 System ready for Phase 4: Validation")
        else:
            print("⚠️  Migration completed with issues")
            print("❗ Please review validation errors before proceeding")
        
        return migration_success
        
    except Exception as e:
        print(f"❌ Migration failed with error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    # Import required modules
    import aiosqlite
    from app.core.migration_logging import MigrationEvent
    
    success = asyncio.run(main())
    sys.exit(0 if success else 1)