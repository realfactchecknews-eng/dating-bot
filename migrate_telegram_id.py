#!/usr/bin/env python3
"""
Migration script to change telegram_id from INTEGER to BIGINT
Run this once to update the database schema
"""

import asyncio
import asyncpg
from sqlalchemy import text
from app.config import Config
from app.database import async_session, engine

async def migrate_telegram_id():
    """Change telegram_id column type from INTEGER to BIGINT"""
    
    print("Starting migration for telegram_id field...")
    
    try:
        # Get database URL from config
        database_url = Config.DATABASE_URL
        
        # Extract connection details for asyncpg
        if database_url.startswith("postgresql+asyncpg://"):
            connection_string = database_url.replace("postgresql+asyncpg://", "postgresql://")
        else:
            raise ValueError("Expected postgresql+asyncpg:// connection string")
        
        # Connect directly with asyncpg for ALTER TABLE
        conn = await asyncpg.connect(connection_string)
        
        try:
            # Check if column is already BIGINT
            result = await conn.fetchval("""
                SELECT data_type 
                FROM information_schema.columns 
                WHERE table_name = 'users' AND column_name = 'telegram_id'
            """)
            
            if result == 'bigint':
                print("✅ telegram_id is already BIGINT. Migration not needed.")
                return
            
            print(f"📊 Current telegram_id type: {result}")
            print("🔄 Converting telegram_id from INTEGER to BIGINT...")
            
            # Alter the column type
            await conn.execute("""
                ALTER TABLE users 
                ALTER COLUMN telegram_id TYPE BIGINT
            """)
            
            print("✅ Migration completed successfully!")
            
        finally:
            await conn.close()
            
    except Exception as e:
        print(f"❌ Migration failed: {e}")
        raise

if __name__ == "__main__":
    asyncio.run(migrate_telegram_id())
