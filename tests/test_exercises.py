import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

import models

# Test Exercises


# Insert an exercise directly so endpoint tests can control its initial assignment state.
async def add_exercise(
	db_session: AsyncSession,
	title: str,
	html_filename: str,
	task: bool = True,
	chapter_id: int = -1,
	position: int | None = None,
) -> models.Exercise:
	# Persist an exercise with the values needed by an individual route test.
	exercise = models.Exercise(
		title=title,
		html_filename=html_filename,
		task=task,
		chapter_id=chapter_id,
		position=position,
	)
	db_session.add(exercise)
	await db_session.commit()
	return exercise


## Test get_all_exercises
# Check list contents for a logged-in user and reject requests without a token.


@pytest.mark.anyio
async def test_get_all_exercises_returns_exercises_to_logged_in_user(
	client: AsyncClient,
	db_session: AsyncSession,
	user_auth_headers: dict[str, str],
):
	# An authenticated user should receive every stored exercise.
	await add_exercise(db_session, "First exercise", "first.html")
	await add_exercise(db_session, "Second exercise", "second.html")

	response = await client.get("/api/exercises", headers=user_auth_headers)

	assert response.status_code == 200
	assert {exercise["title"] for exercise in response.json()} == {
		"First exercise",
		"Second exercise",
	}


@pytest.mark.anyio
async def test_get_all_exercises_rejects_missing_token(client: AsyncClient):
	# Listing exercises without a bearer token should return the auth error.
	response = await client.get("/api/exercises")

	assert response.status_code == 401
	assert response.json()["detail"] == "Invalid or expired authentication token"


## Test get_single_exercise
# Check authenticated lookup, the not-found response, and missing-token rejection.


@pytest.mark.anyio
async def test_get_single_exercise_returns_exercise_to_logged_in_user(
	client: AsyncClient,
	db_session: AsyncSession,
	user_auth_headers: dict[str, str],
):
	# An authenticated user should be able to retrieve an exercise by ID.
	exercise = await add_exercise(db_session, "Requested exercise", "requested.html")

	response = await client.get(
		f"/api/exercises/{exercise.id}", headers=user_auth_headers
	)

	assert response.status_code == 200
	assert response.json()["id"] == exercise.id
	assert response.json()["title"] == "Requested exercise"


@pytest.mark.anyio
async def test_get_single_exercise_returns_not_found_for_unknown_id(
	client: AsyncClient,
	user_auth_headers: dict[str, str],
):
	# A valid user token cannot retrieve an exercise that does not exist.
	response = await client.get("/api/exercises/99999", headers=user_auth_headers)

	assert response.status_code == 404
	assert response.json()["detail"] == "Exercise not found"


@pytest.mark.anyio
async def test_get_single_exercise_rejects_missing_token(client: AsyncClient):
	# Exercise details must not be accessible without authentication.
	response = await client.get("/api/exercises/1")

	assert response.status_code == 401
	assert response.json()["detail"] == "Invalid or expired authentication token"


## Test get_exercises_belonging_to_chapter
# Seed exercises at different positions to verify ordering, empty results, and auth checks.


@pytest.mark.anyio
async def test_get_exercises_belonging_to_chapter_returns_position_order(
	client: AsyncClient,
	db_session: AsyncSession,
	user_auth_headers: dict[str, str],
):
	# Exercises in a chapter should be returned in ascending position order.
	chapter = models.Chapter(title="Ordered exercise chapter", position=0, active=True)
	db_session.add(chapter)
	await db_session.commit()
	await add_exercise(
		db_session, "Later exercise", "later.html", chapter_id=chapter.id, position=2
	)
	await add_exercise(
		db_session, "Earlier exercise", "earlier.html", chapter_id=chapter.id, position=1
	)

	response = await client.get(
		f"/api/exercises/chapter/{chapter.id}", headers=user_auth_headers
	)

	assert response.status_code == 200
	assert [exercise["title"] for exercise in response.json()] == [
		"Earlier exercise",
		"Later exercise",
	]


@pytest.mark.anyio
async def test_get_exercises_belonging_to_chapter_returns_empty_list(
	client: AsyncClient,
	user_auth_headers: dict[str, str],
):
	# A chapter with no exercises should return an empty list.
	response = await client.get("/api/exercises/chapter/99999", headers=user_auth_headers)

	assert response.status_code == 200
	assert response.json() == []


@pytest.mark.anyio
async def test_get_exercises_belonging_to_chapter_rejects_missing_token(
	client: AsyncClient,
):
	# Chapter exercise lists also require an authenticated user.
	response = await client.get("/api/exercises/chapter/1")

	assert response.status_code == 401
	assert response.json()["detail"] == "Invalid or expired authentication token"


## Test create_exercise
# Check admin creation defaults, case-insensitive duplicates, and write authorization.


@pytest.mark.anyio
async def test_create_exercise_sets_unassigned_defaults_for_admin(
	client: AsyncClient,
	admin_auth_headers: dict[str, str],
):
	# An admin can create an exercise, initially unassigned from any chapter.
	response = await client.post(
		"/api/exercises",
		json={"title": "New exercise", "html_filename": "new.html", "task": True},
		headers=admin_auth_headers,
	)

	assert response.status_code == 201
	assert response.json()["title"] == "New exercise"
	assert response.json()["html_filename"] == "new.html"
	assert response.json()["chapter_id"] == -1


@pytest.mark.anyio
async def test_create_exercise_rejects_duplicate_title(
	client: AsyncClient,
	admin_auth_headers: dict[str, str],
):
	# Exercise titles are unique without regard to letter case.
	await client.post(
		"/api/exercises",
		json={"title": "Existing exercise", "html_filename": "existing.html", "task": True},
		headers=admin_auth_headers,
	)

	response = await client.post(
		"/api/exercises",
		json={"title": "EXISTING EXERCISE", "html_filename": "different.html", "task": True},
		headers=admin_auth_headers,
	)

	assert response.status_code == 400
	assert response.json()["detail"] == "Exercise with this title already created"


@pytest.mark.anyio
async def test_create_exercise_rejects_duplicate_filename(
	client: AsyncClient,
	admin_auth_headers: dict[str, str],
):
	# HTML filenames are also unique without regard to letter case.
	await client.post(
		"/api/exercises",
		json={"title": "First exercise", "html_filename": "shared.html", "task": True},
		headers=admin_auth_headers,
	)

	response = await client.post(
		"/api/exercises",
		json={"title": "Second exercise", "html_filename": "SHARED.HTML", "task": False},
		headers=admin_auth_headers,
	)

	assert response.status_code == 400
	assert response.json()["detail"] == "Exercise with this filename already created"


@pytest.mark.anyio
async def test_create_exercise_rejects_missing_token(client: AsyncClient):
	# Exercise creation requires authentication before checking admin privileges.
	response = await client.post(
		"/api/exercises",
		json={"title": "No token exercise", "html_filename": "no-token.html", "task": True},
	)

	assert response.status_code == 401
	assert response.json()["detail"] == "Invalid or expired authentication token"


@pytest.mark.anyio
async def test_create_exercise_rejects_regular_user(
	client: AsyncClient,
	user_auth_headers: dict[str, str],
):
	# A regular logged-in user cannot create exercises.
	response = await client.post(
		"/api/exercises",
		json={"title": "User exercise", "html_filename": "user.html", "task": True},
		headers=user_auth_headers,
	)

	assert response.status_code == 403
	assert response.json()["detail"] == "Admin privileges required"


## Test assign_exercise
# Check assignment and unassignment, invalid IDs, position conflicts, and admin-only access.


@pytest.mark.anyio
async def test_assign_exercise_sets_chapter_and_position_for_admin(
	client: AsyncClient,
	db_session: AsyncSession,
	admin_auth_headers: dict[str, str],
):
	# An admin can assign an existing exercise to an existing chapter position.
	chapter = models.Chapter(title="Assignment chapter", position=0, active=True)
	db_session.add(chapter)
	await db_session.commit()
	exercise = await add_exercise(db_session, "To assign", "to-assign.html")

	response = await client.put(
		f"/api/exercises/assignment?exercise_id={exercise.id}",
		json={"chapter_id": chapter.id, "position": 0},
		headers=admin_auth_headers,
	)

	assert response.status_code == 200
	assert response.json()["chapter_id"] == chapter.id
	assert response.json()["position"] == 0


@pytest.mark.anyio
async def test_assign_exercise_can_unassign_from_chapter(
	client: AsyncClient,
	db_session: AsyncSession,
	admin_auth_headers: dict[str, str],
):
	# The -1 chapter sentinel lets an admin unassign an exercise.
	chapter = models.Chapter(title="Previously assigned chapter", position=0, active=True)
	db_session.add(chapter)
	await db_session.commit()
	exercise = await add_exercise(
		db_session,
		"Assigned exercise",
		"assigned.html",
		chapter_id=chapter.id,
		position=0,
	)

	response = await client.put(
		f"/api/exercises/assignment?exercise_id={exercise.id}",
		json={"chapter_id": -1, "position": -1},
		headers=admin_auth_headers,
	)

	assert response.status_code == 200
	assert response.json()["chapter_id"] == -1
	assert response.json()["position"] == -1


@pytest.mark.anyio
async def test_assign_exercise_can_unassign_multiple_exercises(
	client: AsyncClient,
	db_session: AsyncSession,
	admin_auth_headers: dict[str, str],
):
	# Multiple exercises can be left unassigned at the same time.
	chapter = models.Chapter(title="Multiple unassignment chapter", position=0, active=True)
	db_session.add(chapter)
	await db_session.commit()
	first = await add_exercise(
		db_session, "First unassigned", "first-unassigned.html", chapter_id=chapter.id, position=0
	)
	second = await add_exercise(
		db_session, "Second unassigned", "second-unassigned.html", chapter_id=chapter.id, position=1
	)

	positions = []
	for exercise in (first, second):
		response = await client.put(
			f"/api/exercises/assignment?exercise_id={exercise.id}",
			json={"chapter_id": -1, "position": -1},
			headers=admin_auth_headers,
		)
		assert response.status_code == 200, response.text
		assert response.json()["chapter_id"] == -1
		positions.append(response.json()["position"])

	assert positions == [-1, -2]


@pytest.mark.anyio
async def test_assign_exercise_returns_not_found_for_unknown_exercise(
	client: AsyncClient,
	admin_auth_headers: dict[str, str],
):
	# Assigning an exercise ID absent from the database returns its not-found error.
	response = await client.put(
		"/api/exercises/assignment?exercise_id=99999",
		json={"chapter_id": -1, "position": -1},
		headers=admin_auth_headers,
	)

	assert response.status_code == 404
	assert response.json()["detail"] == "Exercise not found"


@pytest.mark.anyio
async def test_assign_exercise_returns_not_found_for_unknown_chapter(
	client: AsyncClient,
	db_session: AsyncSession,
	admin_auth_headers: dict[str, str],
):
	# Assigning to a nonexistent chapter returns the chapter-specific error.
	exercise = await add_exercise(db_session, "Orphan exercise", "orphan.html")

	response = await client.put(
		f"/api/exercises/assignment?exercise_id={exercise.id}",
		json={"chapter_id": 99999, "position": 0},
		headers=admin_auth_headers,
	)

	assert response.status_code == 404
	assert response.json()["detail"] == "Chapter not found"


@pytest.mark.anyio
async def test_assign_exercise_rejects_position_already_used_in_chapter(
	client: AsyncClient,
	db_session: AsyncSession,
	admin_auth_headers: dict[str, str],
):
	# A chapter cannot contain two exercises at the same position.
	chapter = models.Chapter(title="Occupied chapter", position=0, active=True)
	db_session.add(chapter)
	await db_session.commit()
	await add_exercise(
		db_session,
		"Occupying exercise",
		"occupying.html",
		chapter_id=chapter.id,
		position=0,
	)
	exercise = await add_exercise(db_session, "Waiting exercise", "waiting.html")

	response = await client.put(
		f"/api/exercises/assignment?exercise_id={exercise.id}",
		json={"chapter_id": chapter.id, "position": 0},
		headers=admin_auth_headers,
	)

	assert response.status_code == 409
	assert response.json()["detail"] == "Position already assigned"


@pytest.mark.anyio
async def test_assign_exercise_rejects_missing_token(client: AsyncClient):
	# Exercise assignment requires a valid token.
	response = await client.put(
		"/api/exercises/assignment?exercise_id=1",
		json={"chapter_id": -1, "position": -1},
	)

	assert response.status_code == 401
	assert response.json()["detail"] == "Invalid or expired authentication token"


@pytest.mark.anyio
async def test_assign_exercise_rejects_regular_user(
	client: AsyncClient,
	user_auth_headers: dict[str, str],
):
	# A regular logged-in user cannot assign exercises to chapters.
	response = await client.put(
		"/api/exercises/assignment?exercise_id=1",
		json={"chapter_id": -1, "position": -1},
		headers=user_auth_headers,
	)

	assert response.status_code == 403
	assert response.json()["detail"] == "Admin privileges required"


## Test update_exercise
# Check admin field updates, unknown IDs, and denial of unauthenticated or regular users.


@pytest.mark.anyio
async def test_update_exercise_changes_fields_for_admin(
	client: AsyncClient,
	db_session: AsyncSession,
	admin_auth_headers: dict[str, str],
):
	# An admin can update the supported exercise fields.
	exercise = await add_exercise(db_session, "Before update", "before.html")

	response = await client.put(
		f"/api/exercises/update/{exercise.id}",
		json={
			"title": "After update",
			"html_filename": "after.html",
			"task": False,
		},
		headers=admin_auth_headers,
	)

	assert response.status_code == 200
	assert response.json()["title"] == "After update"
	assert response.json()["html_filename"] == "after.html"
	assert response.json()["task"] is False


@pytest.mark.anyio
async def test_update_exercise_returns_not_found_for_unknown_id(
	client: AsyncClient,
	admin_auth_headers: dict[str, str],
):
	# Updating an exercise ID absent from the database returns a not-found error.
	response = await client.put(
		"/api/exercises/update/99999",
		json={"title": "Missing exercise update"},
		headers=admin_auth_headers,
	)

	assert response.status_code == 404
	assert response.json()["detail"] == "Exercise not found"


@pytest.mark.anyio
async def test_update_exercise_rejects_missing_token(client: AsyncClient):
	# Exercise updates require a valid bearer token.
	response = await client.put(
		"/api/exercises/update/1",
		json={"title": "Unauthorized update"},
	)

	assert response.status_code == 401
	assert response.json()["detail"] == "Invalid or expired authentication token"


@pytest.mark.anyio
async def test_update_exercise_rejects_regular_user(
	client: AsyncClient,
	user_auth_headers: dict[str, str],
):
	# A regular logged-in user cannot update exercise fields.
	response = await client.put(
		"/api/exercises/update/1",
		json={"title": "Unauthorized update"},
		headers=user_auth_headers,
	)

	assert response.status_code == 403
	assert response.json()["detail"] == "Admin privileges required"


## Test delete_exercise
# Check removal, missing-exercise errors, and admin-only access.


@pytest.mark.anyio
async def test_delete_exercise_removes_exercise_for_admin(
	client: AsyncClient,
	db_session: AsyncSession,
	admin_auth_headers: dict[str, str],
):
	exercise = await add_exercise(db_session, "Exercise to delete", "delete.html")

	response = await client.delete(
		f"/api/exercises/delete/{exercise.id}", headers=admin_auth_headers
	)

	assert response.status_code == 204
	assert await db_session.get(models.Exercise, exercise.id) is None


@pytest.mark.anyio
async def test_delete_exercise_returns_not_found_for_unknown_id(
	client: AsyncClient,
	admin_auth_headers: dict[str, str],
):
	response = await client.delete(
		"/api/exercises/delete/99999", headers=admin_auth_headers
	)

	assert response.status_code == 404
	assert response.json()["detail"] == "Exercise not found"


@pytest.mark.anyio
async def test_delete_exercise_rejects_missing_token(client: AsyncClient):
	response = await client.delete("/api/exercises/delete/1")

	assert response.status_code == 401
	assert response.json()["detail"] == "Invalid or expired authentication token"


@pytest.mark.anyio
async def test_delete_exercise_rejects_regular_user(
	client: AsyncClient,
	user_auth_headers: dict[str, str],
):
	response = await client.delete(
		"/api/exercises/delete/1", headers=user_auth_headers
	)

	assert response.status_code == 403
	assert response.json()["detail"] == "Admin privileges required"

