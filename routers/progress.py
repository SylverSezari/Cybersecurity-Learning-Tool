from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

import models
from database import get_db
from exercise_progress import get_exercise_progress
from security import Principal, get_current_principal

router = APIRouter()


async def _require_user_account(
	db: AsyncSession,
	principal: Principal,
) -> int:
	account_id = principal["account_id"]
	if principal["role"] != "user" or account_id is None:
		raise HTTPException(
			status_code=status.HTTP_403_FORBIDDEN,
			detail="User account required",
		)

	result = await db.execute(
		select(models.Account.id).where(models.Account.id == account_id)
	)
	if result.scalar_one_or_none() is None:
		raise HTTPException(
			status_code=status.HTTP_401_UNAUTHORIZED,
			detail="Account no longer exists",
		)
	return account_id


@router.get("/chapters/{chapter_id}")
async def chapter_progress(
	chapter_id: int,
	db: Annotated[AsyncSession, Depends(get_db)],
	principal: Annotated[Principal, Depends(get_current_principal)],
):
	account_id = await _require_user_account(db, principal)
	result = await db.execute(
		select(models.Chapter.id).where(
			models.Chapter.id == chapter_id,
			models.Chapter.active.is_(True),
		)
	)
	if result.scalar_one_or_none() is None:
		raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chapter not found")

	completed_ids, locked_by = await get_exercise_progress(db, chapter_id, account_id)
	return {
		"completed_ids": sorted(completed_ids),
		"locked_by": locked_by,
	}


@router.post("/exercises/{exercise_id}/complete")
async def complete_exercise(
	exercise_id: int,
	db: Annotated[AsyncSession, Depends(get_db)],
	principal: Annotated[Principal, Depends(get_current_principal)],
):
	account_id = await _require_user_account(db, principal)
	result = await db.execute(
		select(models.Exercise)
		.join(models.Chapter)
		.where(
			models.Exercise.id == exercise_id,
			models.Chapter.active.is_(True),
		)
	)
	exercise = result.scalar_one_or_none()
	if exercise is None or exercise.chapter_id is None:
		raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Exercise not found")

	completed_ids, locked_by = await get_exercise_progress(
		db, exercise.chapter_id, account_id
	)
	if exercise_id in locked_by:
		raise HTTPException(
			status_code=status.HTTP_403_FORBIDDEN,
			detail="Exercise is locked",
		)

	if exercise_id not in completed_ids:
		db.add(
			models.ExerciseCompletion(
				account_id=account_id,
				exercise_id=exercise_id,
			)
		)
		await db.commit()

	return {"completed": True}