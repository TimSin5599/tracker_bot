import os
from dotenv import load_dotenv

load_dotenv()


class Settings:
    BOT_TOKEN = os.getenv("BOT_TOKEN")
    ADMIN_IDS = [int(x) for x in os.getenv("ADMIN_IDS", "").split(",") if x]
    DB_PATH = os.getenv("DB_PATH")
    GROUP_ID = os.getenv("GROUP_ID")
    TOPIC_ID = os.getenv("TOPIC_ID")
    REQUIRED_PUSHUPS = os.getenv("REQUIRED_PUSHUPS")


settings = Settings()