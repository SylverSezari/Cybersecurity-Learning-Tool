from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

import models
from database import get_db
from schemas import ExerciseResponse

router = APIRouter()

# All available http requests to exercises are here

## Get all exercises
@router.get("", response_model=list[ExerciseResponse])
async def get_all_chapters(db: Annotated[AsyncSession, Depends(get_db)]):
    result = await db.execute(select(models.Exercise))
    
    exercises = result.scalars().all()
    return exercises


## Get single chapter
@router.get("/{exercise_id}", response_model=ExerciseResponse)
async def get_single_exercise(exercise_id: int, db: Annotated[AsyncSession, Depends(get_db)]):
    result = await db.execute(select(models.Exercise)
                              .options(selectinload(list[models.Exercise.chapter]))
                              .where(models.Exercise.id == exercise_id))
    
    exercise = result.scalars().first() 
    if exercise:
        return exercise
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Exercise not found")


## Get all exercises belonging to a single chapter ordered by position
@router.get("/{chapter_id}", response_model=list[ExerciseResponse])
async def get_exercises_belonging_to_chapter(chapter_id: int, db: Annotated[AsyncSession, Depends(get_db)]):
    result = await db.execute(select(models.Exercise)
                              .where(models.Exercise.chapter_id == chapter_id)
                              .order_by(models.Exercise.position))
    exercises = result.scalars().all()
    return exercises