from aiogram import Router
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message, InlineKeyboardButton, InlineKeyboardMarkup
from numpy.core.defchararray import upper

from bot.database.session import async_session
from bot.database.storage import (
    update_user_activity, save_user_consent, get_or_create_group, get_all_types_training_group, add_training_type,
    get_user_stats, get_users_without_training_today, get_required_count, get_or_create_user, get_group_stats
)
from bot.handlers.possible_states import PossibleStates

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
    /add_type - Добавить тип упражнений

    Групповые команды:
    /group_stats - Статистика группы
    /lazy - Кто еще не сделал отжимания сегодня

    Просто отправляйте кружочки в чат: ○ ⚪ ⭕ 🔵
    1 кружок = N отжиманий
    """
    await message.answer(help_text)

@router.message(Command(commands='add_type'))
async def add_type(message: Message, state: FSMContext):
    await get_or_create_user(user_id=message.from_user.id,
                             username=message.from_user.username,
                             first_name=message.from_user.first_name,
                             last_name=message.from_user.last_name, )
    await get_or_create_group(group_id=str(message.chat.id),
                              group_name=message.chat.title,
                              topic_id=message.message_thread_id)

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

    await state.set_state(PossibleStates.choose_count)
    await state.set_data({
        'training_type': new_type,
    })
    await message.answer(f"✅ Теперь введите количество:")

@router.message(PossibleStates.choose_count)
async def choose_count(message: Message, state: FSMContext):
    training_type = str(await state.get_value('training_type'))
    group_id = str(message.chat.id)
    required_count = message.text.strip()

    try:
        required_count = int(required_count)
        await add_training_type(group_id=group_id, training_type=training_type, required_count=required_count)
        await state.clear()
        await message.answer(f"✅ Тип '{training_type}' создан с количеством {required_count}!")
    except ValueError:
        await message.answer("❌ Пожалуйста, введите число (например: 15, 30, 42)")

@router.message(Command(commands='stats'))
async def stats_command(message: Message):
    """Команда /stats - полная статистика (только по отжиманиям)"""

    await get_or_create_user(user_id=message.from_user.id,
                             username=message.from_user.username,
                             first_name=message.from_user.first_name,
                             last_name=message.from_user.last_name, )
    await get_or_create_group(group_id=str(message.chat.id),
                              group_name=message.chat.title,
                              topic_id=message.message_thread_id)

    user_id = message.from_user.id if message.from_user else None
    pushup_stats = await get_user_stats(user_id=user_id, group_id=str(message.chat.id))

    if not pushup_stats:
        await message.answer("📊 Нет данных для отображения")
        return

    response = f"📊 ПОЛНАЯ СТАТИСТИКА @{message.from_user.username}\n\n"
    for key, value in pushup_stats.items():
        response += f"🏆 {key}:\n"
        response += f"   📅 Сегодня: {value['today']}\n"
        response += f"   🏋️ Всего: {value['total']}\n\n"

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

        if not stats:
            await message.answer("📊 В группе пока нет данных об отжиманиях")
            return

        response = f"🏆 Статистика группы {message.chat.title}:\n\n"
        response += f"Участников: {len(stats.items())} 👥\n\n"

        for user, user_stats in stats.items():
            response += f"@{user}:\n"
            for type, type_stats in user_stats.items():
                if type == 'total_size_trainings': continue
                response += f"    • {upper(type)}:\n        Сегодня - {type_stats['today']}, всего - {type_stats['total']}\n"
            total_size_trainings = user_stats['total_size_trainings']
            response += f"\n    Общее число выполненных упражнений - {total_size_trainings}\n"
        await message.answer(response)

    except Exception as e:
        await message.answer("❌ Ошибка при получении статистики")
        print(f"Error in stats_command: {e}")

# @router.message(Command(commands='change_required'))
# async def change_required(message: Message, state: FSMContext):


@router.message(Command(commands='lazy'))
async def lazy_command(message: Message, state: FSMContext):
    """Команда /lazy - показать кто не сделал отжимания сегодня"""
    if message.chat.type not in ['group', 'supergroup']:
        await message.answer("❌ Эта команда работает только в группах!")
        return

    await get_or_create_user(user_id=message.from_user.id,
                             username=message.from_user.username,
                             first_name=message.from_user.first_name,
                             last_name=message.from_user.last_name, )
    await get_or_create_group(group_id=str(message.chat.id),
                              group_name=message.chat.title,
                              topic_id=message.message_thread_id)

    all_types_training_group = await get_all_types_training_group(group_id=str(message.chat.id))

    if len(all_types_training_group) == 0:
        await message.answer('❌ Отсутствуют типы упражнений')
        return

    keyboard = []
    for type in all_types_training_group:
        keyboard.append([InlineKeyboardButton(text=type, callback_data='type_' + type)])
    keyboard.append([InlineKeyboardButton(text='Все', callback_data='type_all')])

    reply_markup = InlineKeyboardMarkup(inline_keyboard=keyboard)

    await message.answer(
        "💪 Выберите тип упражнения:",
        reply_markup=reply_markup
    )

    await state.clear()
    await state.set_state(PossibleStates.choose_training_type)

@router.message(Command(commands='types'))
async def types_command(message: Message, state: FSMContext):
    await get_or_create_user(user_id=message.from_user.id,
                             username=message.from_user.username,
                             first_name=message.from_user.first_name,
                             last_name=message.from_user.last_name,)
    await get_or_create_group(group_id=str(message.chat.id),
                              group_name=message.chat.title,
                              topic_id=message.message_thread_id)

    all_types = await get_all_types_training_group(group_id=str(message.chat.id))

    if all_types is None or len(all_types) == 0:
        await message.answer(f'В группе отсутствуют тренировки для отслеживания\n'
                             f'Чтобы добавить тренировку - введите /add_type')
        return

    result = f"Все виды тренировок в группе {message.chat.title}:\n\n"
    for type in all_types:
        result += f" • {type}\n"
    await message.answer(result)

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
#     await callback.message.answer()
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
