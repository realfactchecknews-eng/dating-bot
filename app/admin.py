import logging
from datetime import datetime
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from sqlalchemy import select, func, update, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.states import AdminStates, AdminReportStates
from app.models import User, Profile, Rating, Match, Statistic, Report
from app.keyboards import get_admin_keyboard, get_back_keyboard, get_main_menu_keyboard, get_reports_list_keyboard, get_report_detail_keyboard
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

@router.callback_query(F.data == "admin_clear_photos")
async def admin_clear_photos(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("Нет доступа!")
        return
    
    async with async_session() as session:
        # Получаем все профили с фото
        result = await session.execute(select(Profile).where(Profile.photos.isnot(None)))
        profiles = result.scalars().all()
        
        cleared_count = 0
        for profile in profiles:
            if profile.photos:
                # Фильтруем только валидные file_id
                valid_photos = []
                for photo in profile.photos:
                    # Если это локальный путь, пропускаем
                    if '/' in photo or '.' in photo or photo.startswith('photos/'):
                        continue
                    # Если это file_id, оставляем
                    if photo.startswith('AgACAgIAAxk') or len(photo) > 20:
                        valid_photos.append(photo)
                
                # Обновляем профиль
                await session.execute(
                    update(Profile).where(Profile.id == profile.id).values(photos=valid_photos)
                )
                cleared_count += len(profile.photos) - len(valid_photos)
        
        await session.commit()
        
        await callback.message.edit_text(
            f"🧹 <b>Очистка завершена!</b>\n\n"
            f"Удалено некорректных путей: {cleared_count}\n"
            f"Обработано профилей: {len(profiles)}",
            parse_mode="HTML",
            reply_markup=get_admin_keyboard()
        )
    await callback.answer("Фото очищены!")

# Обработчики для управления репортами
@router.callback_query(F.data == "admin_reports")
async def admin_reports(callback: CallbackQuery):
    logger.info(f"Admin reports callback received from user {callback.from_user.id}")
    
    if not is_admin(callback.from_user.id):
        logger.warning(f"Non-admin user {callback.from_user.id} tried to access admin reports")
        await callback.answer("Нет доступа!")
        return
    
    logger.info("Admin accessing reports...")
    
    try:
        async with async_session() as session:
            # Получаем нерешённые репорты
            result = await session.execute(
                select(Report, User).join(User, Report.from_user_id == User.id)
                .where(Report.is_resolved == False)
                .order_by(Report.created_at.desc()).limit(10)
            )
            reports = result.all()
            
            if not reports:
                text = "🚨 <b>Репорты</b>\n\n✅ Нет нерешённых репортов!"
            else:
                text = f"🚨 <b>Нерешённые репорты ({len(reports)}):</b>\n\n"
                for i, (report, user) in enumerate(reports, 1):
                    status_emoji = {"bug": "🐛", "user": "👤", "profile": "📝", "other": "📄"}
                    emoji = status_emoji.get(report.report_type, "📄")
                    text += f"{i}. {emoji} <b>#{report.id}</b> от @{user.username or 'user'}\n"
                    text += f"💬 {report.message[:50]}{'...' if len(report.message) > 50 else ''}\n"
                    text += f"🕐 {report.created_at.strftime('%d.%m.%Y %H:%M')}\n\n"
            
            try:
                await callback.message.edit_text(
                    text,
                    parse_mode="HTML",
                    reply_markup=get_reports_list_keyboard(reports)
                )
            except Exception as e:
                if "message is not modified" in str(e):
                    # Сообщение не изменилось, это нормально
                    await callback.answer()
                else:
                    # Другая ошибка
                    logger.error(f"Error updating reports list: {e}")
                    raise
    except Exception as e:
        logger.error(f"Error fetching reports: {e}")
        await callback.message.edit_text(
            "❌ Ошибка при загрузке репортов. Попробуй позже.",
            reply_markup=get_admin_keyboard()
        )
    await callback.answer()

@router.callback_query(F.data == "admin_resolved_reports")
async def admin_resolved_reports(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("Нет доступа!")
        return
    
    async with async_session() as session:
        # Получаем решённые репорты
        result = await session.execute(
            select(Report, User).join(User, Report.from_user_id == User.id)
            .where(Report.is_resolved == True)
            .order_by(Report.created_at.desc()).limit(10)
        )
        reports = result.all()
        
        if not reports:
            text = "✅ <b>Решённые репорты</b>\n\nНет решённых репортов!"
        else:
            text = f"✅ <b>Решённые репорты ({len(reports)}):</b>\n\n"
            for i, (report, user) in enumerate(reports, 1):
                status_emoji = {"bug": "🐛", "user": "👤", "profile": "📝", "other": "📄"}
                emoji = status_emoji.get(report.report_type, "📄")
                text += f"{i}. {emoji} <b>#{report.id}</b> от @{user.username or 'user'}\n"
                text += f"💬 {report.message[:50]}{'...' if len(report.message) > 50 else ''}\n"
                text += f"🕐 {report.created_at.strftime('%d.%m.%Y %H:%M')}\n\n"
        
        try:
            await callback.message.edit_text(
                text,
                parse_mode="HTML",
                reply_markup=get_reports_list_keyboard(reports)
            )
        except Exception as e:
            if "message is not modified" in str(e):
                # Сообщение не изменилось, это нормально
                await callback.answer()
            else:
                # Другая ошибка
                logger.error(f"Error updating resolved reports list: {e}")
                raise
    await callback.answer()

@router.callback_query(F.data.startswith("view_report_"))
async def view_report(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("Нет доступа!")
        return
    
    report_id = int(callback.data.split("_")[2])
    
    async with async_session() as session:
        result = await session.execute(
            select(Report, User).join(User, Report.from_user_id == User.id).where(Report.id == report_id)
        )
        report_data = result.one_or_none()
        
        if not report_data:
            await callback.answer("Репорт не найден!")
            return
        
        report, user = report_data
        
        status_emoji = {"bug": "🐛", "user": "👤", "profile": "📝", "other": "📄"}
        emoji = status_emoji.get(report.report_type, "📄")
        status_text = "✅ Решён" if report.is_resolved else "⏳ В ожидании"
        
        text = (
            f"🚨 <b>Репорт #{report.id}</b>\n\n"
            f"👤 От: @{user.username or 'пользователь'} (ID: {user.telegram_id})\n"
            f"📝 Тип: {emoji} {report.report_type}\n"
            f"📊 Статус: {status_text}\n"
            f"🕐 Создан: {report.created_at.strftime('%d.%m.%Y %H:%M')}\n\n"
            f"💬 <b>Сообщение:</b>\n{report.message}"
        )
        
        await callback.message.edit_text(
            text,
            parse_mode="HTML",
            reply_markup=get_report_detail_keyboard(report_id, report.is_resolved)
        )
    await callback.answer()

@router.callback_query(F.data.startswith("reply_report_"))
async def reply_report(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("Нет доступа!")
        return
    
    report_id = int(callback.data.split("_")[2])
    
    await state.update_data(report_id=report_id)
    await callback.message.answer("💬 Введи ответ на репорт:")
    await state.set_state(AdminReportStates.reply)
    await callback.answer()

@router.message(AdminReportStates.reply)
async def process_reply_report(message: Message, state: FSMContext, bot: Bot):
    data = await state.get_data()
    report_id = data.get("report_id")
    
    if not report_id:
        await message.answer("Ошибка: ID репорта не найден")
        await state.clear()
        return
    
    async with async_session() as session:
        # Получаем информацию о репорте
        result = await session.execute(
            select(Report, User).join(User, Report.from_user_id == User.id).where(Report.id == report_id)
        )
        report_data = result.one_or_none()
        
        if not report_data:
            await message.answer("Репорт не найден!")
            await state.clear()
            return
        
        report, user = report_data
        
        # Отправляем ответ пользователю
        try:
            await bot.send_message(
                user.telegram_id,
                f"💬 <b>Ответ на твой репорт:</b>\n\n"
                f"{message.text}\n\n"
                f"Спасибо за обращение! 👍",
                parse_mode="HTML"
            )
            
            await message.answer(
                f"✅ Ответ отправлен пользователю @{user.username or 'user'}"
            )
            
        except Exception as e:
            logger.error(f"Failed to send reply to user {user.telegram_id}: {e}")
            await message.answer("❌ Не удалось отправить ответ пользователю")
        
        await state.clear()

@router.callback_query(F.data.startswith("resolve_report_"))
async def resolve_report(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("Нет доступа!")
        return
    
    report_id = int(callback.data.split("_")[2])
    logger.info(f"Resolving report {report_id}")
    
    try:
        async with async_session() as session:
            await session.execute(
                update(Report).where(Report.id == report_id).values(is_resolved=True)
            )
            await session.commit()
            
            # Обновляем интерфейс
            result = await session.execute(
                select(Report, User).join(User, Report.from_user_id == User.id).where(Report.id == report_id)
            )
            report_data = result.one_or_none()
            
            if report_data:
                report, user = report_data
                status_emoji = {"bug": "🐛", "user": "👤", "profile": "📝", "other": "📄"}
                emoji = status_emoji.get(report.report_type, "📄")
                
                text = (
                    f"🚨 <b>Репорт #{report.id}</b>\n\n"
                    f"👤 От: @{user.username or 'пользователь'} (ID: {user.telegram_id})\n"
                    f"📝 Тип: {emoji} {report.report_type}\n"
                    f"📊 Статус: ✅ Решён\n"
                    f"🕐 Создан: {report.created_at.strftime('%d.%m.%Y %H:%M')}\n\n"
                    f"💬 <b>Сообщение:</b>\n{report.message}"
                )
                
                await callback.message.edit_text(
                    text,
                    parse_mode="HTML",
                    reply_markup=get_report_detail_keyboard(report_id, True)
                )
            
            await callback.answer("✅ Репорт отмечен как решённый!")
            
    except Exception as e:
        logger.error(f"Error resolving report {report_id}: {e}")
        await callback.answer("❌ Ошибка при изменении статуса!")

@router.callback_query(F.data.startswith("reopen_report_"))
async def reopen_report(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("Нет доступа!")
        return
    
    report_id = int(callback.data.split("_")[2])
    logger.info(f"Reopening report {report_id}")
    
    try:
        async with async_session() as session:
            await session.execute(
                update(Report).where(Report.id == report_id).values(is_resolved=False)
            )
            await session.commit()
            
            # Обновляем интерфейс
            result = await session.execute(
                select(Report, User).join(User, Report.from_user_id == User.id).where(Report.id == report_id)
            )
            report_data = result.one_or_none()
            
            if report_data:
                report, user = report_data
                status_emoji = {"bug": "🐛", "user": "👤", "profile": "📝", "other": "📄"}
                emoji = status_emoji.get(report.report_type, "📄")
                
                text = (
                    f"🚨 <b>Репорт #{report.id}</b>\n\n"
                    f"👤 От: @{user.username or 'пользователь'} (ID: {user.telegram_id})\n"
                    f"📝 Тип: {emoji} {report.report_type}\n"
                    f"📊 Статус: ⏳ В ожидании\n"
                    f"🕐 Создан: {report.created_at.strftime('%d.%m.%Y %H:%M')}\n\n"
                    f"💬 <b>Сообщение:</b>\n{report.message}"
                )
                
                await callback.message.edit_text(
                    text,
                    parse_mode="HTML",
                    reply_markup=get_report_detail_keyboard(report_id, False)
                )
            
            await callback.answer("🔄 Репорт переоткрыт!")
            
    except Exception as e:
        logger.error(f"Error reopening report {report_id}: {e}")
        await callback.answer("❌ Ошибка при изменении статуса!")

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
