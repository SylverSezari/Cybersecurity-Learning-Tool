from sqlalchemy import inspect, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from config import settings

engine = create_async_engine(settings.database_url, connect_args={"check_same_thread": False})

AsyncSessionLocal = async_sessionmaker(
    engine, class_=AsyncSession, expire_on_commit=False
)


class Base(DeclarativeBase):
    pass


async def init_db():
    import models

    required_tables = {
        models.Chapter.__tablename__,
        models.Exercise.__tablename__,
        models.Account.__tablename__,
    }

    async with engine.begin() as connection:
        existing_tables = await connection.run_sync(
            lambda sync_connection: set(inspect(sync_connection).get_table_names())
        )

        if not required_tables.issubset(existing_tables):
            await connection.run_sync(Base.metadata.create_all)

        await connection.execute(
            text("UPDATE chapters SET position = -1 WHERE position IS NULL")
        )

        exercise_columns = await connection.run_sync(
            lambda sync_connection: {
                column["name"]
                for column in inspect(sync_connection).get_columns("exercises")
            }
        )

        if "html_filename" not in exercise_columns:
            await connection.execute(
                text(
                    "ALTER TABLE exercises "
                    "ADD COLUMN html_filename VARCHAR NOT NULL DEFAULT ''"
                )
            )


async def get_db():
    async with AsyncSessionLocal() as session:
        yield session
