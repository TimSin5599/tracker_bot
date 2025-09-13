from sqlalchemy import Column, Integer, String, DateTime, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.dialects.sqlite import JSON
from datetime import datetime

Base = declarative_base()

class User(Base):
    __tablename__ = 'users'

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, unique=True, nullable=False)
    username = Column(String(100))
    first_name = Column(String(100))
    last_name = Column(String(100))
    has_consent = Column(Boolean, default=False)
    last_activity = Column(DateTime)
    message_count = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.now)
    # Поля для отжиманий
    pushups_today = Column(Integer, default=0)
    pushups_total = Column(Integer, default=0)
    last_pushup_date = Column(DateTime)
    pushup_history = Column(JSON, default=[])
    circle_weight = Column(Integer, default=1)