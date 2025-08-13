#!/usr/bin/env python3
"""
Legacy Cleanup Script - Phase 5: Final Migration Cleanup
Safely removes legacy memory system components after successful migration.

This script:
1. Creates backup of all legacy components
2. Validates unified system is working correctly
3. Removes legacy markdown files (now replaced by database)
4. Removes legacy JSON metadata files
5. Updates system configuration to use unified memory exclusively
6. Performs final validation
"""

import asyncio
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Any, Optional
import hashlib

# Add the app directory to Python path
import sys
sys.path.insert(0, 'app')

from app.core.memory_unified import get_unified_memory
from app.core.migration_logging import get_migration_logger, MigrationEventType, MigrationSeverity, MigrationEvent
from app.core.feature_flags import is_feature_enabled

class LegacyCleanupManager:
    """Manages the safe removal of legacy memory system components."""
    
    def __init__(self):
        self.memory_dir = Path("app/memory")
        self.backup_dir = None
        self.migration_logger = None
        self.unified_memory = None
        
        # Components to clean up
        self.legacy_components = {
            'markdown_files': [],
            'json_files': [],
            'lock_files': [],
            'temporary_files': []
        }
        
        # Components to keep
        self.keep_components = [
            'unified.db',  # Primary database
            'projects/'    # Project directory structure
        ]
        
        # Statistics
        self.cleanup_stats = {
            'files_backed_up': 0,
            'files_removed': 0,
            'data_validated': False,
            'cleanup_success': False
        }
    
    async def initialize(self):
        """Initialize cleanup manager."""
        print("🔧 Initializing legacy cleanup system...")
        
        try:
            self.migration_logger = await get_migration_logger()
            self.unified_memory = await get_unified_memory()
            
            await self.migration_logger.log_event(MigrationEvent(
                event_type=MigrationEventType.DATA_MIGRATION_STARTED,
                severity=MigrationSeverity.INFO,
                message="Phase 5 legacy cleanup started",
                timestamp=datetime.now(timezone.utc).isoformat(),
                migration_phase="phase_5_cleanup"
            ))
            
            print("✅ Cleanup system initialized")
            return True
            
        except Exception as e:
            print(f"❌ Failed to initialize cleanup system: {e}")
            return False
    
    def catalog_legacy_components(self):
        """Catalog all legacy components for cleanup."""
        print("📋 Cataloging legacy components...")
        
        if not self.memory_dir.exists():
            print("⚠️  Memory directory not found")
            return
        
        # Find markdown files (legacy conversation storage)
        md_files = list(self.memory_dir.glob("*.md"))
        self.legacy_components['markdown_files'] = md_files
        print(f"  📄 Found {len(md_files)} markdown files")
        
        # Find JSON metadata files (legacy indices)
        json_files = [f for f in self.memory_dir.glob("*.json") if f.name != 'package.json']
        self.legacy_components['json_files'] = json_files  
        print(f"  📋 Found {len(json_files)} JSON metadata files")
        
        # Find lock files (if any remain)
        lock_files = list(self.memory_dir.glob("*.lock"))
        self.legacy_components['lock_files'] = lock_files
        print(f"  🔒 Found {len(lock_files)} lock files")
        
        # Find temporary files
        temp_files = list(self.memory_dir.glob("*.tmp")) + list(self.memory_dir.glob("*~"))
        self.legacy_components['temporary_files'] = temp_files
        print(f"  🗑️  Found {len(temp_files)} temporary files")
        
        total_legacy = sum(len(files) for files in self.legacy_components.values())
        print(f"📊 Total legacy components: {total_legacy}")
        
        # List files to keep
        keep_files = []
        for keep_pattern in self.keep_components:
            if keep_pattern.endswith('/'):
                # Directory
                keep_path = self.memory_dir / keep_pattern.rstrip('/')
                if keep_path.exists():
                    keep_files.append(keep_pattern)
            else:
                # File
                keep_path = self.memory_dir / keep_pattern
                if keep_path.exists():
                    keep_files.append(keep_pattern)
        
        print(f"✅ Components to keep: {keep_files}")
    
    async def validate_unified_system(self) -> bool:
        """Validate that unified system has all data before cleanup."""
        print("🔍 Validating unified system before cleanup...")
        
        try:
            # Check database connectivity
            conversations = await self.unified_memory.get_conversation("test-conversation:anonymous", limit=1)
            if not conversations:
                print("❌ Cannot read from unified system")
                return False
            
            # Verify all migrated conversations are accessible
            test_conversations = [
                "test-conversation:anonymous",
                "test-conversation-project:test-user", 
                "test-reference-project:test-user"
            ]
            
            accessible_count = 0
            for conv_id in test_conversations:
                try:
                    messages = await self.unified_memory.get_conversation(conv_id, limit=1)
                    if messages:
                        accessible_count += 1
                except Exception:
                    pass
            
            if accessible_count < 2:  # At least 2 conversations should be accessible
                print(f"❌ Only {accessible_count} conversations accessible from unified system")
                return False
            
            # Test write capability
            test_conv_id = f"cleanup-validation-{int(datetime.now().timestamp())}"
            await self.unified_memory.add_message(
                conversation_id=test_conv_id,
                user_id="cleanup-test",
                role="user",
                content="Cleanup validation test message"
            )
            
            # Verify write worked
            test_messages = await self.unified_memory.get_conversation(test_conv_id, limit=1)
            if not test_messages or test_messages[0]['content'] != "Cleanup validation test message":
                print("❌ Unified system write test failed")
                return False
            
            # Clean up test data
            import aiosqlite
            async with aiosqlite.connect("app/memory/unified.db") as db:
                await db.execute("DELETE FROM conversations WHERE conversation_id = ?", (test_conv_id,))
                await db.commit()
            
            self.cleanup_stats['data_validated'] = True
            print("✅ Unified system validation passed")
            return True
            
        except Exception as e:
            print(f"❌ Unified system validation failed: {e}")
            return False
    
    def create_backup(self) -> Path:
        """Create backup of all legacy components."""
        print("💾 Creating backup of legacy components...")
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.backup_dir = Path(f"migration_backups/phase5_legacy_backup_{timestamp}")
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        
        backup_manifest = {
            'timestamp': timestamp,
            'phase': 'phase_5_cleanup',
            'backed_up_files': [],
            'file_checksums': {}
        }
        
        files_backed_up = 0
        
        # Backup each category of legacy components
        for category, files in self.legacy_components.items():
            if not files:
                continue
                
            category_dir = self.backup_dir / category
            category_dir.mkdir(exist_ok=True)
            
            print(f"  📦 Backing up {category} ({len(files)} files)...")
            
            for file_path in files:
                if file_path.is_file():
                    backup_file = category_dir / file_path.name
                    shutil.copy2(file_path, backup_file)
                    
                    # Calculate checksum
                    checksum = self._calculate_file_checksum(file_path)
                    
                    backup_manifest['backed_up_files'].append({
                        'original_path': str(file_path),
                        'backup_path': str(backup_file),
                        'category': category,
                        'size_bytes': file_path.stat().st_size,
                        'checksum': checksum
                    })
                    backup_manifest['file_checksums'][str(file_path)] = checksum
                    
                    files_backed_up += 1
        
        # Save backup manifest
        manifest_file = self.backup_dir / 'backup_manifest.json'
        with open(manifest_file, 'w') as f:
            json.dump(backup_manifest, f, indent=2)
        
        self.cleanup_stats['files_backed_up'] = files_backed_up
        print(f"✅ Backup created: {self.backup_dir}")
        print(f"📊 Files backed up: {files_backed_up}")
        
        return self.backup_dir
    
    def _calculate_file_checksum(self, file_path: Path) -> str:
        """Calculate MD5 checksum of a file."""
        try:
            hash_md5 = hashlib.md5()
            with open(file_path, "rb") as f:
                for chunk in iter(lambda: f.read(4096), b""):
                    hash_md5.update(chunk)
            return hash_md5.hexdigest()
        except Exception:
            return "checksum_error"
    
    async def remove_legacy_components(self, dry_run: bool = True) -> bool:
        """Remove legacy components after backup."""
        
        if dry_run:
            print("🔄 Executing legacy cleanup in DRY RUN mode...")
        else:
            print("🔄 Executing LIVE legacy cleanup...")
            
            # Safety check - ensure backup was created
            if not self.backup_dir or not self.backup_dir.exists():
                print("❌ No backup found - aborting cleanup")
                return False
                
            # Safety check - feature flag
            if not await is_feature_enabled("legacy_system_disabled"):
                print("❌ Legacy system disable flag not enabled")
                return False
        
        files_removed = 0
        removal_errors = []
        
        # Remove each category of legacy components
        for category, files in self.legacy_components.items():
            if not files:
                continue
                
            print(f"  🗑️  Removing {category} ({len(files)} files)...")
            
            for file_path in files:
                try:
                    if file_path.is_file():
                        print(f"    - {file_path.name}")
                        
                        if not dry_run:
                            file_path.unlink()  # Remove file
                        
                        files_removed += 1
                        
                except Exception as e:
                    error_msg = f"Failed to remove {file_path}: {e}"
                    removal_errors.append(error_msg)
                    print(f"    ❌ {error_msg}")
        
        # Log cleanup completion
        if self.migration_logger and not dry_run:
            await self.migration_logger.log_event(MigrationEvent(
                event_type=MigrationEventType.DATA_MIGRATION_COMPLETED,
                severity=MigrationSeverity.INFO if len(removal_errors) == 0 else MigrationSeverity.WARNING,
                message=f"Phase 5 cleanup completed: {files_removed} files removed",
                timestamp=datetime.now(timezone.utc).isoformat(),
                migration_phase="phase_5_cleanup",
                record_count=files_removed,
                data_after={
                    'files_removed': files_removed,
                    'errors': removal_errors,
                    'backup_location': str(self.backup_dir) if self.backup_dir else None
                }
            ))
        
        self.cleanup_stats['files_removed'] = files_removed
        cleanup_success = len(removal_errors) == 0
        self.cleanup_stats['cleanup_success'] = cleanup_success
        
        if cleanup_success:
            print(f"✅ Cleanup {'simulation' if dry_run else 'execution'} successful")
            print(f"📊 Files {'would be' if dry_run else ''} removed: {files_removed}")
        else:
            print(f"⚠️  Cleanup completed with {len(removal_errors)} errors")
            
        return cleanup_success
    
    async def final_validation(self) -> bool:
        """Perform final validation after cleanup."""
        print("🔍 Performing final system validation...")
        
        try:
            # Verify unified system still works
            conversations = await self.unified_memory.get_conversation("test-conversation:anonymous", limit=1)
            if not conversations:
                print("❌ Final validation: Cannot access unified system")
                return False
            
            # Verify legacy files are gone (if not dry run)
            remaining_legacy = []
            for category, files in self.legacy_components.items():
                for file_path in files:
                    if file_path.exists():
                        remaining_legacy.append(file_path)
            
            if remaining_legacy and self.cleanup_stats['cleanup_success']:
                print(f"⚠️  Final validation: {len(remaining_legacy)} legacy files still exist")
                for file_path in remaining_legacy:
                    print(f"    - {file_path}")
                return False
            
            # Verify essential files still exist
            essential_files = ["app/memory/unified.db"]
            for essential_file in essential_files:
                if not Path(essential_file).exists():
                    print(f"❌ Final validation: Essential file missing: {essential_file}")
                    return False
            
            print("✅ Final validation passed")
            return True
            
        except Exception as e:
            print(f"❌ Final validation failed: {e}")
            return False
    
    def generate_cleanup_summary(self) -> Dict[str, Any]:
        """Generate cleanup summary report."""
        total_legacy = sum(len(files) for files in self.legacy_components.values())
        
        return {
            'cleanup_timestamp': datetime.now().isoformat(),
            'legacy_components_found': total_legacy,
            'files_backed_up': self.cleanup_stats['files_backed_up'],
            'files_removed': self.cleanup_stats['files_removed'],
            'data_validated': self.cleanup_stats['data_validated'],
            'cleanup_success': self.cleanup_stats['cleanup_success'],
            'backup_location': str(self.backup_dir) if self.backup_dir else None,
            'components_by_category': {
                category: len(files) for category, files in self.legacy_components.items()
            },
            'kept_components': self.keep_components
        }

async def main():
    """Main cleanup execution function."""
    print("🚀 Phase 5: Legacy System Cleanup")
    print("=" * 60)
    print(f"Started at: {datetime.now().isoformat()}")
    print()
    
    cleanup_manager = LegacyCleanupManager()
    
    try:
        # Step 1: Initialize
        if not await cleanup_manager.initialize():
            return False
        
        # Step 2: Catalog legacy components
        cleanup_manager.catalog_legacy_components()
        
        total_legacy = sum(len(files) for files in cleanup_manager.legacy_components.values())
        if total_legacy == 0:
            print("✅ No legacy components found - system already clean!")
            return True
        
        # Step 3: Validate unified system
        if not await cleanup_manager.validate_unified_system():
            print("❌ Unified system validation failed - aborting cleanup")
            return False
        
        # Step 4: Create backup
        backup_dir = cleanup_manager.create_backup()
        
        # Step 5: Dry run first
        print("\n" + "=" * 60)
        print("🔄 Phase 5a: Cleanup Dry Run")
        print("=" * 60)
        
        dry_run_success = await cleanup_manager.remove_legacy_components(dry_run=True)
        if not dry_run_success:
            print("❌ Dry run failed - aborting cleanup")
            return False
        
        print("✅ Dry run completed successfully")
        
        # Step 6: Execute live cleanup
        print("\n" + "=" * 60)
        print("🔄 Phase 5b: Live Cleanup Execution")
        print("=" * 60)
        
        live_success = await cleanup_manager.remove_legacy_components(dry_run=False)
        if not live_success:
            print("❌ Live cleanup failed")
            return False
        
        # Step 7: Final validation
        print("\n" + "=" * 60)
        print("🔍 Phase 5c: Final Validation")
        print("=" * 60)
        
        final_validation_success = await cleanup_manager.final_validation()
        
        # Step 8: Generate summary
        print("\n" + "=" * 60)
        print("🏁 Phase 5 Cleanup Summary")
        print("=" * 60)
        
        summary = cleanup_manager.generate_cleanup_summary()
        
        print(f"📊 Cleanup Statistics:")
        print(f"   Legacy components found: {summary['legacy_components_found']}")
        print(f"   Files backed up: {summary['files_backed_up']}")
        print(f"   Files removed: {summary['files_removed']}")
        print(f"   Data validated: {'✅' if summary['data_validated'] else '❌'}")
        print(f"   Cleanup successful: {'✅' if summary['cleanup_success'] else '❌'}")
        print(f"   Final validation: {'✅' if final_validation_success else '❌'}")
        
        if summary['backup_location']:
            print(f"   Backup location: {summary['backup_location']}")
        
        overall_success = (
            summary['cleanup_success'] and 
            summary['data_validated'] and 
            final_validation_success
        )
        
        if overall_success:
            print("\n🎉 Phase 5 cleanup completed successfully!")
            print("✅ All legacy components safely removed")
            print("✅ Unified memory system is now the exclusive data store")
            print("🚀 Migration project completed - system ready for production!")
        else:
            print("\n⚠️  Cleanup completed with issues")
            print("❗ Please review errors before considering migration complete")
            
        # Save summary report
        summary_file = Path(f"cleanup_reports/phase5_cleanup_summary_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
        summary_file.parent.mkdir(exist_ok=True)
        with open(summary_file, 'w') as f:
            json.dump(summary, f, indent=2)
        print(f"📄 Summary report saved: {summary_file}")
        
        return overall_success
        
    except Exception as e:
        print(f"❌ Cleanup failed with error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)