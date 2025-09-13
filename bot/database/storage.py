import aiosqlite
from datetime import datetime, timedelta, date
from sqlalchemy import select, update, func
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from bot.database.models import Base, User
from config.settings import settings
import os
import json

# Создаем папку data если не существует
os.makedirs(os.path.dirname(settings.DB_PATH), exist_ok=True)

# Используем асинхронный engine для SQLite
engine = create_async_engine(f'sqlite+aiosqlite:///{settings.DB_PATH}')
AsyncSessionLocal = async_sessionmaker(bind=engine, expire_on_commit=False)


async def init_database():
    """Инициализация базы данных"""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def save_user_consent(user_id: int, username: str, first_name: str, has_consent: bool):
    """Сохранение согласия пользователя"""
    async with AsyncSessionLocal() as session:
        # Проверяем есть ли пользователь
        result = await session.execute(
            select(User).where(User.user_id == user_id)
        )
        user = result.scalar_one_or_none()

        if user:
            user.has_consent = has_consent
            user.username = username
            user.first_name = first_name
        else:
            user = User(
                user_id=user_id,
                username=username,
                first_name=first_name,
                has_consent=has_consent,
                last_activity=datetime.now() if has_consent else None
            )
            session.add(user)

        await session.commit()


async def get_user_consent(user_id: int) -> bool:
    """Получение статуса согласия пользователя"""
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(User.has_consent).where(User.user_id == user_id)
        )
        consent = result.scalar_one_or_none()
        return consent if consent else False


async def update_user_activity(user_id: int, username: str, first_name: str,
                               last_name: str = None, message_text: str = None):
    """Обновление активности пользователя"""
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(User).where(User.user_id == user_id)
        )
        user = result.scalar_one_or_none()

        if user:
            user.last_activity = datetime.now()
            user.message_count += 1
            user.username = username
            user.first_name = first_name
            user.last_name = last_name
        else:
            user = User(
                user_id=user_id,
                username=username,
                first_name=first_name,
                last_name=last_name,
                has_consent=True,
                last_activity=datetime.now(),
                message_count=1
            )
            session.add(user)

        await session.commit()


async def get_active_users_stats():
    """Получение статистики активных пользователей"""
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(User).where(User.has_consent == True)
            .order_by(User.last_activity.desc())
        )
        users = result.scalars().all()

        return [{
            'user_id': user.user_id,
            'username': user.username,
            'first_name': user.first_name,
            'last_activity': user.last_activity,
            'message_count': user.message_count
        } for user in users]


async def get_online_users(minutes: int = 5):
    """Получение пользователей онлайн (активных в последние X минут)"""
    time_threshold = datetime.now() - timedelta(minutes=minutes)

    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(User).where(
                User.has_consent == True,
                User.last_activity >= time_threshold
            ).order_by(User.last_activity.desc())
        )
        users = result.scalars().all()

        return [{
            'user_id': user.user_id,
            'username': user.username,
            'first_name': user.first_name,
            'last_activity': user.last_activity
        } for user in users]


async def add_pushups(user_id: int, count: int = 1):
    """Добавление отжиманий пользователю с учетом веса кружка"""
    today = date.today()

    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(User).where(User.user_id == user_id)
        )
        user = result.scalar_one_or_none()

        if user:
            # Получаем вес кружка
            weight = user.circle_weight or 1
            actual_count = count * weight

            # Если последние отжимания были не сегодня, сбрасываем счетчик
            if user.last_pushup_date and user.last_pushup_date.date() != today:
                user.pushups_today = 0

            user.pushups_today += actual_count
            user.pushups_total += actual_count
            user.last_pushup_date = datetime.now()

            # Обновляем историю
            history = user.pushup_history or []
            today_str = today.isoformat()

            # Ищем запись за сегодня
            found = False
            for entry in history:
                if entry['date'] == today_str:
                    entry['count'] += actual_count
                    found = True
                    break

            if not found:
                history.append({'date': today_str, 'count': actual_count})

            user.pushup_history = history

            await session.commit()
            return user.pushups_today, actual_count, weight
    return 0, 0, 1


async def get_today_pushups(user_id: int):
    """Получение количества отжиманий за сегодня"""
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(User.pushups_today).where(User.user_id == user_id)
        )
        count = result.scalar_one_or_none()
        return count or 0


async def get_users_without_pushups_today():
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(User).where(
                User.has_consent == True,
                User.pushups_today < 25
            )
        )
        users = result.scalars().all()

        return [
            {
                "user_id": u.user_id,
                "username": u.username,
                "first_name": u.first_name
            }
            for u in users
        ]



async def reset_daily_pushups():
    """Сброс ежедневных отжиманий (вызывается в 00:00)"""
    async with AsyncSessionLocal() as session:
        await session.execute(
            update(User).values(pushups_today=0)
        )
        await session.commit()


async def get_pushup_stats():
    """Получение статистики по отжиманиям"""
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(User).where(User.has_consent == True)
            .order_by(User.pushups_total.desc())
        )
        users = result.scalars().all()

        return [{
            'username': user.username or user.first_name,
            'today': user.pushups_today,
            'total': user.pushups_total,
            'last_date': user.last_pushup_date
        } for user in users]


async def set_circle_weight(user_id: int, weight: int):
    """Установка веса кружка (сколько отжиманий за 1 кружок)"""
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(User).where(User.user_id == user_id)
        )
        user = result.scalar_one_or_none()

        if user:
            user.circle_weight = max(1, min(weight, 100))  # Ограничиваем от 1 до 100
            await session.commit()
            return user.circle_weight
    return 1


async def get_circle_weight(user_id: int):
    """Получение веса кружка пользователя"""
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(User.circle_weight).where(User.user_id == user_id)
        )
        weight = result.scalar_one_or_none()
        return weight or 1