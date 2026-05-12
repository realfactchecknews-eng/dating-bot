#!/usr/bin/env python3
"""
Simple test script to diagnose bot issues
"""

import asyncio
import logging
import os
from aiogram import Bot
from app.config import Config

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_bot_connection():
    """Test basic bot functionality"""
    try:
        logger.info("🔍 Testing bot connection...")
        
        # Test bot token
        bot = Bot(token=Config.BOT_TOKEN)
        bot_info = await bot.get_me()
        
        logger.info(f"✅ Bot connected: @{bot_info.username} (ID: {bot_info.id})")
        
        # Test database
        logger.info("🔍 Testing database connection...")
        from app.database import engine, async_session
        
        async with engine.begin() as conn:
            result = await conn.execute("SELECT 1")
            logger.info("✅ Database connected")
        
        # Test user creation
        logger.info("🔍 Testing user operations...")
        from app.models import User
        from sqlalchemy import select
        
        async with async_session() as session:
            # Test query
            result = await session.execute(select(User).limit(1))
            users = result.all()
            logger.info(f"✅ Database operations work (found {len(users)} users)")
        
        logger.info("🎉 All tests passed! Bot should work.")
        return True
        
    except Exception as e:
        logger.error(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

async def test_migration():
    """Test if migration worked"""
    try:
        logger.info("🔍 Testing telegram_id migration...")
        
        from app.database import engine
        from sqlalchemy import text
        
        async with engine.begin() as conn:
            result = await conn.execute(text("""
                SELECT data_type 
                FROM information_schema.columns 
                WHERE table_name = 'users' AND column_name = 'telegram_id'
            """))
            data_type = result.scalar()
            
            if data_type == 'bigint':
                logger.info("✅ Migration successful: telegram_id is BIGINT")
                return True
            else:
                logger.error(f"❌ Migration failed: telegram_id is {data_type}")
                return False
                
    except Exception as e:
        logger.error(f"❌ Migration test failed: {e}")
        return False

async def main():
    """Run all tests"""
    logger.info("🚀 Starting bot diagnostics...")
    
    # Test basic functionality
    basic_ok = await test_bot_connection()
    
    # Test migration
    migration_ok = await test_migration()
    
    # Summary
    logger.info("\n" + "="*50)
    logger.info("📊 DIAGNOSTIC RESULTS:")
    logger.info(f"Bot Connection: {'✅ OK' if basic_ok else '❌ FAILED'}")
    logger.info(f"Database Migration: {'✅ OK' if migration_ok else '❌ FAILED'}")
    
    if basic_ok and migration_ok:
        logger.info("🎉 Bot should work! Check for conflicting instances.")
    else:
        logger.info("🔧 Need to fix issues before bot can work.")
    
    logger.info("="*50)

if __name__ == "__main__":
    asyncio.run(main())
