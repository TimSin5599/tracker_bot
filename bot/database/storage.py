from datetime import datetime, date
from sqlalchemy import select, func, and_, delete, or_
from sqlalchemy.orm import selectinload, aliased
from sqlalchemy.sql.sqltypes import NULLTYPE

from bot.database.models import Base, User, Group, GroupPushupRecord, DailyPushup, user_group_association
from bot.database.session import async_session
from bot.database.session import engine
import os

from config.settings import settings

# Создаем папку data если не существует
os.makedirs(os.path.dirname(settings.DB_PATH), exist_ok=True)  # или используйте settings.DB_PATH

async def init_database():
    """Инициализация базы данных"""
    async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)


async def get_or_create_user(user_id: int, username: str, first_name: str, last_name: str = None):
    """Получает или создает пользователя без передачи session"""
    async with async_session() as session:
        result = await session.execute(
            select(User).where(User.user_id == user_id)
        )
        user = result.scalar_one_or_none()

        if not user:
            user = User(
                user_id=user_id,
                username=username,
                first_name=first_name,
                last_name=last_name,
                created_at=datetime.now()
            )
            session.add(user)
            await session.commit()
            await session.refresh(user)

        return user


async def get_or_create_group(group_id: str, group_name: str = None, topic_id: str = None):
    """Получает или создает группу без передачи session"""
    async with async_session() as session:
        result = await session.execute(
            select(Group)
            .where(Group.group_id == group_id)
        )
        group = result.scalar_one_or_none()


        if not group:
            group = Group(
                group_id=group_id,
                group_name=group_name,
                created_at=date.today(),
                is_topics_enabled=False,
                topic_id=topic_id,
                total_pushups=0,
                last_activity=None
            )
            session.add(group)
            await session.commit()
            await session.refresh(group)

        return group


async def add_user_to_group(user_id: int, group_id: str, group_name: str = None, topic_id: str = None):
    """Добавляет пользователя в группу, безопасно проверяя наличие"""
    async with async_session() as session:
        user = await get_or_create_user(user_id, "", "")
        group = await get_or_create_group(group_id, group_name, topic_id)
        user = await session.get(User, user.id, options=[selectinload(User.groups)])
        group = await session.get(Group, group.id)
        if group not in user.groups:
            user.groups.append(group)
            await session.commit()


async def add_pushups(user_id: int, group_id: str, count: int = 1, group_name: str = None, topic_id: str = None):
    """Добавление отжиманий пользователю в конкретной группе"""
    today = date.today()
    async with async_session() as session:
        user = await get_or_create_user(user_id, "", "")
        group = await get_or_create_group(group_id, group_name, topic_id)
        await add_user_to_group(user_id, group_id, group_name, topic_id)

        # Получаем вес кружка
        weight = user.circle_weight or 1
        actual_count = count * weight

        # Записываем в общую историю группы
        group_record = GroupPushupRecord(
            user_id=user.id,
            group_id=group.id,
            count=actual_count,
            date=datetime.now()
        )
        session.add(group_record)

        # Обновляем ежедневные отжимания
        result = await session.execute(
            select(DailyPushup).where(
                DailyPushup.user_id == user.id,
                DailyPushup.group_id == group.id,
                DailyPushup.date == today
            )
        )
        daily_record = result.scalar_one_or_none()

        if daily_record:
            daily_record.count += actual_count
        else:
            daily_record = DailyPushup(
                user_id=user.id,
                group_id=group.id,
                topic_id=topic_id if topic_id else None,
                date=today,
                count=actual_count
            )
            session.add(daily_record)

        # Обновляем общую статистику
        user.pushups_total += actual_count

        # безопасно подгружаем members для группы
        group = await session.get(Group, group.id, options=[selectinload(Group.members)])
        group.total_pushups += actual_count
        group.last_activity = datetime.now()

        result_total = await session.execute(
            select(func.coalesce(func.sum(DailyPushup.count), 0))
            .where(DailyPushup.user_id == user.id)
        )
        total_pushups = result_total.scalar_one_or_none() or 0

        await session.commit()
        return total_pushups, actual_count, weight


async def get_group_stats(group_id: str):
    """Получение статистики по отжиманиям в группе"""
    async with async_session() as session:
        group = await get_or_create_group(group_id)

        # Подгружаем участников
        group = await session.get(Group, group.id, options=[selectinload(Group.members)])

        # Получаем статистику по участникам группы
        result = await session.execute(
            select(User, func.sum(DailyPushup.count).label('today_pushups'))
            .join(user_group_association, User.id == user_group_association.c.user_id)
            .join(Group, Group.id == user_group_association.c.group_id)
            .join(DailyPushup, and_(DailyPushup.user_id == User.id, DailyPushup.group_id == Group.id))
            .where(Group.group_id == group_id, DailyPushup.date == date.today())
            .group_by(User.id)
        )

        today_stats = result.all()

        # Получаем общую статистику по группе
        result = await session.execute(
            select(User, func.sum(GroupPushupRecord.count).label('total_pushups'))
            .join(user_group_association, User.id == user_group_association.c.user_id)
            .join(Group, Group.id == user_group_association.c.group_id)
            .join(GroupPushupRecord, GroupPushupRecord.user_id == User.id)
            .where(Group.group_id == group_id)
            .group_by(User.id)
        )

        total_stats = result.all()

        # Формируем объединенную статистику
        stats = []
        for user, total in total_stats:
            today = next((today for u, today in today_stats if u.id == user.id), 0)
            stats.append({
                'user_id': user.user_id,
                'username': user.username or user.first_name,
                'today_pushups': today or 0,
                'total_pushups': total or 0
            })

        return {
            'group_name': group.group_name,
            'total_pushups': group.total_pushups,
            'member_count': len(group.members),
            'members': sorted(stats, key=lambda x: x['today_pushups'], reverse=True)
        }


async def get_user_group_stats(user_id: int, group_id: str):
    async with async_session() as session:
        user = await get_or_create_user(user_id, "", "")
        group = await get_or_create_group(group_id)
        await add_user_to_group(user_id, group_id)

        today = date.today()

        result = await session.execute(
            select(DailyPushup.count)
            .where(DailyPushup.user_id == user.id,
                   DailyPushup.group_id == group.id,
                   DailyPushup.date == today)
        )
        today_pushups = result.scalar_one_or_none() or 0

        result = await session.execute(
            select(func.sum(GroupPushupRecord.count))
            .where(GroupPushupRecord.user_id == user.id,
                   GroupPushupRecord.group_id == group.id)
        )
        total_pushups = result.scalar_one_or_none() or 0

        return {
            'user_id': user.user_id,
            'group_id': group.group_id,
            'today_pushups': today_pushups,
            'total_pushups': total_pushups
        }


async def get_today_pushups(user_id: int, group_id: str):
    async with async_session() as session:
        user = await get_or_create_user(user_id, "", "")
        group = await get_or_create_group(group_id)

        today = date.today()

        result = await session.execute(
            select(DailyPushup.count)
            .where(DailyPushup.user_id == user.id,
                   DailyPushup.group_id == group.id,
                   DailyPushup.date == today)
        )
        count = result.scalar_one_or_none() or 0
        return count


# async def set_circle_weight(user_id: int, weight: int):
#     async with async_session() as session:
#         result = await session.execute(
#             select(User).where(User.user_id == user_id)
#         )
#         user = result.scalar_one_or_none()
#         if user:
#             user.circle_weight = weight
#             await session.commit()
#             return True
#         return False


# async def get_circle_weight(user_id: int):
#     async with async_session() as session:
#         result = await session.execute(
#             select(User.circle_weight).where(User.user_id == user_id)
#         )
#         weight = result.scalar_one_or_none()
#         return weight or 1


async def get_pushup_stats(user_id: int = None, group_id: str = None):
    """
    Получить статистику по отжиманиям:
    1. Если указан group_id и НЕ указан user_id: вернуть список пользователей с ключами user_id, username, today_pushups, total_pushups.
    2. Если указан user_id и НЕ указан group_id: вернуть суммарные данные пользователя.
    3. Если указаны оба: вернуть статистику пользователя в конкретной группе.
    """
    async with async_session() as session:
        if group_id is not None and user_id is None:
            # 1. Список пользователей группы с их статистикой
            group = await get_or_create_group(group_id)
            group = await session.get(Group, group.id, options=[selectinload(Group.members)])
            stats = []
            for member in group.members:
                # Статистика сегодня
                result_today = await session.execute(
                    select(func.coalesce(func.sum(DailyPushup.count), 0))
                    .where(DailyPushup.user_id == member.id,
                           DailyPushup.group_id == group.id,
                           DailyPushup.date == date.today())
                )
                today_pushups = result_today.scalar_one_or_none() or 0
                # Общая статистика
                result_total = await session.execute(
                    select(func.coalesce(func.sum(GroupPushupRecord.count), 0))
                    .where(GroupPushupRecord.user_id == member.id,
                           GroupPushupRecord.group_id == group.id)
                )
                total_pushups = result_total.scalar_one_or_none() or 0
                stats.append({
                    'user_id': member.user_id,
                    'username': member.username or member.first_name,
                    'today_pushups': today_pushups,
                    'total_pushups': total_pushups
                })
            return sorted(stats, key=lambda x: x['today_pushups'], reverse=True)
        elif user_id is not None and group_id is None:
            # Статистика конкретного пользователя по всем группам, данные из DailyPushup
            user = await get_or_create_user(user_id, "", "")

            # Суммируем все отжимания по всем группам
            result_total = await session.execute(
                select(func.coalesce(func.sum(DailyPushup.count), 0))
                .where(DailyPushup.user_id == user.id)
            )
            total = result_total.scalar_one_or_none() or 0

            # Считаем количество дней, когда пользователь делал хотя бы одно отжимание
            result_days = await session.execute(
                select(func.count(func.distinct(DailyPushup.date)))
                .where(DailyPushup.user_id == user.id)
            )
            days = result_days.scalar_one_or_none() or 0

            return {
                'user_id': user.user_id,
                'username': user.username or user.first_name,
                'total_pushups': total,
                'days_active': days
            }
        elif group_id is not None and user_id is not None:
            # 3. Статистика пользователя в конкретной группе
            user = await get_or_create_user(user_id, "", "")
            result_today = await session.execute(
                select(func.coalesce(func.sum(DailyPushup.count), 0))
                .where(DailyPushup.user_id == user.id,
                       DailyPushup.date == date.today())
            )
            today_pushups = result_today.scalar_one_or_none() or 0
            result_total = await session.execute(
                select(func.coalesce(func.sum(DailyPushup.count), 0))
                .where(DailyPushup.user_id == user.id)
            )
            total_pushups = result_total.scalar_one_or_none() or 0
            return {
                'group_id': group_id,
                'user_id': user.user_id,
                'username': user.username or user.first_name,
                'today_pushups': today_pushups,
                'total_pushups': total_pushups
            }
        else:
            raise ValueError("Необходимо указать хотя бы user_id или group_id")


async def get_users_without_pushups_today(group: Group):
    async with (async_session() as session):
        today = date.today()

        subquery = (
            select(DailyPushup.user_id,
                   func.coalesce(func.sum(DailyPushup.count), 0).label("total_pushups")
            )
            .where(
    DailyPushup.group_id == group.group_id,
                DailyPushup.topic_id == group.topic_id,
                DailyPushup.date == today,
            )
            .group_by(DailyPushup.user_id)
            .subquery()
        )

        daily_sum = aliased(subquery)

        result = await session.execute(
            select(User)
            .join(user_group_association, User.id == user_group_association.c.user_id)
            .where(user_group_association.c.group_id == group.id)
            .outerjoin(daily_sum, User.id == daily_sum.c.user_id)
            .where(
                or_(daily_sum.c.total_pushups == None,
                daily_sum.c.total_pushups < settings.REQUIRED_PUSHUPS)
            )
        )
        users = result.scalars().all()
        return users

async def update_user_activity(
    user_id: int,
    username: str,
    first_name: str,
    last_name: str = None,
    group_id: str = None,
    group_name: str = None,
    topic_id: str = None,
):
    async with async_session() as session:
        user = await get_or_create_user(user_id, username, first_name, last_name)
        if group_id:
            group = await get_or_create_group(group_id, group_name, topic_id)
            await add_user_to_group(user_id, group_id, group_name)
        user.last_activity = datetime.now()
        user.message_count += 1
        await session.commit()

# --- Пользовательское согласие ---
async def save_user_consent(user_id: int, username: str, first_name: str):
    """Сохраняет согласие пользователя на участие. Если согласие уже дано, возвращает соответствующее сообщение"""
    async with async_session() as session:
        user = await get_or_create_user(user_id, username, first_name)

        user.last_activity = datetime.now()
        await session.commit()
        return "✅ Согласие сохранено."

async def reset_daily_pushups():
    """
    Сбрасывает дневные счетчики отжиманий и возвращает список пользователей,
    которые не сделали отжимания сегодня.
    """
    async with async_session() as session:
        # Получаем всех пользователей
        result = await session.execute(select(User.id, User.username, User.first_name))
        all_users = result.all()

        # Получаем пользователей, которые сделали отжимания
        result_done = await session.execute(select(DailyPushup.user_id))
        users_done_ids = {row.user_id for row in result_done.all()}

        # Пользователи, которые не сделали отжимания
        users_not_done = [
            {"user_id": user.id, "username": user.username, "first_name": user.first_name}
            for user in all_users
            if user.id not in users_done_ids
        ]

        # Сбрасываем все записи отжиманий
        await session.execute(delete(DailyPushup))
        await session.commit()

    return users_not_done