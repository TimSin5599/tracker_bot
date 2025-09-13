from telegram import Update
from telegram.ext import ContextTypes, CallbackQueryHandler
from bot.database.storage import save_user_consent


async def handle_consent(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка согласия пользователя"""
    query = update.callback_query
    user = query.from_user
    await query.answer()

    if query.data == "consent_yes":
        await save_user_consent(user.id, user.username, user.first_name, True)

        # Информативное сообщение после согласия
        await query.edit_message_text(
            "✅ Вы согласились на отслеживание активности!\n\n"
            "Теперь я буду следить за вашими кружочками и помогать считать отжимания! 💪\n\n"
            "📋 Как это работает:\n"
            "• Отправляйте кружочки ○ в чат\n"
            "• Я спрошу сколько отжиманий вы сделали\n"
            "• Выбирайте количество или вводите своё\n"
            "• Я буду вести статистику ваших тренировок\n\n"
            "🏆 Команды для управления:\n"
            "/my_pushups - ваша статистика\n"
            "/set_weight - настройка веса кружка\n"
            "/stats - общая статистика\n\n"
            "Начните с отправки первого кружочка! 🎯"
        )

    else:
        await save_user_consent(user.id, user.username, user.first_name, False)
        await query.edit_message_text(
            "❌ Вы отказались от отслеживания активности.\n\n"
            "Если передумаете - просто напишите /start"
        )


def setup_consent_handlers(application):
    """Регистрация обработчиков согласия"""
    application.add_handler(CallbackQueryHandler(handle_consent, pattern="^consent_"))