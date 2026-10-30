import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

import main
import models


async def add_chapter(db_session: AsyncSession) -> models.Chapter:
	chapter = models.Chapter(title="Progress chapter", position=0, active=True)
	db_session.add(chapter)
	await db_session.flush()
	return chapter


async def add_exercise(
	db_session: AsyncSession,
	chapter_id: int,
	title: str,
	position: int,
	*,
	requires_previous: bool = False,
) -> models.Exercise:
	exercise = models.Exercise(
		title=title,
		html_filename=f"{title.lower().replace(' ', '-')}.html",
		requires_previous=requires_previous,
		chapter_id=chapter_id,
		position=position,
	)
	db_session.add(exercise)
	await db_session.flush()
	return exercise


@pytest.mark.anyio
async def test_locked_exercise_blocks_later_exercises_until_previous_is_completed(
	client: AsyncClient,
	db_session: AsyncSession,
	user_auth_headers: dict[str, str],
	tmp_path,
	monkeypatch,
):
	chapter = await add_chapter(db_session)
	first = await add_exercise(db_session, chapter.id, "First lesson", 0)
	second = await add_exercise(
		db_session, chapter.id, "Second lesson", 1, requires_previous=True
	)
	third = await add_exercise(db_session, chapter.id, "Third lesson", 2)
	for exercise in (first, second, third):
		(tmp_path / exercise.html_filename).write_text(
			f"<title>{exercise.title}</title>", encoding="utf-8"
		)
	monkeypatch.setattr(main, "EXERCISES_DIRECTORY", tmp_path)

	progress = await client.get(
		f"/api/progress/chapters/{chapter.id}", headers=user_auth_headers
	)
	assert progress.json()["locked_by"] == {
		str(second.id): first.id,
		str(third.id): first.id,
	}

	locked_page = await client.get(
		f"/chapters/{chapter.id}/exercises/{second.id}",
		headers=user_auth_headers,
	)
	assert "Übung gesperrt" in locked_page.text
	assert 'id="exerciseFrame"' not in locked_page.text

	locked_content = await client.get(
		f"/exercise-content/{second.id}/{second.html_filename}",
		headers=user_auth_headers,
	)
	assert locked_content.status_code == 403

	locked_completion = await client.post(
		f"/api/progress/exercises/{second.id}/complete",
		headers=user_auth_headers,
	)
	assert locked_completion.status_code == 403

	completed_first = await client.post(
		f"/api/progress/exercises/{first.id}/complete",
		headers=user_auth_headers,
	)
	assert completed_first.status_code == 200

	updated_progress = await client.get(
		f"/api/progress/chapters/{chapter.id}", headers=user_auth_headers
	)
	assert updated_progress.json()["completed_ids"] == [first.id]
	assert updated_progress.json()["locked_by"] == {}

	available_content = await client.get(
		f"/exercise-content/{second.id}/{second.html_filename}",
		headers=user_auth_headers,
	)
	assert available_content.status_code == 200


@pytest.mark.anyio
async def test_progress_is_independent_for_each_user(
	client: AsyncClient,
	db_session: AsyncSession,
	user_auth_headers: dict[str, str],
	test_account_factory,
):
	chapter = await add_chapter(db_session)
	first = await add_exercise(db_session, chapter.id, "First lesson", 0)
	second = await add_exercise(
		db_session, chapter.id, "Second lesson", 1, requires_previous=True
	)

	await test_account_factory("second_progress_user")
	login = await client.post(
		"/api/accounts/token",
		json={"username": "second_progress_user", "password": "testpassword123"},
	)
	second_user_headers = {
		"Authorization": f"Bearer {login.json()['access_token']}"
	}

	completed = await client.post(
		f"/api/progress/exercises/{first.id}/complete",
		headers=user_auth_headers,
	)
	assert completed.status_code == 200

	first_user_progress = await client.get(
		f"/api/progress/chapters/{chapter.id}", headers=user_auth_headers
	)
	second_user_progress = await client.get(
		f"/api/progress/chapters/{chapter.id}", headers=second_user_headers
	)

	assert first_user_progress.json()["locked_by"] == {}
	assert second_user_progress.json()["locked_by"] == {str(second.id): first.id}