from aiogram import F, Router, Bot
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message, InlineKeyboardButton, InlineKeyboardMarkup
from bot.database.session import async_session
from bot.database.storage import (
    update_user_activity, save_user_consent, get_or_create_group, get_all_types_training_group, add_training_type,
    get_user_stats
)
from bot.handlers.PossibleStates import PossibleStates
from config.settings import settings

router = Router()

@router.message(CommandStart())
async def start_command(message: Message):
    """Обработчик команды /start"""

    user = message.from_user
    chat = message.chat
    topic_id = message.message_thread_id if message else None

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

@router.message(Command(commands='add_type'))
async def add_type(message: Message, state: FSMContext):
    await state.set_state(PossibleStates.create_training_type)
    await message.answer(
        '''Введите наименование тренировки, которое вы хотите отслеживать'''
    )

@router.message(PossibleStates.create_training_type)
async def create_training_type(message: Message, state: FSMContext):
    new_type = message.text.strip()
    group_id = str(message.chat.id)

    # Проверяем и добавляем новый тип
    existing_types = await get_all_types_training_group(group_id=group_id)
    if new_type in existing_types:
        await message.answer("❌ Этот тип уже существует! Введите другое название:")
        return

    await add_training_type(group_id=group_id, training_type=new_type)
    await state.clear()

    await message.answer(f"✅ Тип '{new_type}' создан! Теперь введите количество:")

@router.message(Command(commands='stats'))
async def stats_command(message: Message):
    """Команда /stats - полная статистика (только по отжиманиям)"""
    user_id = message.from_user.id if message.from_user else None
    pushup_stats = await get_user_stats(user_id=user_id, type_record_id=1) # Дополнить type_record_id

    if not pushup_stats:
        await message.answer("📊 Нет данных для отображения")
        return

    response = "📊 ПОЛНАЯ СТАТИСТИКА\n\n"
    response += "🏆 ОТЖИМАНИЯ:\n"
    response += f"{message.from_user.username}:\n"
    response += f"   📅 Сегодня: {pushup_stats['today']}\n"
    response += f"   🏋️ Всего: {pushup_stats['total']}\n"

    await message.answer(response)

# @router.message(Command(commands='group_stats'))
# async def stats_group_command(message: Message):
#     """Команда /group_stats - статистика текущей группы"""
#     if message.chat.type not in ['group', 'supergroup']:
#         await message.answer("❌ Эта команда работает только в группах!")
#         return
#
#     chat_id = str(message.chat.id)
#
#     try:
#         stats = await get_group_stats(chat_id)
#
#         if not stats or not stats['members']:
#             await message.answer("📊 В группе пока нет данных об отжиманиях")
#             return
#
#         response = f"🏆 Статистика группы {stats['group_name']}:\n\n"
#         response += f"Всего отжиманий: {stats['total_pushups']} 🏋️\n"
#         response += f"Участников: {stats['member_count']} 👥\n\n"
#         response += "Топ сегодня:\n"
#
#         for i, member in enumerate(stats['members'][:10], 1):
#             response += f"{i}. {member['username']}: {member['today_pushups']} отжиманий\n"
#
#         await message.answer(response)
#
#     except Exception as e:
#         await message.answer("❌ Ошибка при получении статистики")
#         print(f"Error in stats_command: {e}")
#
# @router.message(Command(commands='lazy'))
# async def lazy_command(message: Message):
#     """Команда /lazy - показать кто не сделал отжимания сегодня"""
#     if message.chat.type not in ['group', 'supergroup']:
#         await message.answer("❌ Эта команда работает только в группах!")
#         return
#
#     group_id = str(message.chat.id)
#     topic_id = message.message_thread_id
#
#     # print(f"group_id: {update.effective_chat.id}, thread_id: {update.message.message_thread_id}")
#     group = await get_or_create_group(group_id=group_id, topic_id=topic_id)
#
#     try:
#         lazy_users = await get_users_without_pushups_today(group=group)
#
#         if not lazy_users:
#             await message.answer("✅ Сегодня все уже сделали отжимания! Молодцы! 🏆")
#             return
#
#         response = "😴 Еще не сделали отжимания сегодня:\n\n"
#         for user in lazy_users:
#             response += f" • @{user.username} (осталось сделать - {int(settings.REQUIRED_PUSHUPS) - user.pushups_today})\n"
#
#         response += "\nДавайте чемпионы, все получится💪"
#
#         await message.answer(response)
#
#     except Exception as e:
#         await message.answer("❌ Ошибка при получении данных")
#         print(f"Error in lazy_command: {e}")
#
# @router.message(Command(commands='remove'))
# async def remove_command(message: Message):
#     """Команда /remove - удаляет выбранное количество отжиманий"""
#
#     group_id = str(message.chat.id)
#     topic_id = message.message_thread_id
#
#     group = await get_or_create_group(group_id=group_id, topic_id=topic_id)
#
#     try:
#         count_users_pushups = await get_today_pushups(user_id=message.from_user.id, group_id=group.group_id)
#
#         if not count_users_pushups:
#             await message.answer("❌ Отсутствуют данные отжиманий за сегодня")
#     except Exception as e:
#         await message.answer("❌ Ошибка при получении данных")
#
#     inline_keyboard = [
#         [InlineKeyboardButton(text="10 отжиманий", callback_data="remove_10"),
#          InlineKeyboardButton(text="15 отжиманий", callback_data="remove_15")],
#         [InlineKeyboardButton(text="20 отжиманий", callback_data="remove_20"),
#          InlineKeyboardButton(text="30 отжиманий", callback_data="remove_30"),
#          InlineKeyboardButton(text="Другое число", callback_data="remove_custom")],
#         [InlineKeyboardButton(text="⏭️ Пропустить", callback_data="remove_0")]
#     ]
#
#     reply_markup = InlineKeyboardMarkup(inline_keyboard=inline_keyboard)
#
#     await message.answer(
#         "💪 Сколько отжиманий вы хотите удалить за сегодня?\n\n"
#         "• Выберите стандартное количество\n"
#         "• Или введите своё число\n"
#         "• ⏭️ Пропустить",
#         reply_markup=reply_markup
#     )
#
# @router.callback_query(F.data.startswith("remove_"))
# async def handle_remove_count_callback(callback: CallbackQuery, state: FSMContext, bot: Bot):
#     state_user_id = await state.get_value('user_id')
#     if state_user_id is None:
#         return
#
#     if state_user_id != callback.from_user.id:
#         await bot.send_message(
#             chat_id=callback.message.chat.id,
#             message_thread_id=callback.message.message_thread_id,
#             text=f'''Пользователь @{callback.from_user.username}, вы не можете выбирать количество отжиманий за других'''
#         )
#         return
#
#     await callback.answer()
#
#     user_id = callback.from_user.id
#     group_id = callback.message.chat.id if callback.message else None
#     count_str = callback.data.split('_')[1]
#
#     if count_str == 'custom':
#         # Для кнопки "Другое число" запрашиваем точное число
#         print("🔔 Запрошен ввод своего числа")
#
#         keyboard = [
#             [InlineKeyboardButton(text="Отмена", callback_data="remove_cancel")]
#         ]
#         reply_markup = InlineKeyboardMarkup(inline_keyboard=keyboard)
#
#         # ОЧИЩАЕМ предыдущие состояния и устанавливаем новое
#         await state.clear()  # Очищаем все предыдущие состояния
#         await state.set_data({
#             'awaiting_remove_count': True,
#             'user_id': user_id,
#             'bot_msg_id': callback.message.message_id,
#         })
#
#         print(f"🔔 Установлены состояния: {await state.get_data()}")
#
#         await callback.message.edit_text(
#             "🔢 Введите точное количество отжиманий:\n\n"
#             "Отправьте число сообщением\n"
#             "Примеры: 15, 30, 42\n\n",
#             reply_markup=reply_markup
#         )
#         return
#
#     elif count_str == '0' or count_str == 'cancel':
#         # Для кнопки "Пропустить" - просто удаляем сообщение
#         print("🔔 Пропуск подхода - удаляем сообщение")
#         await callback.message.delete()
#         await state.clear()
#         return
#
#     else:
#         # Для числовых кнопок обрабатываем как обычно
#         count = int(count_str)
#         print(f"🔔 Обрабатываем {count} отжиманий")
#         await process_pushup_count(bot, callback.message.message_id, group_id, callback.message.message_thread_id, user_id, count)
