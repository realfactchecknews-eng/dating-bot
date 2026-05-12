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
    field = State()
    value = State()
    photos = State()

class RatingStates(StatesGroup):
    voting = State()

class AdminStates(StatesGroup):
    broadcast = State()
    ban_user = State()
    unban_user = State()

class SearchStates(StatesGroup):
    browsing = State()
