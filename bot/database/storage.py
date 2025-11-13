from datetime import datetime, date
from typing import Optional

from aiogram.types import Message, User as TG_USER, Chat
from sqlalchemy import select, func, and_, delete, or_, update
from sqlalchemy.orm import selectinload, aliased
from bot.database.models import Base, User, Group, user_group_association, DailyGroupRecords, GroupsRecords, \
    UsersRecords, RecordTypes
from bot.database.session import async_session
from bot.database.session import engine
from config.settings import settings


async def init_database():
    """Инициализация базы данных"""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def get_or_create_user(user_id: int, username: str, first_name: str, last_name: str = ""):
    """Получает или создает пользователя без передачи session"""
    async with async_session() as session:
        result = await session.execute(
            select(User).where(User.tg_user_id == user_id)
        )
        user = result.scalar_one_or_none()

        if not user:
            user = User(
                tg_user_id=user_id,
                username=username,
                first_name=first_name,
                last_name=last_name,
            )
            session.add(user)
            await session.commit()
            await session.refresh(user)

        return user


async def get_or_create_group(group_id: int, group_name: str = 'private', topic_id: int | None = None):
    """Получает или создает группу без передачи session"""
    async with async_session() as session:
        result = await session.execute(
            select(Group)
            .where(Group.tg_group_id == group_id)
        )

        group = result.scalar_one_or_none()

        if not group:
            group = Group(
                tg_group_id=group_id,
                group_name=group_name,
                topic_id=topic_id,
                created_at=date.today(),
            )
            session.add(group)
            await session.commit()
            await session.refresh(group)

        return group

async def get_users_from_group(message: Message):
    async with async_session() as session:
        tg_group_id, tg_group_name, tg_topic_id = check_group_params(message)
        group = await get_or_create_group(tg_group_id, tg_group_name, tg_topic_id)
        
        result = await session.execute(
            select(User)
            .join(user_group_association, User.id == user_group_association.c.user_id)
            .where(user_group_association.c.group_id == group.id)
        )
        users = result.scalars().all()
        return users

async def add_user_to_group(message: Message):
    """Добавляет пользователя в группу, безопасно проверяя наличие"""
    async with async_session() as session:
        tg_user_id, tg_username, tg_first_name, tg_last_name = check_user_params(message)
        tg_group_id, tg_group_name, tg_topic_id = check_group_params(message)

        user = await get_or_create_user(tg_user_id, tg_username, tg_first_name, tg_last_name)
        group = await get_or_create_group(tg_group_id, tg_group_name, tg_topic_id)

        user = await session.get(User, user.id, options=[selectinload(User.groups)])
        group = await session.get(Group, group.id)

        if user is not None and group not in user.groups:
            user.groups.append(group)
            await session.commit()


async def add_pushups(message: Message,
                      type_record: str,
                      count: int = 0):
    """Добавление отжиманий пользователю в конкретной группе"""

    async with async_session() as session:
        tg_user_id, tg_username, tg_first_name, tg_last_name = check_user_params(message)
        tg_group_id, tg_group_name, tg_topic_id = check_group_params(message)

        await get_or_create_user(tg_user_id, tg_username, tg_first_name, tg_last_name)
        await get_or_create_group(tg_group_id, tg_group_name, tg_topic_id)
        
        type_record_id = await get_id_group_training_type(group_id=tg_group_id, training_type=type_record)
        await add_user_to_group(message)

        # Ежедневная запись пользователя из группы по конкретному типу тренировки
        result = await session.execute(
            select(DailyGroupRecords.count).where(
                DailyGroupRecords.tg_user_id == tg_user_id,
                DailyGroupRecords.tg_group_id == tg_group_id,
                DailyGroupRecords.type_record_id == type_record_id
            )
        )
        daily_count = result.scalar_one_or_none()

        if daily_count:
            daily_count += count
            await session.execute(
                update(DailyGroupRecords)
                .where(DailyGroupRecords.tg_user_id == tg_user_id,
                       DailyGroupRecords.tg_group_id == tg_group_id,
                       DailyGroupRecords.type_record_id == type_record_id)
                .values(count=daily_count, date=datetime.now())
            )
        else:
            daily_count = count
            group_record = DailyGroupRecords(
                tg_user_id=tg_user_id,
                tg_group_id=tg_group_id,
                type_record_id=type_record_id,
                count=count,
                date=datetime.now()
            )
            session.add(group_record)

        # Обновляем общую статистику группы
        result = await session.execute(
            select(GroupsRecords.summary_count)
            .where(GroupsRecords.tg_group_id == tg_group_id,
                   GroupsRecords.type_record_id == type_record_id)
        )
        summary_record = result.scalar_one_or_none()

        if summary_record:
            summary_record += count
        else:
            group_record = GroupsRecords(
                tg_group_id=tg_group_id,
                type_record_id=type_record_id,
                summary_count=count
            )
            session.add(group_record)

        # Обновляем общую статистику пользователя
        result = await session.execute(
            select(UsersRecords.summary_count).where(
                UsersRecords.tg_user_id == tg_user_id,
                UsersRecords.type_record_id == type_record_id
            )
        )
        summary_record = result.scalar_one_or_none()

        if summary_record:
            summary_record += count

            await session.execute(
                update(UsersRecords)
                .where(UsersRecords.tg_user_id == tg_user_id,
                       UsersRecords.type_record_id == type_record_id)
                .values(summary_count=summary_record)
            )
        else:
            summary_record = count
            user_record = UsersRecords(
                tg_user_id=tg_user_id,
                type_record_id=type_record_id,
                summary_count=count
            )
            session.add(user_record)

        await session.commit()

        return summary_record, daily_count, count


async def get_id_group_training_type(group_id: int, training_type: str):
    async with async_session() as session:
        result = await session.execute(
            select(RecordTypes.id)
            .where(RecordTypes.tg_group_id == group_id)
            .where(RecordTypes.record_type == training_type)
        )
        training_type_id = result.scalar_one_or_none() or 0
        return training_type_id


async def get_all_types_training_group(group_id: int):
    async with async_session() as session:
        result = await session.execute(
            select(RecordTypes.record_type)
            .where(RecordTypes.tg_group_id == group_id)
        )
        records = result.scalars().all()
        return records


async def add_training_type(group_id: int, training_type: str, required_count: int):
    async with async_session() as session:
        record_types = RecordTypes(
            tg_group_id=group_id,
            record_type=training_type,
            required=required_count
        )
        session.add(record_types)
        await session.commit()


async def get_group_stats(message: Message, training_type: str | None = None):
    """Получение статистики по тренировкам в группе"""
    async with async_session() as session:
        tg_group, group_name, topic_id = check_group_params(message)
        _ = await get_or_create_group(tg_group, group_name, topic_id)
        users = await get_users_from_group(message)
        group_stats = {}

        if training_type:
            # training_type_id = await get_id_group_training_type(group_id, training_type)
            # TO DO:
            print()
        else:
            try:
                for user in users:
                    user_stats = await get_user_stats(message)
                    total_size_trainings = 0
                    for type, stats in user_stats.items():
                            total_size_trainings += int(stats['today'])
                    user_stats['total_size_trainings'] = total_size_trainings
                    group_stats[user.username] = user_stats
            except Exception as e:
                print(e)
        return dict(sorted(group_stats.items(), key=lambda x: x[1]['total_size_trainings'], reverse=True))

# Получение статистики пользователя из определенной группы
async def get_user_group_training_type_stats(message: Message, training_type: str):
    async with async_session() as session:
        tg_user_id, tg_username, tg_first_name, tg_last_name = check_user_params(message)
        tg_group_id, tg_group_name, tg_topic_id = check_group_params(message)

        user = await get_or_create_user(tg_user_id, tg_username, tg_first_name, tg_last_name)
        group = await get_or_create_group(tg_group_id, tg_group_name, tg_topic_id)
        training_type_id = await get_id_group_training_type(tg_group_id, training_type)
        await add_user_to_group(message)

        result = await session.execute(
            select(DailyGroupRecords.count)
            .where(DailyGroupRecords.tg_user_id == tg_user_id,
                   DailyGroupRecords.tg_group_id == tg_group_id,
                   DailyGroupRecords.type_record_id == training_type_id)
        )
        today = result.scalar_one_or_none() or 0

        result = await session.execute(
            select(func.sum(UsersRecords.summary_count))
            .where(UsersRecords.tg_user_id == tg_user_id,
                   UsersRecords.type_record_id == training_type_id)
        )
        total = result.scalar_one_or_none() or 0

        return {
            'user_id': user.tg_user_id,
            'group_id': group.tg_group_id,
            'training_type': training_type,
            'today': today,
            'total': total
        }


async def get_today_records(user_id: int, group_id: str, type_record_id: int):
    async with async_session() as session:
        user = await get_or_create_user(user_id, "", "")

        result = await session.execute(
            select(DailyGroupRecords.count)
            .where(DailyGroupRecords.tg_user_id == user.id,
                   DailyGroupRecords.tg_group_id == group_id,
                   DailyGroupRecords.type_record_id == type_record_id)
        )
        count = result.scalar_one_or_none() or 0
        return count


async def get_total_records(user_id: int, type_record_id: int):
    async with async_session() as session:
        user = await get_or_create_user(user_id, "", "")

        result = await session.execute(
            select(UsersRecords.summary_count)
            .where(UsersRecords.tg_user_id == user.id,
                   UsersRecords.type_record_id == type_record_id)
        )
        count = result.scalar_one_or_none() or 0
        return count


async def get_user_stats(message: Message):
    async with async_session() as session:
        tg_user_id, tg_username, tg_first_name, tg_last_name = check_user_params(message)
        tg_group_id, _, _ = check_group_params(message)
        await get_or_create_user(user_id=tg_user_id, username=tg_username, first_name=tg_first_name, last_name=tg_last_name)

        # Результат за сегодня
        all_types = await get_all_types_training_group(tg_group_id)
        result = {}
        for type in all_types:
            result[type] = await get_user_group_training_type_stats(message,
                                                      training_type=type)
        return result


async def get_users_without_training_today(group: Group):
    async with async_session() as session:
        result = await session.execute(
            select(
                User.username,
                RecordTypes.record_type,
                RecordTypes.required,
                DailyGroupRecords.count
            )
            .select_from(User)
            .join(user_group_association, User.id == user_group_association.c.user_id)
            .join(RecordTypes, RecordTypes.tg_group_id == group.tg_group_id)
            .outerjoin(DailyGroupRecords, and_(
                User.tg_user_id == DailyGroupRecords.tg_user_id,
                RecordTypes.id == DailyGroupRecords.type_record_id,
            ))
            .where(and_(
                user_group_association.c.group_id == group.id,
                or_(
                    DailyGroupRecords.count < RecordTypes.required,
                    DailyGroupRecords.count.is_(None)
                )
            ))
        )
        users_not_done = result.all()
    return users_not_done


async def update_user_activity(message: Message):
    try:
        user_id, username, first_name, last_name = check_user_params(message)
        group_id, group_name, topic_id = check_group_params(message)

        async with async_session() as session:
            await get_or_create_user(user_id, username, first_name, last_name)
            await get_or_create_group(group_id, group_name, topic_id)
            await add_user_to_group(message)
            await session.commit()
    except ValueError as e:
        message.answer(f"❌ Ошибка при обновлении активности пользователя: {e}")


async def get_required_count(group_id: int, training_type: str):
    async with async_session() as session:
        result = await session.execute(
            select(RecordTypes.required)
            .where(RecordTypes.tg_group_id == group_id,
                   RecordTypes.record_type == training_type)
        )

        required_count = result.scalar_one_or_none()
        return required_count


# --- Пользовательское согласие ---
async def save_user_consent(user_id: int, username: str, first_name: str):
    """Сохраняет согласие пользователя на участие. Если согласие уже дано, возвращает соответствующее сообщение"""
    async with async_session() as session:
        user = await get_or_create_user(user_id, username, first_name)
        await session.commit()
        return "✅ Согласие сохранено."

async def reset_daily_trainings(group: Group):
    """
    Сбрасывает дневные счетчики отжиманий и возвращает список пользователей,
    которые не сделали отжимания сегодня.
    """
    async with async_session() as session:
        await session.execute(
            delete(DailyGroupRecords)
            .where(DailyGroupRecords.tg_group_id == group.tg_group_id))
        await session.commit()

def check_user_params(message: Message):

    user_obj: Optional[TG_USER] = message.from_user
    if user_obj is None:
        raise ValueError("Информация о пользователе отсутствует в сообщении.")
    
    user_id = user_obj.id if user_obj.id else None
    username = user_obj.username if user_obj.username else None
    first_name = user_obj.first_name if user_obj.first_name else None
    last_name = user_obj.last_name if user_obj.last_name else ""
    
    if user_id is None or username is None or first_name is None:
        raise ValueError(f"Недостаточно данных: user_id={user_id}, username={username}, first_name={first_name}")
    
    return user_id, username, first_name, last_name

def check_group_params(message: Message):

    group_obj: Optional[Chat] = message.chat
    if group_obj is None:
        raise ValueError("Информация о группе отсутствует в сообщении.")
    
    group_id = group_obj.id if group_obj.id else None
    group_name = group_obj.title if group_obj.title else None
    topic_id = message.message_thread_id if message.message_thread_id else None

    if group_id is None or group_name is None:
        raise ValueError(f"Недостаточно данных: group_id={group_id}, group_name={group_name}, topic_id={topic_id}")
    
    return group_id, group_name, topic_id
