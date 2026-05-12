import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from app.database import init_db

async def create_database():
    print("Initializing database...")
    await init_db()
    print("Database created successfully!")

if __name__ == "__main__":
    asyncio.run(create_database())
