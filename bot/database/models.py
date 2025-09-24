from sqlalchemy import Column, Integer, String, Date, Boolean, ForeignKey, Table
from sqlalchemy.orm import relationship
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.dialects.sqlite import JSON
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
    username = Column(String(100))
    first_name = Column(String(100))
    last_name = Column(String(100))
    has_consent = Column(Boolean, default=False)
    last_activity = Column(Date)
    message_count = Column(Integer, default=0)
    created_at = Column(Date, default=datetime.now)

    # Связь с группами
    groups = relationship("Group", secondary=user_group_association, back_populates="members")

    # Статистика отжиманий (общая для всех групп)
    pushups_today = Column(Integer, default=0)
    pushups_total = Column(Integer, default=0)
    last_pushup_date = Column(Date)
    pushup_history = Column(JSON, default=[])
    circle_weight = Column(Integer, default=1)


class DailyPushup(Base):
    __tablename__ = 'daily_pushups'

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'))
    group_id = Column(Integer, ForeignKey('groups.id'))
    topic_id = Column(Integer, default=None)
    date = Column(Date, default=datetime.now().date)
    count = Column(Integer, default=0)

    # Связи
    user = relationship("User")
    group = relationship("Group")

class Group(Base):
    __tablename__ = 'groups'

    id = Column(Integer, primary_key=True)
    group_id = Column(String, unique=True, nullable=False)  # Telegram group ID (отрицательное число)
    group_name = Column(String(200))
    created_at = Column(Date, default=datetime.now)
    is_topics_enabled = Column(Boolean, default=False)
    topic_id = Column(String, nullable=True)

    # Связь с пользователями
    members = relationship("User", secondary=user_group_association, back_populates="groups")

    # Статистика группы
    total_pushups = Column(Integer, default=0)
    last_activity = Column(Date)


class GroupPushupRecord(Base):
    __tablename__ = 'group_pushup_records'

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'))
    group_id = Column(Integer, ForeignKey('groups.id'))
    count = Column(Integer, nullable=False)
    date = Column(Date, default=datetime.now)
    created_at = Column(Date, default=datetime.now)

    # Связи
    user = relationship("User")
    group = relationship("Group")