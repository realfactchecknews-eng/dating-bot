import logging
import asyncio
import os
from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.client.default import DefaultBotProperties

from app.config import Config
from app.database import init_db, engine
from sqlalchemy import text
from app import handlers, admin

os.makedirs("logs", exist_ok=True)
os.makedirs("data", exist_ok=True)
os.makedirs("photos", exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("logs/bot.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

bot = Bot(token=Config.BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher(storage=MemoryStorage())

dp.include_router(handlers.router)
dp.include_router(admin.router)

async def on_startup():
    logger.info("Starting bot...")
    await init_db()
    
    # Auto-migrate telegram_id to BIGINT if needed
    try:
        async with engine.begin() as conn:
            # Check if telegram_id is still INTEGER
            result = await conn.execute(text("""
                SELECT data_type 
                FROM information_schema.columns 
                WHERE table_name = 'users' AND column_name = 'telegram_id'
            """))
            current_type = result.scalar()
            
            if current_type == 'integer':
                logger.info("🔄 Auto-migrating telegram_id from INTEGER to BIGINT...")
                # First convert to BIGINT using USBIGINT to handle large values
                await conn.execute(text("""
                    ALTER TABLE users 
                    ALTER COLUMN telegram_id TYPE BIGINT USING telegram_id::BIGINT
                """))
                logger.info("✅ Migration completed successfully!")
                
                # Refresh metadata and clear caches
                from app.models import Base
                Base.metadata.reflect(bind=conn)
                
                # Clear all prepared statement caches
                await conn.execute(text("DISCARD ALL"))
                await conn.commit()
                
                logger.info("🧹 Cleared database caches")
                
            else:
                logger.info(f"✅ telegram_id is already {current_type}")
                
    except Exception as e:
        logger.error(f"❌ Migration failed: {e}")
    
    logger.info("Database initialized")
    
    from aiogram.types import BotCommand
    await bot.set_my_commands([
        BotCommand(command="start", description="Запустить бота"),
        BotCommand(command="stats", description="Статистика (админ)"),
    ])

async def on_shutdown():
    logger.info("Shutting down...")
    await bot.session.close()

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

async def main():
    await on_startup()
    await init_db()
    logger.info("Database initialized")
    
    try:
        await dp.start_polling(bot, skip_updates=True)
    finally:
        await on_shutdown()

if __name__ == "__main__":
    asyncio.run(main())
