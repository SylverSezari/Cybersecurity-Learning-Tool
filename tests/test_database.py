import pytest
from sqlalchemy import inspect, text
from sqlalchemy.ext.asyncio import create_async_engine

import database


@pytest.mark.anyio
async def test_init_db_migrates_task_column_to_nullable_solution(
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
				"INSERT INTO exercises "
				"(id, title, html_filename, task, position, chapter_id) "
				"VALUES (1, 'Legacy exercise', 'legacy.html', 1, 0, 1)"
			)
		)

	try:
		await database.init_db()
		async with legacy_engine.connect() as connection:
			columns = await connection.run_sync(
				lambda sync_connection: {
					column["name"]: column
					for column in inspect(sync_connection).get_columns("exercises")
				}
			)
			result = await connection.execute(
				text("SELECT solution FROM exercises WHERE id = 1")
			)
			assert result.scalar_one() == "[]"
		assert "task" not in columns
		assert columns["solution"]["nullable"] is True

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