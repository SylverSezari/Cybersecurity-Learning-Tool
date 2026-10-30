# Calculate which exercises are completed or blocked for a learner.

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

import models


async def get_exercise_progress(
	db: AsyncSession,
	chapter_id: int,
	account_id: int | None,
) -> tuple[set[int], dict[int, int]]:
	# Return completion IDs and each locked exercise's first unmet prerequisite.
	if account_id is None:
		return set(), {}

	exercise_result = await db.execute(
		select(models.Exercise)
		.where(models.Exercise.chapter_id == chapter_id)
		.order_by(models.Exercise.position, models.Exercise.id)
	)
	exercises = exercise_result.scalars().all()
	completed_result = await db.execute(
		select(models.ExerciseCompletion.exercise_id)
		.join(models.Exercise)
		.where(models.ExerciseCompletion.account_id == account_id)
		.where(models.Exercise.chapter_id == chapter_id)
	)
	completed_ids = set(completed_result.scalars().all())

	locked_by: dict[int, int] = {}
	previous_blocker: int | None = None
	for index, exercise in enumerate(exercises):
		if index == 0:
			continue

		if previous_blocker is not None:
			# A blocked prerequisite also blocks later exercises in the sequence.
			locked_by[exercise.id] = previous_blocker
		elif exercise.requires_previous:
			previous = exercises[index - 1]
			if previous.id not in completed_ids:
				locked_by[exercise.id] = previous.id

		previous_blocker = locked_by.get(exercise.id)

	return completed_ids, locked_by