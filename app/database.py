import os
from pathlib import Path
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import declarative_base
from sqlalchemy.engine.base import Engine
from sqlalchemy import text
from app.config import Config

# Monkey patch to completely disable SQLAlchemy logging
def _disabled_log_info(self, *args, **kwargs):
    """Completely disabled logging to prevent RecursionError"""
    pass

def _disabled_log_error(self, *args, **kwargs):
    """Completely disabled logging to prevent RecursionError"""
    pass

# Apply monkey patch
Engine._log_info = _disabled_log_info
Engine._log_error = _disabled_log_error

Base = declarative_base()

engine = create_async_engine(
    Config.DATABASE_URL,
    echo=False,  # Disable SQL logging to prevent recursion errors
    echo_pool=False,  # Disable pool logging
    pool_pre_ping=True,
    pool_recycle=3600,
    future=True,
    connect_args={
        "server_settings": {"application_name": "dating_bot"},
        "prepared_statement_cache_size": 0,  # Disable prepared statement cache
    },
    # Disable all logging
    logging_name=None
)

async_session = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False
)

async def init_db():
    # Create tables without DISCARD ALL to avoid transaction issues
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

async def get_session() -> AsyncSession:
    async with async_session() as session:
        yield session
