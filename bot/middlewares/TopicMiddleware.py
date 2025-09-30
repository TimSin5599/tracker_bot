from aiogram.types import Update, TelegramObject
from aiogram import BaseMiddleware
from typing import Callable, Dict, Any, Awaitable

from bot.database.models import Group
from bot.database.session import async_session
from sqlalchemy import select


class TopicMiddlewares(BaseMiddleware):
    async def __call__(
            self,
            handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
            event: Update,
            data: Dict[str, Any]
    ) -> Any:

        if not isinstance(event, Update) or not event.message:
            return await handler(event, data)

        chat_id = str(event.message.chat.id)
        topic_id = getattr(event.message, 'message_thread_id', None)
        print(f"group - {chat_id}, topic_id - {topic_id}")
        async with async_session() as session:
            result = await session.execute(
                select(Group).where(Group.group_id == chat_id)
            )
            group = result.scalar_one_or_none()

        if group is None:
            return await handler(event, data)

        if group.topic_id is not None and int(group.topic_id) != int(topic_id):
            return

        return await handler(event, data)
