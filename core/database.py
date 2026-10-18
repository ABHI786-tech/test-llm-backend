import os

from dotenv import load_dotenv
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

load_dotenv()

engine = create_async_engine(
    os.getenv("DATABASE_URL"),
    echo=True,
    pool_size=10,
    max_overflow=5,
)
async_session = async_sessionmaker(bind=engine, autoflush=False, class_=AsyncSession)


class Base(DeclarativeBase):
    pass


async def get_db():
    async with async_session() as db:
        yield db