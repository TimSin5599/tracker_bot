from aiogram import Router, F, Bot
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext

from sqlalchemy import select
from bot.database.models import Group

import logging
from bot.database.session import async_session
from bot.database.storage import (
    add_pushups, check_group_params, check_user_params, 
    get_all_types_training_group, get_id_group_training_type,
    get_or_create_user, get_or_create_group
)
from bot.handlers.possible_states import PossibleStates

logger = logging.getLogger(__name__)


router = Router()

@router.message(Command(commands='add'))
@router.message(F.video_note)
@router.message(F.video)
async def handle_select_trainig_type(message: Message, state: FSMContext):
    """Обработка видео-кружочка - спрашиваем количество с удобными кнопками"""
    if not message or not message.from_user:
        print("❌ Нет данных: update.message или from_user отсутствует")
        return
    
    tg_user_id, tg_username, tg_first_name, tg_last_name = check_user_params(message)
    tg_group_id, tg_group_name, tg_topic_id = check_group_params(message)

    await get_or_create_user(user_id=tg_user_id,
                                username=tg_username,
                                first_name=tg_first_name,
                                last_name=tg_last_name)
    group = await get_or_create_group(group_id=tg_group_id,
                                      group_name=tg_group_name,
                                      topic_id=tg_topic_id)

    async with async_session() as session:
        result = await session.execute(
            select(Group).where((Group.tg_group_id == tg_group_id) &
                                (Group.topic_id == tg_topic_id))
        )
        group = result.scalar_one_or_none()
        if group:
            logger.debug(f"🔍 Найдена группа {group.tg_group_id}, топик={tg_topic_id}")
        else:
            logger.warning(f"❌ Группа {tg_group_id} не найдена в БД")
            return


    # ОЧИЩАЕМ предыдущие состояния
    await state.clear()

    # Удобные кнопки для разных уровней нагрузки
    all_types_training_group = await get_all_types_training_group(group_id=tg_group_id)

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

    await state.set_data({
        'user_id': message.from_user.id,
        'chat_id': message.chat.id,
        'message_id': message.message_id
    })    
    await state.set_state(PossibleStates.awaiting_type_training)


@router.callback_query(PossibleStates.awaiting_type_training)
async def handle_awaiting_type_training(callback: CallbackQuery, state: FSMContext):
    if callback.data is None:
        await state.clear()
        return
    
    type_training = callback.data.split('_')[1]
    data = await state.get_data()
    
    if callback.from_user.id != data.get('user_id'):
        await callback.answer("❌ Это не ваше сообщение!", show_alert=True)
        return


    if type_training == 'cancel':
        await state.clear()
        if isinstance(callback.message, Message):
            await callback.message.delete()
        return

    keyboard = [
        [InlineKeyboardButton(text="20", callback_data="count_20"),
         InlineKeyboardButton(text="25", callback_data="count_25")],
        [InlineKeyboardButton(text="30", callback_data="count_30"),
         InlineKeyboardButton(text="40", callback_data="count_40"),
         InlineKeyboardButton(text="Другое число", callback_data="count_custom")],
        [InlineKeyboardButton(text="⏭️ Пропустить", callback_data="count_0")]
    ]

    reply_markup = InlineKeyboardMarkup(inline_keyboard=keyboard)

    if not isinstance(callback.message, Message):
        await state.clear()
        return
    
    await callback.message.edit_text(
        text =f'{type_training}\n\n' +
        '💪 Какое количество вы сделали в этом подходе?\n' +
        '• Выберите стандартную величину\n' +
        '• Или введите своё число\n' +
        '• ⏭️ Пропустить',
        reply_markup=reply_markup
    )

    # Сохраняем информацию для следующего шага
    await state.update_data({
        'training_type': type_training,
        'bot_message_id': callback.message.message_id
    })

    await state.set_state(PossibleStates.awaiting_count)



@router.callback_query(PossibleStates.awaiting_count)
async def handle_count_callback(callback: CallbackQuery, state: FSMContext, bot: Bot):
    """Обработка выбора количества через кнопки"""
    data = await state.get_data()

    user_id = data.get('user_id')
    training_type = data.get('training_type')

    if callback.from_user.id != user_id:
        await callback.answer("❌ Вы не можете выбирать за других!", show_alert=True)
        return

    await callback.answer()



    if not callback.data:
        await state.clear()
        return
    
    count_str = callback.data.split('_')[1]

    if count_str == 'custom':
        # Для кнопки "Другое число" запрашиваем точное число
        logger.debug("🔔 Запрошен ввод своего числа")

        keyboard = [
            [InlineKeyboardButton(text="Отмена", callback_data="count_cancel")]
        ]
        reply_markup = InlineKeyboardMarkup(inline_keyboard=keyboard)

        # Устанавливаем статус ожидания текста, но сохраняем данные
        await state.set_state(PossibleStates.awaiting_count)
        
        await callback.message.edit_text(
            "🔢 Введите точное количество:\n\n"
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
        logger.info(f"🔔 Обрабатываем {count} тренировок для {callback.from_user.username}")
        
        # Нам нужно восстановить объект сообщения или достаточно данных?
        # process_pushup_count использует message для извлечения параметров
        # В aiogram 3 можно создать объект Message вручную или переделать функцию
        
        await process_pushup_count(
            bot=bot,
            chat_id=callback.message.chat.id,
            message_thread_id=callback.message.message_thread_id,
            user_id=callback.from_user.id,
            username=callback.from_user.username,
            first_name=callback.from_user.first_name,
            last_name=callback.from_user.last_name or "",
            bot_message_id=callback.message.message_id,
            count=count,
            training_type=training_type
        )



        await state.clear()
        print("✅ Состояние очищено")

@router.message(PossibleStates.awaiting_count)
async def handle_pushup_text_input(message: Message, state: FSMContext, bot: Bot):
    """Обработка текстового ввода количества отжиманий"""

    data = await state.get_data()
    user_id = data.get('user_id')
    training_type = data.get('training_type')
    bot_message_id = data.get('bot_message_id') or data.get('bot_msg_id')

    if not user_id or not training_type:
        await state.clear()
        return
    
    if message.from_user is None or message.from_user.id != user_id:
        if message.from_user:
            await message.answer(f"❌ @{message.from_user.username}, вы не можете вводить данные за другого пользователя!")
        return



    if not message:
        print("❌ Нет update.message")
        return
    if not message.text:
        print("❌ Нет текста в сообщении")
        return


    text = message.text.strip()

    logger.debug(f"🔍 Получен текст от user_id={user_id}: '{text}'")
    # print(f"🔍 ВСЕ user_data: {message.from_user}")


    # ПРОВЕРЯЕМ СОСТОЯНИЯ
    user_id_in_context = await state.get_value('user_id')
    try:
        count = int(text)

        if count == 0:
            if bot_message_id:
                try:
                    await bot.delete_message(chat_id=message.chat.id, message_id=bot_message_id)
                except Exception:
                    pass

            await state.clear()
            await message.delete()
            logger.debug("✅ Удалено сообщение пользователя и сообщение бота, состояние очищено")
            return


        if count < 0:
            await message.reply("❌ Число не может быть отрицательным")
            return

        if count > 200:
            await message.reply("❌ Слишком большое число. Максимум 200")
            return

        # Получаем данные из стейта
        data = await state.get_data()
        bot_message_id = data.get('bot_message_id')
        
        # ПЕРЕДАЕМ данные в новую функцию
        await process_pushup_count(
            bot=bot,
            chat_id=message.chat.id,
            message_thread_id=message.message_thread_id,
            user_id=message.from_user.id,
            username=message.from_user.username,
            first_name=message.from_user.first_name,
            last_name=message.from_user.last_name or "",
            bot_message_id=bot_message_id,
            count=count,
            training_type=training_type
        )

        await message.chat.delete_message(message.message_id)

        # Очищаем состояние
        await state.clear()
        print("✅ Состояние очищено")

    except ValueError:
        await message.answer("❌ Пожалуйста, введите число (например: 15, 30, 42)")



async def process_pushup_count(bot: Bot, chat_id, message_thread_id, user_id, username, first_name, last_name, bot_message_id, count, training_type):
    """Обработка введенного количества тренировок и обновление сообщения бота"""
    from bot.database.storage import add_pushups_new
    
    summary_record, today_total, actual_count = await add_pushups_new(
        user_id=user_id, 
        username=username, 
        first_name=first_name, 
        last_name=last_name,
        chat_id=chat_id,
        chat_title="Group", 
        topic_id=message_thread_id,
        type_record=training_type, 
        count=count
    )

    if count <= 15:
        emoji, level = "👶", "Начальный уровень"
    elif count <= 30:
        emoji, level = "💪", "Средний уровень"
    elif count <= 50:
        emoji, level = "🔥", "Продвинутый уровень"
    else:
        emoji, level = "🏆", "Экспертный уровень"

    try:
        await bot.edit_message_text(
            chat_id=chat_id,
            message_id=bot_message_id,
            text=f"{training_type} пользователя @{username}\n\n"
                 f"{emoji} {level}\n"
                 f"✔️ Засчитано: {actual_count}!\n"
                 f"📅 Сегодня: {today_total}\n"
                 f"📈 За всё время: {summary_record}\n"
                 f"⭐ Отличная работа! Продолжайте в том же духе! 🎯"
        )
    except Exception as e:
        logger.error(f"Ошибка при редактировании сообщения: {e}")



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