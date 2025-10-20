import re
from aiogram import Router, F, Bot
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext

from sqlalchemy import select
from bot.database.models import Group

from bot.database.session import async_session
from bot.database.storage import add_pushups, get_all_types_training_group, get_id_group_training_type, \
    get_or_create_user, get_or_create_group
from bot.handlers.possible_states import PossibleStates

router = Router()

@router.message(Command(commands='add'))
@router.message(F.video_note)
@router.message(F.video)
async def handle_select_trainig_type(message: Message, state: FSMContext):
    """Обработка видео-кружочка - спрашиваем количество с удобными кнопками"""
    if not message or not message.from_user:
        print("❌ Нет данных: update.message или from_user отсутствует")
        return

    user = await get_or_create_user(user_id=message.from_user.id,
                                    username=message.from_user.username,
                                    first_name=message.from_user.first_name,
                                    last_name=message.from_user.last_name)
    group = await get_or_create_group(group_id=str(message.chat.id),
                                      group_name=message.chat.title,
                                      topic_id=message.message_thread_id)
    group_id = group.group_id
    topic_id = message.message_thread_id if message else None

    async with async_session() as session:
        result = await session.execute(
            select(Group).where((Group.group_id == group_id) &
                                (Group.topic_id == topic_id))
        )
        group = result.scalar_one_or_none()
        if group:
            print(f"🔍 Найдена группа {group.group_id}, проверяю topic_id={topic_id} vs {group.topic_id}")
        else:
            print(f"❌ Группа {group_id} не найдена в БД")
            return

    # ОЧИЩАЕМ предыдущие состояния
    await state.clear()

    # Удобные кнопки для разных уровней нагрузки
    all_types_training_group = await get_all_types_training_group(group_id=group_id)

    if len(all_types_training_group) == 0:
        await message.answer('''Чтобы записывать подходы к упражнениям, добавьте их типы через команду /add_type''')
        return

    keyboard = []
    for type in all_types_training_group:
        keyboard.append([InlineKeyboardButton(text=type, callback_data='type_'+type)])
    keyboard.append([InlineKeyboardButton(text='⏭️ Пропустить', callback_data='type_cancel')])
    reply_markup = InlineKeyboardMarkup(inline_keyboard=keyboard)

    await message.answer(
        "💪 Выберите тип упражнения:",
        reply_markup=reply_markup
    )

    print(f'user_id={message.from_user.id}')

    await state.set_state(PossibleStates.awaiting_type_training)

@router.callback_query(PossibleStates.awaiting_type_training)
async def handle_awaiting_type_training(callback: CallbackQuery, state: FSMContext):
    type_training = callback.data.split('_')[1]
    print(f'type_training: {type_training}, user_id={callback.from_user.id}')

    if type_training == 'cancel':
        await state.clear()
        await callback.message.delete()
        return

    keyboard = [
        [InlineKeyboardButton(text="10", callback_data="count_10"),
         InlineKeyboardButton(text="15", callback_data="count_15")],
        [InlineKeyboardButton(text="20", callback_data="count_20"),
         InlineKeyboardButton(text="30", callback_data="count_30"),
         InlineKeyboardButton(text="Другое число", callback_data="count_custom")],
        [InlineKeyboardButton(text="⏭️ Пропустить", callback_data="count_0")]
    ]

    reply_markup = InlineKeyboardMarkup(inline_keyboard=keyboard)

    await callback.message.edit_text(
        text =f'{type_training}\n\n' +
        '💪 Какое количество вы сделали в этом подходе?\n' +
        '• Выберите стандартную величину\n' +
        '• Или введите своё число\n' +
        '• ⏭️ Пропустить',
        reply_markup=reply_markup
    )

    await state.clear()

    # Сохраняем информацию о кружочке
    await state.set_data({
        'training_type': type_training,
        'last_video_note': callback.message.video_note,
        'user_id': callback.message.from_user.id
    })

    await state.set_state(PossibleStates.awaiting_count)

    print(f"📹 Установлены состояния после видео: {state}")

@router.callback_query(PossibleStates.awaiting_count)
async def handle_count_callback(callback: CallbackQuery, state: FSMContext, bot: Bot):
    """Обработка выбора количества через кнопки"""
    state_user_id = await state.get_value('user_id')
    training_type = await state.get_value('training_type')

    if state_user_id is None:
        await state.clear()
        return

    if state_user_id != callback.message.from_user.id:
        await bot.send_message(
            chat_id=callback.message.chat.id,
            message_thread_id=callback.message.message_thread_id,
            text=f'''Пользователь @{callback.from_user.username}, вы не можете выбирать количество отжиманий за других'''
        )
        return

    await callback.answer()

    user_id = callback.from_user.id
    group_id = str(callback.message.chat.id) if callback.message else None
    count_str = callback.data.split('_')[1]

    if count_str == 'custom':
        # Для кнопки "Другое число" запрашиваем точное число
        print("🔔 Запрошен ввод своего числа")

        keyboard = [
            [InlineKeyboardButton(text="Отмена", callback_data="count_cancel")]
        ]
        reply_markup = InlineKeyboardMarkup(inline_keyboard=keyboard)

        # ОЧИЩАЕМ предыдущие состояния и устанавливаем новое
        await state.clear()  # Очищаем все предыдущие состояния

        await state.set_state(PossibleStates.awaiting_count)
        await state.set_data({
            'user_id': user_id,
            'bot_msg_id': callback.message.message_id,
            'training_type': training_type
        })

        print(f"🔔 Установлены состояния: {await state.get_data()}")

        await callback.message.edit_text(
            "🔢 Введите точное количество отжиманий:\n\n"
            "Отправьте число сообщением\n"
            "Примеры: 15, 30, 42\n\n",
            reply_markup=reply_markup
        )
        return

    elif count_str == '0' or count_str == 'cancel':
        # Для кнопки "Пропустить" - просто удаляем сообщение
        print("🔔 Пропуск подхода - удаляем сообщение")
        await callback.message.delete()
        await state.clear()
        return

    else:
        # Для числовых кнопок обрабатываем как обычно
        count = int(count_str)
        print(f"🔔 Обрабатываем {count} отжиманий")
        await process_pushup_count(bot=bot,
                                   bot_message_id=callback.message.message_id,
                                   group_id=group_id,
                                   topic_id=callback.message.message_thread_id,
                                   user_id=user_id,
                                   count=count,
                                   training_type=training_type)

        await state.clear()
        print("✅ Состояние очищено")

@router.message(PossibleStates.awaiting_count)
async def handle_pushup_text_input(message: Message, state: FSMContext, bot: Bot):
    """Обработка текстового ввода количества отжиманий"""

    """Проверка что пользователь выполнял шаги до этого"""
    state_user_id = await state.get_value('user_id')
    training_type = await state.get_value('training_type')

    if state_user_id is None or training_type is None:
        await state.clear()
        return

    if state_user_id != message.from_user.id:
        await bot.send_message(
            chat_id=message.chat.id,
            message_thread_id=message.message_thread_id,
            text=f'''Пользователь @{message.from_user.username}, вы не можете выбирать количество отжиманий за других'''
        )
        return


    if not message:
        print("❌ Нет update.message")
        return
    if not message.text:
        print("❌ Нет текста в сообщении")
        return


    user_id = message.from_user.id
    text = message.text.strip()

    print(f"🔍 Получен текст от user_id={user_id}: '{text}'")
    print(f"🔍 ВСЕ user_data: {message.from_user}")

    # ПРОВЕРЯЕМ СОСТОЯНИЯ
    user_id_in_context = await state.get_value('user_id')
    try:
        count = int(text)

        if count == 0:
            user_msg_id = message.message_id
            bot_msg_id = await state.get_value('bot_msg_id')

            await message.delete()
            if bot_msg_id:
                await bot.delete_message(
                    chat_id=message.chat.id,
                    message_id=bot_msg_id
                )

            await state.clear()
            await message.delete()
            print("✅ Удалено сообщение пользователя и сообщение бота, состояние очищено")
            return

        if count < 0:
            await message.reply_text("❌ Число не может быть отрицательным")
            return

        if count > 200:
            await message.reply_text("❌ Слишком большое число. Максимум 200")
            return

        # Получаем group_id
        group_id = str(message.chat.id)
        bot_message_id = await state.get_value('bot_msg_id')
        # ПЕРЕДАЕМ update, user_id, count, group_id
        await process_pushup_count(bot=bot,
                                   bot_message_id=bot_message_id,
                                   group_id=group_id,
                                   topic_id=message.message_thread_id,
                                   user_id=user_id,
                                   count=count,
                                   training_type=training_type)
        await message.chat.delete_message(message.message_id)

        # Очищаем состояние
        await state.clear()
        print("✅ Состояние очищено")

    except ValueError:
        await message.answer("❌ Пожалуйста, введите число (например: 15, 30, 42)")



async def process_pushup_count(bot: Bot, bot_message_id, group_id: str, topic_id, user_id, count, training_type):
    """Обработка введенного количества отжиманий"""
    summary_record, today_total, actual_count = await add_pushups(user_id=user_id, group_id=group_id, type_record=training_type, count=count, topic_id=topic_id)
    user = await get_or_create_user(user_id=user_id)

    if count <= 15:
        emoji = "👶"
        level = "Начальный уровень"
    elif count <= 30:
        emoji = "💪"
        level = "Средний уровень"
    elif count <= 50:
        emoji = "🔥"
        level = "Продвинутый уровень"
    else:
        emoji = "🏆"
        level = "Экспертный уровень"

    # ПРАВИЛЬНО определяем как отвечать
    await bot.edit_message_text(
        chat_id=group_id,
        message_id=bot_message_id,
        text=
            f"{training_type} пользователя @{user.username}\n\n"
            f"{emoji} {level}\n"
            f"✔️ Засчитано: {actual_count}!\n"
            f"📅 Сегодня: {today_total}\n"
            f"📈 За всё время: {summary_record}\n"
            f"⭐ Отличная работа! Продолжайте в том же духе! 🎯"
    )

@router.message(Command(commands='/cancel'))
async def cancel_command(message: Message, state: FSMContext):
    """Команда отмены ввода"""
    # Очищаем состояние
    await state.clear()
    await message.answer("❌ Ввод отменен")


# async def handle_pushup_text_circles(message: Message, state: FSMContext):
#     """Обработка текстовых кружочков"""
#     if not message or not message.from_user:
#         return
#
#     user = message.from_user
#     user_id = user.id
#
#
#     # Проверяем, не ожидаем ли мы ввод числа
#     if await state.get_value('awaiting_exact_count') or await state.get_value('awaiting_pushup_count'):
#         print("🔍 Пропускаем текстовые кружочки - ожидаем ввод числа")
#         return
#
#     # Проверяем есть ли кружочек в текстовом сообщении
#     message_text = message.text or ""
#     circle_pattern = r'[○⚪⭕🔵🔘◯〇⚬🔄💪]'
#     circles = re.findall(circle_pattern, message_text)
#
#     if circles:
#         count = len(circles)
#         today_total, actual_count, used_weight = await add_pushups(user_id, count)
#
#         await message.answer(
#             f"💪 Засчитано: {actual_count} отжиманий за текстовые кружочки!\n"
#             f"📊 Сегодня: {today_total} отжиманий\n"
#             f"⚖️ Вес кружка: {used_weight}"
#         )


# async def correct_pushups_command(message: Message):
#     """Команда /correct - ручная корректировка"""
#     if not context.args:
#         await update.message.reply_text("Используйте: /correct <число>")
#         return
#
#     try:
#         correct_count = int(context.args[0])
#         user_id = update.message.from_user.id
#         group_id = str(update.effective_chat.id) if update.effective_chat else None
#         topic_id = update.message.message_thread_id if update.message else None
#
#         # Обновляем счетчик
#         today_total, actual_count, used_weight = await add_pushups(user_id=user_id, group_id=group_id, count=correct_count, topic_id=topic_id)
#
#         await update.message.reply_text(
#             f"✅ Исправлено! Засчитано: {actual_count} отжиманий\n"
#             f"📊 Сегодня: {today_total} отжиманий"
#         )
#
#     except ValueError:
#         await update.message.reply_text("❌ Используйте число после команды")