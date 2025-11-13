from aiogram import Router, F
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message, InlineKeyboardButton, InlineKeyboardMarkup
from numpy.core.defchararray import upper

from bot.database.session import async_session
from bot.database.storage import (
    check_group_params, check_user_params, update_user_activity, save_user_consent, get_or_create_group, get_all_types_training_group, add_training_type,
    get_user_stats, get_or_create_user, get_group_stats
)
from bot.handlers.possible_states import PossibleStates

router = Router()

@router.message(CommandStart())
async def start_command(message: Message):
    """Обработчик команды /start"""
    async with async_session() as session:
        await update_user_activity(message)

    tg_user_id, tg_username, tg_first_name, tg_last_name = check_user_params(message)
    tg_group_id, tg_group_name, tg_topic_id = check_group_params(message)

    await get_or_create_group(group_id=tg_group_id,
                        group_name=tg_group_name,
                        topic_id=tg_topic_id)
    await get_or_create_user(user_id=tg_user_id,
                       username=tg_username,
                       first_name=tg_first_name,
                       last_name=tg_last_name)

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
    tg_user_id, tg_username, tg_first_name, tg_last_name = check_user_params(message)
    tg_group_id, tg_group_name, tg_topic_id = check_group_params(message)

    await get_or_create_user(user_id=tg_user_id,
                             username=tg_username,
                             first_name=tg_first_name,
                             last_name=tg_last_name)
    await get_or_create_group(group_id=tg_group_id,
                              group_name=tg_group_name,
                              topic_id=tg_topic_id)

    await state.set_state(PossibleStates.create_training_type)
    await message.answer(
        '''Введите наименование тренировки, которое вы хотите отслеживать'''
    )

@router.message(PossibleStates.create_training_type)
async def create_training_type(message: Message, state: FSMContext):
    if message.text is not None:
        new_type = message.text.strip()
    else:
        await message.answer("❌ Некорректный ввод! Введите название типа тренировки:")
        return
    
    tg_group_id, _, _ = check_group_params(message)
    # Проверяем и добавляем новый тип
    existing_types = await get_all_types_training_group(group_id=tg_group_id)
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
    tg_group_id, _, _ = check_group_params(message)
    if message.text is not None:
        required_count = int(message.text.strip())
    else:
        await message.answer("❌ Некорректный ввод! Введите необходимое количество:")
        return

    try:
        await add_training_type(group_id=tg_group_id, training_type=training_type, required_count=required_count)
        await state.clear()
        await message.answer(f"✅ Тип '{training_type}' создан с количеством {required_count}!")
    except ValueError:
        await message.answer("❌ Пожалуйста, введите число (например: 15, 30, 42)")

@router.message(Command(commands='stats'))
async def stats_command(message: Message):
    """Команда /stats - полная статистика (только по отжиманиям)"""
    tg_user_id, tg_username, tg_first_name, tg_last_name = check_user_params(message)
    tg_group_id, tg_group_name, tg_topic_id = check_group_params(message)

    await get_or_create_user(user_id=tg_user_id,
                             username=tg_username,
                             first_name=tg_first_name,
                             last_name=tg_last_name)
    await get_or_create_group(group_id=tg_group_id,
                              group_name=tg_group_name,
                              topic_id=tg_topic_id)

    pushup_stats = await get_user_stats(message)

    if not pushup_stats:
        await message.answer("📊 Нет данных для отображения")
        return

    response = f"📊 ПОЛНАЯ СТАТИСТИКА @{tg_username}\n\n"
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

    tg_user_id, tg_username, tg_first_name, tg_last_name = check_user_params(message)
    tg_group_id, tg_group_name, tg_topic_id = check_group_params(message)
    
    await get_or_create_user(user_id=tg_user_id,
                             username=tg_username,
                             first_name=tg_first_name,
                             last_name=tg_last_name)
    await get_or_create_group(group_id=tg_group_id,
                              group_name=tg_group_name,
                              topic_id=tg_topic_id)

    try:
        stats = await get_group_stats(message)

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


@router.message(Command(commands=['lazy', 'remove']))
async def choose_training_type(message: Message, state: FSMContext):
    """Команда /lazy - показать кто не сделал отжимания сегодня"""
    if message.chat.type not in ['group', 'supergroup']:
        await message.answer("❌ Эта команда работает только в группах!")
        return
    
    tg_user_id, tg_username, tg_first_name, tg_last_name = check_user_params(message)
    tg_group_id, tg_group_name, tg_topic_id = check_group_params(message)

    await get_or_create_user(user_id=tg_user_id,
                             username=tg_username,
                             first_name=tg_first_name,
                             last_name=tg_last_name)
    await get_or_create_group(group_id=tg_group_id,
                              group_name=tg_group_name,
                              topic_id=tg_topic_id)

    all_types_training_group = await get_all_types_training_group(group_id=tg_group_id)

    if len(all_types_training_group) == 0:
        await message.answer('❌ Отсутствуют типы упражнений')
        return

    keyboard = []
    for type in all_types_training_group:
        keyboard.append([InlineKeyboardButton(text=type, callback_data='type_' + type)])

    if message.text is not None and message.text.lower() == 'lazy':
        keyboard.append([InlineKeyboardButton(text='Все', callback_data='type_all')])

    reply_markup = InlineKeyboardMarkup(inline_keyboard=keyboard)

    await message.answer(
        "💪 Выберите тип упражнения:",
        reply_markup=reply_markup
    )

    await state.clear()
    await state.set_state(PossibleStates.choose_training_type)
    await state.set_data({
        'command': str(message.text)
    })

@router.callback_query(PossibleStates.choose_training_type)
async def callback_choose_training_type(callback: CallbackQuery, state: FSMContext):
    if callback.data is None:
        return
    
    callback_data = callback.data.split('_')[1]
    command = str(await state.get_value('command'))

    if callback_data == '':
        return

    if command == '/lazy' and isinstance(callback.message, Message):
        await callback.message.edit_text(text='Метод находится в разработке...')
    elif command == '/remove':
        keyboard = [
            [InlineKeyboardButton(text="10", callback_data="count_10"),
             InlineKeyboardButton(text="15", callback_data="count_15")],
            [InlineKeyboardButton(text="20", callback_data="count_20"),
             InlineKeyboardButton(text="30", callback_data="count_30"),
             InlineKeyboardButton(text="Другое число", callback_data="count_custom")],
            [InlineKeyboardButton(text="⏭️ Пропустить", callback_data="count_0")]
        ]

        await state.clear()
        await state.set_state(PossibleStates.awaiting_remove)
        await state.set_data({
            'record_type': callback_data
        })
        if isinstance(callback.message, Message):
            await callback.message.edit_text(text=f'Тип: {callback_data.upper()}\nВыберете количество, которое хотите удалить:',reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard))
        else:
            await state.clear()
            return
    else:
        await state.clear()
        return

@router.message(Command(commands='types'))
async def types_command(message: Message, state: FSMContext):
    tg_user_id, tg_username, tg_first_name, tg_last_name = check_user_params(message)
    tg_group_id, tg_group_name, tg_topic_id = check_group_params(message)

    await get_or_create_user(user_id=tg_user_id,
                             username=tg_username,
                             first_name=tg_first_name,
                             last_name=tg_last_name)
    await get_or_create_group(group_id=tg_group_id,
                              group_name=tg_group_name,
                              topic_id=tg_topic_id)

    all_types = await get_all_types_training_group(group_id=tg_group_id)

    if all_types is None or len(all_types) == 0:
        await message.answer(f'В группе отсутствуют тренировки для отслеживания\n'
                             f'Чтобы добавить тренировку - введите /add_type')
        return

    result = f"Все виды тренировок в группе {message.chat.title}:\n\n"
    for type in all_types:
        result += f" • {type}\n"
    await message.answer(result)

# @router.callback_query(PossibleStates.awaiting_remove)
# async def handle_remove_count_callback(callback: CallbackQuery, state: FSMContext):
#     print('handle_remove_count_callback')
#     callback_data = callback.data.split('_')[1]
#     record_type = await state.get_value('record_type')
#     print(isinstance(callback_data, int), record_type)
#     if callback_data == '':
#         await state.clear()
#         return
#     elif callback_data == 'custom':
#         print()
#     else:
#         callback_data = int(callback_data)
#
#         if callback_data == 0:
#             await state.clear()
#             await callback.message.delete()
#             return
#
#         await update_records(user=callback.message.from_user,
#                              group=callback.message.chat,
#                              count=-callback_data,
#                              record_type=record_type)
#         await state.clear()