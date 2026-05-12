import logging
import asyncio
import os
from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.client.default import DefaultBotProperties

from app.config import Config
from app.database import init_db
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
