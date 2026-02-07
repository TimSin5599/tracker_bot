import asyncio
import logging
from bot.database.storage import init_database, add_pushups_new, get_users_without_training_today, get_or_create_group
from bot.database.models import Group

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_db_logic():
    logger.info("🚀 Начинаем тест логики БД...")
    
    # 1. Инициализация
    await init_database()
    
    # 2. Тестовые данные
    user_id = 123456789
    username = "test_user"
    first_name = "Test"
    last_name = "User"
    chat_id = -100123456789
    chat_title = "Test Group"
    topic_id = 1
    training_type = "pushups"
    count = 20

    # Создаем тип тренировки (нужно для внешнего ключа)
    from bot.database.storage import add_training_type
    logger.info(f"Создаем тип тренировки '{training_type}'...")
    try:
        await add_training_type(chat_id, training_type, 50)
    except Exception as e:
        logger.info(f"Тип тренировки уже существует или произошла ошибка: {e}")
    
    # 3. Добавление тренировки

    logger.info(f"Добавляем {count} {training_type} для {username}...")
    summary, today, actual = await add_pushups_new(
        user_id=user_id,
        username=username,
        first_name=first_name,
        last_name=last_name,
        chat_id=chat_id,
        chat_title=chat_title,
        topic_id=topic_id,
        type_record=training_type,
        count=count
    )
    
    logger.info(f"✅ Результат: Всего={summary}, Сегодня={today}, Засчитано={actual}")
    
    # 4. Проверка напоминаний
    logger.info("Проверяем 'прогульщиков'...")
    group = await get_or_create_group(chat_id, chat_title, topic_id)
    not_done = await get_users_without_training_today(group)
    
    logger.info(f"Пользователи, не выполнившие норму: {not_done}")
    
    logger.info("✨ Тест завершен!")

if __name__ == "__main__":
    asyncio.run(test_db_logic())
