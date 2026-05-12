import os
from dotenv import load_dotenv

load_dotenv()

# Глобальная переменная для режима технических работ
MAINTENANCE_MODE = False
MAINTENANCE_MESSAGE = ""

class Config:
    BOT_TOKEN = os.getenv("BOT_TOKEN", "")
    ADMIN_IDS = [int(x) for x in os.getenv("ADMIN_IDS", "1031760975").split(",") if x]
    DATABASE_URL = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///data/dating_bot.db")
    DEBUG = os.getenv("DEBUG", "False").lower() == "true"
    MIN_VOTES_FOR_RATING = int(os.getenv("MIN_VOTES_FOR_RATING", "5"))
    
    PSL_SCALE = {
        1: "Subhuman",
        2: "Subhuman",
        3: "Subhuman",
        4: "Below Average",
        5: "Average",
        6: "Good Looking",
        7: "Chad/Chadette",
        8: "GigaChad",
        9: "God Tier",
        10: "Perfection"
    }
    
    APPEAL_SCALE = {
        1: "Unappealing",
        2: "Unappealing",
        3: "Below Average",
        4: "Average",
        5: "Above Average",
        6: "Attractive",
        7: "Very Attractive",
        8: "Gorgeous",
        9: "Stunning",
        10: "Irresistible"
    }
    
    GENDERS = {
        "male": "Мужчина",
        "female": "Женщина"
    }
    
    ORIENTATIONS = {
        "straight": "Гетеро",
        "gay": "Гей",
        "lesbian": "Лесби",
        "bisexual": "Би"
    }
