import re
from aiogram import Router, F, Bot
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext

from sqlalchemy import select
from bot.database.models import Group

from bot.database.session import async_session
from bot.database.storage import add_pushups

router = Router()

@router.message(F.video_note)
async def handle_pushup_video_note(message: Message, state: FSMContext):
    """Обработка видео-кружочка - спрашиваем количество с удобными кнопками"""
    if not message or not message.from_user:
        print("❌ Нет данных: update.message или from_user отсутствует")
        return

    group_id = message.chat.id if message.chat else None
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

    user = message.from_user

    if message.video_note or message.video:
        # ОЧИЩАЕМ предыдущие состояния
        await state.clear()

        # Удобные кнопки для разных уровней нагрузки
        keyboard = [
            [InlineKeyboardButton(text="15 отжиманий", callback_data="pushup_15"),
             InlineKeyboardButton(text="30 отжиманий", callback_data="pushup_30")],
            [InlineKeyboardButton(text="50 отжиманий", callback_data="pushup_50"),
             InlineKeyboardButton(text="Другое число", callback_data="pushup_custom")],
            [InlineKeyboardButton(text="⏭️ Пропустить", callback_data="pushup_0")]
        ]
        reply_markup = InlineKeyboardMarkup(inline_keyboard=keyboard)

        await message.answer(
            "💪 Сколько отжиманий вы сделали в этом подходе?\n\n"
            "• Выберите стандартное количество\n"
            "• Или введите своё число\n"
            "• ⏭️ Пропустить",
            reply_markup=reply_markup
        )

        # Сохраняем информацию о кружочке
        await state.set_data({
            "last_video_note": message.video_note,
            'awaiting_pushup_count': True
        })

        print(f"📹 Установлены состояния после видео: {state}")

@router.callback_query(F.data.startswith("pushup_"))
async def handle_pushup_count_callback(callback: CallbackQuery, state: FSMContext, bot: Bot):
    """Обработка выбора количества отжиманий через кнопки"""
    await callback.answer()

    user_id = callback.from_user.id
    # callback_data = query.data
    # print(f"🔔 Получен callback: {callback_data}")

    group_id = callback.message.chat.id if callback.message else None

    count_str = callback.data.split('_')[1]

    if count_str == 'custom':
        # Для кнопки "Другое число" запрашиваем точное число
        print("🔔 Запрошен ввод своего числа")

        keyboard = [
            [InlineKeyboardButton(text="Отмена", callback_data="pushup_cancel")]
        ]
        reply_markup = InlineKeyboardMarkup(inline_keyboard=keyboard)

        # ОЧИЩАЕМ предыдущие состояния и устанавливаем новое
        await state.clear()  # Очищаем все предыдущие состояния
        await state.set_data({
            'awaiting_exact_count': True,
            'user_id': user_id,
            'bot_msg_id': callback.message.message_id,
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
        await process_pushup_count(bot, callback.message.message_id, group_id, callback.message.message_thread_id, user_id, count)

@router.message(F.text)
async def handle_pushup_text_input(message: Message, state: FSMContext, bot: Bot):
    """Обработка текстового ввода количества отжиманий"""
    print("🎯 handle_pushup_text_input ВЫЗВАН!")

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
    awaiting_exact = await state.get_value('awaiting_exact_count')
    user_id_in_context = await state.get_value('user_id')

    print(f"🔍 Состояния: exact={awaiting_exact}, context_user_id={user_id_in_context}")

    # ПРИОРИТЕТ: сначала exact, потом pushup
    if awaiting_exact and user_id_in_context == user_id:
        print("🔍 Обрабатываем как точное число...")
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

                message.user_data.clear()
                print("✅ Удалено сообщение пользователя и сообщение бота, состояние очищено")
                return

            if count < 0:
                await message.reply_text("❌ Число не может быть отрицательным")
                return

            if count > 200:
                await message.reply_text("❌ Слишком большое число. Максимум 200")
                return

            # Получаем group_id
            group_id = message.chat.id if message.chat else None
            bot_message_id = await state.get_value('bot_msg_id')
            # ПЕРЕДАЕМ update, user_id, count, group_id
            await process_pushup_count(bot, bot_message_id, group_id, message.message_thread_id, user_id, count)
            await message.chat.delete_message(message.message_id)

            # Очищаем состояние
            await state.clear()
            print("✅ Состояние очищено")

        except ValueError:
            await message.reply_text("❌ Пожалуйста, введите число (например: 15, 30, 42)")

    else:
        print("🔍 Не ожидаем ввод, проверяем на текстовые кружочки...")
        await handle_pushup_text_circles(message, state)


async def process_pushup_count(bot: Bot, bot_message_id, group_id, topic_id, user_id, count):
    """Обработка введенного количества отжиманий"""

    today_total, actual_count, used_weight = await add_pushups(user_id=user_id, group_id=group_id, count=count, topic_id=topic_id)

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
        f"{emoji} {level}\n"
        f"✅ Засчитано: {actual_count} отжиманий!\n"
        f"📊 Сегодня: {today_total} отжиманий\n"
        f"🎯 Отличная работа! Продолжайте в том же духе!"
    )

@router.message(Command(commands='/cancel'))
async def cancel_command(message: Message, state: FSMContext):
    """Команда отмены ввода"""
    # Очищаем состояние
    await state.clear()
    await message.answer("❌ Ввод отменен")


async def handle_pushup_text_circles(message: Message, state: FSMContext):
    """Обработка текстовых кружочков"""
    if not message or not message.from_user:
        return

    user = message.from_user
    user_id = user.id


    # Проверяем, не ожидаем ли мы ввод числа
    if await state.get_value('awaiting_exact_count') or await state.get_value('awaiting_pushup_count'):
        print("🔍 Пропускаем текстовые кружочки - ожидаем ввод числа")
        return

    # Проверяем есть ли кружочек в текстовом сообщении
    message_text = message.text or ""
    circle_pattern = r'[○⚪⭕🔵🔘◯〇⚬🔄💪]'
    circles = re.findall(circle_pattern, message_text)

    if circles:
        count = len(circles)
        today_total, actual_count, used_weight = await add_pushups(user_id, count)

        await message.answer(
            f"💪 Засчитано: {actual_count} отжиманий за текстовые кружочки!\n"
            f"📊 Сегодня: {today_total} отжиманий\n"
            f"⚖️ Вес кружка: {used_weight}"
        )


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