import pytz
from aiogram import Bot
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from sqlalchemy import select

from bot.database.models import Group
from bot.database.session import async_session
from bot.database.storage import get_users_without_pushups_today
from config.settings import settings

MOSCOW_TZ = pytz.timezone("Europe/Moscow")


async def send_reminders(bot: Bot):
    async with async_session() as session:
        # Берём все группы
        groups = await session.execute(select(Group))
        groups = groups.scalars().all()

        for group in groups:
            # Получаем пользователей этой группы
            users = await get_users_without_pushups_today(group=group)

            if users:
                # Если есть "прогульщики"
                report_text = "⏰ Напоминание!\nДо конца дня осталось 2 часа.\n\n"
                report_text += "❌ Эти пользователи ещё не сделали отжимания:\n"
                for user in users:
                    report_text += f" • @{user['username']} (осталось сделать - {int(settings.REQUIRED_PUSHUPS) - user.pushups_today})"
            else:
                # Все молодцы
                report_text = "✅ Все молодцы! Сегодня все сделали отжимания 🎉"

            try:
                await bot.send_message(chat_id=group.group_id, text=report_text, message_thread_id=group.topic_id)
            except Exception as e:
                print(f"Не удалось отправить сообщение в группу {group.group_id}: {e}")



async def send_daily_report(bot: Bot):
    """Отправка отчета в 00:00 о тех, кто не сделал отжимания"""
    async with async_session() as session:
        groups = await session.execute(select(Group))
        groups = groups.scalars().all()

        for group in groups:
            users_without_pushups = await get_users_without_pushups_today(group=group)

            if users_without_pushups:
                report_text = "📊 Отчет за день:\n\n"
                report_text += "❌ Не сделали отжимания сегодня:\n"

                for user in users_without_pushups:
                    report_text += f" • @{user.username} (было сделано - {user.pushups_today})\n"

            try:
                await bot.send_message(chat_id=group.group_id, text=report_text, message_thread_id=group.topic_id)
            except Exception as e:
                print(f"Не удалось отправить сообщение в группу {group.group_id}: {e}")

            # Сбрасываем дневные счетчики
            from bot.database.storage import reset_daily_pushups
            await reset_daily_pushups()


def setup_reminders(bot: Bot):
    """Настройка напоминаний"""
    scheduler = AsyncIOScheduler(timezone=MOSCOW_TZ)

    scheduler.add_job(send_reminders,
                      trigger=CronTrigger(hour=22, minute=0),
                      args=[bot],
                      id='daily_reminders',
                      replace_existing=True)

    scheduler.add_job(send_daily_report,
                      trigger=CronTrigger(hour=0, minute=0),
                      args=[bot],
                      id='daily_report',
                      replace_existing=True)

    scheduler.start()