from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import inspect, text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

import database
import models


@pytest.mark.anyio
async def test_init_db_migrates_exercise_fields_and_drops_challenge_solution(
    tmp_path,
    monkeypatch,
):
    legacy_engine = create_async_engine(
        f"sqlite+aiosqlite:///{tmp_path / 'legacy.db'}",
        connect_args={"check_same_thread": False},
    )
    monkeypatch.setattr(database, "engine", legacy_engine)

    async with legacy_engine.begin() as connection:
        await connection.execute(
            text(
                "CREATE TABLE chapters ("
                "id INTEGER PRIMARY KEY, title VARCHAR(50) NOT NULL UNIQUE, "
                "position INTEGER NOT NULL, active BOOLEAN NOT NULL)"
            )
        )
        await connection.execute(
            text(
                "CREATE TABLE exercises ("
                "id INTEGER PRIMARY KEY, title VARCHAR(100) NOT NULL UNIQUE, "
                "html_filename VARCHAR NOT NULL UNIQUE, task BOOLEAN NOT NULL, "
                "position INTEGER, chapter_id INTEGER)"
            )
        )
        await connection.execute(
            text(
                "CREATE TABLE accounts ("
                "id INTEGER PRIMARY KEY, username VARCHAR(20) NOT NULL UNIQUE, "
                "password_hash VARCHAR(200) NOT NULL)"
            )
        )
        await connection.execute(
            text(
                "INSERT INTO accounts (id, username, password_hash) "
                "VALUES (1, 'legacy_user', 'legacy_hash')"
            )
        )
        await connection.execute(
            text(
                "CREATE TABLE challenges ("
                "id INTEGER PRIMARY KEY, title VARCHAR(50) NOT NULL UNIQUE, "
                "html_filename VARCHAR NOT NULL UNIQUE, "
                "solution JSON NOT NULL DEFAULT '[]')"
            )
        )
        # Simulate legacy challenge rows with an answer-key column and no order.
        await connection.execute(
            text(
                "INSERT INTO exercises "
                "(id, title, html_filename, task, position, chapter_id) "
                "VALUES (1, 'Legacy exercise', 'legacy.html', 1, 0, 1)"
            )
        )
        await connection.execute(
            text(
                "INSERT INTO chapters (id, title, position, active) "
                "VALUES (1, 'Legacy chapter', 0, 1)"
            )
        )
        await connection.execute(
            text(
                "INSERT INTO challenges (id, title, html_filename) VALUES "
                "(2, 'Second challenge', 'second.html'), "
                "(1, 'First challenge', 'first.html')"
            )
        )

    try:
        await database.init_db()
        async with legacy_engine.connect() as connection:
            chapter_columns = await connection.run_sync(
                lambda sync_connection: {
                    column["name"]: column
                    for column in inspect(sync_connection).get_columns("chapters")
                }
            )
            columns = await connection.run_sync(
                lambda sync_connection: {
                    column["name"]: column
                    for column in inspect(sync_connection).get_columns("exercises")
                }
            )
            account_columns = await connection.run_sync(
                lambda sync_connection: {
                    column["name"]
                    for column in inspect(sync_connection).get_columns("accounts")
                }
            )
            challenge_columns = await connection.run_sync(
                lambda sync_connection: {
                    column["name"]
                    for column in inspect(sync_connection).get_columns("challenges")
                }
            )
            result = await connection.execute(
                text("SELECT solution FROM exercises WHERE id = 1")
            )
            assert result.scalar_one() == "[]"
            picture_result = await connection.execute(
                text("SELECT picture FROM chapters WHERE id = 1")
            )
            assert picture_result.scalar_one() is None
            challenge_result = await connection.execute(
                text("SELECT id, position FROM challenges ORDER BY position")
            )
            assert challenge_result.all() == [(1, 0), (2, 1)]
            klasse_result = await connection.execute(
                text("SELECT klasse FROM accounts WHERE id = 1")
            )
            assert klasse_result.scalar_one() in database.RANDOM_CLASSES
        assert chapter_columns["picture"]["nullable"] is True
        assert "task" not in columns
        assert columns["solution"]["nullable"] is True
        assert {
            "record_time",
            "start_time",
            "end_time",
            "previous_record_time",
            "current_challenge_id",
            "current_challenge_complete",
            "klasse",
        } <= account_columns
        assert "position" in challenge_columns
        assert "solution" not in challenge_columns

        async with legacy_engine.begin() as connection:
            await connection.execute(
                text("UPDATE exercises SET solution = '42' WHERE id = 1")
            )
        await database.init_db()
        async with legacy_engine.connect() as connection:
            result = await connection.execute(
                text("SELECT solution FROM exercises WHERE id = 1")
            )
            assert result.scalar_one() == "[42]"
    finally:
        await legacy_engine.dispose()


@pytest.mark.anyio
async def test_account_challenge_timestamps_round_trip_in_utc(tmp_path):
    engine = create_async_engine(
        f"sqlite+aiosqlite:///{tmp_path / 'challenge-times.db'}",
        connect_args={"check_same_thread": False},
    )

    try:
        async with engine.begin() as connection:
            await connection.run_sync(database.Base.metadata.create_all)

        async with AsyncSession(engine) as session:
            account = models.Account(
                username="timed_user",
                password_hash="hash",
                start_time=datetime(
                    2026, 11, 12, 12, tzinfo=timezone(timedelta(hours=2))
                ),
                end_time=datetime(
                    2026, 11, 12, 12, 5, tzinfo=timezone(timedelta(hours=2))
                ),
                record_time=300_000,
            )
            session.add(account)
            await session.commit()
            await session.refresh(account)

            assert account.start_time == datetime(
                2026, 11, 12, 10, tzinfo=timezone.utc
            )
            assert account.end_time == datetime(
                2026, 11, 12, 10, 5, tzinfo=timezone.utc
            )
            assert account.record_time == 300_000
    finally:
        await engine.dispose()
