import logging
from typing import Optional
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.enums import ParseMode
from sqlalchemy import select, and_, or_, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.states import RegistrationStates, ProfileEditStates, RatingStates, AdminStates, SearchStates, NewsStates, ChatStates, ReportStates
from app.models import User, Profile, Rating, Like, Match, News, Message, Report
from app.keyboards import (
    get_main_menu_keyboard, get_registration_keyboard, get_gender_keyboard,
    get_orientation_keyboard, get_psl_rating_keyboard, get_appeal_rating_keyboard,
    get_search_action_keyboard, get_rating_keyboard, get_profile_edit_keyboard,
    get_confirm_keyboard, get_settings_keyboard, get_admin_keyboard,
    get_back_keyboard, get_matches_keyboard, get_skip_keyboard, get_rating_result_keyboard,
    get_news_keyboard, get_news_management_keyboard, get_chat_keyboard, get_report_keyboard
)
from app.utils import (
    get_or_create_user, get_profile_by_telegram_id, format_profile_text,
    update_user_rating, check_mutual_like, create_match,
    get_search_profiles, get_random_profile_for_rating, get_user_matches,
    is_admin, get_psl_description, get_appeal_description
)
from app.config import Config, MAINTENANCE_MODE, MAINTENANCE_MESSAGE
from app.database import async_session

router = Router()
logger = logging.getLogger(__name__)

# Безопасное редактирование сообщения
async def safe_edit_message(callback: CallbackQuery, text: str, reply_markup=None, parse_mode=None):
    """Безопасно редактирует сообщение, обрабатывая ошибки"""
    try:
        if callback.message.text:
            await callback.message.edit_text(
                text, 
                reply_markup=reply_markup, 
                parse_mode=parse_mode
            )
        elif callback.message.caption:
            await callback.message.edit_caption(
                caption=text,
                reply_markup=reply_markup,
                parse_mode=parse_mode
            )
        else:
            # Если нет текста и caption, отправляем новое сообщение
            await callback.message.answer(
                text,
                reply_markup=reply_markup,
                parse_mode=parse_mode
            )
    except Exception as e:
        logger.error(f"Error editing message: {e}")
        # Если не получилось редактировать, отправляем новое сообщение
        try:
            await callback.message.answer(
                text,
                reply_markup=reply_markup,
                parse_mode=parse_mode
            )
        except Exception as e2:
            logger.error(f"Error sending new message: {e2}")
            await callback.answer("Произошла ошибка, попробуй еще раз")

# Функция проверки режима технических работ
async def check_maintenance(message: Message):
    if MAINTENANCE_MODE and message.from_user.id not in Config.ADMIN_IDS:
        await message.answer(MAINTENANCE_MESSAGE)
        return True
    return False

@router.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext):
    # Проверка режима технических работ
    if await check_maintenance(message):
        return
        
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
        
        profile = Profile(
            user_id=user.id,
            name=data["name"],
            age=data["age"],
            gender=data["gender"],
            orientation=data["orientation"],
            city=data.get("city", ""),
            bio=data["bio"],
            photos=data["photos"]  # Сохраняем file_id напрямую
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
async def back_to_main_menu(callback: CallbackQuery, state: FSMContext):
    await state.clear()  # Сбрасываем состояние чата
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
async def show_my_profile(callback: CallbackQuery, state: FSMContext):
    await state.clear()  # Сбрасываем состояние чата
    async with async_session() as session:
        profile = await get_profile_by_telegram_id(session, callback.from_user.id)
        if not profile:
            await callback.message.edit_text("У тебя нет профиля!")
            return
        
        user_result = await session.execute(select(User).where(User.telegram_id == callback.from_user.id))
        user = user_result.scalar_one()
        
        text = format_profile_text(profile, user)
        
        if profile.photos:
            photo_file_id = profile.photos[0]
            await callback.message.delete()
            await bot.send_photo(
                callback.from_user.id,
                photo=photo_file_id,
                caption=text,
                parse_mode=ParseMode.HTML,
                reply_markup=get_profile_edit_keyboard()
            )
        else:
            await callback.message.edit_text(text, parse_mode=ParseMode.HTML, 
                reply_markup=get_profile_edit_keyboard())
    await callback.answer()

@router.callback_query(F.data == "my_rating")
async def show_my_rating(callback: CallbackQuery):
    async with async_session() as session:
        user_result = await session.execute(select(User).where(User.telegram_id == callback.from_user.id))
        user = user_result.scalar_one_or_none()
        
        if not user:
            await callback.answer("Сначала создай профиль!")
            return
        
        profile = await get_profile_by_telegram_id(session, callback.from_user.id)
        if not profile:
            await callback.answer("У тебя нет профиля!")
            return
        
        # Получаем оценки пользователя
        ratings_result = await session.execute(
            select(Rating).where(Rating.rated_id == user.id)
        )
        ratings = ratings_result.scalars().all()
        
        if not ratings:
            await safe_edit_message(
                callback,
                "📊 <b>Твоя оценка:</b>\n\n"
                "У тебя пока нет оценок от других пользователей.\n"
                "Оценивай других, чтобы получал оценки в ответ!",
                reply_markup=get_profile_edit_keyboard(),
                parse_mode="HTML"
            )
            return
        
        # Рассчитываем средние оценки
        psl_scores = [r.psl_score for r in ratings if r.psl_score is not None]
        appeal_scores = [r.appeal_score for r in ratings if r.appeal_score is not None]
        
        avg_psl = sum(psl_scores) / len(psl_scores) if psl_scores else 0
        avg_appeal = sum(appeal_scores) / len(appeal_scores) if appeal_scores else 0
        
        psl_desc = get_psl_description(int(round(avg_psl)))
        appeal_desc = get_appeal_description(int(round(avg_appeal)))
        
        text = (
            f"📊 <b>Твоя оценка:</b>\n\n"
            f"👥 Всего оценок: {len(ratings)}\n\n"
            f"📊 <b>PSL:</b> {avg_psl:.1f}/10 ({psl_desc})\n"
            f"💖 <b>APPEAL:</b> {avg_appeal:.1f}/10 ({appeal_desc})\n\n"
        )
        
        if profile.psl_rating and profile.appeal_rating:
            text += (
                f"📈 <b>Текущий рейтинг:</b>\n"
                f"📊 PSL: {profile.psl_rating:.1f}/10\n"
                f"💖 APPEAL: {profile.appeal_rating:.1f}/10"
            )
        
        await safe_edit_message(
            callback,
            text,
            reply_markup=get_profile_edit_keyboard(),
            parse_mode="HTML"
        )
    await callback.answer()

@router.callback_query(F.data == "my_likes")
async def show_my_likes(callback: CallbackQuery):
    async with async_session() as session:
        user_result = await session.execute(select(User).where(User.telegram_id == callback.from_user.id))
        user = user_result.scalar_one_or_none()
        
        if not user:
            await callback.answer("Сначала создай профиль!")
            return
        
        # Получаем лайки пользователя
        likes_result = await session.execute(
            select(Like, Profile, User).join(Profile, Like.to_user_id == Profile.user_id)
            .join(User, Profile.user_id == User.id)
            .where(Like.from_user_id == user.id, Like.is_like == True)
            .order_by(Like.created_at.desc())
            .limit(20)
        )
        likes = likes_result.all()
        
        if not likes:
            await safe_edit_message(
                callback,
                "❤️ <b>Мои лайки:</b>\n\n"
                "Ты пока никому не ставил(а) лайки!\n"
                "Начни поиск и лайкай понравившихся людей!",
                reply_markup=get_profile_edit_keyboard(),
                parse_mode="HTML"
            )
            return
        
        text = f"❤️ <b>Твои лайки ({len(likes)}):</b>\n\n"
        
        for i, (like, profile, target_user) in enumerate(likes[:10], 1):  # Показываем только первые 10
            gender_icon = "👨" if profile.gender == "male" else "👩"
            text += f"{i}. {gender_icon} <b>{profile.name}</b>, {profile.age}\n"
            text += f"   🏙 {profile.city or 'Не указан'}\n"
            text += f"   🕐 {like.created_at.strftime('%d.%m.%Y %H:%M')}\n\n"
        
        if len(likes) > 10:
            text += f"... и еще {len(likes) - 10} лайков"
        
        await safe_edit_message(
            callback,
            text,
            reply_markup=get_profile_edit_keyboard(),
            parse_mode="HTML"
        )
    await callback.answer()

search_cache = {}

@router.callback_query(F.data == "search")
async def start_search(callback: CallbackQuery, state: FSMContext):
    logger.info(f"Search button pressed by user {callback.from_user.id}")
    await state.clear()  # Сбрасываем состояние чата
    await _perform_search(callback)

@router.message(F.text == "/search")
async def search_command(message: Message):
    logger.info(f"Search command used by user {message.from_user.id}")
    async with async_session() as session:
        user_result = await session.execute(
            select(User).where(User.telegram_id == message.from_user.id)
        )
        user = user_result.scalar_one_or_none()
        
        if not user:
            await message.answer("Сначала создай профиль!")
            return
        
        profiles = await get_search_profiles(session, user.id, limit=10)
        logger.info(f"Found {len(profiles)} profiles for user {user.id}")
        
        if not profiles:
            # Создаем тестовых пользователей если их нет
            await create_test_users(session)
            
            # Пробуем поиск снова
            profiles = await get_search_profiles(session, user.id, limit=10)
            logger.info(f"After creating test users: Found {len(profiles)} profiles for user {user.id}")
            
            if not profiles:
                await message.answer("Пока нет подходящих анкет 😔\nПопробуй позже или оценивай других пользователей!")
                return
        
        # Показываем первую анкету
        if profiles:
            profile, user_obj = profiles[0]
            text = format_profile_text(profile, user_obj)
            
            if profile.photos:
                photo_file_id = profile.photos[0]
                await message.answer_photo(
                    photo=photo_file_id,
                    caption=text,
                    parse_mode=ParseMode.HTML,
                    reply_markup=get_search_action_keyboard(user_obj.id)
                )
            else:
                await message.answer(
                    text,
                    parse_mode=ParseMode.HTML,
                    reply_markup=get_search_action_keyboard(user_obj.id)
                )

async def _perform_search(callback: CallbackQuery):
    async with async_session() as session:
        user_result = await session.execute(
            select(User).where(User.telegram_id == callback.from_user.id)
        )
        user = user_result.scalar_one_or_none()
        
        if not user:
            await callback.answer("Сначала создай профиль!")
            return
        
        profiles = await get_search_profiles(session, user.id, limit=10)
        logger.info(f"Found {len(profiles)} profiles for user {user.id}")
        
        if not profiles:
            # Создаем тестовых пользователей если их нет
            await create_test_users(session)
            
            # Пробуем поиск снова
            profiles = await get_search_profiles(session, user.id, limit=10)
            logger.info(f"After creating test users: Found {len(profiles)} profiles for user {user.id}")
            
            if not profiles:
                await safe_edit_message(
                    callback,
                    "Пока нет подходящих анкет 😔\nПопробуй позже или оценивай других пользователей!",
                    reply_markup=get_back_keyboard()
                )
                await callback.answer()
                return
        
        search_cache[callback.from_user.id] = profiles
        await show_next_profile(callback, session)

async def create_test_users(session: AsyncSession):
    """Создает тестовых пользователей для демонстрации"""
    from app.models import User, Profile
    from datetime import datetime
    
    # Проверяем есть ли уже тестовые пользователи
    existing_test = await session.execute(
        select(User).where(User.username.like("test_%"))
    )
    if existing_test.scalar_one_or_none():
        logger.info("Test users already exist")
        return
    
    logger.info("Creating test users...")
    
    # Создаем тестовых пользователей с разными профилями
    test_users = [
        {
            "telegram_id": 999999901,
            "username": "test_anna",
            "name": "Анна",
            "age": 25,
            "gender": "female",
            "orientation": "straight",
            "city": "Москва",
            "bio": "Люблю путешествия и фотография 📸"
        },
        {
            "telegram_id": 999999902,
            "username": "test_maria",
            "name": "Мария",
            "age": 23,
            "gender": "female", 
            "orientation": "straight",
            "city": "Санкт-Петербург",
            "bio": "Студентка, люблю книги и кофе ☕"
        },
        {
            "telegram_id": 999999903,
            "username": "test_olga",
            "name": "Ольга",
            "age": 28,
            "gender": "female",
            "orientation": "bisexual",
            "city": "Казань",
            "bio": "Йога и здоровое питание 🧘‍♀️"
        },
        {
            "telegram_id": 999999904,
            "username": "test_ekaterina",
            "name": "Екатерина",
            "age": 26,
            "gender": "female",
            "orientation": "straight",
            "city": "Новосибирск",
            "bio": "Маркетолог, люблю дизайн и искусство 🎨"
        },
        {
            "telegram_id": 999999905,
            "username": "test_daria",
            "name": "Дарья",
            "age": 24,
            "gender": "female",
            "orientation": "straight",
            "city": "Екатеринбург",
            "bio": "Волонтер, люблю животных 🐕"
        }
    ]
    
    for test_data in test_users:
        # Создаем пользователя
        test_user = User(
            telegram_id=test_data["telegram_id"],
            username=test_data["username"],
            is_active=True,
            is_banned=False,
            created_at=datetime.utcnow(),
            last_activity=datetime.utcnow()
        )
        session.add(test_user)
        await session.flush()  # Получаем ID
        
        # Создаем профиль
        test_profile = Profile(
            user_id=test_user.id,
            name=test_data["name"],
            age=test_data["age"],
            gender=test_data["gender"],
            orientation=test_data["orientation"],
            city=test_data["city"],
            bio=test_data["bio"],
            photos=None,  # Можно добавить фото позже
            is_visible=True
        )
        session.add(test_profile)
    
    await session.commit()
    logger.info(f"Created {len(test_users)} test users")

async def show_next_profile(callback: CallbackQuery, session: AsyncSession):
    user_id = callback.from_user.id
    profiles = search_cache.get(user_id, [])
    logger.info(f"Showing next profile for user {user_id}, cache has {len(profiles)} profiles")
    
    if not profiles:
        await safe_edit_message(
            callback,
            "Анкеты закончились 😔\nПопробуй позже!",
            reply_markup=get_back_keyboard()
        )
        return
    
    profile, user = profiles.pop(0)
    search_cache[user_id] = profiles
    
    text = format_profile_text(profile, user)
    
    await callback.message.delete()
    
    if profile.photos:
        photo_file_id = profile.photos[0]
        await callback.bot.send_photo(
            callback.from_user.id,
            photo=photo_file_id,
            caption=text,
            parse_mode=ParseMode.HTML,
            reply_markup=get_search_action_keyboard(user.id)
        )
    else:
        await callback.bot.send_message(
            callback.from_user.id,
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
        
        # Отправляем уведомление о лайке с информацией о том, кто лайкнул
        target_result = await session.execute(
            select(User, Profile).join(Profile, User.id == Profile.user_id).where(User.id == target_id)
        )
        target_data = target_result.one_or_none()
        
        if target_data:
            target_user, target_profile = target_data
            
            # Получаем профиль того, кто лайкнул
            liker_result = await session.execute(
                select(Profile).where(Profile.user_id == user.id)
            )
            liker_profile = liker_result.scalar_one_or_none()
            
            try:
                if liker_profile:
                    notification_text = (
                        f"❤️ Тебя лайкнул(а) @{callback.from_user.username or 'пользователь'}!\n\n"
                        f"👤 <b>Информация:</b>\n"
                        f"📝 Имя: {liker_profile.name}\n"
                        f"🔢 Возраст: {liker_profile.age}\n"
                        f"🏙 Город: {liker_profile.city or 'Не указан'}\n\n"
                        f"💬 Если взаимно - будет мэтч!"
                    )
                else:
                    notification_text = f"❤️ Тебя лайкнул(а) @{callback.from_user.username or 'пользователь'}!"
                
                await callback.bot.send_message(
                    target_user.telegram_id,
                    notification_text,
                    parse_mode="HTML"
                )
            except Exception as e:
                logger.error(f"Failed to send like notification: {e}")
        
        is_mutual = await check_mutual_like(session, user.id, target_id)
        if is_mutual:
            await create_match(session, user.id, target_id)
            
            await callback.bot.send_message(
                target_user.telegram_id,
                f"💘 У тебя новый мэтч! @{callback.from_user.username or 'пользователь'}"
            )
            await callback.answer("💘 Мэтч! Проверь раздел 'Мэтчи'")
        else:
            await callback.answer("❤️ Лайк отправлен!")
        
        await show_next_profile(callback, session)

@router.callback_query(F.data.startswith("rate_user_"))
async def rate_user_from_search(callback: CallbackQuery, state: FSMContext):
    target_id = int(callback.data.split("_")[2])
    async with async_session() as session:
        user_result = await session.execute(
            select(User).where(User.telegram_id == callback.from_user.id)
        )
        user = user_result.scalar_one_or_none()
        
        if not user:
            await callback.answer("Сначала создай профиль!")
            return
        
        # Получаем профиль для оценки
        result = await session.execute(
            select(Profile, User).join(User).where(Profile.user_id == target_id)
        )
        profile_target = result.one_or_none()
        
        if not profile_target:
            await callback.answer("Профиль не найден!")
            return
        
        profile, target_user = profile_target
        rating_cache[callback.from_user.id] = target_id
        
        text = format_profile_text(profile, target_user)
        text += "\n\n<b>Оцени по шкале 1-10:</b>"
        
        await callback.message.delete()
        
        if profile.photos:
            photo_file_id = profile.photos[0]
            await callback.bot.send_photo(
                callback.from_user.id,
                photo=photo_file_id,
                caption=text,
                parse_mode=ParseMode.HTML,
                reply_markup=get_rating_keyboard(target_id)
            )
        else:
            await callback.bot.send_message(
                callback.from_user.id,
                text,
                parse_mode=ParseMode.HTML,
                reply_markup=get_rating_keyboard(target_id)
            )
    
    await state.set_state(RatingStates.voting)
    await callback.answer()

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
    await state.clear()  # Сбрасываем состояние чата
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
            await safe_edit_message(
                callback,
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
        
        if profile.photos:
            photo_file_id = profile.photos[0]
            await callback.bot.send_photo(
                callback.from_user.id,
                photo=photo_file_id,
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

@router.callback_query(F.data.startswith("show_appeal_"))
async def show_appeal_rating(callback: CallbackQuery):
    target_id = int(callback.data.split("_")[2])
    await callback.message.edit_reply_markup(reply_markup=get_appeal_rating_keyboard(target_id))
    await callback.answer("Выбери APPEAL оценку (1-10)")

@router.callback_query(F.data == "back_to_rate")
async def back_to_rate(callback: CallbackQuery):
    async with async_session() as session:
        user_result = await session.execute(
            select(User).where(User.telegram_id == callback.from_user.id)
        )
        user = user_result.scalar_one_or_none()
        
        if not user:
            await callback.answer("Сначала создай профиль!")
            return
        
        profiles = await get_search_profiles(session, user.id, limit=10)
        logger.info(f"Found {len(profiles)} profiles for user {user.id}")
        
        if not profiles:
            # Создаем тестовых пользователей если их нет
            await create_test_users(session)
            
            # Пробуем поиск снова
            profiles = await get_search_profiles(session, user.id, limit=10)
            logger.info(f"After creating test users: Found {len(profiles)} profiles for user {user.id}")
            
            if not profiles:
                await safe_edit_message(
                    callback,
                    "Пока нет подходящих анкет 😔\nПопробуй позже или оценивай других пользователей!",
                    reply_markup=get_back_keyboard()
                )
                await callback.answer()
                return
        
        search_cache[callback.from_user.id] = profiles
        await show_next_profile(callback, session)
    await callback.answer()

@router.callback_query(F.data.startswith("open_chat_"))
async def open_chat(callback: CallbackQuery, state: FSMContext):
    target_user_id = int(callback.data.split("_")[2])
    
    async with async_session() as session:
        # Получаем информацию о текущем пользователе
        user_result = await session.execute(
            select(User).where(User.telegram_id == callback.from_user.id)
        )
        current_user = user_result.scalar_one()
        
        # Получаем информацию о собеседнике
        target_result = await session.execute(
            select(User, Profile).join(Profile).where(User.id == target_user_id)
        )
        target_data = target_result.one_or_none()
        
        if not target_data:
            await callback.answer("Пользователь не найден")
            return
        
        target_user, target_profile = target_data
        
        # Получаем историю сообщений
        messages_result = await session.execute(
            select(Message).where(
                or_(
                    and_(Message.from_user_id == current_user.id, Message.to_user_id == target_user_id),
                    and_(Message.from_user_id == target_user_id, Message.to_user_id == current_user.id)
                )
            ).order_by(Message.created_at.desc()).limit(20)
        )
        messages = messages_result.scalars().all()
        
        # Формируем текст чата
        chat_text = f"💬 **Чат с {target_profile.name}**\n\n"
        
        if not messages:
            chat_text += "Начни разговор первым! 👋"
        else:
            # Показываем сообщения в обратном порядке (старые снизу)
            for msg in reversed(messages):
                if msg.from_user_id == current_user.id:
                    sender = "Ты"
                    if msg.is_anonymous:
                        sender = "Ты (анонимно)"
                else:
                    sender = target_profile.name
                    if msg.is_anonymous:
                        sender = "Собеседник (анонимно)"
                
                chat_text += f"**{sender}:** {msg.content}\n\n"
        
        # Сохраняем ID собеседника в состоянии
        await state.update_data(chat_user_id=target_user_id, is_anonymous=False)
        await state.set_state(ChatStates.messaging)
        
        await safe_edit_message(
            callback,
            chat_text,
            reply_markup=get_chat_keyboard(target_user_id, is_anonymous=False),
            parse_mode="Markdown"
        )
    await callback.answer()

@router.callback_query(F.data.startswith("toggle_anonymous_"))
async def toggle_anonymous(callback: CallbackQuery, state: FSMContext):
    target_user_id = int(callback.data.split("_")[2])
    data = await state.get_data()
    current_anonymous = data.get("is_anonymous", False)
    
    new_anonymous = not current_anonymous
    await state.update_data(is_anonymous=new_anonymous)
    
    status = "анонимно" if new_anonymous else "неанонимно"
    await callback.answer(f"Теперь сообщения будут отправляться {status}")

@router.message(ChatStates.messaging)
async def handle_chat_message(message: Message, state: FSMContext, bot: Bot):
    data = await state.get_data()
    target_user_id = data.get("chat_user_id")
    is_anonymous = data.get("is_anonymous", False)
    
    if not target_user_id:
        await message.answer("Ошибка: собеседник не найден")
        await state.clear()
        return
    
    async with async_session() as session:
        # Получаем информацию о текущем пользователе
        user_result = await session.execute(
            select(User).where(User.telegram_id == message.from_user.id)
        )
        current_user = user_result.scalar_one()
        
        # Получаем информацию о собеседнике
        target_result = await session.execute(
            select(User, Profile).join(Profile).where(User.id == target_user_id)
        )
        target_data = target_result.one_or_none()
        
        if not target_data:
            await message.answer("Собеседник не найден")
            await state.clear()
            return
        
        target_user, target_profile = target_data
        
        # Сохраняем сообщение в базу
        new_message = Message(
            from_user_id=current_user.id,
            to_user_id=target_user_id,
            content=message.text,
            is_anonymous=is_anonymous
        )
        session.add(new_message)
        await session.commit()
        
        # Формируем текст для отправки собеседнику
        if is_anonymous:
            sender_text = "Собеседник (анонимно)"
        else:
            current_profile = await get_profile_by_telegram_id(session, message.from_user.id)
            sender_text = current_profile.name if current_profile else "Пользователь"
        
        message_text = f"💬 **{sender_text}:** {message.text}"
        
        try:
            # Отправляем сообщение собеседнику
            await bot.send_message(
                target_user.telegram_id,
                message_text,
                parse_mode="Markdown"
            )
            
            # Подтверждаем отправку
            await message.answer("✅ Сообщение отправлено")
            
        except Exception as e:
            logger.error(f"Failed to send message to {target_user.telegram_id}: {e}")
            await message.answer("❌ Не удалось отправить сообщение")

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
        await safe_edit_message(
            callback,
            text,
            reply_markup=get_appeal_rating_keyboard(target_id),
            parse_mode="HTML"
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
                await safe_edit_message(
                    callback,
                    text,
                    reply_markup=get_rating_result_keyboard(),
                    parse_mode="HTML"
                )
        
        await state.clear()
        await callback.answer("Оценка сохранена!")
    except Exception as e:
        logger.error(f"Error saving rating: {e}")
        await callback.answer("Ошибка сохранения оценки", show_alert=True)

@router.callback_query(F.data == "my_matches")
async def show_matches(callback: CallbackQuery, state: FSMContext):
    await state.clear()  # Сбрасываем состояние чата
    async with async_session() as session:
        user_result = await session.execute(
            select(User).where(User.telegram_id == callback.from_user.id)
        )
        user = user_result.scalar_one()
        
        matches = await get_user_matches(session, user.id)
        
        if not matches:
            await safe_edit_message(
                callback,
                "У тебя пока нет мэтчей 😔\n\n"
                "Лайкай понравившихся людей и жди взаимности!",
                reply_markup=get_back_keyboard()
            )
        else:
            await safe_edit_message(
                callback,
                f"💘 Твои мэтчи ({len(matches)}):\n\n"
                "Нажми на имя, чтобы начать чат",
                reply_markup=get_matches_keyboard(matches)
            )
    await callback.answer()

@router.callback_query(F.data == "settings")
async def settings(callback: CallbackQuery):
    await safe_edit_message(
        callback,
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

# Обработчики редактирования профиля
@router.callback_query(F.data.startswith("edit_"))
async def edit_profile_field(callback: CallbackQuery, state: FSMContext):
    logger.info(f"Edit profile callback: {callback.data}")
    
    field = callback.data.split("_")[1]
    logger.info(f"Field to edit: {field}")
    
    if field == "name":
        await callback.message.answer("Введи новое имя:")
        await state.set_state(ProfileEditStates.edit_name)
    elif field == "age":
        await callback.message.answer("Введи новый возраст (18-100):")
        await state.set_state(ProfileEditStates.edit_age)
    elif field == "city":
        await callback.message.answer("Введи новый город:")
        await state.set_state(ProfileEditStates.edit_city)
    elif field == "bio":
        await callback.message.answer("Введи новую биографию (до 500 символов):")
        await state.set_state(ProfileEditStates.edit_bio)
    elif field == "photos":
        await callback.message.answer("Отправь новые фото (до 5 штук):")
        await state.set_state(ProfileEditStates.edit_photos)
        await state.update_data(photos=[])
    else:
        logger.error(f"Unknown field: {field}")
        await callback.answer("Ошибка: неизвестное поле")
        return
    
    await state.update_data(edit_field=field)
    await callback.answer()

@router.message(ProfileEditStates.edit_name)
async def process_edit_name(message: Message, state: FSMContext):
    logger.info(f"Processing edit name: {message.text}")
    
    if len(message.text) > 100:
        await message.answer("Слишком длинно. Максимум 100 символов:")
        return
    
    async with async_session() as session:
        profile = await get_profile_by_telegram_id(session, message.from_user.id)
        if profile:
            profile.name = message.text
            await session.commit()
            await message.answer("✅ Имя обновлено!", reply_markup=get_main_menu_keyboard())
        else:
            logger.error(f"Profile not found for user {message.from_user.id}")
            await message.answer("Ошибка: профиль не найден")
    
    await state.clear()

@router.message(ProfileEditStates.edit_age)
async def process_edit_age(message: Message, state: FSMContext):
    try:
        age = int(message.text)
        if age < 18 or age > 100:
            await message.answer("Возраст должен быть от 18 до 100:")
            return
        
        async with async_session() as session:
            profile = await get_profile_by_telegram_id(session, message.from_user.id)
            if profile:
                profile.age = age
                await session.commit()
                await message.answer("✅ Возраст обновлён!", reply_markup=get_main_menu_keyboard())
        
        await state.clear()
    except ValueError:
        await message.answer("Введи корректное число:")

@router.message(ProfileEditStates.edit_city)
async def process_edit_city(message: Message, state: FSMContext):
    if len(message.text) > 100:
        await message.answer("Слишком длинно. Максимум 100 символов:")
        return
    
    async with async_session() as session:
        profile = await get_profile_by_telegram_id(session, message.from_user.id)
        if profile:
            profile.city = message.text
            await session.commit()
            await message.answer("✅ Город обновлён!", reply_markup=get_main_menu_keyboard())
    
    await state.clear()

@router.message(ProfileEditStates.edit_bio)
async def process_edit_bio(message: Message, state: FSMContext):
    if len(message.text) > 500:
        await message.answer("Слишком длинно. Максимум 500 символов:")
        return
    
    async with async_session() as session:
        profile = await get_profile_by_telegram_id(session, message.from_user.id)
        if profile:
            profile.bio = message.text
            await session.commit()
            await message.answer("✅ Биография обновлена!", reply_markup=get_main_menu_keyboard())
    
    await state.clear()

@router.message(ProfileEditStates.edit_photos, F.photo)
async def process_edit_photos(message: Message, state: FSMContext):
    data = await state.get_data()
    photos = data.get("photos", [])
    
    if len(photos) >= 5:
        await message.answer("Максимум 5 фото. Напиши 'готово':")
        return
    
    file_id = message.photo[-1].file_id
    photos.append(file_id)
    await state.update_data(photos=photos)
    
    await message.answer(f"Фото {len(photos)}/5 добавлено. Отправь еще или напиши 'готово':")

@router.message(ProfileEditStates.edit_photos, F.text.lower() == "готово")
async def finish_edit_photos(message: Message, state: FSMContext):
    data = await state.get_data()
    photos = data.get("photos", [])
    
    if not photos:
        await message.answer("Нужно хотя бы одно фото!")
        return
    
    async with async_session() as session:
        profile = await get_profile_by_telegram_id(session, message.from_user.id)
        if profile:
            profile.photos = photos
            await session.commit()
            await message.answer("✅ Фото обновлены!", reply_markup=get_main_menu_keyboard())
    
    await state.clear()

# Обработчики для новостей
@router.callback_query(F.data == "news")
async def show_news(callback: CallbackQuery):
    async with async_session() as session:
        # Получаем последние 5 новостей
        result = await session.execute(
            select(News).where(News.is_active == True).order_by(News.created_at.desc()).limit(5)
        )
        news_list = result.scalars().all()
        
        if not news_list:
            text = "📰 <b>Новостей пока нет</b>\n\nСледите за обновлениями!"
        else:
            text = "📰 <b>Последние новости:</b>\n\n"
            for i, news in enumerate(news_list, 1):
                text += f"🔸 <b>{news.title}</b>\n"
                text += f"{news.content}\n"
                text += f"<i>{news.created_at.strftime('%d.%m.%Y %H:%M')}</i>\n\n"
        
        await safe_edit_message(
            callback,
            text,
            reply_markup=get_news_keyboard(is_admin=is_admin(callback.from_user.id)),
            parse_mode="HTML"
        )
    await callback.answer()

@router.callback_query(F.data == "add_news")
async def add_news_start(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("Нет доступа!")
        return
    
    await safe_edit_message(callback, "📝 Введи заголовок новости:")
    await state.set_state(NewsStates.title)
    await callback.answer()

@router.message(NewsStates.title)
async def process_news_title(message: Message, state: FSMContext):
    if len(message.text) > 200:
        await message.answer("Слишком длинный заголовок. Максимум 200 символов:")
        return
    
    await state.update_data(title=message.text)
    await message.answer("📄 Введи текст новости:")
    await state.set_state(NewsStates.content)

@router.message(NewsStates.content)
async def process_news_content(message: Message, state: FSMContext, bot: Bot):
    if len(message.text) > 2000:
        await message.answer("Слишком длинный текст. Максимум 2000 символов:")
        return
    
    data = await state.get_data()
    
    async with async_session() as session:
        # Получаем ID пользователя
        user_result = await session.execute(
            select(User).where(User.telegram_id == message.from_user.id)
        )
        user = user_result.scalar_one()
        
        # Создаем новость
        news = News(
            title=data["title"],
            content=message.text,
            author_id=user.id
        )
        session.add(news)
        await session.commit()
        
        # Рассылаем новость всем активным пользователям
        users_result = await session.execute(
            select(User).where(User.is_active == True, User.is_banned == False)
        )
        users = users_result.scalars().all()
        
        news_text = f"📰 <b>{data['title']}</b>\n\n{message.text}"
        
        sent_count = 0
        for user in users:
            try:
                await bot.send_message(user.telegram_id, news_text, parse_mode="HTML")
                sent_count += 1
            except Exception as e:
                logger.error(f"Failed to send news to user {user.telegram_id}: {e}")
        
        await message.answer(
            f"✅ Новость опубликована!\n\n"
            f"📊 Отправлено: {sent_count} пользователям\n"
            f"📝 Заголовок: {data['title']}",
            reply_markup=get_main_menu_keyboard(is_admin=is_admin(message.from_user.id))
        )
    
    await state.clear()

@router.callback_query(F.data == "manage_news")
async def manage_news(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("Нет доступа!")
        return
    
    await safe_edit_message(
        callback,
        "📝 <b>Управление новостями:</b>",
        reply_markup=get_news_management_keyboard(),
        parse_mode="HTML"
    )
    await callback.answer()

@router.callback_query(F.data == "list_news")
async def list_news(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("Нет доступа!")
        return
    
    async with async_session() as session:
        result = await session.execute(
            select(News).order_by(News.created_at.desc()).limit(10)
        )
        news_list = result.scalars().all()
        
        if not news_list:
            text = "📰 Новостей пока нет"
        else:
            text = "📰 <b>Последние новости:</b>\n\n"
            for i, news in enumerate(news_list, 1):
                status = "✅" if news.is_active else "❌"
                text += f"{status} <b>{news.title}</b>\n"
                text += f"ID: {news.id} | {news.created_at.strftime('%d.%m.%Y %H:%M')}\n\n"
        
        await safe_edit_message(
            callback,
            text,
            reply_markup=get_news_management_keyboard(),
            parse_mode="HTML"
        )
    await callback.answer()

# Обработчики для репортов
@router.callback_query(F.data == "report")
async def show_report_menu(callback: CallbackQuery):
    await safe_edit_message(
        callback,
        "🚨 <b>Выбери тип репорта:</b>\n\n"
        "Опиши проблему или ошибку, с которой столкнулся.",
        reply_markup=get_report_keyboard(),
        parse_mode="HTML"
    )
    await callback.answer()

@router.callback_query(F.data.startswith("report_"))
async def handle_report_type(callback: CallbackQuery, state: FSMContext):
    report_type = callback.data.split("_")[1]
    
    type_messages = {
        "bug": "🐛 Опиши баг или ошибку:",
        "user": "👤 Укажи ID пользователя и опиши проблему:",
        "profile": "📝 Опиши проблему с профилем:",
        "other": "📄 Опиши твою проблему:"
    }
    
    await state.update_data(report_type=report_type)
    await callback.message.answer(type_messages.get(report_type, "Опиши проблему:"))
    await state.set_state(ReportStates.message)
    await callback.answer()

@router.message(ReportStates.message)
async def handle_report_message(message: Message, state: FSMContext, bot: Bot):
    data = await state.get_data()
    report_type = data.get("report_type", "other")
    
    async with async_session() as session:
        user_result = await session.execute(
            select(User).where(User.telegram_id == message.from_user.id)
        )
        user = user_result.scalar_one()
        
        # Создаем репорт
        report = Report(
            from_user_id=user.id,
            message=message.text,
            report_type=report_type
        )
        session.add(report)
        await session.commit()
        
        # Отправляем уведомление админу
        admin_text = (
            f"🚨 <b>Новый репорт!</b>\n\n"
            f"👤 От: @{message.from_user.username or 'пользователь'} (ID: {message.from_user.id})\n"
            f"📝 Тип: {report_type}\n"
            f"💬 Сообщение: {message.text}\n"
            f"🕐 Время: {report.created_at.strftime('%d.%m.%Y %H:%M')}"
        )
        
        try:
            await bot.send_message(1031760975, admin_text, parse_mode="HTML")
        except Exception as e:
            logger.error(f"Failed to send report notification: {e}")
        
        await message.answer(
            "✅ Репорт отправлен! Спасибо за помощь в улучшении бота.",
            reply_markup=get_main_menu_keyboard()
        )
    
    await state.clear()

# Обработчик кнопки "Оценивать дальше"
@router.callback_query(F.data == "continue_rating")
async def continue_rating(callback: CallbackQuery, state: FSMContext):
    async with async_session() as session:
        user_result = await session.execute(
            select(User).where(User.telegram_id == callback.from_user.id)
        )
        user = user_result.scalar_one_or_none()
        
        if not user:
            await callback.answer("Сначала создай профиль!")
            return
        
        # Всегда ищем новую анкету для оценки
        result = await get_random_profile_for_rating(session, user.id)
        
        if not result:
            await safe_edit_message(
                callback,
                "😔 <b>Анкет для оценки нет!</b>\n\n"
                "Попробуй позже или пригласи друзей в бот!\n\n"
                "📢 Хочешь больше анкет? Приглашай друзей — чем больше пользователей, тем больше анкет для оценки!",
                reply_markup=get_back_keyboard(),
                parse_mode="HTML"
            )
            await callback.answer()
            return
        
        profile, target_user = result
        rating_cache[callback.from_user.id] = target_user.id
        
        text = format_profile_text(profile, target_user)
        text += "\n\n<b>Оцени по шкале 1-10:</b>"
        
        await callback.message.delete()
        
        if profile.photos:
            photo_file_id = profile.photos[0]
            await callback.bot.send_photo(
                callback.from_user.id,
                photo_file_id,
                caption=text,
                parse_mode=ParseMode.HTML,
                reply_markup=get_rating_keyboard(target_user.id)
            )
        else:
            await callback.bot.send_message(
                callback.from_user.id,
                text,
                parse_mode=ParseMode.HTML,
                reply_markup=get_rating_keyboard(target_user.id)
            )
    
    await state.set_state(RatingStates.voting)
    await callback.answer()

# Команда для технических работ (только для админа)
@router.message(Command("maintenance"))
async def cmd_maintenance(message: Message):
    if not is_admin(message.from_user.id):
        await message.answer("⛔ Доступ запрещен!")
        return
    
    global MAINTENANCE_MODE, MAINTENANCE_MESSAGE
    
    if MAINTENANCE_MODE:
        # Выключаем режим
        MAINTENANCE_MODE = False
        MAINTENANCE_MESSAGE = ""
        await message.answer("✅ Режим технических работ выключен!")
    else:
        # Включаем режим на 5 минут
        MAINTENANCE_MODE = True
        MAINTENANCE_MESSAGE = (
            "🔧 <b>Технические работы</b>\n\n"
            "Бот временно недоступен.\n"
            "⏰ Примерное время: 5 минут\n\n"
            "Пожалуйста, подожди немного! 😊"
        )
        await message.answer("🔧 Режим технических работ включен на 5 минут!")
        
        # Автоматическое выключение через 5 минут
        import asyncio
        await asyncio.sleep(300)  # 5 минут
        MAINTENANCE_MODE = False
        MAINTENANCE_MESSAGE = ""

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
        
        await safe_edit_message(
            callback,
            "😔 Твой профиль удален.\n\n"
            "Если передумаешь, создай новый через /start"
        )
    await callback.answer()
