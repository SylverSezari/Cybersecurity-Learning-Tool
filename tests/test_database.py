from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import inspect
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

import database
import models


@pytest.mark.anyio
async def test_init_db_creates_current_schema_for_empty_database(tmp_path, monkeypatch):
    engine = create_async_engine(
        f"sqlite+aiosqlite:///{tmp_path / 'fresh.db'}",
        connect_args={"check_same_thread": False},
    )
    monkeypatch.setattr(database, "engine", engine)

    try:
        await database.init_db()
        async with engine.connect() as connection:
            table_names = await connection.run_sync(
                lambda sync_connection: set(
                    inspect(sync_connection).get_table_names()
                )
            )

        assert table_names == {
            "accounts",
            "chapters",
            "challenges",
            "exercise_completions",
            "exercises",
        }
    finally:
        await engine.dispose()


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
