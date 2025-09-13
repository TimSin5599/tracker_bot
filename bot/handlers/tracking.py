from telegram import Update
from telegram.ext import ContextTypes, MessageHandler, filters
from bot.database.storage import update_user_activity, get_user_consent


async def track_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отслеживание сообщений пользователей (общее)"""
    if not update.message or not update.message.from_user:
        return

    user = update.message.from_user
    user_id = user.id

    # Проверяем есть ли согласие у пользователя
    has_consent = await get_user_consent(user_id)

    if has_consent:
        # Обновляем активность пользователя
        await update_user_activity(
            user_id=user_id,
            username=user.username,
            first_name=user.first_name,
            last_name=user.last_name,
            message_text=update.message.text
        )
        print(f"📝 Активность пользователя {user.username}")


def setup_tracking_handlers(application):
    """Регистрация обработчиков отслеживания - НИЗКИЙ ПРИОРИТЕТ"""
    # Отслеживание всех текстовых сообщений - низкий приоритет
    application.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND,
        track_message
    ), group=2)  # Низкая группа