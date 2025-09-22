# # handlers/tracking.py
# from telegram import Update
# from telegram.ext import ContextTypes, MessageHandler, filters
# from bot.database.storage import update_user_activity, add_pushups
# import re
#
# # Регулярное выражение для поиска кружков
# CIRCLE_PATTERN = re.compile(r'[○⚪⭕🔵🔘◯〇⚬🔄💪]')
#
#
# async def track_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
#     """Отслеживание сообщений и кружков"""
#     if not update.message or not update.message.text:
#         return
#
#     user = update.effective_user
#     chat = update.effective_chat
#     topic_id = update.message.message_thread_id
#
#     # Обновляем активность пользователя
#     await update_user_activity(
#         user_id=user.id,
#         username=user.username,
#         first_name=user.first_name,
#         last_name=user.last_name,
#         group_id=str(chat.id) if chat.type in ['group', 'supergroup'] else None,
#         group_name=chat.title if chat.type in ['group', 'supergroup'] else None,
#         topic_id=topic_id,
#     )
#
#     # Проверяем кружки только в группах
#     if chat.type in ['group', 'supergroup']:
#         circles = CIRCLE_PATTERN.findall(update.message.text)
#         if circles:
#             try:
#                 today_count, actual_count, weight = await add_pushups(
#                     user.id,
#                     str(chat.id),
#                     len(circles),
#                     chat.title
#                 )
#
#                 # Можно добавить реакцию на кружки
#                 if len(circles) > 0:
#                     await update.message.reply_text(
#                         f"✅ +{actual_count} отжиманий! "
#                         f"(×{weight} за {len(circles)} кружков)\n"
#                         f"Сегодня: {today_count} отжиманий"
#                     )
#
#             except Exception as e:
#                 print(f"Error processing circles: {e}")
#
#
# def setup_tracking_handlers(application):
#     """Регистрация обработчиков сообщений"""
#     application.add_handler(MessageHandler(
#         filters.TEXT & ~filters.COMMAND,
#         track_message
#     ))