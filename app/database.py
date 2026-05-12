import os
from pathlib import Path
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import declarative_base
from app.config import Config

Base = declarative_base()

engine = create_async_engine(
    Config.DATABASE_URL,
    echo=Config.DEBUG,
    future=True
)

async_session = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False
)

async def init_db():
    # Создаем папку /app/data, если её нет
    data_dir = Path(Config.DATA_DIR)
    data_dir.mkdir(parents=True, exist_ok=True)
    
    # Создаем .gitkeep файл, чтобы bothost.ru не отключал хранилище
    gitkeep_path = data_dir / ".gitkeep"
    if not gitkeep_path.exists():
        gitkeep_path.write_text("# Persistent storage marker\n")
    
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

async def get_session() -> AsyncSession:
    async with async_session() as session:
        yield session
