from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

import models
from database import get_db
from schemas import (
    ExerciseAssignment,
    ExerciseOrder,
    ExercisePost,
    ExercisePut,
    ExerciseResponse,
)
from security import Principal, get_current_principal, require_admin

router = APIRouter()

# All available http requests to exercises are here


## Get all exercises
@router.get("", response_model=list[ExerciseResponse])
async def get_all_exercises(
    db: Annotated[AsyncSession, Depends(get_db)],
    principal: Annotated[Principal, Depends(get_current_principal)],
):
    # Return the exercise catalog to an authenticated caller.
    result = await db.execute(select(models.Exercise))

    exercises = result.scalars().all()
    return exercises


## Get single exercise
@router.get("/{exercise_id}", response_model=ExerciseResponse)
async def get_single_exercise(
    exercise_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    principal: Annotated[Principal, Depends(get_current_principal)],
):
    # Return one exercise by ID, or report that it does not exist.
    # check if exercise exists
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
    chapter_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    principal: Annotated[Principal, Depends(get_current_principal)],
):
    # Return exercises assigned to a chapter in display order.
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
    exercise: ExercisePost,
    db: Annotated[AsyncSession, Depends(get_db)],
    principal: Annotated[Principal, Depends(get_current_principal)],
):
    # Create an unassigned exercise with its answer key and prerequisite rule.
    require_admin(principal)

    # Check if exercise with title exists already
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

    # Check if filename is already taken
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

    # create new exercise
    new_exercise = models.Exercise(
        title=exercise.title,
        html_filename=exercise.html_filename,
        solution=exercise.solution,
        requires_previous=exercise.requires_previous,
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
    principal: Annotated[Principal, Depends(get_current_principal)],
):
    # Assign an exercise to a chapter position or move it to the unassigned pool.
    require_admin(principal)

    # Check if exercise exists
    result = await db.execute(
        select(models.Exercise).where(models.Exercise.id == exercise_id)
    )

    exercise = result.scalars().first()
    if not exercise:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Exercise not found"
        )

    position = assignment.position

    # Keep unassigned exercises at unique negative positions for the database constraint.
    if assignment.chapter_id == -1:
        result = await db.execute(
            select(models.Exercise.position).where(
                models.Exercise.chapter_id == -1,
                models.Exercise.id != exercise_id,
            )
        )
        unassigned_positions = set(result.scalars().all())
        position = -1
        while position in unassigned_positions:
            position -= 1

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
    exercise.position = position

    await db.commit()
    await db.refresh(exercise, attribute_names=["chapter"])
    return exercise


## Reorder exercises assigned to a chapter
@router.put("/assignment/order/{chapter_id}", response_model=list[ExerciseResponse])
async def reorder_chapter_exercises(
    chapter_id: int,
    order: ExerciseOrder,
    db: Annotated[AsyncSession, Depends(get_db)],
    principal: Annotated[Principal, Depends(get_current_principal)],
):
    # Save the complete order as one admin-only operation.
    require_admin(principal)

    result = await db.execute(
        select(models.Chapter).where(models.Chapter.id == chapter_id)
    )
    if not result.scalars().first():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Chapter not found"
        )

    result = await db.execute(
        select(models.Exercise).where(models.Exercise.chapter_id == chapter_id)
    )
    assigned = result.scalars().all()
    submitted_ids = order.exercise_ids
    assigned_by_id = {exercise.id: exercise for exercise in assigned}

    if (
        len(submitted_ids) != len(set(submitted_ids))
        or set(submitted_ids) != set(assigned_by_id)
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Include each assigned exercise exactly once",
        )

    existing_positions = [
        exercise.position for exercise in assigned if exercise.position is not None
    ]
    temporary_position = min(existing_positions, default=0) - len(assigned) - 1
    for offset, exercise in enumerate(assigned):
        exercise.position = temporary_position - offset
    await db.flush()

    for position, exercise_id in enumerate(submitted_ids):
        assigned_by_id[exercise_id].position = position

    await db.commit()
    return [assigned_by_id[exercise_id] for exercise_id in submitted_ids]


## Update exercise name or filename
@router.put("/update/{exercise_id}", response_model=ExerciseResponse)
async def update_exercise(
    exercise_id: int,
    update_data: ExercisePut,
    db: Annotated[AsyncSession, Depends(get_db)],
    principal: Annotated[Principal, Depends(get_current_principal)],
):
    # Apply only submitted exercise fields after enforcing title uniqueness.
    require_admin(principal)

    # Check if exercise exists
    result = await db.execute(
        select(models.Exercise).where(models.Exercise.id == exercise_id)
    )

    exercise = result.scalars().first()
    if not exercise:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Exercise not found"
        )

    # Update exercise with relevant data
    exercise_data = update_data.model_dump(exclude_unset=True)
    if "title" in exercise_data:
        result = await db.execute(
            select(models.Exercise).where(
                func.lower(models.Exercise.title) == exercise_data["title"].lower(),
                models.Exercise.id != exercise_id,
            )
        )
        if result.scalars().first():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Exercise with this title already created",
            )

    for field, value in exercise_data.items():
        setattr(exercise, field, value)

    await db.commit()
    await db.refresh(exercise)
    return exercise


## delete exercise
@router.delete("/delete/{exercise_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_exercise(
    exercise_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    principal: Annotated[Principal, Depends(get_current_principal)],
):
    # Delete an exercise and its recorded completion rows.

    require_admin(principal)

    # Check if exercise exists
    result = await db.execute(
        select(models.Exercise).where(models.Exercise.id == exercise_id)
    )

    exercise = result.scalars().first()
    if not exercise:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Exercise not found"
        )

    await db.execute(
        delete(models.ExerciseCompletion).where(
            models.ExerciseCompletion.exercise_id == exercise_id
        )
    )

    # delete exercise
    await db.delete(exercise)
    await db.commit()
