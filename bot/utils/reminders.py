import os
from datetime import time
from telegram.ext import ContextTypes
from bot.database.storage import get_users_without_pushups_today
from config.settings import settings
import pytz

MOSCOW_TZ = pytz.timezone("Europe/Moscow")


async def send_reminders(context, chat_id: int):
    users = await get_users_without_pushups_today()

    chat_members_ids = set()
    admins = await context.bot.get_chat_administrators(chat_id)
    chat_members_ids.update(admin.user.id for admin in admins)

    for user in users:
        if user['user_id'] in chat_members_ids:
            # Пользователь есть в чате — не пишем в личку
            continue
        try:
            await context.bot.send_message(
                chat_id=user['user_id'],
                text="⏰ Напоминание! До конца дня осталось 2 часа..."
            )
        except Exception as e:
            print(f"Не удалось отправить напоминание пользователю {user['user_id']}: {e}")

    # Отправка отчета в чат
    report_text = "📊 Отчет за день:\n"
    report_text += "\n".join([u['username'] or u['first_name'] for u in users if u['user_id'] in chat_members_ids])
    await context.bot.send_message(chat_id=chat_id, text=report_text)



async def send_daily_report(context: ContextTypes.DEFAULT_TYPE):
    """Отправка отчета в 00:00 о тех, кто не сделал отжимания"""
    users_without_pushups = await get_users_without_pushups_today()

    if users_without_pushups:
        report_text = "📊 Отчет за день:\n\n"
        report_text += "❌ Не сделали отжимания сегодня:\n"

        for user in users_without_pushups:
            report_text += f"• {user['username'] or user['first_name']}\n"

        # Отправляем отчет админам
        for admin_id in settings.ADMIN_IDS:
            print("ADMIN_IDS:", settings.ADMIN_IDS, type(settings.ADMIN_IDS))
            try:
                await context.bot.send_message(chat_id=admin_id, text=report_text)
            except Exception as e:
                print(f"Не удалось отправить отчет админу {admin_id}: {e}")

    # Сбрасываем дневные счетчики
    from bot.database.storage import reset_daily_pushups
    await reset_daily_pushups()


def setup_reminders(application):
    """Настройка напоминаний"""
    # Напоминание за 2 часа до конца дня (22:00)
    application.job_queue.run_daily(
        send_reminders,
        time(hour=14, minute=2, tzinfo=MOSCOW_TZ),  # 22:00
        name="daily_reminders"
    )

    # Отчет в полночь (00:00)
    application.job_queue.run_daily(
        send_daily_report,
        time(hour=0, minute=0, tzinfo=MOSCOW_TZ),  # 00:00
        name="daily_report"
    )