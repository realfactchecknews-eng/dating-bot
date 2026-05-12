import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from sqlalchemy import select, update
from app.database import async_session
from app.models import Profile

async def clear_photos():
    """Очищает поле photos от локальных путей, оставляя только валидные file_id"""
    async with async_session() as session:
        # Получаем все профили с фото
        result = await session.execute(select(Profile).where(Profile.photos.isnot(None)))
        profiles = result.scalars().all()
        
        for profile in profiles:
            if profile.photos:
                # Фильтруем только валидные file_id (начинаются с AgACAgIAAxk или похожие)
                valid_photos = []
                for photo in profile.photos:
                    # Если это локальный путь (содержит / или .jpg), пропускаем
                    if '/' in photo or '.' in photo or photo.startswith('photos/'):
                        continue
                    # Если это file_id, оставляем
                    if photo.startswith('AgACAgIAAxk') or len(photo) > 20:
                        valid_photos.append(photo)
                
                # Обновляем профиль
                await session.execute(
                    update(Profile).where(Profile.id == profile.id).values(photos=valid_photos)
                )
                print(f"Profile {profile.id}: {len(profile.photos)} -> {len(valid_photos)} photos")
        
        await session.commit()
        print("✅ Photos cleared successfully!")

if __name__ == "__main__":
    asyncio.run(clear_photos())
