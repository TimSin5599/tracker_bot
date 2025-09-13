import logging
import asyncio
from telegram.ext import Application
from config.settings import settings
from bot.handlers.commands import setup_command_handlers
from bot.handlers.consent import setup_consent_handlers
from bot.handlers.tracking import setup_tracking_handlers
from bot.handlers.pushups import setup_pushups_handlers
from bot.database.storage import init_database
from bot.utils.reminders import setup_reminders

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO  # Измените на INFO вместо DEBUG
)
logger = logging.getLogger(__name__)


async def main():
    """Основная функция запуска бота"""
    if not settings.BOT_TOKEN:
        logger.error("❌ BOT_TOKEN не найден! Проверьте файл .env")
        return

    logger.info("✅ Токен найден, инициализируем базу данных...")

    # Инициализируем базу данных
    await init_database()

    # Создаем приложение
    application = Application.builder().token(settings.BOT_TOKEN).build()

    # Настраиваем обработчики в правильном порядке
    setup_pushups_handlers(application)  # ПЕРВЫМ - высокий приоритет
    setup_command_handlers(application)
    setup_consent_handlers(application)
    setup_tracking_handlers(application)

    # Настраиваем напоминания
    setup_reminders(application)

    # Запускаем бота
    logger.info("🤖 Бот запускается...")
    await application.initialize()
    await application.start()
    await application.updater.start_polling()

    logger.info("✅ Бот запущен и работает!")
    logger.info("⏰ Напоминания настроены: 22:00 и 00:00")
    logger.info("🔍 Режим отладки включен")

    # Бесконечный цикл
    try:
        while True:
            await asyncio.sleep(3600)
    except KeyboardInterrupt:
        logger.info("🛑 Остановка бота...")
        await application.updater.stop()
        await application.stop()
        await application.shutdown()


if __name__ == "__main__":
    asyncio.run(main())