from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CommandHandler
from bot.database.storage import (
    get_group_stats,
    get_users_without_pushups_today,
    update_user_activity, get_pushup_stats
)

async def start_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [
            InlineKeyboardButton("Добавить отжимания", callback_data="add_pushups"),
            InlineKeyboardButton("Посмотреть статистику", callback_data="stats"),
        ],
        [
            InlineKeyboardButton("Помощь", callback_data="help"),
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("Выберите действие:", reply_markup=reply_markup)

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /start"""
    keyboard = [
        [InlineKeyboardButton("✅ Согласиться на отслеживание", callback_data="consent_yes")],
        [InlineKeyboardButton("❌ Отказаться", callback_data="consent_no")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    user = update.effective_user
    chat = update.effective_chat

    from bot.database.session import async_session  # import sessionmaker

    async with async_session() as session:
        await update_user_activity(
            user_id=user.id,
            username=user.username,
            first_name=user.first_name,
            last_name=user.last_name,
            group_id=str(chat.id) if chat.type in ['group', 'supergroup'] else None,
            group_name=chat.title if chat.type in ['group', 'supergroup'] else None
        )

    await update.message.reply_text(
        "👋 Привет! Я бот для отслеживания отжиманий!\n\n"
        "Я помогу вам:\n"
        "• Вести статистику отжиманий 📊\n"
        "• Напоминать об отжиманиях ⏰\n"
        "• Следить за прогрессом 🏆\n\n"
        "Для работы мне нужно ваше согласие на отслеживание активности:",
        reply_markup=reply_markup
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /help"""
    help_text = """
    📋 Доступные команды:

    Личные команды:
    /start - Начать работу с ботом
    /help - Показать справку
    /stats - Личная статистика

    Групповые команды:
    /group_stats - Статистика группы
    /lazy - Кто еще не сделал отжимания сегодня

    Просто отправляйте кружочки в чат: ○ ⚪ ⭕ 🔵
    1 кружок = N отжиманий
    """
    await update.message.reply_text(help_text)

async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /stats - полная статистика (только по отжиманиям)"""
    group_id = update.effective_chat.id if update.effective_chat else None
    user_id = update.effective_user.id if update.effective_user else None
    pushup_stats = await get_pushup_stats(group_id=group_id, user_id=user_id)

    if not pushup_stats:
        await update.message.reply_text("📊 Нет данных для отображения")
        return

    response = "📊 ПОЛНАЯ СТАТИСТИКА\n\n"
    # Статистика отжиманий
    response += "🏆 ОТЖИМАНИЯ:\n"

    if isinstance(pushup_stats, dict):
        response += f"{pushup_stats['username']}:\n"
        response += f"   📅 Сегодня: {pushup_stats['today_pushups']}\n"
        response += f"   🏋️ Всего: {pushup_stats['total_pushups']}\n"
    else:
        for i, user in enumerate(pushup_stats, 1):
            response += f"{i}. {user['username']}:\n"
            response += f"   📅 Сегодня: {user['today_pushups']}\n"
            response += f"   🏋️ Всего: {user['total_pushups']}\n"

    await update.message.reply_text(response)

async def stats_group_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /group_stats - статистика текущей группы"""
    if update.effective_chat.type not in ['group', 'supergroup']:
        await update.message.reply_text("❌ Эта команда работает только в группах!")
        return

    chat_id = str(update.effective_chat.id)

    try:
        stats = await get_group_stats(chat_id)

        if not stats or not stats['members']:
            await update.message.reply_text("📊 В группе пока нет данных об отжиманиях")
            return

        response = f"🏆 Статистика группы {stats['group_name']}:\n\n"
        response += f"Всего отжиманий: {stats['total_pushups']} 🏋️\n"
        response += f"Участников: {stats['member_count']} 👥\n\n"
        response += "Топ сегодня:\n"

        for i, member in enumerate(stats['members'][:10], 1):
            response += f"{i}. {member['username']}: {member['today_pushups']} отжиманий\n"

        await update.message.reply_text(response)

    except Exception as e:
        await update.message.reply_text("❌ Ошибка при получении статистики")
        print(f"Error in stats_command: {e}")


async def lazy_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /lazy - показать кто не сделал отжимания сегодня"""
    if update.effective_chat.type not in ['group', 'supergroup']:
        await update.message.reply_text("❌ Эта команда работает только в группах!")
        return

    chat_id = str(update.effective_chat.id)

    try:
        lazy_users = await get_users_without_pushups_today(group_id=chat_id)

        if not lazy_users:
            await update.message.reply_text("✅ Сегодня все уже сделали отжимания! Молодцы! 🏆")
            return

        response = "😴 Еще не сделали отжимания сегодня:\n\n"
        for user in lazy_users:
            response += f"• {user.username or user.first_name}\n"

        response += "\nНе забудьте сделать отжимания! 💪"

        await update.message.reply_text(response)

    except Exception as e:
        await update.message.reply_text("❌ Ошибка при получении данных")
        print(f"Error in lazy_command: {e}")


def setup_command_handlers(application):
    """Регистрация обработчиков команд"""
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("group_stats", stats_group_command))
    application.add_handler(CommandHandler("stats", stats_command))
    application.add_handler(CommandHandler("lazy", lazy_command))