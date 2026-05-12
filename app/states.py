from aiogram.fsm.state import State, StatesGroup

class RegistrationStates(StatesGroup):
    name = State()
    age = State()
    gender = State()
    orientation = State()
    city = State()
    bio = State()
    photos = State()
    confirm = State()

class ProfileEditStates(StatesGroup):
    edit_name = State()
    edit_age = State()
    edit_city = State()
    edit_bio = State()
    edit_photos = State()

class RatingStates(StatesGroup):
    voting = State()

class AdminStates(StatesGroup):
    broadcast = State()
    ban_user = State()
    unban_user = State()

class SearchStates(StatesGroup):
    browsing = State()

class NewsStates(StatesGroup):
    title = State()
    content = State()
