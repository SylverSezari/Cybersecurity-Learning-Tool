from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload, selectinload

import models
from database import get_db
from schemas import (
    ChapterActivationChange,
    ChapterPost,
    ChapterPut,
    ChapterResponse,
)
from security import Principal, get_current_principal, require_admin

router = APIRouter()

# All available http requests to chapters are here


## Get all chapters (only possible if auth header is valid)
@router.get("", response_model=list[ChapterResponse])
async def get_all_chapters(
    db: Annotated[AsyncSession, Depends(get_db)],
    principal: Annotated[Principal, Depends(get_current_principal)],
):
    # Return the chapter catalog to an authenticated caller.
    result = await db.execute(select(models.Chapter))

    chapters = result.scalars().all()
    return chapters


## Get single chapter (only possible if auth header is valid)
@router.get("/{chapter_id}", response_model=ChapterResponse)
async def get_single_chapter(
    chapter_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    principal: Annotated[Principal, Depends(get_current_principal)],
):
    # Return one chapter with its exercises, or a not-found response.
    # get all chapters with the same id
    result = await db.execute(
        select(models.Chapter)
        .options(selectinload(models.Chapter.exercises))
        .where(models.Chapter.id == chapter_id)
    )
    chapter = result.scalars().first()

    # check if chapter exists
    if not chapter:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Chapter not found"
        )

    return chapter


## Create a chapter
@router.post("", response_model=ChapterResponse, status_code=status.HTTP_201_CREATED)
async def create_chapter(
    chapter: ChapterPost,
    db: Annotated[AsyncSession, Depends(get_db)],
    principal: Annotated[Principal, Depends(get_current_principal)],
):
    # Create an inactive chapter that an administrator can later publish.
    # check that user is the admin
    require_admin(principal)

    # check if chapter with same title exists
    result = await db.execute(
        select(models.Chapter).where(
            func.lower(models.Chapter.title) == chapter.title.lower()
        )
    )
    existing_chapter = result.scalars().first()
    if existing_chapter:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Chapter with this title exists already",
        )

    # create new chapter
    new_chapter = models.Chapter(
        title=chapter.title,
        position=-1,
        active=False,
    )

    db.add(new_chapter)
    await db.commit()
    await db.refresh(new_chapter)
    return ChapterResponse(
        id=new_chapter.id,
        title=new_chapter.title,
        position=new_chapter.position,
        active=new_chapter.active,
        exercises=[],
    )


## Update chapter
@router.put("/update/{chapter_id}", response_model=ChapterResponse)
async def update_chapter(
    chapter_id: int,
    update_data: ChapterPut,
    db: Annotated[AsyncSession, Depends(get_db)],
    principal: Annotated[Principal, Depends(get_current_principal)],
):
    # Rename a chapter after checking that its title remains unique.
    require_admin(principal)

    # check if chapter exists
    result = await db.execute(
        select(models.Chapter).where(models.Chapter.id == chapter_id)
    )

    chapter = result.scalars().first()
    if not chapter:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Chapter not found"
        )

    # check if chapter with this title exists
    result = await db.execute(
        select(models.Chapter).where(
            func.lower(models.Chapter.title) == update_data.title.lower(),
            models.Chapter.id != chapter_id,
        )
    )

    titles = result.scalars().first()
    if titles:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Chapter with this title already exists",
        )

    # update title
    chapter.title = update_data.title

    await db.commit()
    await db.refresh(chapter)
    return chapter


## Change chapter activation
@router.put("/activation/change", response_model=list[ChapterResponse])
async def change_chapters_active(
    chapters_updated: ChapterActivationChange,
    db: Annotated[AsyncSession, Depends(get_db)],
    principal: Annotated[Principal, Depends(get_current_principal)],
):
    # Validate and save the complete active/inactive chapter ordering.
    require_admin(principal)

    # Load every chapter and its exercises so the returned response can include them.
    result = await db.execute(
        select(models.Chapter).options(joinedload(models.Chapter.exercises))
    )
    chapters = result.scalars().unique().all()

    # Index submitted changes by chapter ID and collect IDs and positions for validation.
    updates_by_id = {
        chapter_update.chapter_id: chapter_update
        for chapter_update in chapters_updated.chapters
    }
    database_ids = {chapter.id for chapter in chapters}
    submitted_ids = [chapter.chapter_id for chapter in chapters_updated.chapters]
    active_positions = [
        chapter.position
        for chapter in chapters_updated.chapters
        if chapter.active and chapter.position != -1
    ]

    # Active chapters must have unique assigned positions; -1 is a shared sentinel.
    if len(active_positions) != len(set(active_positions)):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Assigned chapter positions must be unique",
        )

    # Require each database chapter exactly once, with no duplicate or unknown IDs.
    if (
        len(submitted_ids) != len(set(submitted_ids))
        or set(submitted_ids) != database_ids
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Include each existing chapter exactly once",
        )

    # Inactive chapters share position -1; active chapters keep their submitted position.
    for chapter in chapters:
        chapter_update = updates_by_id[chapter.id]
        chapter.position = chapter_update.position if chapter_update.active else -1
        chapter.active = chapter_update.active

    await db.commit()
    return chapters


## delete chapter
@router.delete("/delete/{chapter_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_chapter(
    chapter_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    principal: Annotated[Principal, Depends(get_current_principal)],
):
    # Delete a chapter while leaving its former exercises unassigned.

    require_admin(principal)

    # Check if chapter exists
    result = await db.execute(
        select(models.Chapter).where(models.Chapter.id == chapter_id)
    )

    chapter = result.scalars().first()
    if not chapter:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Chapter not found"
        )

    await db.execute(
        update(models.Exercise)
        .where(models.Exercise.chapter_id == chapter_id)
        .values(chapter_id=None, position=-1)
    )
    await db.delete(chapter)
    await db.commit()
