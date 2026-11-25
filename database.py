# Async SQLAlchemy setup and schema initialization.
from pathlib import Path

from sqlalchemy import event
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from config import settings

engine = create_async_engine(
    settings.database_url,
    connect_args={
        "check_same_thread": False,
        "timeout": 15,
    },
)

@event.listens_for(engine.sync_engine, "connect")
def configure_sqlite_connection(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL;")
    cursor.execute("PRAGMA synchronous=NORMAL;")
    cursor.execute("PRAGMA busy_timeout=15000;")
    cursor.execute("PRAGMA foreign_keys=ON;")
    cursor.close()

AsyncSessionLocal = async_sessionmaker(
    engine, class_=AsyncSession, expire_on_commit=False
)


class Base(DeclarativeBase):
    # Declarative base shared by all ORM models.

    pass


async def init_db():
    # Create tables for a fresh database.
    import models
    
    db_path = make_url(settings.database_url).database
    if db_path and db_path != ":memory:":
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)

    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)


async def get_db():
    # Yield one request-scoped async session and close it when the request ends.
    async with AsyncSessionLocal() as session:
        yield session
