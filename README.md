# LOOKSMAX Dating Bot

Telegram бот для знакомств с системой оценки внешности по шкалам **PSL** (Pickup/Seduction/Looks) и **APPEAL**.

## Функции

- 🔍 **Поиск анкет** — находи людей по ориентации и городу
- ⭐ **Система оценки** — оценивай других по шкалам PSL и APPEAL (1-10)
- 💘 **Мэтчи** — взаимные лайки создают мэтчи
- 👤 **Профили** — фото, биография, рейтинги
- 🔧 **Админ-панель** — статистика, рассылки, баны

## Шкалы оценки

### PSL (Pickup/Seduction/Looks)
- 1-3: Subhuman
- 4: Below Average
- 5: Average
- 6: Good Looking
- 7: Chad/Chadette
- 8: GigaChad
- 9: God Tier
- 10: Perfection

### APPEAL (Привлекательность/Харизма)
- 1-2: Unappealing
- 3: Below Average
- 4: Average
- 5: Above Average
- 6: Attractive
- 7: Very Attractive
- 8: Gorgeous
- 9: Stunning
- 10: Irresistible

## Установка

1. Склонируй репозиторий:
```bash
cd C:\Users\Матвей\CascadeProjects\dating-bot
```

2. Создай виртуальное окружение:
```bash
python -m venv venv
venv\Scripts\activate  # Windows
source venv/bin/activate  # Linux/Mac
```

3. Установи зависимости:
```bash
pip install -r requirements.txt
```

4. Создай файл `.env` на основе `.env.example`:
```bash
cp .env.example .env
```

5. Отредактируй `.env`:
```
BOT_TOKEN=your_telegram_bot_token_here
ADMIN_IDS=123456789,987654321
DATABASE_URL=sqlite+aiosqlite:///data/dating_bot.db
DEBUG=True
MIN_VOTES_FOR_RATING=5
```

6. Инициализируй базу данных:
```bash
python create_db.py
```

7. Запусти бота:
```bash
python run.py
```

## Получение токена бота

1. Напиши [@BotFather](https://t.me/BotFather) в Telegram
2. Отправь команду `/newbot`
3. Следуй инструкциям
4. Скопируй токен в `.env` файл

## Структура проекта

```
dating-bot/
├── app/
│   ├── __init__.py
│   ├── bot.py          # Основной бот
│   ├── config.py       # Конфигурация
│   ├── database.py     # База данных
│   ├── handlers.py     # Обработчики
│   ├── keyboards.py    # Клавиатуры
│   ├── models.py       # Модели SQLAlchemy
│   ├── states.py       # FSM состояния
│   ├── utils.py        # Утилиты
│   └── admin.py        # Админ-панель
├── data/               # База данных
├── photos/             # Фото пользователей
├── logs/               # Логи
├── .env                # Переменные окружения
├── .env.example        # Пример .env
├── requirements.txt    # Зависимости
├── run.py              # Точка входа
├── create_db.py        # Создание БД
└── README.md
```

## Команды бота

- `/start` — Запустить бота / создать профиль
- `/stats` — Статистика (только для админов)

## Как работает бот

1. Пользователь создаёт профиль с фото и информацией
2. Можно искать анкеты с учётом ориентации
3. Другие пользователи оценивают по PSL и APPEAL
4. При взаимных лайках создаётся мэтч
5. Можно общаться с мэтчами

## Требования

- Python 3.9+
- aiogram 3.x
- SQLAlchemy 2.x

## Лицензия

MIT License
