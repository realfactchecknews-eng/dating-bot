from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

def get_main_menu_keyboard(is_admin=False):
    builder = InlineKeyboardBuilder()
    builder.button(text="🔍 Искать", callback_data="search")
    builder.button(text="👤 Мой профиль", callback_data="my_profile")
    builder.button(text="⭐ Оценивать", callback_data="rate_profiles")
    builder.button(text="🔔 Мэтчи", callback_data="my_matches")
    builder.button(text="⚙️ Настройки", callback_data="settings")
    if is_admin:
        builder.button(text="🔧 Админ", callback_data="admin_panel")
    builder.adjust(2)
    return builder.as_markup()

def get_registration_keyboard():
    builder = InlineKeyboardBuilder()
    builder.button(text="📝 Создать профиль", callback_data="create_profile")
    return builder.as_markup()

def get_gender_keyboard():
    builder = InlineKeyboardBuilder()
    builder.button(text="👨 Мужчина", callback_data="gender_male")
    builder.button(text="👩 Женщина", callback_data="gender_female")
    builder.adjust(2)
    return builder.as_markup()

def get_orientation_keyboard():
    builder = InlineKeyboardBuilder()
    builder.button(text="💑 Гетеро", callback_data="orientation_straight")
    builder.button(text="🏳️‍🌈 Гей", callback_data="orientation_gay")
    builder.button(text="🏳️‍🌈 Лесби", callback_data="orientation_lesbian")
    builder.button(text="💜 Би", callback_data="orientation_bisexual")
    builder.adjust(2)
    return builder.as_markup()

def get_psl_rating_keyboard(user_id: int):
    builder = InlineKeyboardBuilder()
    for i in range(1, 11):
        builder.button(text=f"{i}", callback_data=f"psl_{user_id}_{i}")
    builder.adjust(5, 5)
    return builder.as_markup()

def get_appeal_rating_keyboard(user_id: int):
    builder = InlineKeyboardBuilder()
    for i in range(1, 11):
        builder.button(text=f"{i}", callback_data=f"appeal_{user_id}_{i}")
    builder.adjust(5, 5)
    return builder.as_markup()

def get_search_action_keyboard(target_user_id: int):
    builder = InlineKeyboardBuilder()
    builder.button(text="❤️ Лайк", callback_data=f"like_{target_user_id}")
    builder.button(text="💔 Дизлайк", callback_data=f"dislike_{target_user_id}")
    builder.button(text="⭐ Оценить", callback_data=f"rate_user_{target_user_id}")
    builder.button(text="⏭ Далее", callback_data="next_profile")
    builder.button(text="🔙 Меню", callback_data="main_menu")
    builder.adjust(2, 2, 1)
    return builder.as_markup()

def get_rating_keyboard(user_id: int):
    builder = InlineKeyboardBuilder()
    builder.button(text="📊 PSL оценка", callback_data=f"show_psl_{user_id}")
    builder.button(text="💖 APPEAL оценка", callback_data=f"show_appeal_{user_id}")
    builder.button(text="🔙 Назад", callback_data="back_to_rate")
    builder.adjust(2, 1)
    return builder.as_markup()

def get_profile_edit_keyboard():
    builder = InlineKeyboardBuilder()
    builder.button(text="📝 Имя", callback_data="edit_name")
    builder.button(text="🔢 Возраст", callback_data="edit_age")
    builder.button(text="🏙 Город", callback_data="edit_city")
    builder.button(text="📄 О себе", callback_data="edit_bio")
    builder.button(text="📸 Фото", callback_data="edit_photos")
    builder.button(text="🔙 Назад", callback_data="main_menu")
    builder.adjust(2, 2, 1, 1)
    return builder.as_markup()

def get_confirm_keyboard():
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Подтвердить", callback_data="confirm_yes")
    builder.button(text="🔄 Изменить", callback_data="confirm_no")
    return builder.as_markup()

def get_settings_keyboard():
    builder = InlineKeyboardBuilder()
    builder.button(text="👁 Скрыть/показать профиль", callback_data="toggle_visibility")
    builder.button(text="🚫 Удалить профиль", callback_data="delete_profile")
    builder.button(text="🔙 Назад", callback_data="main_menu")
    builder.adjust(1, 1, 1)
    return builder.as_markup()

def get_admin_keyboard():
    builder = InlineKeyboardBuilder()
    builder.button(text="📊 Статистика", callback_data="admin_stats")
    builder.button(text="📢 Рассылка", callback_data="admin_broadcast")
    builder.button(text="🧹 Очистить фото", callback_data="admin_clear_photos")
    builder.button(text="🚫 Забанить", callback_data="admin_ban")
    builder.button(text="✅ Разбанить", callback_data="admin_unban")
    builder.button(text="📋 Список пользователей", callback_data="admin_users")
    builder.button(text="🔙 Назад", callback_data="main_menu")
    builder.adjust(2, 2, 2, 1)
    return builder.as_markup()

def get_back_keyboard():
    builder = InlineKeyboardBuilder()
    builder.button(text="🔙 Назад", callback_data="main_menu")
    return builder.as_markup()

def get_rating_result_keyboard():
    builder = InlineKeyboardBuilder()
    builder.button(text="⭐ Оценивать дальше", callback_data="rate_profiles")
    builder.button(text="🔙 В меню", callback_data="main_menu")
    builder.adjust(1)
    return builder.as_markup()

def get_matches_keyboard(matches):
    builder = InlineKeyboardBuilder()
    for match in matches:
        builder.button(
            text=f"💬 {match['name']}", 
            callback_data=f"open_chat_{match['user_id']}"
        )
    builder.button(text="🔙 Назад", callback_data="main_menu")
    builder.adjust(1)
    return builder.as_markup()

def get_skip_keyboard():
    builder = InlineKeyboardBuilder()
    builder.button(text="⏭ Пропустить", callback_data="skip_step")
    return builder.as_markup()
