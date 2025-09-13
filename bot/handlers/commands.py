from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CommandHandler
from bot.database.storage import get_active_users_stats, get_online_users


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /start"""
    keyboard = [
        [InlineKeyboardButton("✅ Согласиться на отслеживание", callback_data="consent_yes")],
        [InlineKeyboardButton("❌ Отказаться", callback_data="consent_no")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        "👋 Привет! Я бот для отслеживания отжиманий!\n\n"
        "Я помогу вам:\n"
        "• Считать отжимания по кружочкам ○\n"
        "• Вести статистику тренировок 📊\n"
        "• Напоминать о тренировках ⏰\n"
        "• Следить за прогрессом 🏆\n\n"
        "Для работы мне нужно ваше согласие на отслеживание активности:",
        reply_markup=reply_markup
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /help"""
    help_text = """
    📋 Доступные команды:
    /start - Начать работу с ботом
    /help - Показать справку
    /stats - Статистика активности
    /online - Кто сейчас онлайн
    """
    await update.message.reply_text(help_text)


async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /stats - показать статистику"""
    stats = await get_active_users_stats()

    if not stats:
        await update.message.reply_text("📊 Нет данных для отображения")
        return

    response = "📊 Статистика активности:\n\n"
    for user in stats:
        last_seen = user['last_activity'].strftime("%d.%m.%Y %H:%M") if user['last_activity'] else "никогда"
        response += f"👤 {user['username'] or user['first_name']}:\n"
        response += f"   📨 Сообщений: {user['message_count']}\n"
        response += f"   ⏰ Последняя активность: {last_seen}\n\n"

    await update.message.reply_text(response)


async def online_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /online - кто сейчас онлайн"""
    # Пользователи активные в последние 5 минут считаются онлайн
    online_users = await get_online_users(minutes=5)

    if not online_users:
        await update.message.reply_text("❌ Сейчас никто не онлайн")
        return

    response = "✅ Сейчас онлайн:\n\n"
    for user in online_users:
        response += f"• {user['username'] or user['first_name']}\n"

    await update.message.reply_text(response)


def setup_command_handlers(application):
    """Регистрация обработчиков команд"""
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("stats", stats_command))
    application.add_handler(CommandHandler("online", online_command))

async def pushups_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /pushups - показать статистику отжиманий"""
    from bot.database.storage import get_pushup_stats

    stats = await get_pushup_stats()

    if not stats:
        await update.message.reply_text("📊 Нет данных об отжиманиях")
        return

    response = "🏆 Статистика отжиманий:\n\n"
    for i, user in enumerate(stats, 1):
        last_date = user['last_date'].strftime("%d.%m.%Y") if user['last_date'] else "никогда"
        response += f"{i}. {user['username']}:\n"
        response += f"   📅 Сегодня: {user['today']}\n"
        response += f"   🏋️ Всего: {user['total']}\n"
        response += f"   ⏰ Последние: {last_date}\n\n"

    await update.message.reply_text(response)


def setup_command_handlers(application):
    """Регистрация обработчиков команд"""
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("stats", stats_command))
    application.add_handler(CommandHandler("online", online_command))
    application.add_handler(CommandHandler("pushups", pushups_command))


async def test_circle_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Тестовая команда для проверки кружков"""
    test_message = """
    Отправьте эти кружочки для теста:
    ○ ⚪ ⭕ 🔵 🔘 ◯ 〇 ⚬ 🔄 💪

    Бот должен реагировать на каждый кружочек!
    """
    await update.message.reply_text(test_message)