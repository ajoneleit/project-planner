#!/usr/bin/env python3
"""
Migration script to convert existing JSON conversation files to modern LangGraph format.
Run this script to migrate all conversations from the legacy system to the new memory system.
"""

import asyncio
import json
import logging
import sys
from pathlib import Path
from typing import Dict, List, Any

# Add the app directory to the path so we can import our modules
sys.path.append(str(Path(__file__).parent.parent))

from memory.modern_memory import ModernConversationMemory, ConversationMigrator
from langchain_core.messages import HumanMessage, AIMessage

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def main():
    """Main migration function."""
    logger.info("Starting conversation migration to modern LangGraph system")
    
    # Initialize modern memory system
    modern_memory = ModernConversationMemory(db_path="app/memory/conversations.db")
    migrator = ConversationMigrator(modern_memory)
    
    # Find all JSON conversation files
    memory_dir = Path("app/memory")
    json_files = list(memory_dir.glob("*_conversations.json"))
    
    if not json_files:
        logger.info("No conversation files found to migrate")
        return
    
    logger.info(f"Found {len(json_files)} conversation files to migrate")
    
    # Track migration results
    migration_results = {}
    total_conversations_migrated = 0
    
    # Migrate each file
    for json_file in json_files:
        logger.info(f"Migrating {json_file.name}...")
        
        # Extract project slug from filename
        project_slug = json_file.stem.replace("_conversations", "")
        
        try:
            # Load the JSON file to count conversations
            with open(json_file, 'r') as f:
                data = json.load(f)
            
            conversation_count = len(data.get("conversations", []))
            logger.info(f"  - Found {conversation_count} conversations for project '{project_slug}'")
            
            # Perform migration
            success = await migrator.migrate_json_conversation(str(json_file), project_slug)
            migration_results[str(json_file)] = success
            
            if success:
                total_conversations_migrated += conversation_count
                logger.info(f"  ✓ Successfully migrated {conversation_count} conversations")
            else:
                logger.error(f"  ✗ Failed to migrate {json_file.name}")
                
        except Exception as e:
            logger.error(f"  ✗ Error migrating {json_file.name}: {e}")
            migration_results[str(json_file)] = False
    
    # Print summary
    successful_migrations = sum(1 for success in migration_results.values() if success)
    failed_migrations = len(migration_results) - successful_migrations
    
    logger.info("\n" + "="*60)
    logger.info("MIGRATION SUMMARY")
    logger.info("="*60)
    logger.info(f"Total files processed: {len(migration_results)}")
    logger.info(f"Successful migrations: {successful_migrations}")
    logger.info(f"Failed migrations: {failed_migrations}")
    logger.info(f"Total conversations migrated: {total_conversations_migrated}")
    
    if failed_migrations > 0:
        logger.info("\nFailed files:")
        for file_path, success in migration_results.items():
            if not success:
                logger.info(f"  - {file_path}")
    
    # Validate migrations
    logger.info("\nValidating migrations...")
    await validate_migrations(modern_memory, json_files)
    
    logger.info("Migration complete!")


async def validate_migrations(modern_memory: ModernConversationMemory, json_files: List[Path]):
    """Validate that migrations were successful by comparing message counts."""
    validation_errors = []
    
    for json_file in json_files:
        project_slug = json_file.stem.replace("_conversations", "")
        
        try:
            # Count original conversations
            with open(json_file, 'r') as f:
                data = json.load(f)
            original_count = len(data.get("conversations", []))
            
            # Count migrated messages (each conversation = 2 messages usually)
            migrated_messages = await modern_memory.get_messages(project_slug)
            migrated_count = len(migrated_messages) // 2  # Approximate conversation count
            
            if original_count != migrated_count:
                validation_errors.append(
                    f"Project '{project_slug}': Original={original_count}, Migrated={migrated_count}"
                )
            else:
                logger.info(f"  ✓ Project '{project_slug}': {original_count} conversations verified")
                
        except Exception as e:
            validation_errors.append(f"Project '{project_slug}': Validation error - {e}")
    
    if validation_errors:
        logger.warning("Validation errors found:")
        for error in validation_errors:
            logger.warning(f"  - {error}")
    else:
        logger.info("All migrations validated successfully!")


async def create_backup():
    """Create a backup of existing conversation files before migration."""
    memory_dir = Path("app/memory")
    backup_dir = memory_dir / "backup_before_migration"
    backup_dir.mkdir(exist_ok=True)
    
    json_files = list(memory_dir.glob("*_conversations.json"))
    
    if not json_files:
        logger.info("No files to backup")
        return
    
    logger.info(f"Creating backup of {len(json_files)} files...")
    
    for json_file in json_files:
        backup_file = backup_dir / json_file.name
        backup_file.write_text(json_file.read_text())
        logger.info(f"  Backed up {json_file.name}")
    
    logger.info(f"Backup created in {backup_dir}")


if __name__ == "__main__":
    # Option to create backup first
    if len(sys.argv) > 1 and sys.argv[1] == "--backup":
        print("Creating backup...")
        asyncio.run(create_backup())
        print("Backup complete. Run without --backup to perform migration.")
    else:
        asyncio.run(main())