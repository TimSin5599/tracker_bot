from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from config.settings import settings

DATABASE_URL = f'sqlite+aiosqlite:///{settings.DB_PATH}'

engine = create_async_engine(
    DATABASE_URL,
    echo=True,
    future=True
)

async_session = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False
)