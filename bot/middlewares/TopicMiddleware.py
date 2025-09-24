# from telegram import Update
# from telegram.ext import Application, ContextTypes
# from bot.database.models import Group
# from bot.database.session import async_session
# from sqlalchemy import select
#
# async def topic_check_middleware(update: Update, context: ContextTypes.DEFAULT_TYPE):
#     # Если нет сообщения, просто пропускаем
#     if not update.message:
#         return
#
#     chat_id = update.effective_chat.id
#     topic_id = update.message.message_thread_id
#
#     async with async_session() as session:
#         result = await session.execute(
#             select(Group).where(Group.group_id == str(chat_id))
#         )
#         group = result.scalar_one_or_none()
#
#     # Если топик не совпадает — блокируем обработку
#     if group is None or (group.topic_id is not None and group.topic_id != topic_id):
#         # Прерываем цепочку, сообщение дальше не пойдет к хендлерам
#         raise Exception("Blocked by topic filter")  # Можно заменить на кастомный Exception