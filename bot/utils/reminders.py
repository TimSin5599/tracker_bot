from sklearn.metrics import mean_squared_log_error

from bot.database.session import async_session
from datetime import time
from telegram.ext import ContextTypes
from bot.database.storage import get_users_without_pushups_today
from config.settings import settings
from sqlalchemy import select
from bot.database.models import Group
import pytz

MOSCOW_TZ = pytz.timezone("Europe/Moscow")


async def send_reminders(context: ContextTypes.DEFAULT_TYPE):
    async with async_session() as session:
        # Берём все группы
        groups = await session.execute(select(Group))
        groups = groups.scalars().all()

        for group in groups:
            # Получаем пользователей этой группы
            users = await get_users_without_pushups_today(group_id=group.group_id)

            if users:
                # Если есть "прогульщики"
                report_text = "⏰ Напоминание!\nДо конца дня осталось 2 часа.\n\n"
                report_text += "❌ Эти пользователи ещё не сделали отжимания:\n"
                report_text += "\n".join([u.username or u.first_name for u in users])
            else:
                # Все молодцы
                report_text = "✅ Все молодцы! Сегодня все сделали отжимания 🎉"

            try:
                await context.bot.send_message(chat_id=group.group_id, text=report_text, message_thread_id=group.topic_id)
            except Exception as e:
                print(f"Не удалось отправить сообщение в группу {group.group_id}: {e}")



async def send_daily_report(context: ContextTypes.DEFAULT_TYPE):
    """Отправка отчета в 00:00 о тех, кто не сделал отжимания"""
    async with async_session() as session:
        groups = await session.execute(select(Group))
        groups = groups.scalars().all()

        for group in groups:
            users_without_pushups = await get_users_without_pushups_today(group_id=group.group_id)

            if users_without_pushups:
                report_text = "📊 Отчет за день:\n\n"
                report_text += "❌ Не сделали отжимания сегодня:\n"

                for user in users_without_pushups:
                    report_text += f"• {user.username or user.first_name}\n"

                # Отправляем отчет админам
                # for admin_id in settings.ADMIN_IDS:
                #     print("ADMIN_IDS:", settings.ADMIN_IDS, type(settings.ADMIN_IDS))
                #     try:
                #         await context.bot.send_message(chat_id=admin_id, text=report_text)
                #     except Exception as e:
                #         print(f"Не удалось отправить отчет админу {admin_id}: {e}")

            try:
                await context.bot.send_message(chat_id=group.group_id, text=report_text, message_thread_id=group.topic_id)
            except Exception as e:
                print(f"Не удалось отправить сообщение в группу {group.group_id}: {e}")

            # Сбрасываем дневные счетчики
            from bot.database.storage import reset_daily_pushups
            await reset_daily_pushups()


def setup_reminders(application):
    """Настройка напоминаний"""
    # Напоминание за 2 часа до конца дня (22:00)
    application.job_queue.run_daily(
        send_reminders,
        time(hour=22, minute=00, tzinfo=MOSCOW_TZ),  # 22:00
        name="daily_reminders"
    )

    # Отчет в полночь (00:00)
    application.job_queue.run_daily(
        send_daily_report,
        time(hour=0, minute=0, tzinfo=MOSCOW_TZ),  # 00:00
        name="daily_report"
    )