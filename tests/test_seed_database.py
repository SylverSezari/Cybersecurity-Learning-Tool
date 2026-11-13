from datetime import UTC, datetime

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

import database
import seed_database
from models import Account, Challenge, Chapter, Exercise


def configure_seed_database(tmp_path, monkeypatch):
    engine = create_async_engine(
        f"sqlite+aiosqlite:///{tmp_path / 'seed.db'}",
        connect_args={"check_same_thread": False},
    )
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    async def init_test_db():
        async with engine.begin() as connection:
            await connection.run_sync(database.Base.metadata.create_all)

    monkeypatch.setattr(seed_database, "AsyncSessionLocal", session_factory)
    monkeypatch.setattr(seed_database, "init_db", init_test_db)
    return engine, session_factory


@pytest.mark.anyio
async def test_seed_content_matches_catalog_and_removes_empty_retired_chapter(
    tmp_path,
    monkeypatch,
):
    engine, session_factory = configure_seed_database(tmp_path, monkeypatch)
    try:
        await seed_database.init_db()
        async with session_factory() as session, session.begin():
            old_chapter = Chapter(title="Kryptografie", position=0, active=True)
            session.add(old_chapter)
            session.add(Chapter(title="Phishing", position=2, active=True))
            await session.flush()
            legacy_challenge = Challenge(
                title="Legacy static challenge",
                html_filename="legacy.html",
                position=99,
            )
            account = Account(
                username="legacy_user",
                password_hash="hash",
                start_time=datetime.now(UTC),
                current_challenge_id=legacy_challenge.id,
            )
            session.add_all([legacy_challenge, account])
            await session.flush()
            account.current_challenge_id = legacy_challenge.id
            for position, exercise_data in enumerate(seed_database.EXERCISES):
                session.add(
                    Exercise(
                        title=exercise_data["title"],
                        html_filename=exercise_data["html_filename"],
                        solution=[],
                        requires_previous=False,
                        position=position,
                        chapter=old_chapter,
                    )
                )

        await seed_database.seed_content()
        await seed_database.seed_content()

        async with session_factory() as session:
            result = await session.execute(select(Challenge))
            challenges = {
                challenge.html_filename: challenge
                for challenge in result.scalars()
            }
            assert set(challenges) == {
                challenge["html_filename"] for challenge in seed_database.CHALLENGES
            }
            for challenge_data in seed_database.CHALLENGES:
                challenge = challenges[challenge_data["html_filename"]]
                assert challenge.title == challenge_data["title"]
                assert not hasattr(challenge, "solution")
            assert "legacy.html" not in challenges
            result = await session.execute(
                select(Account).where(Account.username == "legacy_user")
            )
            account = result.scalar_one()
            assert account.start_time is None
            assert account.current_challenge_id is None
            assert account.current_challenge_complete is False

            result = await session.execute(select(Chapter))
            chapters = {chapter.title: chapter for chapter in result.scalars()}
            assert set(chapters) == {
                chapter["title"] for chapter in seed_database.CHAPTERS
            }
            for chapter_data in seed_database.CHAPTERS:
                chapter = chapters[chapter_data["title"]]
                assert chapter.picture == chapter_data["picture"]
                assert chapter.position == chapter_data["position"]
                assert chapter.active == chapter_data["active"]

            result = await session.execute(
                select(Exercise, Chapter.title).join(Chapter)
            )
            exercises = {
                exercise.html_filename: (exercise, chapter_title)
                for exercise, chapter_title in result.all()
            }
            assert len(exercises) == len(seed_database.EXERCISES)
            for exercise_data in seed_database.EXERCISES:
                exercise, chapter_title = exercises[exercise_data["html_filename"]]
                assert exercise.title == exercise_data["title"]
                assert exercise.solution == exercise_data["solution"]
                assert exercise.requires_previous == exercise_data["requires_previous"]
                assert exercise.position == exercise_data["position"]
                assert chapter_title == exercise_data["chapter_title"]
    finally:
        await engine.dispose()


@pytest.mark.anyio
async def test_seed_content_refuses_to_remove_chapter_with_exercises(
    tmp_path,
    monkeypatch,
):
    engine, session_factory = configure_seed_database(tmp_path, monkeypatch)
    try:
        await seed_database.init_db()
        async with session_factory() as session, session.begin():
            chapter = Chapter(title="Phishing", position=2, active=True)
            session.add(chapter)
            session.add(
                Exercise(
                    title="Old phishing exercise",
                    html_filename="old_phishing.html",
                    solution=[],
                    requires_previous=False,
                    position=0,
                    chapter=chapter,
                )
            )

        with pytest.raises(ValueError, match="Cannot remove chapter"):
            await seed_database.seed_content()

        async with session_factory() as session:
            result = await session.execute(
                select(Chapter).where(Chapter.title == "Phishing")
            )
            assert result.scalar_one_or_none() is not None
    finally:
        await engine.dispose()
