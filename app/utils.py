import os
import aiohttp
import logging
from typing import Optional
from aiogram import Bot
from aiogram.types import InputFile, FSInputFile
from sqlalchemy import select, func, and_, or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import User, Profile, Rating, Match, Like
from app.config import Config
from app.database import async_session

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def download_photo(bot: Bot, file_id: str, user_id: int, photo_index: int) -> str:
    file = await bot.get_file(file_id)
    file_path = f"photos/{user_id}_{photo_index}.jpg"
    
    await bot.download_file(file.file_path, file_path)
    return file_path

def get_psl_description(score: int) -> str:
    return Config.PSL_SCALE.get(score, "Unknown")

def get_appeal_description(score: int) -> str:
    return Config.APPEAL_SCALE.get(score, "Unknown")

def format_profile_text(profile: Profile, user: User) -> str:
    gender_icon = "👨" if profile.gender == "male" else "👩"
    orientation_text = Config.ORIENTATIONS.get(profile.orientation, profile.orientation)
    
    text = f"""
{gender_icon} <b>{profile.name}</b>, {profile.age}
🏙 {profile.city or 'Не указан'}
💜 {orientation_text}

📄 <b>О себе:</b>
{profile.bio or 'Нет описания'}
"""
    
    if profile.psl_votes_count >= Config.MIN_VOTES_FOR_RATING:
        psl_desc = get_psl_description(int(profile.psl_rating))
        text += f"\n📊 <b>PSL:</b> {profile.psl_rating:.1f}/10 ({psl_desc}) • {profile.psl_votes_count} голосов"
    
    if profile.appeal_votes_count >= Config.MIN_VOTES_FOR_RATING:
        appeal_desc = get_appeal_description(int(profile.appeal_rating))
        text += f"\n💖 <b>APPEAL:</b> {profile.appeal_rating:.1f}/10 ({appeal_desc}) • {profile.appeal_votes_count} голосов"
    
    return text

async def get_or_create_user(session: AsyncSession, telegram_id: int, username: Optional[str] = None) -> User:
    result = await session.execute(select(User).where(User.telegram_id == telegram_id))
    user = result.scalar_one_or_none()
    
    if not user:
        user = User(telegram_id=telegram_id, username=username)
        session.add(user)
        try:
            await session.commit()
        except IntegrityError:
            await session.rollback()
            result = await session.execute(select(User).where(User.telegram_id == telegram_id))
            user = result.scalar_one()
    else:
        user.last_activity = func.now()
        if username:
            user.username = username
        await session.commit()
    
    return user

async def get_profile_by_telegram_id(session: AsyncSession, telegram_id: int) -> Optional[Profile]:
    result = await session.execute(
        select(Profile).join(User).where(User.telegram_id == telegram_id)
    )
    return result.scalar_one_or_none()

async def update_user_rating(session: AsyncSession, user_id: int):
    result = await session.execute(
        select(func.avg(Rating.psl_score), func.count(Rating.id))
        .where(Rating.rated_id == user_id)
    )
    psl_data = result.one()
    
    result = await session.execute(
        select(func.avg(Rating.appeal_score), func.count(Rating.id))
        .where(Rating.rated_id == user_id)
    )
    appeal_data = result.one()
    
    profile_result = await session.execute(
        select(Profile).where(Profile.user_id == user_id)
    )
    profile = profile_result.scalar_one_or_none()
    
    if profile:
        if psl_data[1] > 0:
            profile.psl_rating = round(psl_data[0], 1)
            profile.psl_votes_count = psl_data[1]
        if appeal_data[1] > 0:
            profile.appeal_rating = round(appeal_data[0], 1)
            profile.appeal_votes_count = appeal_data[1]
        await session.commit()

async def check_mutual_like(session: AsyncSession, user1_id: int, user2_id: int) -> bool:
    like1 = await session.execute(
        select(Like).where(
            and_(Like.from_user_id == user1_id, Like.to_user_id == user2_id, Like.is_like == True)
        )
    )
    like2 = await session.execute(
        select(Like).where(
            and_(Like.from_user_id == user2_id, Like.to_user_id == user1_id, Like.is_like == True)
        )
    )
    
    return like1.scalar_one_or_none() is not None and like2.scalar_one_or_none() is not None

async def create_match(session: AsyncSession, user1_id: int, user2_id: int):
    u1, u2 = sorted([user1_id, user2_id])
    
    result = await session.execute(
        select(Match).where(
            and_(Match.user1_id == u1, Match.user2_id == u2)
        )
    )
    existing = result.scalar_one_or_none()
    
    if not existing:
        from datetime import datetime
        match = Match(
            user1_id=u1,
            user2_id=u2,
            is_mutual=True,
            matched_at=datetime.utcnow()
        )
        session.add(match)
        await session.commit()
        return True
    return False

async def get_search_profiles(session: AsyncSession, user_id: int, gender_filter: str = None, 
                             orientation_filter: str = None, limit: int = 10):
    user_result = await session.execute(
        select(User, Profile).join(Profile).where(User.id == user_id)
    )
    user_data = user_result.one_or_none()
    
    if not user_data:
        return []
    
    user, profile = user_data
    
    query = select(Profile, User).join(User).where(
        and_(
            Profile.user_id != user_id,
            Profile.is_visible == True,
            User.is_banned == False
        )
    )
    
    if gender_filter:
        query = query.where(Profile.gender == gender_filter)
    
    if profile.orientation == "straight":
        if profile.gender == "male":
            query = query.where(Profile.gender == "female", Profile.orientation.in_(["straight", "bisexual"]))
        else:
            query = query.where(Profile.gender == "male", Profile.orientation.in_(["straight", "bisexual"]))
    elif profile.orientation == "gay":
        query = query.where(Profile.gender == "male", Profile.orientation.in_(["gay", "bisexual"]))
    elif profile.orientation == "lesbian":
        query = query.where(Profile.gender == "female", Profile.orientation.in_(["lesbian", "bisexual"]))
    elif profile.orientation == "bisexual":
        preferred_genders = []
        if profile.gender == "male":
            query = query.where(
                or_(
                    and_(Profile.gender == "female", Profile.orientation.in_(["straight", "bisexual"])),
                    and_(Profile.gender == "male", Profile.orientation.in_(["gay", "bisexual"]))
                )
            )
        else:
            query = query.where(
                or_(
                    and_(Profile.gender == "male", Profile.orientation.in_(["straight", "bisexual"])),
                    and_(Profile.gender == "female", Profile.orientation.in_(["lesbian", "bisexual"]))
                )
            )
    
    query = query.order_by(func.random()).limit(limit)
    
    result = await session.execute(query)
    return result.all()

async def get_random_profile_for_rating(session: AsyncSession, user_id: int):
    result = await session.execute(
        select(Rating.rated_id).where(Rating.rater_id == user_id)
    )
    rated_ids = [r[0] for r in result.all()]
    
    query = select(Profile, User).join(User).where(
        and_(
            Profile.user_id != user_id,
            ~Profile.user_id.in_(rated_ids) if rated_ids else True,
            Profile.is_visible == True,
            User.is_banned == False
        )
    ).order_by(func.random()).limit(1)
    
    result = await session.execute(query)
    return result.one_or_none()

async def get_user_matches(session: AsyncSession, user_id: int):
    result = await session.execute(
        select(Match).where(
            or_(Match.user1_id == user_id, Match.user2_id == user_id),
            Match.is_mutual == True
        )
    )
    matches = result.scalars().all()
    
    match_data = []
    for match in matches:
        other_id = match.user2_id if match.user1_id == user_id else match.user1_id
        profile_result = await session.execute(
            select(Profile).where(Profile.user_id == other_id)
        )
        other_profile = profile_result.scalar_one_or_none()
        if other_profile:
            match_data.append({
                "user_id": other_id,
                "name": other_profile.name,
                "profile": other_profile
            })
    
    return match_data

def is_admin(telegram_id: int) -> bool:
    return telegram_id in Config.ADMIN_IDS
