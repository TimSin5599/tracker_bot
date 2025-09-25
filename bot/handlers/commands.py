from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.types import CallbackQuery, Message
from bot.database.session import async_session
from bot.database.storage import (
    get_group_stats,
    get_users_without_pushups_today,
    update_user_activity, get_pushup_stats, save_user_consent, get_or_create_group
)
from config.settings import settings

router = Router()

@router.message(CommandStart())
async def start_command(message: Message):
    """Обработчик команды /start"""

    user = message.from_user
    chat = message.chat
    topic_id = message.message_thread_id if message else None
    # print(f'chat_type - {chat.type}, chat_id - {chat.id}')
    async with async_session() as session:
        await update_user_activity(
            user_id=user.id,
            username=user.username,
            first_name=user.first_name,
            last_name=user.last_name,
            group_id=str(chat.id) if chat.type in ['group', 'supergroup', 'private'] else None,
            group_name=chat.title if chat.type in ['group', 'supergroup', 'private'] else None,
            topic_id=topic_id,
        )

    await save_user_consent(user.id, user.username, user.first_name)

    await message.answer(
        "👋 Привет! Я бот для отслеживания отжиманий!\n\n"
        "Я помогу вам:\n"
        "• Вести статистику отжиманий 📊\n"
        "• Напоминать об отжиманиях ⏰\n"
        "• Следить за прогрессом 🏆\n\n"
        "Вам достаточно просто отправить кружок или ввести команду /add для подсчета отжиманий\n\n"
    )

@router.message(Command(commands='help'))
async def help_command(message: Message):
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
    await message.answer(help_text)

@router.message(Command(commands='stats'))
async def stats_command(message: Message):
    """Команда /stats - полная статистика (только по отжиманиям)"""
    group_id = message.chat.id if message.chat else None
    user_id = message.from_user.id if message.from_user else None
    pushup_stats = await get_pushup_stats(group_id=group_id, user_id=user_id)

    if not pushup_stats:
        await message.answer("📊 Нет данных для отображения")
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

    await message.answer(response)

@router.message(Command(commands='group_stats'))
async def stats_group_command(message: Message):
    """Команда /group_stats - статистика текущей группы"""
    if message.chat.type not in ['group', 'supergroup']:
        await message.answer("❌ Эта команда работает только в группах!")
        return

    chat_id = str(message.chat.id)

    try:
        stats = await get_group_stats(chat_id)

        if not stats or not stats['members']:
            await message.answer("📊 В группе пока нет данных об отжиманиях")
            return

        response = f"🏆 Статистика группы {stats['group_name']}:\n\n"
        response += f"Всего отжиманий: {stats['total_pushups']} 🏋️\n"
        response += f"Участников: {stats['member_count']} 👥\n\n"
        response += "Топ сегодня:\n"

        for i, member in enumerate(stats['members'][:10], 1):
            response += f"{i}. {member['username']}: {member['today_pushups']} отжиманий\n"

        await message.answer(response)

    except Exception as e:
        await message.answer("❌ Ошибка при получении статистики")
        print(f"Error in stats_command: {e}")

@router.message(Command(commands='lazy'))
async def lazy_command(message: Message):
    """Команда /lazy - показать кто не сделал отжимания сегодня"""
    if message.chat.type not in ['group', 'supergroup']:
        await message.answer("❌ Эта команда работает только в группах!")
        return

    group_id = str(message.chat.id)
    topic_id = message.message_thread_id

    # print(f"group_id: {update.effective_chat.id}, thread_id: {update.message.message_thread_id}")
    group = await get_or_create_group(group_id=group_id, topic_id=topic_id)

    try:
        lazy_users = await get_users_without_pushups_today(group=group)

        if not lazy_users:
            await message.answer("✅ Сегодня все уже сделали отжимания! Молодцы! 🏆")
            return

        response = "😴 Еще не сделали отжимания сегодня:\n\n"
        for user in lazy_users:
            response += f" • @{user.username} (осталось сделать - {int(settings.REQUIRED_PUSHUPS) - user.pushups_today})\n"

        response += "\nДавайте чемпионы, все получится💪"

        await message.answer(response)

    except Exception as e:
        await message.answer("❌ Ошибка при получении данных")
        print(f"Error in lazy_command: {e}")
