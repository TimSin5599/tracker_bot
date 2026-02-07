import logging
import asyncio

from aiogram import Dispatcher, Bot
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from bot.handlers import commands
from bot.handlers import pushups
from bot.middlewares.TopicMiddleware import TopicMiddlewares
from bot.utils.reminders import setup_reminders
from config.settings import settings
from bot.database.storage import init_database
# from bot.utils.reminders import setup_reminders

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
# Настройка логгера для текущего модуля
logger = logging.getLogger(__name__)



async def main():
    """Основная функция запуска бота"""
    if not settings.BOT_TOKEN:
        logger.error("❌ BOT_TOKEN не найден! Проверьте файл .env")
        return

    logger.info("✅ Токен найден, инициализируем базу данных...")

    # Инициализируем базу данных
    await init_database()

    bot = Bot(token=settings.BOT_TOKEN)
    dp = Dispatcher()

    # Middleware
    dp.update.outer_middleware(TopicMiddlewares())
    
    # Регистрация роутеров
    dp.include_router(commands.router)
    dp.include_router(pushups.router)

    # Настраиваем напоминания (передаем только бота, планировщик создается внутри)
    setup_reminders(bot)

    # Запускаем бота
    logger.info("🤖 Бот запускается...")
    try:
        await bot.delete_webhook(drop_pending_updates=True)
        await dp.start_polling(bot)
    except Exception as e:
        logger.error(f"❌ Ошибка во время работы бота: {e}")
    finally:
        await bot.session.close()
        logger.info("👋 Бот остановлен")



if __name__ == "__main__":
    asyncio.run(main())