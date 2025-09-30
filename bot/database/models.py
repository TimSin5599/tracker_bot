from sqlalchemy import Column, Integer, String, Date, ForeignKey, Table
from sqlalchemy.orm import relationship
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime

Base = declarative_base()

user_group_association = Table(
    'user_groups',
    Base.metadata,
    Column('user_id', Integer, ForeignKey('users.id')),
    Column('group_id', Integer, ForeignKey('groups.id'))
)


class User(Base):
    __tablename__ = 'users'

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, unique=True, nullable=False)  # Telegram user ID
    username = Column(String(255))
    first_name = Column(String(255))
    last_name = Column(String(255))
    # has_consent = Column(Boolean, default=False)
    # last_activity = Column(Date)
    # message_count = Column(Integer, default=0)
    # created_at = Column(Date, default=datetime.now)

    # Связь с группами
    groups = relationship("Group", secondary=user_group_association, back_populates="members")

    # Статистика отжиманий (общая для всех групп)
    # pushups_today = Column(Integer, default=0)
    # pushups_total = Column(Integer, default=0)
    # last_pushup_date = Column(Date)
    # pushup_history = Column(JSON, default=[])
    # circle_weight = Column(Integer, default=1)

class Group(Base):
    __tablename__ = 'groups'

    id = Column(Integer, primary_key=True)
    group_id = Column(String(255), unique=True, nullable=False)  # Telegram group ID (отрицательное число)
    group_name = Column(String(255))
    topic_id = Column(Integer, nullable=True)
    created_at = Column(Date, default=datetime.now)
    # is_topics_enabled = Column(Boolean, default=False)

    # Связь с пользователями
    members = relationship("User", secondary=user_group_association, back_populates="groups")

    # Статистика группы
    # total_pushups = Column(Integer, default=0)
    # last_activity = Column(Date)

class RecordTypes(Base):
    __tablename__ = 'record_types'

    id = Column(Integer, primary_key=True)
    group_id = Column(String(255), ForeignKey('groups.group_id'))
    record_type = Column(String(255))

    # Связи
    group = relationship('Group')

class DailyGroupRecords(Base):
    __tablename__ = 'daily_group_records'

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.user_id'))
    group_id = Column(String(255), ForeignKey('groups.group_id'))
    type_record_id = Column(Integer, ForeignKey('record_types.id'))
    count = Column(Integer, nullable=False)
    date = Column(Date, default=datetime.now)

    # Связи
    user = relationship("User")
    group = relationship("Group")
    record_types = relationship("RecordTypes")

class GroupsRecords(Base):
    __tablename__ = 'groups_records'

    id = Column(Integer, primary_key=True)
    group_id = Column(String(255), ForeignKey('groups.group_id'))
    type_record_id = Column(Integer, ForeignKey('record_types.id'))
    summary_count = Column(Integer, nullable=False)

    # Связи
    group = relationship("Group")
    record_types = relationship("RecordTypes")

class UsersRecords(Base):
    __tablename__ = 'users_records'

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.user_id'))
    type_record_id = Column(Integer, ForeignKey('record_types.id'))
    summary_count = Column(Integer, nullable=False)

    # Связи
    group = relationship("User")
    record_types = relationship("RecordTypes")