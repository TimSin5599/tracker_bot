import re
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, MessageHandler, filters, CommandHandler, CallbackQueryHandler
from bot.database.storage import add_pushups


async def handle_pushup_video_note(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка видео-кружочка - спрашиваем количество с удобными кнопками"""
    if not update.message or not update.message.from_user:
        print("❌ Нет данных: update.message или from_user отсутствует")
        return

    user = update.message.from_user
    user_id = user.id


    if update.message.video_note or update.message.video:
        # ОЧИЩАЕМ предыдущие состояния
        context.user_data.clear()

        # Удобные кнопки для разных уровней нагрузки
        keyboard = [
            [InlineKeyboardButton("10 отжиманий", callback_data="pushup_10"),
             InlineKeyboardButton("25 отжиманий", callback_data="pushup_25")],
            [InlineKeyboardButton("50 отжиманий", callback_data="pushup_50"),
             InlineKeyboardButton("Другое число", callback_data="pushup_custom")],
            [InlineKeyboardButton("⏭️ Пропустить", callback_data="pushup_0")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await update.message.reply_text(
            "💪 Сколько отжиманий вы сделали в этом подходе?\n\n"
            "• Выберите стандартное количество\n"
            "• Или введите своё число\n"
            "• ⏭️ Пропустить",
            reply_markup=reply_markup
        )

        # Сохраняем информацию о кружочке
        context.user_data['last_video_note'] = update.message.video_note
        context.user_data['awaiting_pushup_count'] = True
        print(f"📹 Установлены состояния после видео: {context.user_data}")


async def handle_pushup_count_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка выбора количества отжиманий через кнопки"""
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id
    callback_data = query.data
    print(f"🔔 Получен callback: {callback_data}")

    group_id = update.effective_chat.id if update.effective_chat else None

    count_str = callback_data.split('_')[1]

    if count_str == 'custom':
        # Для кнопки "Другое число" запрашиваем точное число
        print("🔔 Запрошен ввод своего числа")

        keyboard = [
            [InlineKeyboardButton("Отмена", callback_data="pushup_cancel")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        # ОЧИЩАЕМ предыдущие состояния и устанавливаем новое
        context.user_data.clear()  # Очищаем все предыдущие состояния
        context.user_data['awaiting_exact_count'] = True
        context.user_data['user_id'] = user_id
        context.user_data['last_bot_message_id'] = update.callback_query.message.message_id

        print(f"🔔 Установлены состояния: {context.user_data}")

        await query.edit_message_text(
            "🔢 Введите точное количество отжиманий:\n\n"
            "Отправьте число сообщением\n"
            "Примеры: 15, 30, 42\n\n",
            reply_markup=reply_markup
        )
        return

    elif count_str == '0' or count_str == 'cancel':
        # Для кнопки "Пропустить" - просто удаляем сообщение
        print("🔔 Пропуск подхода - удаляем сообщение")
        await query.delete_message()
        context.user_data.clear()
        return

    else:
        # Для числовых кнопок обрабатываем как обычно
        count = int(count_str)
        print(f"🔔 Обрабатываем {count} отжиманий")
        await process_pushup_count(update, user_id, count, group_id)


async def handle_pushup_text_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка текстового ввода количества отжиманий"""
    print("🎯 handle_pushup_text_input ВЫЗВАН!")

    if not update.message:
        print("❌ Нет update.message")
        return
    if not update.message.text:
        print("❌ Нет текста в сообщении")
        return

    user_id = update.message.from_user.id
    text = update.message.text.strip()

    print(f"🔍 Получен текст от user_id={user_id}: '{text}'")
    print(f"🔍 ВСЕ user_data: {context.user_data}")

    # ПРОВЕРЯЕМ СОСТОЯНИЯ
    awaiting_exact = context.user_data.get('awaiting_exact_count')
    awaiting_pushup = context.user_data.get('awaiting_pushup_count')
    user_id_in_context = context.user_data.get('user_id')

    print(f"🔍 Состояния: exact={awaiting_exact}, pushup={awaiting_pushup}, context_user_id={user_id_in_context}")

    # ПРИОРИТЕТ: сначала exact, потом pushup
    if awaiting_exact and user_id_in_context == user_id:
        print("🔍 Обрабатываем как точное число...")
        try:
            count = int(text)

            if count == 0:
                user_msg_id = update.message.message_id
                bot_msg_id = context.user_data.get('last_bot_message_id')

                await update.message.delete()
                if bot_msg_id:
                    await update.message.chat.delete_message(bot_msg_id)

                context.user_data.clear()
                print("✅ Удалено сообщение пользователя и сообщение бота, состояние очищено")
                return

            if count < 0:
                await update.message.reply_text("❌ Число не может быть отрицательным")
                return

            if count > 200:
                await update.message.reply_text("❌ Слишком большое число. Максимум 200")
                return

            # Получаем group_id
            group_id = update.effective_chat.id if update.effective_chat else None
            # ПЕРЕДАЕМ update, user_id, count, group_id
            await process_pushup_count(update, user_id, count, group_id)

            # Очищаем состояние
            context.user_data.clear()
            print("✅ Состояние очищено")

        except ValueError:
            await update.message.reply_text("❌ Пожалуйста, введите число (например: 15, 30, 42)")

    elif awaiting_pushup:
        print("🔍 Обрабатываем как число после кружочка...")
        try:
            count = int(text)
            if count < 0:
                await update.message.reply_text("❌ Число не может быть отрицательным")
                return

            if count > 200:
                await update.message.reply_text("❌ Слишком большое число. Максимум 200")
                return

            group_id = update.effective_chat.id if update.effective_chat else None
            # ПЕРЕДАЕМ update, user_id, count, group_id
            await process_pushup_count(update, user_id, count, group_id)

            # Очищаем состояние
            context.user_data.clear()
            print("✅ Состояние очищено")

        except ValueError:
            await update.message.reply_text("❌ Пожалуйста, введите число или используйте кнопки")

    else:
        print("🔍 Не ожидаем ввод, проверяем на текстовые кружочки...")
        await handle_pushup_text_circles(update, context)


async def process_pushup_count(update, user_id, count, group_id):
    """Обработка введенного количества отжиманий"""
    # Убрали проверку на 0, так как она теперь обрабатывается в callback

    # Добавляем отжимания в базу
    today_total, actual_count, used_weight = await add_pushups(user_id, group_id, count)

    # Определяем уровень сложности
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
    if hasattr(update, 'callback_query') and update.callback_query:
        # Если это callback (кнопки)
        await update.callback_query.edit_message_text(
            f"{emoji} {level}\n"
            f"✅ Засчитано: {actual_count} отжиманий!\n"
            f"📊 Сегодня: {today_total} отжиманий\n"
            f"🎯 Отличная работа! Продолжайте в том же духе!"
        )
    else:
        # Если это текстовое сообщение
        await update.message.reply_text(
            f"{emoji} {level}\n"
            f"✅ Засчитано: {actual_count} отжиманий!\n"
            f"📊 Сегодня: {today_total} отжиманий\n"
            f"🎯 Отличная работа! Продолжайте в том же духе!"
        )


async def cancel_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда отмены ввода"""
    # Очищаем состояние
    context.user_data.pop('awaiting_pushup_count', None)
    context.user_data.pop('awaiting_exact_count', None)
    context.user_data.pop('last_video_note', None)
    context.user_data.pop('user_id', None)

    await update.message.reply_text("❌ Ввод отменен")


async def handle_pushup_text_circles(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка текстовых кружочков"""
    if not update.message or not update.message.from_user:
        return

    user = update.message.from_user
    user_id = user.id


    # Проверяем, не ожидаем ли мы ввод числа
    if context.user_data.get('awaiting_exact_count') or context.user_data.get('awaiting_pushup_count'):
        print("🔍 Пропускаем текстовые кружочки - ожидаем ввод числа")
        return

    # Проверяем есть ли кружочек в текстовом сообщении
    message_text = update.message.text or ""
    circle_pattern = r'[○⚪⭕🔵🔘◯〇⚬🔄💪]'
    circles = re.findall(circle_pattern, message_text)

    if circles:
        count = len(circles)
        today_total, actual_count, used_weight = await add_pushups(user_id, count)

        await update.message.reply_text(
            f"💪 Засчитано: {actual_count} отжиманий за текстовые кружочки!\n"
            f"📊 Сегодня: {today_total} отжиманий\n"
            f"⚖️ Вес кружка: {used_weight}"
        )


def setup_pushups_handlers(application):
    """Регистрация обработчиков отжиманий"""
    print("🔄 Регистрируем обработчики отжиманий...")

    # 1. Callback обработчики (ВЫСОКИЙ приоритет)
    application.add_handler(CallbackQueryHandler(
        handle_pushup_count_callback,
        pattern="^pushup_"
    ))

    # 2. Текстовые обработчики (НИЗКИЙ приоритет)
    application.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND,
        handle_pushup_text_input
    ))

    # 3. Обработка видео
    application.add_handler(MessageHandler(
        filters.VIDEO_NOTE | filters.VIDEO,
        handle_pushup_video_note
    ))

    # 4. Команды
    print("📌 Регистрируем команды...")
    application.add_handler(CommandHandler("correct", correct_pushups_command))
    application.add_handler(CommandHandler("cancel", cancel_command))

    print("✅ Все обработчики зарегистрированы")


async def correct_pushups_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /correct - ручная корректировка"""
    if not context.args:
        await update.message.reply_text("Используйте: /correct <число>")
        return

    try:
        correct_count = int(context.args[0])
        user_id = update.message.from_user.id
        group_id = update.effective_chat.id if update.effective_chat else None

        # Обновляем счетчик
        today_total, actual_count, used_weight = await add_pushups(user_id, group_id, correct_count)

        await update.message.reply_text(
            f"✅ Исправлено! Засчитано: {actual_count} отжиманий\n"
            f"📊 Сегодня: {today_total} отжиманий"
        )

    except ValueError:
        await update.message.reply_text("❌ Используйте число после команды")