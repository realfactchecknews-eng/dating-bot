import logging
from datetime import datetime
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from sqlalchemy import select, func, update, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.states import AdminStates
from app.models import User, Profile, Rating, Match, Statistic
from app.keyboards import get_admin_keyboard, get_back_keyboard, get_main_menu_keyboard
from app.utils import is_admin
from app.database import async_session

router = Router()
logger = logging.getLogger(__name__)

@router.callback_query(F.data == "admin_panel")
async def admin_panel(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("Нет доступа!")
        return
    await callback.message.edit_text(
        "🔧 <b>Панель администратора</b>",
        parse_mode="HTML",
        reply_markup=get_admin_keyboard()
    )
    await callback.answer()

@router.callback_query(F.data == "admin_stats")
async def admin_stats(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("Нет доступа!")
        return
    
    async with async_session() as session:
        total_users = await session.execute(select(func.count(User.id)))
        total_users = total_users.scalar()
        
        active_users = await session.execute(
            select(func.count(User.id)).where(User.is_active == True)
        )
        active_users = active_users.scalar()
        
        total_profiles = await session.execute(select(func.count(Profile.id)))
        total_profiles = total_profiles.scalar()
        
        total_ratings = await session.execute(select(func.count(Rating.id)))
        total_ratings = total_ratings.scalar()
        
        total_matches = await session.execute(
            select(func.count(Match.id)).where(Match.is_mutual == True)
        )
        total_matches = total_matches.scalar()
        
        banned_users = await session.execute(
            select(func.count(User.id)).where(User.is_banned == True)
        )
        banned_users = banned_users.scalar()
        
        avg_psl = await session.execute(select(func.avg(Profile.psl_rating)))
        avg_psl = avg_psl.scalar() or 0
        
        avg_appeal = await session.execute(select(func.avg(Profile.appeal_rating)))
        avg_appeal = avg_appeal.scalar() or 0
        
        top_rated = await session.execute(
            select(Profile).where(Profile.psl_votes_count >= 5)
            .order_by(Profile.psl_rating.desc())
            .limit(5)
        )
        top_rated = top_rated.scalars().all()
        
        stats_text = f"""
📊 <b>Статистика бота</b>

👥 Пользователей: {total_users}
✅ Активных: {active_users}
👤 Профилей: {total_profiles}
⭐ Оценок: {total_ratings}
💘 Мэтчей: {total_matches}
🚫 Забанено: {banned_users}

📊 Средний PSL: {avg_psl:.1f}/10
💖 Средний APPEAL: {avg_appeal:.1f}/10

🏆 Топ по PSL рейтингу:
"""
        for i, profile in enumerate(top_rated, 1):
            stats_text += f"{i}. {profile.name} - {profile.psl_rating:.1f}/10\n"
        
        await callback.message.edit_text(
            stats_text,
            parse_mode="HTML",
            reply_markup=get_admin_keyboard()
        )
    await callback.answer()

@router.callback_query(F.data == "admin_broadcast")
async def admin_broadcast(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("Нет доступа!")
        return
    
    await callback.message.edit_text(
        "📢 Введи сообщение для рассылки:\n\n"
        "(отправь /cancel для отмены)",
        reply_markup=get_back_keyboard()
    )
    await state.set_state(AdminStates.broadcast)
    await callback.answer()

@router.message(AdminStates.broadcast)
async def process_broadcast(message: Message, state: FSMContext, bot: Bot):
    if message.text == "/cancel":
        await state.clear()
        await message.answer("Рассылка отменена", reply_markup=get_main_menu_keyboard(is_admin=True))
        return
    
    async with async_session() as session:
        result = await session.execute(
            select(User.telegram_id).where(User.is_banned == False)
        )
        users = result.all()
        
        sent = 0
        failed = 0
        
        for user_id in users:
            try:
                await bot.copy_message(
                    chat_id=user_id[0],
                    from_chat_id=message.chat.id,
                    message_id=message.message_id
                )
                sent += 1
            except Exception as e:
                logger.error(f"Failed to send to {user_id[0]}: {e}")
                failed += 1
        
        await message.answer(
            f"✅ Рассылка завершена!\n"
            f"Отправлено: {sent}\n"
            f"Не удалось: {failed}",
            reply_markup=get_main_menu_keyboard(is_admin=True)
        )
    
    await state.clear()

@router.callback_query(F.data == "admin_ban")
async def admin_ban(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("Нет доступа!")
        return
    
    await callback.message.edit_text(
        "🚫 Введи Telegram ID пользователя для бана:\n\n"
        "(отправь /cancel для отмены)",
        reply_markup=get_back_keyboard()
    )
    await state.set_state(AdminStates.ban_user)
    await callback.answer()

@router.message(AdminStates.ban_user)
async def process_ban(message: Message, state: FSMContext):
    if message.text == "/cancel":
        await state.clear()
        await message.answer("Отменено", reply_markup=get_main_menu_keyboard(is_admin=True))
        return
    
    try:
        user_id = int(message.text)
        async with async_session() as session:
            result = await session.execute(
                update(User).where(User.telegram_id == user_id).values(is_banned=True)
            )
            await session.commit()
            
            if result.rowcount > 0:
                await message.answer(
                    f"✅ Пользователь {user_id} забанен",
                    reply_markup=get_main_menu_keyboard(is_admin=True)
                )
            else:
                await message.answer(
                    "❌ Пользователь не найден",
                    reply_markup=get_main_menu_keyboard(is_admin=True)
                )
    except ValueError:
        await message.answer("Введи корректный ID (число)")
        return
    
    await state.clear()

@router.callback_query(F.data == "admin_unban")
async def admin_unban(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("Нет доступа!")
        return
    
    await callback.message.edit_text(
        "✅ Введи Telegram ID пользователя для разбана:\n\n"
        "(отправь /cancel для отмены)",
        reply_markup=get_back_keyboard()
    )
    await state.set_state(AdminStates.unban_user)
    await callback.answer()

@router.message(AdminStates.unban_user)
async def process_unban(message: Message, state: FSMContext):
    if message.text == "/cancel":
        await state.clear()
        await message.answer("Отменено", reply_markup=get_main_menu_keyboard(is_admin=True))
        return
    
    try:
        user_id = int(message.text)
        async with async_session() as session:
            result = await session.execute(
                update(User).where(User.telegram_id == user_id).values(is_banned=False)
            )
            await session.commit()
            
            if result.rowcount > 0:
                await message.answer(
                    f"✅ Пользователь {user_id} разбанен",
                    reply_markup=get_main_menu_keyboard(is_admin=True)
                )
            else:
                await message.answer(
                    "❌ Пользователь не найден",
                    reply_markup=get_main_menu_keyboard(is_admin=True)
                )
    except ValueError:
        await message.answer("Введи корректный ID (число)")
        return
    
    await state.clear()

@router.callback_query(F.data == "admin_users")
async def admin_users(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("Нет доступа!")
        return
    
    async with async_session() as session:
        result = await session.execute(
            select(User, Profile)
            .join(Profile, User.id == Profile.user_id, isouter=True)
            .order_by(User.created_at.desc())
            .limit(10)
        )
        users = result.all()
        
        users_text = "📋 <b>Последние пользователи:</b>\n\n"
        for user, profile in users:
            status = "🚫" if user.is_banned else "✅"
            name = profile.name if profile else "Нет профиля"
            users_text += f"{status} ID: <code>{user.telegram_id}</code> - {name}\n"
        
        await callback.message.edit_text(
            users_text,
            parse_mode="HTML",
            reply_markup=get_admin_keyboard()
        )
    await callback.answer()

@router.message(Command("stats"))
async def cmd_stats(message: Message):
    if not is_admin(message.from_user.id):
        return
    
    async with async_session() as session:
        total_users = await session.execute(select(func.count(User.id)))
        total_users = total_users.scalar()
        
        today = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        new_today = await session.execute(
            select(func.count(User.id)).where(User.created_at >= today)
        )
        new_today = new_today.scalar()
        
        await message.answer(
            f"📊 Статистика:\n"
            f"Всего пользователей: {total_users}\n"
            f"Новых сегодня: {new_today}"
        )
