from datetime import datetime, date
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
            )
            session.add(user)
            await session.commit()
            await session.refresh(user)

        return user


async def get_or_create_group(group_id: str, group_name: str = 'private', topic_id: int = None):
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
                topic_id=topic_id,
                created_at=date.today(),
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


async def add_pushups(user_id: int,
                      group_id: str,
                      type_record_id: int,
                      group_name: str = None,
                      topic_id: str = None,
                      count: int = 0):
    """Добавление отжиманий пользователю в конкретной группе"""

    async with async_session() as session:
        user = await get_or_create_user(user_id, "", "")
        group = await get_or_create_group(group_id, group_name, topic_id)
        await add_user_to_group(user_id, group_id, group_name, topic_id)

        # Ежедневная запись пользователя из группы по конкретному типу тренировки
        result = await session.execute(
            select(DailyGroupRecords.count).where(
                DailyGroupRecords.user_id == user_id,
                DailyGroupRecords.group_id == group_id,
                DailyGroupRecords.type_record_id == type_record_id
            )
        )
        daily_count = result.scalar_one_or_none()

        if daily_count:
            daily_count += count
            await session.execute(
                update(DailyGroupRecords)
                .where(DailyGroupRecords.user_id == user_id,
                       DailyGroupRecords.group_id == group_id,
                       DailyGroupRecords.type_record_id == type_record_id)
                .values(count=daily_count, date=datetime.now())
            )
        else:
            group_record = DailyGroupRecords(
                user_id=user_id,
                group_id=group_id,
                type_record_id=type_record_id,
                count=count,
                date=datetime.now()
            )
            session.add(group_record)

        # Обновляем общую статистику группы
        result = await session.execute(
            select(GroupsRecords.summary_count)
            .where(GroupsRecords.group_id == group_id,
                   GroupsRecords.type_record_id == type_record_id)
        )
        summary_record = result.scalar_one_or_none()

        if summary_record:
            summary_record += count
        else:
            group_record = GroupsRecords(
                group_id=group_id,
                type_record_id=type_record_id,
                summary_count=count
            )
            session.add(group_record)

        # Обновляем общую статистику пользователя
        result = await session.execute(
            select(UsersRecords.summary_count).where(
                UsersRecords.user_id == user_id,
                GroupsRecords.type_record_id == type_record_id
            )
        )
        summary_record = result.scalar_one_or_none()

        if summary_record:
            summary_record += count

            await session.execute(
                update(UsersRecords)
                .where(UsersRecords.user_id == user_id,
                       GroupsRecords.type_record_id == type_record_id)
                .values(summary_count=summary_record)
            )
        else:
            user_record = UsersRecords(
                user_id=user_id,
                type_record_id=type_record_id,
                summary_count=count
            )
            session.add(user_record)

        total_user_record = summary_record if not None else count
        await session.commit()

        return total_user_record, count


async def get_id_group_training_type(group_id: str, training_type: str):
    async with async_session() as session:
        result = await session.execute(
            select(RecordTypes.id)
            .where(RecordTypes.group_id == group_id)
            .where(RecordTypes.record_type == training_type)
        )
        training_type_id = result.scalar_one_or_none()
        return training_type_id


async def get_all_types_training_group(group_id: str):
    async with async_session() as session:
        result = await session.execute(
            select(RecordTypes.record_type)
            .where(RecordTypes.group_id == group_id)
        )
        records = result.scalars().all()
        return records


async def add_training_type(group_id: str, training_type: str, required_count: int):
    async with async_session() as session:
        record_types = RecordTypes(
            group_id=group_id,
            record_type=training_type,
            required=required_count
        )
        session.add(record_types)
        await session.commit()


async def get_group_stats(group_id: str, training_type: str):
    """Получение статистики по отжиманиям в группе"""
    async with async_session() as session:
        group = await get_or_create_group(group_id)
        training_type_id = await get_id_group_training_type(group_id, training_type)

        # Подгружаем участников
        group = await session.get(Group, group.id, options=[selectinload(Group.members)])

        # Получаем статистику по участникам группы
        result = await session.execute(
            select(User, func.sum(DailyGroupRecords.count).label('today'))
            .join(user_group_association, User.id == user_group_association.c.user_id)
            .join(Group, Group.id == user_group_association.c.group_id)
            .join(DailyGroupRecords, and_(DailyGroupRecords.user_id == User.id,
                                          DailyGroupRecords.group_id == Group.id))
            .where(Group.group_id == group_id,
                   DailyGroupRecords.type_record_id == training_type_id)
            .group_by(User.id)
        )

        today_stats = result.all()

        # Получаем общую статистику по группе
        result = await session.execute(
            select(User, func.sum(GroupsRecords.summary_count).label('total_pushups'))
            .join(user_group_association, User.id == user_group_association.c.user_id)
            .join(Group, Group.id == user_group_association.c.group_id)
            .where(Group.group_id == group_id)
            .group_by(User.id)
        )

        total_stats = result.all()

        # Формируем объединенную статистику
        stats = []
        for user, total in total_stats:
            today = next((today for u, today in today_stats if u.id == user.id), 0)
            print(f'user - {user.username}, total - {total}, today - {today}')
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


async def get_user_group_stats(user_id: int, group_id: str, training_type: str):
    async with async_session() as session:
        user = await get_or_create_user(user_id, "", "")
        group = await get_or_create_group(group_id)
        training_type_id = await get_id_group_training_type(group_id, training_type)
        await add_user_to_group(user_id, group_id)

        result = await session.execute(
            select(DailyGroupRecords.count)
            .where(DailyGroupRecords.user_id == user_id,
                   DailyGroupRecords.group_id == group_id)
        )
        today = result.scalar_one_or_none() or 0

        result = await session.execute(
            select(func.sum(GroupsRecords.summary_count))
            .where(GroupsRecords.group_id == group.id,
                   GroupsRecords.type_record_id == training_type_id)
        )
        total = result.scalar_one_or_none() or 0

        return {
            'user_id': user.user_id,
            'group_id': group.group_id,
            'today': today,
            'total': total
        }


async def get_today_records(user_id: int, group_id: str, type_record_id: int):
    async with async_session() as session:
        user = await get_or_create_user(user_id, "", "")

        result = await session.execute(
            select(DailyGroupRecords.count)
            .where(DailyGroupRecords.user_id == user.id,
                   DailyGroupRecords.group_id == group_id,
                   DailyGroupRecords.type_record_id == type_record_id)
        )
        count = result.scalar_one_or_none() or 0
        return count


async def get_total_records(user_id: int, type_record_id: int):
    async with async_session() as session:
        user = await get_or_create_user(user_id, "", "")

        result = await session.execute(
            select(UsersRecords.summary_count)
            .where(UsersRecords.user_id == user.id,
                   UsersRecords.type_record_id == type_record_id)
        )
        count = result.scalar_one_or_none() or 0
        return count


async def get_user_stats(user_id: int, type_record_id: int):
    async with async_session() as session:
        await get_or_create_user(user_id, "", "")

        # Результат за сегодня
        result_today = await session.execute(
            select(func.coalesce(func.sum(DailyGroupRecords.count), 0))
            .where(DailyGroupRecords.user_id == user_id,
                   DailyGroupRecords.type_record_id == type_record_id)
        )
        today_pushups = result_today.scalar_one_or_none() or 0

        # Результат за все время
        result_total = await session.execute(
            select(func.coalesce(UsersRecords.summary_count, 0))
            .where(UsersRecords.user_id == user_id,
                   UsersRecords.type_record_id == type_record_id)
        )
        total_pushups = result_total.scalar_one_or_none() or 0

        return {
            'today': today_pushups,
            'total': total_pushups
        }


async def get_users_without_training_today(group: Group, training_type: str):
    async with (async_session() as session):
        training_type_id = await get_id_group_training_type(group.group_id, training_type)
        required_count = await get_required_count(group_id=group.group_id, training_type=training_type)
        print(f'Required count: {required_count}, training_type_id: {training_type_id}')

        subquery = (
            select(DailyGroupRecords.user_id,
                   func.coalesce(func.sum(DailyGroupRecords.count), 0).label("count")
                   )
            .where(
                DailyGroupRecords.type_record_id == training_type_id,
            )
            .group_by(DailyGroupRecords.user_id)
            .subquery()
        )

        daily_sum = aliased(subquery)

        result = await session.execute(
            select(User)
            .join(user_group_association, User.id == user_group_association.c.user_id)
            .where(user_group_association.c.group_id == group.id)
            .outerjoin(daily_sum, User.id == daily_sum.c.user_id)
            .where(
                or_(DailyGroupRecords.count is None,
                    DailyGroupRecords.count < int(required_count))
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
        await session.commit()


async def get_required_count(group_id: str, training_type: str):
    async with async_session() as session:
        result = await session.execute(
            select(RecordTypes.required)
            .where(RecordTypes.group_id == group_id,
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

# async def reset_daily_pushups():
#     """
#     Сбрасывает дневные счетчики отжиманий и возвращает список пользователей,
#     которые не сделали отжимания сегодня.
#     """
#     async with async_session() as session:
#         # Получаем всех пользователей
#         result = await session.execute(select(User.id, User.username, User.first_name, User.pushups_today))
#         all_users = result.all()
#
#         # Пользователи, которые не сделали отжимания
#         users_not_done = [
#             {"user_id": user.id, "username": user.username, "first_name": user.first_name, "pushups_today": user.pushups_today}
#             for user in all_users
#             if int(user.pushups_today) < int(settings.REQUIRED_PUSHUPS)
#         ]
#
#         await session.execute(
#             update(User).values(pushups_today=0)
#         )
#
#         # Сбрасываем все записи отжиманий
#         await session.execute(delete(DailyPushup))
#         await session.commit()
#
#     return users_not_done
