# Async SQLAlchemy setup and compatibility upgrades for the SQLite database.

import json

from sqlalchemy import inspect, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from config import settings

engine = create_async_engine(
    settings.database_url, connect_args={"check_same_thread": False}
)

AsyncSessionLocal = async_sessionmaker(
    engine, class_=AsyncSession, expire_on_commit=False
)


class Base(DeclarativeBase):
    # Declarative base shared by all ORM models.

    pass


async def init_db():
    # Create missing tables and upgrade older local databases in place.
    import models

    required_tables = {
        models.Chapter.__tablename__,
        models.Exercise.__tablename__,
        models.Account.__tablename__,
        models.ExerciseCompletion.__tablename__,
        models.Challenge.__tablename__,
    }

    async with engine.begin() as connection:
        existing_tables = await connection.run_sync(
            lambda sync_connection: set(inspect(sync_connection).get_table_names())
        )

        # Create the current schema when opening a fresh or incomplete database.
        if not required_tables.issubset(existing_tables):
            await connection.run_sync(Base.metadata.create_all)

        await connection.execute(
            text("UPDATE chapters SET position = -1 WHERE position IS NULL")
        )

        chapter_columns = await connection.run_sync(
            lambda sync_connection: {
                column["name"]
                for column in inspect(sync_connection).get_columns("chapters")
            }
        )

        if "picture" not in chapter_columns:
            await connection.execute(
                text("ALTER TABLE chapters ADD COLUMN picture VARCHAR")
            )

        # Add challenge-run fields in place so existing learner accounts are preserved.
        account_columns = await connection.run_sync(
            lambda sync_connection: {
                column["name"]
                for column in inspect(sync_connection).get_columns("accounts")
            }
        )

        if "record_time" not in account_columns:
            await connection.execute(
                text("ALTER TABLE accounts ADD COLUMN record_time INTEGER")
            )

        if "start_time" not in account_columns:
            await connection.execute(
                text("ALTER TABLE accounts ADD COLUMN start_time DATETIME")
            )

        if "end_time" not in account_columns:
            await connection.execute(
                text("ALTER TABLE accounts ADD COLUMN end_time DATETIME")
            )

        if "previous_record_time" not in account_columns:
            await connection.execute(
                text("ALTER TABLE accounts ADD COLUMN previous_record_time INTEGER")
            )

        if "current_challenge_id" not in account_columns:
            await connection.execute(
                text("ALTER TABLE accounts ADD COLUMN current_challenge_id INTEGER")
            )

        if "current_challenge_complete" not in account_columns:
            await connection.execute(
                text(
                    "ALTER TABLE accounts ADD COLUMN "
                    "current_challenge_complete BOOLEAN NOT NULL DEFAULT 0"
                )
            )

        # Upgrade older challenge tables and assign a stable initial order by ID.
        challenge_columns = await connection.run_sync(
            lambda sync_connection: {
                column["name"]
                for column in inspect(sync_connection).get_columns("challenges")
            }
        )

        if "position" not in challenge_columns:
            await connection.execute(
                text(
                    "ALTER TABLE challenges "
                    "ADD COLUMN position INTEGER NOT NULL DEFAULT -1"
                )
            )
            challenge_ids = await connection.execute(
                text("SELECT id FROM challenges ORDER BY id")
            )
            for position, (challenge_id,) in enumerate(challenge_ids):
                await connection.execute(
                    text(
                        "UPDATE challenges SET position = :position WHERE id = :id"
                    ),
                    {"position": position, "id": challenge_id},
                )

        # Challenge answers are generated per run; discard legacy stored answer keys.
        if "solution" in challenge_columns:
            await connection.execute(
                text("ALTER TABLE challenges DROP COLUMN solution")
            )

        exercise_columns = await connection.run_sync(
            lambda sync_connection: {
                column["name"]
                for column in inspect(sync_connection).get_columns("exercises")
            }
        )

        # Add columns introduced after the first version without replacing user data.
        if "html_filename" not in exercise_columns:
            await connection.execute(
                text(
                    "ALTER TABLE exercises "
                    "ADD COLUMN html_filename VARCHAR NOT NULL DEFAULT ''"
                )
            )

        if "requires_previous" not in exercise_columns:
            await connection.execute(
                text(
                    "ALTER TABLE exercises "
                    "ADD COLUMN requires_previous BOOLEAN NOT NULL DEFAULT 0"
                )
            )

        if "solution" not in exercise_columns:
            await connection.execute(
                text("ALTER TABLE exercises ADD COLUMN solution JSON")
            )

        def normalize_solutions(sync_connection):
            # Convert legacy scalar solutions to the current list representation.
            rows = sync_connection.execute(
                text("SELECT id, solution FROM exercises")
            ).all()
            for exercise_id, stored_solution in rows:
                if isinstance(stored_solution, str):
                    try:
                        solution = json.loads(stored_solution)
                    except json.JSONDecodeError:
                        solution = stored_solution
                else:
                    solution = stored_solution

                if isinstance(solution, list):
                    continue
                solution_list = [] if solution is None else [solution]
                sync_connection.execute(
                    text("UPDATE exercises SET solution = :solution WHERE id = :id"),
                    {"solution": json.dumps(solution_list), "id": exercise_id},
                )

        await connection.run_sync(normalize_solutions)

        # The old task column was replaced by the separately stored HTML lesson.
        if "task" in exercise_columns:
            await connection.execute(text("ALTER TABLE exercises DROP COLUMN task"))


async def get_db():
    # Yield one request-scoped async session and close it when the request ends.
    async with AsyncSessionLocal() as session:
        yield session
