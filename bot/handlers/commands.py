import logging
from aiogram import Router, F, Bot
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

logger = logging.getLogger(__name__)


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
    try:
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
    except ValueError as e:
        logger.error(f"Ошибка в add_type: {e}")
        await message.answer(f"❌ Не удалось инициализировать добавление типа: {e}")


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
    training_type_data = await state.get_data()

    training_type = training_type_data.get('training_type')
    
    if not training_type:
        await state.clear()
        await message.answer("❌ Сессия устарела. Начните заново через /add_type")
        return

    tg_group_id, _, _ = check_group_params(message)
    
    if message.text is None:
        await message.answer("❌ Пожалуйста, введите число (количество):")
        return

    try:
        required_count = int(message.text.strip())
        await add_training_type(group_id=tg_group_id, training_type=training_type, required_count=required_count)
        await state.clear()
        await message.answer(f"✅ Тип '{training_type}' создан с нормативом {required_count}!")
    except ValueError:
        await message.answer("❌ Пожалуйста, введите число (например: 15, 30, 42)")
    except Exception as e:
        logger.error(f"Ошибка при сохранении типа тренировки: {e}")
        await message.answer("❌ Произошла ошибка при сохранении типа тренировки.")


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
        logger.error(f"Error in stats_group_command: {e}")


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
        'command': str(message.text),
        'issuer_id': message.from_user.id
    })


@router.callback_query(PossibleStates.choose_training_type)
async def callback_choose_training_type(callback: CallbackQuery, state: FSMContext):
    if callback.data is None:
        return
    
    data = await state.get_data()
    command = str(data.get('command'))
    issuer_id = data.get('issuer_id')
    callback_data = callback.data.split('_')[1] if callback.data else ''

    if callback.from_user.id != issuer_id:

        await callback.answer("❌ Это не ваша команда!", show_alert=True)
        return

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

        await state.set_state(PossibleStates.awaiting_remove)
        await state.update_data({
            'record_type': callback_data
        })
        if isinstance(callback.message, Message):
            await callback.message.edit_text(text=f'Тип: {callback_data.upper()}\nВыберите количество, которое хотите удалить:',reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard))
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

@router.callback_query(PossibleStates.awaiting_remove)
async def handle_remove_count_callback(callback: CallbackQuery, state: FSMContext, bot: Bot):
    """Обработка удаления количества выполненных упражнений"""
    data = await state.get_data()

    record_type = data.get('record_type')
    issuer_id = data.get('issuer_id')
    
    if callback.from_user.id != issuer_id:
        await callback.answer("❌ Вы не можете удалять записи за других пользователей!", show_alert=True)
        return

    if not callback.data or not record_type:

        await state.clear()
        return

    count_str = callback.data.split('_')[1]

    if count_str == 'cancel' or count_str == '0':
        await state.clear()
        if isinstance(callback.message, Message):
            await callback.message.delete()
        return

    if count_str == 'custom':
        keyboard = [[InlineKeyboardButton(text="Отмена", callback_data="count_cancel")]]
        await callback.message.edit_text(
            text=f'Тип: {record_type.upper()}\nВведите вручную количество, которое хотите удалить:',
            reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard)
        )
        # Состояние остается awaiting_remove, но теперь ожидаем текст
        return

    try:
        count = int(count_str)
        from bot.database.storage import add_pushups_new, get_id_group_training_type, get_today_records
        
        # Проверка текущего количества
        training_type_id = await get_id_group_training_type(callback.message.chat.id, record_type)
        today_count = await get_today_records(callback.from_user.id, callback.message.chat.id, training_type_id)
        
        if today_count < count:
            await callback.answer(f"❌ Нельзя удалить больше, чем сделано сегодня ({today_count})", show_alert=True)
            return

        # Удаление — это добавление отрицательного числа

        summary_record, today_total, _ = await add_pushups_new(

            user_id=callback.from_user.id,
            username=callback.from_user.username,
            first_name=callback.from_user.first_name,
            last_name=callback.from_user.last_name or "",
            chat_id=callback.message.chat.id,
            chat_title=callback.message.chat.title or "Chat",
            topic_id=callback.message.message_thread_id,
            type_record=record_type,
            count=-count
        )

        await callback.message.edit_text(
            f"❌ Удалено {count} {record_type.upper()}\n\n"
            f"📅 Сегодня осталось: {today_total}\n"
            f"📈 За всё время: {summary_record}"
        )
        await state.clear()

    except Exception as e:
        logger.error(f"Ошибка при удалении записи: {e}")
        await callback.answer("❌ Произошла ошибка")

@router.message(PossibleStates.awaiting_remove)
async def handle_remove_text_input(message: Message, state: FSMContext):
    """Обработка текстового ввода для удаления количества"""
    data = await state.get_data()
    record_type = data.get('record_type')
    issuer_id = data.get('issuer_id')

    if message.from_user.id != issuer_id:
        await message.answer("❌ Эта команда не для вас!")
        return
    
    if not record_type or not message.text:

        await state.clear()
        return

    try:
        count = int(message.text.strip())
        from bot.database.storage import add_pushups_new, get_id_group_training_type, get_today_records
        
        # Проверка текущего количества
        training_type_id = await get_id_group_training_type(message.chat.id, record_type)
        today_count = await get_today_records(message.from_user.id, message.chat.id, training_type_id)
        
        if today_count < count:
            await message.answer(f"❌ Нельзя удалить больше, чем сделано сегодня ({today_count})")
            return

        summary_record, today_total, _ = await add_pushups_new(


            user_id=message.from_user.id,
            username=message.from_user.username,
            first_name=message.from_user.first_name,
            last_name=message.from_user.last_name or "",
            chat_id=message.chat.id,
            chat_title=message.chat.title or "Chat",
            topic_id=message.message_thread_id,
            type_record=record_type,
            count=-count
        )

        await message.answer(
            f"❌ Удалено {count} {record_type.upper()}\n\n"
            f"📅 Сегодня осталось: {today_total}\n"
            f"📈 За всё время: {summary_record}"
        )
        await state.clear()
        await message.delete()

    except ValueError:
        await message.answer("❌ Введите число:")
    except Exception as e:
        logger.error(f"Ошибка при текстовом удалении записи: {e}")
        await message.answer("❌ Ошибка")