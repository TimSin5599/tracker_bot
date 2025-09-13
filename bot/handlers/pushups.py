import re
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, MessageHandler, filters, CommandHandler, CallbackQueryHandler
from bot.database.storage import add_pushups, get_today_pushups, get_pushup_stats, get_user_consent, set_circle_weight, \
    get_circle_weight


async def handle_pushup_video_note(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка видео-кружочка - спрашиваем количество с удобными кнопками"""
    if not update.message or not update.message.from_user:
        return

    user = update.message.from_user
    user_id = user.id

    has_consent = await get_user_consent(user_id)
    if not has_consent:
        await update.message.reply_text("❌ Сначала дайте согласие на отслеживание через /start")
        return

    if update.message.video_note:
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

    count_str = callback_data.split('_')[1]

    if count_str == 'custom':
        # Для кнопки "Другое число" запрашиваем точное число
        print("🔔 Запрошен ввод своего числа")

        # ОЧИЩАЕМ предыдущие состояния и устанавливаем новое
        context.user_data.clear()  # Очищаем все предыдущие состояния
        context.user_data['awaiting_exact_count'] = True
        context.user_data['user_id'] = user_id

        print(f"🔔 Установлены состояния: {context.user_data}")

        await query.edit_message_text(
            "🔢 Введите точное количество отжиманий:\n\n"
            "Отправьте число сообщением\n"
            "Примеры: 15, 30, 42\n\n"
            "Или /cancel для отмены"
        )
        return

    elif count_str == '0':
        # Для кнопки "Пропустить" - просто удаляем сообщение
        print("🔔 Пропуск подхода - удаляем сообщение")
        await query.delete_message()
        return

    else:
        # Для числовых кнопок обрабатываем как обычно
        count = int(count_str)
        print(f"🔔 Обрабатываем {count} отжиманий")
        await process_pushup_count(update, user_id, count)


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
            if count < 0:
                await update.message.reply_text("❌ Число не может быть отрицательным")
                return

            if count > 200:
                await update.message.reply_text("❌ Слишком большое число. Максимум 200")
                return

            # ПЕРЕДАЕМ update и user_id
            await process_pushup_count(update, user_id, count)

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

            # ПЕРЕДАЕМ update и user_id
            await process_pushup_count(update, user_id, count)

            # Очищаем состояние
            context.user_data.clear()
            print("✅ Состояние очищено")

        except ValueError:
            await update.message.reply_text("❌ Пожалуйста, введите число или используйте кнопки")

    else:
        print("🔍 Не ожидаем ввод, проверяем на текстовые кружочки...")
        await handle_pushup_text_circles(update, context)


async def process_pushup_count(update, user_id, count):
    """Обработка введенного количества отжиманий"""
    # Убрали проверку на 0, так как она теперь обрабатывается в callback

    # Добавляем отжимания в базу
    today_total, actual_count, used_weight = await add_pushups(user_id, count)

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
            f"⚖️ Вес кружка: {used_weight}\n\n"
            f"🎯 Отличная работа! Продолжайте в том же духе!"
        )
    else:
        # Если это текстовое сообщение
        await update.message.reply_text(
            f"{emoji} {level}\n"
            f"✅ Засчитано: {actual_count} отжиманий!\n"
            f"📊 Сегодня: {today_total} отжиманий\n"
            f"⚖️ Вес кружка: {used_weight}\n\n"
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

    has_consent = await get_user_consent(user_id)
    if not has_consent:
        return

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
    # Обработка VIDEO_NOTE (кружочков)
    application.add_handler(MessageHandler(
        filters.VIDEO_NOTE,
        handle_pushup_video_note
    ))

    # Обработка текстовых кружочков
    application.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND,
        handle_pushup_text_circles
    ))

    # Обработка callback для выбора количества
    application.add_handler(CallbackQueryHandler(
        handle_pushup_count_callback,
        pattern="^pushup_"
    ))

    # Обработка текстового ввода количества
    application.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND,
        handle_pushup_text_input
    ))

    # Команды
    application.add_handler(CommandHandler("pushups", pushups_stats_command))
    application.add_handler(CommandHandler("my_pushups", my_pushups_command))
    application.add_handler(CommandHandler("set_weight", set_weight_command))
    application.add_handler(CommandHandler("stats", stats_command))
    application.add_handler(CommandHandler("correct", correct_pushups_command))
    application.add_handler(CommandHandler("cancel", cancel_command))

async def pushups_stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /pushups - статистика отжиманий"""
    stats = await get_pushup_stats()

    if not stats:
        await update.message.reply_text("📊 Нет данных об отжиманиях")
        return

    response = "🏆 Статистика отжиманий:\n\n"
    for i, user in enumerate(stats, 1):
        last_date = user['last_date'].strftime("%d.%m.%Y %H:%M") if user['last_date'] else "никогда"
        response += f"{i}. {user['username']}:\n"
        response += f"   📅 Сегодня: {user['today']}\n"
        response += f"   🏋️ Всего: {user['total']}\n"
        response += f"   ⏰ Последние: {last_date}\n\n"

    await update.message.reply_text(response)


async def my_pushups_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /my_pushups - мои отжимания"""
    user = update.message.from_user

    has_consent = await get_user_consent(user.id)
    if not has_consent:
        await update.message.reply_text("❌ Сначала дайте согласие на отслеживание через /start")
        return

    today_count = await get_today_pushups(user.id)
    weight = await get_circle_weight(user.id)

    await update.message.reply_text(
        f"📊 Ваши отжимания сегодня:\n"
        f"💪 Сделано: {today_count}\n"
        f"⚖️ Вес кружка: {weight} отжимание\n"
        f"🎯 Отправляйте кружочки ○ чтобы добавить отжимания!"
    )


async def set_weight_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /set_weight - установка веса кружка"""
    user = update.message.from_user

    has_consent = await get_user_consent(user.id)
    if not has_consent:
        await update.message.reply_text("❌ Сначала дайте согласие на отслеживание через /start")
        return

    # Проверяем аргументы команды
    if not context.args:
        current_weight = await get_circle_weight(user.id)
        await update.message.reply_text(
            f"⚖️ Текущий вес кружка: {current_weight} отжимание за 1 кружок\n"
            f"Используйте: /set_weight <число>\n"
            f"Например: /set_weight 5"
        )
        return

    try:
        new_weight = int(context.args[0])
        if new_weight < 1 or new_weight > 100:
            await update.message.reply_text("❌ Вес кружка должен быть от 1 до 100")
            return

        result_weight = await set_circle_weight(user.id, new_weight)
        await update.message.reply_text(
            f"✅ Вес кружка установлен: {result_weight} отжимание за 1 кружок\n"
            f"Теперь каждый кружочек будет считать как {result_weight} отжиманий!"
        )
    except ValueError:
        await update.message.reply_text("❌ Используйте число после команды: /set_weight 5")


async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /stats - полная статистика"""
    from bot.database.storage import get_active_users_stats

    # Получаем обе статистики
    activity_stats = await get_active_users_stats()
    pushup_stats = await get_pushup_stats()

    if not activity_stats and not pushup_stats:
        await update.message.reply_text("📊 Нет данных для отображения")
        return

    response = "📊 ПОЛНАЯ СТАТИСТИКА\n\n"

    # Статистика активности
    response += "👥 АКТИВНОСТЬ:\n"
    if activity_stats:
        for i, user in enumerate(activity_stats[:5], 1):
            last_seen = user['last_activity'].strftime("%d.%m.%Y %H:%M") if user['last_activity'] else "никогда"
            response += f"{i}. {user['username'] or user['first_name']}:\n"
            response += f"   📨 Сообщений: {user['message_count']}\n"
            response += f"   ⏰ Последняя активность: {last_seen}\n\n"
    else:
        response += "   Нет данных\n\n"

    # Статистика отжиманий
    response += "🏆 ОТЖИМАНИЯ (сегодня):\n"
    if pushup_stats:
        for i, user in enumerate(pushup_stats[:5], 1):
            response += f"{i}. {user['username']}: {user['today']} отжиманий\n"
    else:
        response += "   Нет данных\n\n"

    response += "\nℹ️ Используйте /pushups для детальной статистики отжиманий"

    await update.message.reply_text(response)


async def correct_pushups_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /correct - ручная корректировка"""
    if not context.args:
        await update.message.reply_text("Используйте: /correct <число>")
        return

    try:
        correct_count = int(context.args[0])
        user_id = update.message.from_user.id

        # Обновляем счетчик
        today_total, actual_count, used_weight = await add_pushups(user_id, correct_count)

        await update.message.reply_text(
            f"✅ Исправлено! Засчитано: {actual_count} отжиманий\n"
            f"📊 Сегодня: {today_total} отжиманий"
        )

    except ValueError:
        await update.message.reply_text("❌ Используйте число после команды")


async def cancel_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /cancel - отмена ввода"""
    # Очищаем состояние
    context.user_data.pop('awaiting_pushup_count', None)
    context.user_data.pop('awaiting_exact_count', None)
    context.user_data.pop('last_video_note', None)
    context.user_data.pop('user_id', None)

    await update.message.reply_text("❌ Ввод отменен")


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
        filters.VIDEO_NOTE,
        handle_pushup_video_note
    ))

    # 4. Команды
    print("📌 Регистрируем команды...")
    application.add_handler(CommandHandler("pushups", pushups_stats_command))
    application.add_handler(CommandHandler("my_pushups", my_pushups_command))
    application.add_handler(CommandHandler("set_weight", set_weight_command))
    application.add_handler(CommandHandler("stats", stats_command))
    application.add_handler(CommandHandler("correct", correct_pushups_command))
    application.add_handler(CommandHandler("cancel", cancel_command))

    print("✅ Все обработчики зарегистрированы")