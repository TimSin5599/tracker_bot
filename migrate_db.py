import asyncio
import logging
from sqlalchemy import text
from bot.database.session import async_session

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def migrate():
    # Таблицы и их колонки, которые должны быть BIGINT
    columns_to_fix = [
        ("users", "user_id", "tg_user_id"),
        ("groups", "group_id", "tg_group_id"),
        ("record_types", "group_id", "tg_group_id"),
        ("daily_group_records", "user_id", "tg_user_id"),
        ("daily_group_records", "group_id", "tg_group_id"),
        ("groups_records", "group_id", "tg_group_id"),
        ("users_records", "user_id", "tg_user_id"),
    ]

    async with async_session() as session:
        for table, current_old, target_new in columns_to_fix:
            try:
                # 1. Сначала пробуем переименовать, если еще не переименовано
                # Мы не знаем, на каком этапе остановился пользователь, поэтому проверяем оба варианта
                
                # Проверяем, существует ли целевая колонка
                check_new = text(f"SELECT column_name FROM information_schema.columns WHERE table_name='{table}' AND column_name='{target_new}';")
                res_new = await session.execute(check_new)
                
                column_to_alter = target_new
                
                if not res_new.scalar():
                    # Если целевой нет, значит еще старое имя. Переименовываем.
                    try:
                        sql_rename = text(f"ALTER TABLE {table} RENAME COLUMN {current_old} TO {target_new};")
                        await session.execute(sql_rename)
                        logger.info(f"✅ Таблица '{table}': '{current_old}' -> '{target_new}'")
                    except Exception as e:
                        logger.warning(f"⚠️ Не удалось переименовать {table}.{current_old}: {e}")
                        continue
                
                # 2. Теперь меняем тип на BIGINT с явным приведением
                sql_type = text(f"ALTER TABLE {table} ALTER COLUMN {target_new} TYPE BIGINT USING {target_new}::BIGINT;")
                await session.execute(sql_type)
                logger.info(f"✅ Таблица '{table}': тип '{target_new}' изменен на BIGINT")
                
            except Exception as e:
                logger.error(f"❌ Ошибка в таблице '{table}': {e}")
        
        await session.commit()
    logger.info("🚀 Миграция типов и имен завершена!")

if __name__ == "__main__":
    asyncio.run(migrate())
