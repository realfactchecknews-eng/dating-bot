import os
from pathlib import Path
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import declarative_base
from app.config import Config

Base = declarative_base()

engine = create_async_engine(
    Config.DATABASE_URL,
    echo=Config.DEBUG,
    future=True,
    connect_args={"server_settings": {"application_name": "dating_bot"}}
)

async_session = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False
)

async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

async def get_session() -> AsyncSession:
    async with async_session() as session:
        yield session
