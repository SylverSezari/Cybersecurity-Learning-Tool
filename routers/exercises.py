from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

import models
from database import get_db
from schemas import ExerciseAssignment, ExercisePost, ExercisePut, ExerciseResponse

router = APIRouter()

# All available http requests to exercises are here


## Get all exercises
@router.get("", response_model=list[ExerciseResponse])
async def get_all_exercises(db: Annotated[AsyncSession, Depends(get_db)]):
    result = await db.execute(select(models.Exercise))

    exercises = result.scalars().all()
    return exercises


## Get single exercise
@router.get("/{exercise_id}", response_model=ExerciseResponse)
async def get_single_exercise(
    exercise_id: int, db: Annotated[AsyncSession, Depends(get_db)]
):
    result = await db.execute(
        select(models.Exercise).where(models.Exercise.id == exercise_id)
    )

    exercise = result.scalars().first()
    if exercise:
        return exercise
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND, detail="Exercise not found"
    )


## Get all exercises belonging to a single chapter ordered by position
@router.get("/chapter/{chapter_id}", response_model=list[ExerciseResponse])
async def get_exercises_belonging_to_chapter(
    chapter_id: int, db: Annotated[AsyncSession, Depends(get_db)]
):
    result = await db.execute(
        select(models.Exercise)
        .where(models.Exercise.chapter_id == chapter_id)
        .order_by(models.Exercise.position)
    )
    exercises = result.scalars().all()
    return exercises


## Create an exercise
@router.post("", response_model=ExerciseResponse, status_code=status.HTTP_201_CREATED)
async def create_exercise(
    exercise: ExercisePost, db: Annotated[AsyncSession, Depends(get_db)]
):
    result = await db.execute(
        select(models.Exercise).where(
            func.lower(models.Exercise.title) == exercise.title.lower()
        )
    )
    existing_title = result.scalars().first()
    if existing_title:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Exercise with this title already created",
        )

    result = await db.execute(
        select(models.Exercise).where(
            func.lower(models.Exercise.html_filename) == exercise.html_filename.lower()
        )
    )
    existing_filename = result.scalars().first()
    if existing_filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Exercise with this filename already created",
        )

    new_exercise = models.Exercise(
        title=exercise.title,
        html_filename=exercise.html_filename,
        task=exercise.task,
        chapter_id=-1,
    )

    db.add(new_exercise)
    await db.commit()
    await db.refresh(new_exercise)
    return new_exercise


## Assign a chapter to an exercise
@router.put("/assignment", response_model=ExerciseResponse)
async def assign_exercise(
    exercise_id: int,
    assignment: ExerciseAssignment,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    # Check if exercise exists
    result = await db.execute(
        select(models.Exercise).where(models.Exercise.id == exercise_id)
    )

    exercise = result.scalars().first()
    if not exercise:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Exercise not found"
        )

    # check if chapter exists if you are not unassigning exercise
    if assignment.chapter_id != -1:
        result = await db.execute(
            select(models.Chapter).where(models.Chapter.id == assignment.chapter_id)
        )

        chapter = result.scalars().first()
        if not chapter:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Chapter not found"
            )

        ## check if postion is not already assigned for this chapter
        result = await db.execute(
            select(models.Exercise).where(
                models.Exercise.chapter_id == assignment.chapter_id,
                models.Exercise.position == assignment.position,
            )
        )

        positioning = result.scalars().first()
        if positioning:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT, detail="Position already assigned"
            )

    # assign the new values
    exercise.chapter_id = assignment.chapter_id
    exercise.position = assignment.position

    await db.commit()
    await db.refresh(exercise, attribute_names=["chapter"])
    return exercise


## Update exercise name or filename
@router.put("/update/{exercise_id}", response_model=ExerciseResponse)
async def update_exercise(
    exercise_id: int,
    update_data: ExercisePut,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    # Check if exercise exists
    result = await db.execute(
        select(models.Exercise).where(models.Exercise.id == exercise_id)
    )

    exercise = result.scalars().first()
    if not exercise:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Exercise not found"
        )

    exercise_data = update_data.model_dump(exclude_unset=True)
    for field, value in exercise_data.items():
        setattr(exercise, field, value)

    await db.commit()
    await db.refresh(exercise)
    return exercise
