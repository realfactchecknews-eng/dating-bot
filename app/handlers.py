import os
import logging
from typing import Optional
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, FSInputFile
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.enums import ParseMode
from sqlalchemy import select, and_, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.states import RegistrationStates, ProfileEditStates, RatingStates, AdminStates, SearchStates
from app.models import User, Profile, Rating, Like, Match
from app.keyboards import (
    get_main_menu_keyboard, get_registration_keyboard, get_gender_keyboard,
    get_orientation_keyboard, get_psl_rating_keyboard, get_appeal_rating_keyboard,
    get_search_action_keyboard, get_rating_keyboard, get_profile_edit_keyboard,
    get_confirm_keyboard, get_settings_keyboard, get_admin_keyboard,
    get_back_keyboard, get_matches_keyboard, get_skip_keyboard, get_rating_result_keyboard
)
from app.utils import (
    get_or_create_user, get_profile_by_telegram_id, format_profile_text,
    download_photo, update_user_rating, check_mutual_like, create_match,
    get_search_profiles, get_random_profile_for_rating, get_user_matches,
    is_admin, get_psl_description, get_appeal_description
)
from app.config import Config
from app.database import async_session

router = Router()
logger = logging.getLogger(__name__)

@router.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()
    async with async_session() as session:
        user = await get_or_create_user(session, message.from_user.id, message.from_user.username)
        profile = await get_profile_by_telegram_id(session, message.from_user.id)
        
        if not profile:
            await message.answer(
                "👋 Привет! Добро пожаловать в <b>LOOKSMAX Dating</b>\n\n"
                "Здесь ты найдешь знакомства с оценкой внешности по шкалам:\n"
                "• <b>PSL</b> (Pickup/Seduction/Looks) - объективная привлекательность\n"
                "• <b>APPEAL</b> - общая привлекательность и харизма\n\n"
                "Для начала создай профиль!",
                parse_mode=ParseMode.HTML,
                reply_markup=get_registration_keyboard()
            )
        else:
            await message.answer(
                f"👋 С возвращением, <b>{profile.name}</b>!\n\n"
                f"Твой рейтинг:\n"
                f"📊 PSL: {profile.psl_rating:.1f}/10 ({get_psl_description(int(profile.psl_rating))})\n"
                f"💖 APPEAL: {profile.appeal_rating:.1f}/10 ({get_appeal_description(int(profile.appeal_rating))})",
                parse_mode=ParseMode.HTML,
                reply_markup=get_main_menu_keyboard(is_admin=is_admin(message.from_user.id))
            )

@router.callback_query(F.data == "create_profile")
async def start_registration(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text("Введи свое имя:")
    await state.set_state(RegistrationStates.name)
    await callback.answer()

@router.message(RegistrationStates.name)
async def process_name(message: Message, state: FSMContext):
    if len(message.text) > 50:
        await message.answer("Имя слишком длинное. Введи короче:")
        return
    await state.update_data(name=message.text)
    await message.answer("Сколько тебе лет?")
    await state.set_state(RegistrationStates.age)

@router.message(RegistrationStates.age)
async def process_age(message: Message, state: FSMContext):
    try:
        age = int(message.text)
        if not (18 <= age <= 99):
            await message.answer("Возраст должен быть от 18 до 99 лет:")
            return
        await state.update_data(age=age)
        await message.answer("Выбери пол:", reply_markup=get_gender_keyboard())
        await state.set_state(RegistrationStates.gender)
    except ValueError:
        await message.answer("Введи число:")

@router.callback_query(F.data.startswith("gender_"))
async def process_gender(callback: CallbackQuery, state: FSMContext):
    gender = callback.data.split("_")[1]
    await state.update_data(gender=gender)
    await callback.message.edit_text("Какая у тебя ориентация?", reply_markup=get_orientation_keyboard())
    await state.set_state(RegistrationStates.orientation)
    await callback.answer()

@router.callback_query(F.data.startswith("orientation_"))
async def process_orientation(callback: CallbackQuery, state: FSMContext):
    orientation = callback.data.split("_")[1]
    await state.update_data(orientation=orientation)
    await callback.message.edit_text(
        "В каком городе ты живешь?",
        reply_markup=get_skip_keyboard()
    )
    await state.set_state(RegistrationStates.city)
    await callback.answer()

@router.callback_query(F.data == "skip_step")
async def skip_city(callback: CallbackQuery, state: FSMContext):
    await state.update_data(city="")
    await callback.message.edit_text("Расскажи о себе (биография):")
    await state.set_state(RegistrationStates.bio)
    await callback.answer()

@router.message(RegistrationStates.city)
async def process_city(message: Message, state: FSMContext):
    await state.update_data(city=message.text)
    await message.answer("Расскажи о себе (биография):")
    await state.set_state(RegistrationStates.bio)

@router.message(RegistrationStates.bio)
async def process_bio(message: Message, state: FSMContext):
    if len(message.text) > 500:
        await message.answer("Слишком длинно. Максимум 500 символов:")
        return
    await state.update_data(bio=message.text)
    await message.answer("Отправь свое фото (до 5 фото, отправляй по одному, напиши 'готово' когда закончишь):")
    await state.set_state(RegistrationStates.photos)
    await state.update_data(photos=[])

@router.message(RegistrationStates.photos, F.photo)
async def process_photo(message: Message, state: FSMContext, bot: Bot):
    data = await state.get_data()
    photos = data.get("photos", [])
    
    if len(photos) >= 5:
        await message.answer("Максимум 5 фото. Напиши 'готово':")
        return
    
    file_id = message.photo[-1].file_id
    photos.append(file_id)
    await state.update_data(photos=photos)
    
    await message.answer(f"Фото {len(photos)}/5 добавлено. Отправь еще или напиши 'готово':")

@router.message(RegistrationStates.photos, F.text.lower() == "готово")
async def finish_photos(message: Message, state: FSMContext):
    data = await state.get_data()
    photos = data.get("photos", [])
    
    if not photos:
        await message.answer("Нужно хотя бы одно фото!")
        return
    
    text = f"""
<b>Проверь свой профиль:</b>

👤 {data['name']}, {data['age']}
🏙 {data.get('city', 'Не указан')}
💜 {Config.ORIENTATIONS.get(data['orientation'])}

📄 О себе:
{data['bio']}

Фото: {len(photos)} шт.
"""
    await message.answer(text, parse_mode=ParseMode.HTML, reply_markup=get_confirm_keyboard())
    await state.set_state(RegistrationStates.confirm)

@router.callback_query(F.data == "confirm_yes")
async def confirm_profile(callback: CallbackQuery, state: FSMContext, bot: Bot):
    data = await state.get_data()
    async with async_session() as session:
        user = await get_or_create_user(session, callback.from_user.id, callback.from_user.username)
        
        photos_paths = []
        for i, file_id in enumerate(data["photos"]):
            path = await download_photo(bot, file_id, user.id, i)
            photos_paths.append(path)
        
        profile = Profile(
            user_id=user.id,
            name=data["name"],
            age=data["age"],
            gender=data["gender"],
            orientation=data["orientation"],
            city=data.get("city", ""),
            bio=data["bio"],
            photos=photos_paths
        )
        session.add(profile)
        await session.commit()
        
        await callback.message.edit_text(
            "✅ Профиль создан! Добро пожаловать в LOOKSMAX Dating!",
            reply_markup=get_main_menu_keyboard(is_admin=is_admin(callback.from_user.id))
        )
    await state.clear()
    await callback.answer()

@router.callback_query(F.data == "confirm_no")
async def edit_profile(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text("Что хочешь изменить?", reply_markup=get_profile_edit_keyboard())
    await callback.answer()

@router.callback_query(F.data == "main_menu")
async def main_menu(callback: CallbackQuery):
    if callback.message.photo:
        await callback.message.delete()
        await callback.message.answer(
            "Главное меню:",
            reply_markup=get_main_menu_keyboard(is_admin=is_admin(callback.from_user.id))
        )
    else:
        await callback.message.edit_text(
            "Главное меню:",
            reply_markup=get_main_menu_keyboard(is_admin=is_admin(callback.from_user.id))
        )
    await callback.answer()

@router.callback_query(F.data == "my_profile")
async def show_my_profile(callback: CallbackQuery, bot: Bot):
    async with async_session() as session:
        profile = await get_profile_by_telegram_id(session, callback.from_user.id)
        if not profile:
            await callback.message.edit_text("У тебя нет профиля!")
            return
        
        user_result = await session.execute(select(User).where(User.telegram_id == callback.from_user.id))
        user = user_result.scalar_one()
        
        text = format_profile_text(profile, user)
        
        if profile.photos:
            photo_path = profile.photos[0]
            if os.path.exists(photo_path):
                photo = FSInputFile(photo_path)
                await callback.message.delete()
                await bot.send_photo(
                    callback.from_user.id,
                    photo=photo,
                    caption=text,
                    parse_mode=ParseMode.HTML,
                    reply_markup=get_profile_edit_keyboard()
                )
            else:
                await callback.message.edit_text(text + "\n\n<i>(Фото не найдено)</i>", 
                    parse_mode=ParseMode.HTML, reply_markup=get_profile_edit_keyboard())
        else:
            await callback.message.edit_text(text, parse_mode=ParseMode.HTML, 
                reply_markup=get_profile_edit_keyboard())
    await callback.answer()

search_cache = {}

@router.callback_query(F.data == "search")
async def start_search(callback: CallbackQuery):
    async with async_session() as session:
        user_result = await session.execute(
            select(User).where(User.telegram_id == callback.from_user.id)
        )
        user = user_result.scalar_one_or_none()
        
        if not user:
            await callback.answer("Сначала создай профиль!")
            return
        
        profiles = await get_search_profiles(session, user.id, limit=10)
        
        if not profiles:
            await callback.message.edit_text(
                "Пока нет подходящих анкет 😔\nПопробуй позже или оценивай других пользователей!",
                reply_markup=get_back_keyboard()
            )
            await callback.answer()
            return
        
        search_cache[callback.from_user.id] = profiles
        await show_next_profile(callback, session)

async def show_next_profile(callback: CallbackQuery, session: AsyncSession):
    user_id = callback.from_user.id
    profiles = search_cache.get(user_id, [])
    
    if not profiles:
        await callback.message.edit_text(
            "Анкеты закончились 😔\nПопробуй позже!",
            reply_markup=get_back_keyboard()
        )
        return
    
    profile, user = profiles.pop(0)
    search_cache[user_id] = profiles
    
    text = format_profile_text(profile, user)
    
    await callback.message.delete()
    
    if profile.photos and os.path.exists(profile.photos[0]):
        photo = FSInputFile(profile.photos[0])
        await callback.bot.send_photo(
            callback.from_user.id,
            photo=photo,
            caption=text,
            parse_mode=ParseMode.HTML,
            reply_markup=get_search_action_keyboard(user.id)
        )
    else:
        await callback.message.answer(
            text,
            parse_mode=ParseMode.HTML,
            reply_markup=get_search_action_keyboard(user.id)
        )

@router.callback_query(F.data == "next_profile")
async def next_profile(callback: CallbackQuery):
    async with async_session() as session:
        await show_next_profile(callback, session)
    await callback.answer()

@router.callback_query(F.data.startswith("like_"))
async def like_profile(callback: CallbackQuery):
    target_id = int(callback.data.split("_")[1])
    async with async_session() as session:
        user_result = await session.execute(
            select(User).where(User.telegram_id == callback.from_user.id)
        )
        user = user_result.scalar_one()
        
        like = Like(from_user_id=user.id, to_user_id=target_id, is_like=True)
        session.add(like)
        await session.commit()
        
        is_mutual = await check_mutual_like(session, user.id, target_id)
        if is_mutual:
            await create_match(session, user.id, target_id)
            
            target_result = await session.execute(
                select(User).where(User.id == target_id)
            )
            target_user = target_result.scalar_one()
            
            await callback.bot.send_message(
                target_user.telegram_id,
                f"💘 У тебя новый мэтч! @{callback.from_user.username or 'пользователь'}"
            )
            await callback.answer("💘 Мэтч! Проверь раздел 'Мэтчи'")
        else:
            await callback.answer("❤️ Лайк отправлен!")
        
        await show_next_profile(callback, session)

@router.callback_query(F.data.startswith("dislike_"))
async def dislike_profile(callback: CallbackQuery):
    target_id = int(callback.data.split("_")[1])
    async with async_session() as session:
        user_result = await session.execute(
            select(User).where(User.telegram_id == callback.from_user.id)
        )
        user = user_result.scalar_one()
        
        like = Like(from_user_id=user.id, to_user_id=target_id, is_like=False)
        session.add(like)
        await session.commit()
    
    await callback.answer("💔 Пропущено")
    async with async_session() as session:
        await show_next_profile(callback, session)

rating_cache = {}

@router.callback_query(F.data == "rate_profiles")
async def start_rating(callback: CallbackQuery, state: FSMContext):
    async with async_session() as session:
        user_result = await session.execute(
            select(User).where(User.telegram_id == callback.from_user.id)
        )
        user = user_result.scalar_one_or_none()
        
        if not user:
            await callback.answer("Сначала создай профиль!")
            return
        
        result = await get_random_profile_for_rating(session, user.id)
        
        if not result:
            await callback.message.edit_text(
                "Нет анкет для оценки 😔 Все уже оценены или пока мало пользователей.",
                reply_markup=get_back_keyboard()
            )
            await callback.answer()
            return
        
        profile, target_user = result
        rating_cache[callback.from_user.id] = target_user.id
        
        text = format_profile_text(profile, target_user)
        text += "\n\n<b>Оцени по шкале 1-10:</b>"
        
        await callback.message.delete()
        
        if profile.photos and os.path.exists(profile.photos[0]):
            photo = FSInputFile(profile.photos[0])
            await callback.bot.send_photo(
                callback.from_user.id,
                photo=photo,
                caption=text,
                parse_mode=ParseMode.HTML,
                reply_markup=get_rating_keyboard(target_user.id)
            )
        else:
            await callback.message.answer(
                text,
                parse_mode=ParseMode.HTML,
                reply_markup=get_rating_keyboard(target_user.id)
            )
    
    await state.set_state(RatingStates.voting)
    await callback.answer()

@router.callback_query(F.data.startswith("show_psl_"))
async def show_psl_rating(callback: CallbackQuery):
    target_id = int(callback.data.split("_")[2])
    await callback.message.edit_reply_markup(reply_markup=get_psl_rating_keyboard(target_id))
    await callback.answer("Выбери PSL оценку (1-10)")

@router.callback_query(F.data.startswith("psl_"))
async def process_psl_rating(callback: CallbackQuery, state: FSMContext):
    parts = callback.data.split("_")
    target_id = int(parts[1])
    psl_score = int(parts[2])
    
    await state.update_data(target_id=target_id, psl_score=psl_score)
    
    psl_desc = get_psl_description(psl_score)
    
    text = (
        f"📊 PSL оценка: <b>{psl_score}/10</b> ({psl_desc})\n\n"
        f"Теперь выбери <b>APPEAL</b> оценку (привлекательность/харизма):"
    )
    
    if callback.message.photo:
        await callback.message.edit_caption(
            caption=text,
            parse_mode=ParseMode.HTML,
            reply_markup=get_appeal_rating_keyboard(target_id)
        )
    else:
        await callback.message.edit_text(
            text,
            parse_mode=ParseMode.HTML,
            reply_markup=get_appeal_rating_keyboard(target_id)
        )
    await callback.answer(f"PSL: {psl_score}/10")

@router.callback_query(F.data.startswith("appeal_"))
async def process_appeal_rating(callback: CallbackQuery, state: FSMContext):
    parts = callback.data.split("_")
    target_id = int(parts[1])
    appeal_score = int(parts[2])
    
    data = await state.get_data()
    psl_score = data.get("psl_score")
    
    if psl_score is None:
        await callback.answer("Ошибка: сначала выбери PSL оценку", show_alert=True)
        return
    
    try:
        async with async_session() as session:
            user_result = await session.execute(
                select(User).where(User.telegram_id == callback.from_user.id)
            )
            user = user_result.scalar_one()
            
            rating = Rating(
                rater_id=user.id,
                rated_id=target_id,
                psl_score=psl_score,
                appeal_score=appeal_score
            )
            session.add(rating)
            await session.commit()
            
            await update_user_rating(session, target_id)
            
            psl_desc = get_psl_description(psl_score)
            appeal_desc = get_appeal_description(appeal_score)
            
            text = (
                f"✅ Оценка сохранена!\n\n"
                f"📊 PSL: {psl_score}/10 ({psl_desc})\n"
                f"💖 APPEAL: {appeal_score}/10 ({appeal_desc})\n\n"
                f"Продолжим оценивать?"
            )
            
            if callback.message.photo:
                await callback.message.edit_caption(
                    caption=text,
                    parse_mode=ParseMode.HTML,
                    reply_markup=get_rating_result_keyboard()
                )
            else:
                await callback.message.edit_text(
                    text,
                    parse_mode=ParseMode.HTML,
                    reply_markup=get_rating_result_keyboard()
                )
        
        await state.clear()
        await callback.answer("Оценка сохранена!")
    except Exception as e:
        logger.error(f"Error saving rating: {e}")
        await callback.answer("Ошибка сохранения оценки", show_alert=True)

@router.callback_query(F.data == "my_matches")
async def show_matches(callback: CallbackQuery):
    async with async_session() as session:
        user_result = await session.execute(
            select(User).where(User.telegram_id == callback.from_user.id)
        )
        user = user_result.scalar_one()
        
        matches = await get_user_matches(session, user.id)
        
        if not matches:
            await callback.message.edit_text(
                "У тебя пока нет мэтчей 😔\n\n"
                "Лайкай понравившихся людей и жди взаимности!",
                reply_markup=get_back_keyboard()
            )
        else:
            await callback.message.edit_text(
                f"💘 Твои мэтчи ({len(matches)}):\n\n"
                "Нажми на имя, чтобы начать чат",
                reply_markup=get_matches_keyboard(matches)
            )
    await callback.answer()

@router.callback_query(F.data == "settings")
async def settings(callback: CallbackQuery):
    await callback.message.edit_text(
        "⚙️ Настройки профиля:",
        reply_markup=get_settings_keyboard()
    )
    await callback.answer()

@router.callback_query(F.data == "toggle_visibility")
async def toggle_visibility(callback: CallbackQuery):
    async with async_session() as session:
        profile = await get_profile_by_telegram_id(session, callback.from_user.id)
        if profile:
            profile.is_visible = not profile.is_visible
            await session.commit()
            status = "видимый" if profile.is_visible else "скрытый"
            await callback.answer(f"Профиль теперь {status}!")

@router.callback_query(F.data == "delete_profile")
async def delete_profile(callback: CallbackQuery):
    async with async_session() as session:
        user_result = await session.execute(
            select(User).where(User.telegram_id == callback.from_user.id)
        )
        user = user_result.scalar_one_or_none()
        
        if user:
            await session.execute(delete(Profile).where(Profile.user_id == user.id))
            await session.execute(delete(User).where(User.id == user.id))
            await session.commit()
        
        await callback.message.edit_text(
            "😔 Твой профиль удален.\n\n"
            "Если передумаешь, создай новый через /start"
        )
    await callback.answer()
