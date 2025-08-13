#!/usr/bin/env python3
"""
Migration script to move from LangGraph to OpenAI Agents SDK.

This script helps migrate existing markdown conversations to SQLiteSession format
and verifies the OpenAI Agents SDK integration.
"""

import asyncio
import os
import logging
from pathlib import Path
import sys

# Add the app directory to the Python path
sys.path.insert(0, str(Path(__file__).parent))

from app.openai_agents_runner import get_openai_runner

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def migrate_project_conversations():
    """Migrate all existing project conversations to SQLiteSession format."""
    
    memory_dir = Path("app/memory")
    if not memory_dir.exists():
        logger.info("No memory directory found, nothing to migrate")
        return
    
    runner = await get_openai_runner()
    migrated_count = 0
    
    for md_file in memory_dir.glob("*.md"):
        if md_file.name in ["index.json", "conversations.db"]:
            continue
            
        project_slug = md_file.stem
        logger.info(f"Migrating project: {project_slug}")
        
        try:
            success = await runner.migrate_existing_conversation(project_slug)
            if success:
                migrated_count += 1
                logger.info(f"✅ Successfully migrated {project_slug}")
            else:
                logger.warning(f"⚠️  Failed to migrate {project_slug}")
        except Exception as e:
            logger.error(f"❌ Error migrating {project_slug}: {e}")
    
    logger.info(f"Migration complete: {migrated_count} projects migrated")


async def test_openai_agents_system():
    """Test the OpenAI Agents SDK system with a simple conversation."""
    
    logger.info("Testing OpenAI Agents SDK system...")
    
    try:
        runner = await get_openai_runner()
        
        # Test a simple conversation
        test_project = "test-openai-agents"
        test_message = "Hello, can you help me understand what this project is about?"
        
        logger.info(f"Testing conversation with project: {test_project}")
        
        # Test non-streaming first
        result = await runner.run_conversation(test_project, test_message)
        
        if result["success"]:
            logger.info("✅ Non-streaming conversation test passed")
            logger.info(f"Response: {result['response'][:100]}...")
        else:
            logger.error(f"❌ Non-streaming conversation test failed: {result['error']}")
            return False
        
        # Test streaming
        logger.info("Testing streaming conversation...")
        stream_chunks = []
        async for chunk in runner.run_conversation_stream(test_project, "Tell me more about the project structure."):
            stream_chunks.append(chunk)
            if len(stream_chunks) > 10:  # Limit test output
                break
        
        if stream_chunks:
            logger.info("✅ Streaming conversation test passed")
            logger.info(f"Streamed {len(stream_chunks)} chunks")
        else:
            logger.warning("⚠️  Streaming test produced no output")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ OpenAI Agents SDK test failed: {e}")
        return False


async def verify_environment():
    """Verify that the environment is set up correctly for OpenAI Agents SDK."""
    
    logger.info("Verifying environment setup...")
    
    # Check OpenAI API key
    if not os.getenv("OPENAI_API_KEY"):
        logger.error("❌ OPENAI_API_KEY environment variable not set")
        return False
    else:
        logger.info("✅ OPENAI_API_KEY is set")
    
    # Check if agents module can be imported
    try:
        from agents import Agent, Runner, SQLiteSession
        logger.info("✅ OpenAI Agents SDK imported successfully")
    except ImportError as e:
        logger.error(f"❌ Failed to import OpenAI Agents SDK: {e}")
        return False
    
    # Check if conversations database directory exists
    db_dir = Path("app/memory")
    if not db_dir.exists():
        db_dir.mkdir(parents=True, exist_ok=True)
        logger.info("✅ Created conversations database directory")
    else:
        logger.info("✅ Conversations database directory exists")
    
    return True


async def main():
    """Main migration function."""
    
    logger.info("🚀 Starting OpenAI Agents SDK Migration")
    logger.info("=" * 50)
    
    # Step 1: Verify environment
    logger.info("Step 1: Verifying environment...")
    if not await verify_environment():
        logger.error("❌ Environment verification failed. Please fix the issues above.")
        return 1
    
    # Step 2: Test OpenAI Agents SDK system
    logger.info("\nStep 2: Testing OpenAI Agents SDK system...")
    if not await test_openai_agents_system():
        logger.error("❌ OpenAI Agents SDK test failed. Please check your setup.")
        return 1
    
    # Step 3: Migrate existing conversations
    logger.info("\nStep 3: Migrating existing conversations...")
    await migrate_project_conversations()
    
    logger.info("\n🎉 Migration completed successfully!")
    logger.info("=" * 50)
    logger.info("Next steps:")
    logger.info("1. Set USE_OPENAI_AGENTS=true in your environment")
    logger.info("2. Restart your FastAPI server")
    logger.info("3. Test the chat functionality in the web interface")
    logger.info("4. Monitor logs for any issues")
    
    return 0


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)