import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

import main
import models

# Chapter Tests


# Insert a chapter directly so endpoint tests can focus on request behavior.
async def add_chapter(
	db_session: AsyncSession,
	title: str,
	position: int = -1,
	active: bool = False,
) -> models.Chapter:
	chapter = models.Chapter(title=title, position=position, active=active)
	db_session.add(chapter)
	await db_session.commit()
	return chapter


async def add_chapter_exercise(
	db_session: AsyncSession,
	chapter_id: int,
	title: str,
	html_filename: str,
	position: int,
) -> models.Exercise:
	exercise = models.Exercise(
		title=title,
		html_filename=html_filename,
		chapter_id=chapter_id,
		position=position,
	)
	db_session.add(exercise)
	await db_session.commit()
	return exercise


## Test get_all_chapters
# Seed chapters for the success case, then check that missing credentials are rejected.


@pytest.mark.anyio
async def test_get_all_chapters_returns_all_chapters_to_logged_in_user(
	client: AsyncClient,
	db_session: AsyncSession,
	user_auth_headers: dict[str, str],
):
	# A logged-in user should receive every chapter in the database.
	await add_chapter(db_session, "First chapter")
	await add_chapter(db_session, "Second chapter")
	response = await client.get("/api/chapters", headers=user_auth_headers)

	assert response.status_code == 200
	assert {chapter["title"] for chapter in response.json()} == {
		"First chapter",
		"Second chapter",
	}


@pytest.mark.anyio
async def test_get_all_chapters_rejects_missing_token(client: AsyncClient):
	# A request without a bearer token should return the authentication error.
	response = await client.get("/api/chapters")

	assert response.status_code == 401
	assert response.json()["detail"] == "Invalid or expired authentication token"


@pytest.mark.anyio
async def test_chapter_select_page_shows_only_active_chapters_in_order(
	client: AsyncClient,
	db_session: AsyncSession,
):
	# Learners see active chapters in saved position order, but not inactive chapters.
	await add_chapter(db_session, "Later active", position=2, active=True)
	await add_chapter(db_session, "Inactive chapter")
	earlier_active = await add_chapter(
		db_session, "Earlier active", position=0, active=True
	)

	response = await client.get("/chapters")
	content = response.text

	assert response.status_code == 200
	assert content.index("Earlier active") < content.index("Later active")
	assert "Inactive chapter" not in content
	assert f"/chapters/{earlier_active.id}" in content


@pytest.mark.anyio
async def test_chapter_start_redirects_to_first_exercise(
	client: AsyncClient,
	db_session: AsyncSession,
):
	chapter = await add_chapter(db_session, "Task chapter", position=0, active=True)
	await add_chapter_exercise(db_session, chapter.id, "Second exercise", "second.html", 2)
	first_exercise = await add_chapter_exercise(
		db_session, chapter.id, "First exercise", "first.html", 0
	)

	response = await client.get(f"/chapters/{chapter.id}")

	assert response.status_code == 303
	assert response.headers["location"].endswith(
		f"/chapters/{chapter.id}/exercises/{first_exercise.id}"
	)


@pytest.mark.anyio
async def test_task_page_lists_exercises_and_loads_database_filename(
	client: AsyncClient,
	db_session: AsyncSession,
	user_auth_headers: dict[str, str],
	tmp_path,
	monkeypatch,
):
	chapter = await add_chapter(db_session, "Task chapter", position=0, active=True)
	exercise = await add_chapter_exercise(
		db_session, chapter.id, "Introduction", "intro.html", 0
	)
	(tmp_path / exercise.html_filename).write_text(
		"<!doctype html><title>Lesson content</title>", encoding="utf-8"
	)
	monkeypatch.setattr(main, "EXERCISES_DIRECTORY", tmp_path)

	page = await client.get(f"/chapters/{chapter.id}/exercises/{exercise.id}")
	content = await client.get(
		f"/exercise-content/{exercise.id}/{exercise.html_filename}",
		headers=user_auth_headers,
	)

	assert page.status_code == 200
	assert "Introduction" in page.text
	assert "aria-label=\"Übungen in Task chapter\"" in page.text
	assert f"/exercise-content/{exercise.id}/{exercise.html_filename}" in page.text
	assert content.status_code == 200
	assert "Lesson content" in content.text


@pytest.mark.anyio
async def test_admin_can_open_exercise_page_with_login_cookie(
	client: AsyncClient,
	db_session: AsyncSession,
	admin_auth_headers: dict[str, str],
	tmp_path,
	monkeypatch,
):
	chapter = await add_chapter(db_session, "Admin navigation chapter", position=0, active=True)
	exercise = await add_chapter_exercise(
		db_session, chapter.id, "Admin navigation lesson", "admin-lesson.html", 0
	)
	(tmp_path / exercise.html_filename).write_text(
		"<!doctype html><title>Admin lesson</title>", encoding="utf-8"
	)
	monkeypatch.setattr(main, "EXERCISES_DIRECTORY", tmp_path)

	response = await client.get(
		f"/chapters/{chapter.id}/exercises/{exercise.id}"
	)

	assert response.status_code == 200
	assert "Admin navigation lesson" in response.text


@pytest.mark.anyio
async def test_task_page_displays_error_when_exercise_file_is_missing(
	client: AsyncClient,
	db_session: AsyncSession,
	user_auth_headers: dict[str, str],
	tmp_path,
	monkeypatch,
):
	chapter = await add_chapter(db_session, "Task chapter", position=0, active=True)
	exercise = await add_chapter_exercise(
		db_session, chapter.id, "Missing lesson", "missing.html", 0
	)
	monkeypatch.setattr(main, "EXERCISES_DIRECTORY", tmp_path)

	response = await client.get(
		f"/chapters/{chapter.id}/exercises/{exercise.id}",
		headers=user_auth_headers,
	)

	assert response.status_code == 404
	assert "Übung nicht verfügbar" in response.text
	assert "missing.html" in response.text


## Test get_single_chapter
# Check authenticated retrieval, unknown IDs, and rejection of requests without a token.


@pytest.mark.anyio
async def test_get_single_chapter_returns_chapter_to_logged_in_user(
	client: AsyncClient,
	db_session: AsyncSession,
	user_auth_headers: dict[str, str],
):
	# A logged-in user should be able to retrieve a chapter by its ID.
	chapter = await add_chapter(db_session, "Requested chapter", position=2, active=True)
	response = await client.get(
		f"/api/chapters/{chapter.id}", headers=user_auth_headers
	)

	assert response.status_code == 200
	assert response.json()["id"] == chapter.id
	assert response.json()["title"] == "Requested chapter"


@pytest.mark.anyio
async def test_get_single_chapter_returns_not_found_for_unknown_id(
	client: AsyncClient,
	user_auth_headers: dict[str, str],
):
	# A valid user token does not make a nonexistent chapter available.
	response = await client.get("/api/chapters/99999", headers=user_auth_headers)

	assert response.status_code == 404
	assert response.json()["detail"] == "Chapter not found"


@pytest.mark.anyio
async def test_get_single_chapter_rejects_missing_token(client: AsyncClient):
	# A chapter ID must not be readable without a valid bearer token.
	response = await client.get("/api/chapters/1")

	assert response.status_code == 401
	assert response.json()["detail"] == "Invalid or expired authentication token"


## Test create_chapter
# Check admin creation defaults, duplicate-title errors, and unauthorized write attempts.


@pytest.mark.anyio
async def test_create_chapter_sets_inactive_defaults_for_admin(
	client: AsyncClient,
	admin_auth_headers: dict[str, str],
):
	# An admin can create a chapter, which starts inactive at position -1.
	response = await client.post(
		"/api/chapters",
		json={"title": "New chapter"},
		headers=admin_auth_headers,
	)

	assert response.status_code == 201
	assert response.json()["title"] == "New chapter"
	assert response.json()["position"] == -1
	assert response.json()["active"] is False


@pytest.mark.anyio
async def test_create_chapter_rejects_duplicate_title(
	client: AsyncClient,
	admin_auth_headers: dict[str, str],
):
	# Chapter titles are unique without regard to letter case.
	await client.post(
		"/api/chapters",
		json={"title": "Existing chapter"},
		headers=admin_auth_headers,
	)

	response = await client.post(
		"/api/chapters",
		json={"title": "EXISTING CHAPTER"},
		headers=admin_auth_headers,
	)

	assert response.status_code == 400
	assert response.json()["detail"] == "Chapter with this title exists already"


@pytest.mark.anyio
async def test_create_chapter_rejects_missing_token(client: AsyncClient):
	# Chapter creation requires authentication before admin authorization is checked.
	response = await client.post("/api/chapters", json={"title": "No token"})

	assert response.status_code == 401
	assert response.json()["detail"] == "Invalid or expired authentication token"


@pytest.mark.anyio
async def test_create_chapter_rejects_regular_user(
	client: AsyncClient,
	user_auth_headers: dict[str, str],
):
	# A valid user token is insufficient for an admin-only creation request.
	response = await client.post(
		"/api/chapters",
		json={"title": "User-created chapter"},
		headers=user_auth_headers,
	)

	assert response.status_code == 403
	assert response.json()["detail"] == "Admin privileges required"


## Test update_chapter
# Check successful title changes, missing/duplicate title errors, and write authorization.


@pytest.mark.anyio
async def test_update_chapter_changes_title_for_admin(
	client: AsyncClient,
	db_session: AsyncSession,
	admin_auth_headers: dict[str, str],
):
	# An admin can update an existing chapter's title.
	chapter = await add_chapter(db_session, "Old title")

	response = await client.put(
		f"/api/chapters/update/{chapter.id}",
		json={"title": "New title"},
		headers=admin_auth_headers,
	)

	assert response.status_code == 200
	assert response.json()["title"] == "New title"


@pytest.mark.anyio
async def test_update_chapter_accepts_its_existing_title(
	client: AsyncClient,
	db_session: AsyncSession,
	admin_auth_headers: dict[str, str],
):
	# A chapter's existing title is not a duplicate of another chapter.
	chapter = await add_chapter(db_session, "Current title")

	response = await client.put(
		f"/api/chapters/update/{chapter.id}",
		json={"title": "Current title"},
		headers=admin_auth_headers,
	)

	assert response.status_code == 200
	assert response.json()["title"] == "Current title"


@pytest.mark.anyio
async def test_update_chapter_returns_not_found_for_unknown_id(
	client: AsyncClient,
	admin_auth_headers: dict[str, str],
):
	# Updating an ID absent from the database returns the route's not-found error.
	response = await client.put(
		"/api/chapters/update/99999",
		json={"title": "New title"},
		headers=admin_auth_headers,
	)

	assert response.status_code == 404
	assert response.json()["detail"] == "Chapter not found"


@pytest.mark.anyio
async def test_update_chapter_rejects_duplicate_title(
	client: AsyncClient,
	db_session: AsyncSession,
	admin_auth_headers: dict[str, str],
):
	# An update cannot reuse another chapter's title, including case variants.
	chapter = await add_chapter(db_session, "Original title")
	await add_chapter(db_session, "Already used title")

	response = await client.put(
		f"/api/chapters/update/{chapter.id}",
		json={"title": "ALREADY USED TITLE"},
		headers=admin_auth_headers,
	)

	assert response.status_code == 409
	assert response.json()["detail"] == "Chapter with this title already exists"


@pytest.mark.anyio
async def test_update_chapter_rejects_missing_token(client: AsyncClient):
	# A chapter title cannot be changed without a valid bearer token.
	response = await client.put(
		"/api/chapters/update/1",
		json={"title": "Unauthorized title"},
	)

	assert response.status_code == 401
	assert response.json()["detail"] == "Invalid or expired authentication token"


@pytest.mark.anyio
async def test_update_chapter_rejects_regular_user(
	client: AsyncClient,
	user_auth_headers: dict[str, str],
):
	# A logged-in non-admin must receive the admin-required error for updates.
	response = await client.put(
		"/api/chapters/update/1",
		json={"title": "Unauthorized title"},
		headers=user_auth_headers,
	)

	assert response.status_code == 403
	assert response.json()["detail"] == "Admin privileges required"


## Test change_chapters_active
# Check admin reordering, inactive-position normalization, validation errors, and access control.


@pytest.mark.anyio
async def test_change_chapters_active_updates_positions_and_states(
	client: AsyncClient,
	db_session: AsyncSession,
	admin_auth_headers: dict[str, str],
):
	# An admin can activate a chapter and place all inactive chapters at -1.
	active_chapter = await add_chapter(db_session, "Active", position=0, active=True)
	inactive_chapter_one = await add_chapter(db_session, "Inactive one")
	inactive_chapter_two = await add_chapter(db_session, "Inactive two")

	response = await client.put(
		"/api/chapters/activation/change",
		json={
			"chapters": [
				{"chapter_id": active_chapter.id, "position": 1, "active": True},
				{"chapter_id": inactive_chapter_one.id, "position": 3, "active": False},
				{"chapter_id": inactive_chapter_two.id, "position": -1, "active": False},
			]
		},
		headers=admin_auth_headers,
	)

	assert response.status_code == 200, response.text
	chapters_by_id = {chapter["id"]: chapter for chapter in response.json()}
	assert chapters_by_id[active_chapter.id]["position"] == 1
	assert chapters_by_id[active_chapter.id]["active"] is True
	assert chapters_by_id[inactive_chapter_one.id]["position"] == -1
	assert chapters_by_id[inactive_chapter_two.id]["position"] == -1


@pytest.mark.anyio
async def test_change_chapters_active_rejects_duplicate_active_positions(
	client: AsyncClient,
	db_session: AsyncSession,
	admin_auth_headers: dict[str, str],
):
	# Two active chapters cannot be assigned the same non-sentinel position.
	first_chapter = await add_chapter(db_session, "First", position=0, active=True)
	second_chapter = await add_chapter(db_session, "Second", position=1, active=True)

	response = await client.put(
		"/api/chapters/activation/change",
		json={
			"chapters": [
				{"chapter_id": first_chapter.id, "position": 0, "active": True},
				{"chapter_id": second_chapter.id, "position": 0, "active": True},
			]
		},
		headers=admin_auth_headers,
	)

	assert response.status_code == 400
	assert response.json()["detail"] == "Assigned chapter positions must be unique"


@pytest.mark.anyio
async def test_change_chapters_active_rejects_missing_chapter_ids(
	client: AsyncClient,
	db_session: AsyncSession,
	admin_auth_headers: dict[str, str],
):
	# Every database chapter must appear exactly once in the submitted update.
	first_chapter = await add_chapter(db_session, "Included")
	await add_chapter(db_session, "Omitted")

	response = await client.put(
		"/api/chapters/activation/change",
		json={
			"chapters": [
				{"chapter_id": first_chapter.id, "position": 0, "active": True}
			]
		},
		headers=admin_auth_headers,
	)

	assert response.status_code == 400
	assert response.json()["detail"] == "Include each existing chapter exactly once"


@pytest.mark.anyio
async def test_change_chapters_active_rejects_duplicate_chapter_ids(
	client: AsyncClient,
	db_session: AsyncSession,
	admin_auth_headers: dict[str, str],
):
	# Repeating one ID cannot stand in for submitting each chapter exactly once.
	chapter = await add_chapter(db_session, "Repeated")

	response = await client.put(
		"/api/chapters/activation/change",
		json={
			"chapters": [
				{"chapter_id": chapter.id, "position": 0, "active": True},
				{"chapter_id": chapter.id, "position": 1, "active": True},
			]
		},
		headers=admin_auth_headers,
	)

	assert response.status_code == 400
	assert response.json()["detail"] == "Include each existing chapter exactly once"


@pytest.mark.anyio
async def test_change_chapters_active_rejects_missing_token(client: AsyncClient):
	# Activation and ordering changes require an authenticated admin.
	response = await client.put(
		"/api/chapters/activation/change",
		json={"chapters": []},
	)

	assert response.status_code == 401
	assert response.json()["detail"] == "Invalid or expired authentication token"


@pytest.mark.anyio
async def test_change_chapters_active_rejects_regular_user(
	client: AsyncClient,
	user_auth_headers: dict[str, str],
):
	# A logged-in user without the admin role cannot change activation or ordering.
	response = await client.put(
		"/api/chapters/activation/change",
		json={"chapters": []},
		headers=user_auth_headers,
	)

	assert response.status_code == 403
	assert response.json()["detail"] == "Admin privileges required"


@pytest.mark.anyio
async def test_delete_chapter_unassigns_exercises_and_resets_position(
	client: AsyncClient,
	db_session: AsyncSession,
	admin_auth_headers: dict[str, str],
):
	chapter = await add_chapter(db_session, "Chapter to delete")
	exercises = [
		models.Exercise(
			title=f"Exercise {position}",
			html_filename=f"exercise-{position}.html",
			chapter_id=chapter.id,
			position=position,
		)
		for position in (1, 2)
	]
	db_session.add_all(exercises)
	await db_session.commit()

	response = await client.delete(
		f"/api/chapters/delete/{chapter.id}", headers=admin_auth_headers
	)

	assert response.status_code == 204
	lookup_response = await client.get(
		f"/api/chapters/{chapter.id}", headers=admin_auth_headers
	)
	assert lookup_response.status_code == 404
	for exercise in exercises:
		await db_session.refresh(exercise)
		assert exercise.chapter_id is None
		assert exercise.position == -1


@pytest.mark.anyio
async def test_delete_chapter_returns_not_found_for_unknown_id(
	client: AsyncClient,
	admin_auth_headers: dict[str, str],
):
	response = await client.delete(
		"/api/chapters/delete/99999", headers=admin_auth_headers
	)

	assert response.status_code == 404
	assert response.json()["detail"] == "Chapter not found"


@pytest.mark.anyio
async def test_delete_chapter_rejects_missing_token(client: AsyncClient):
	response = await client.delete("/api/chapters/delete/1")

	assert response.status_code == 401
	assert response.json()["detail"] == "Invalid or expired authentication token"


@pytest.mark.anyio
async def test_delete_chapter_rejects_regular_user(
	client: AsyncClient,
	user_auth_headers: dict[str, str],
):
	response = await client.delete(
		"/api/chapters/delete/1", headers=user_auth_headers
	)

	assert response.status_code == 403
	assert response.json()["detail"] == "Admin privileges required"
