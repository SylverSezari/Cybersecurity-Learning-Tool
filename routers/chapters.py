from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

import models
from database import get_db
from schemas import ChapterPost, ChapterResponse, ChapterPut

router = APIRouter()

# All available http requests to chapters are here


## Get all chapters
@router.get("", response_model=list[ChapterResponse])
async def get_all_chapters(db: Annotated[AsyncSession, Depends(get_db)]):
    result = await db.execute(select(models.Chapter))

    chapters = result.scalars().all()
    return chapters


## Get single chapter
@router.get("/{chapter_id}", response_model=ChapterResponse)
async def get_single_chapter(
    chapter_id: int, db: Annotated[AsyncSession, Depends(get_db)]
):
    result = await db.execute(
        select(models.Chapter)
        .options(selectinload(models.Chapter.exercises))
        .where(models.Chapter.id == chapter_id)
    )

    chapter = result.scalars().first()
    if not chapter:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Chapter not found"
        )

    return chapter


## Create a chapter
@router.post("", response_model=ChapterResponse, status_code=status.HTTP_201_CREATED)
async def create_chapter(
    chapter: ChapterPost, db: Annotated[AsyncSession, Depends(get_db)]
):
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

    new_chapter = models.Chapter(title=chapter.title)

    db.add(new_chapter)
    await db.commit()
    await db.refresh(new_chapter)
    return ChapterResponse(
        id=new_chapter.id,
        title=new_chapter.title,
        exercises=[],
    )
    

## Update chapter
@router.put("/update/{chapter_id}", response_model=ChapterResponse)
async def update_chapter(chapter_id: int, update_data: ChapterPut, db: Annotated[AsyncSession, Depends(get_db)]):
    
    #check if chapter exists
    result = await db.execute(
        select(models.Chapter)
        .where(models.Chapter.id == chapter_id)
    )

    chapter = result.scalars().first()
    if not chapter:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Chapter not found"
        )

    #check if chapter with this title exists
    result = await db.execute(
        select(models.Chapter)
        .where(func.lower(models.Chapter.title) == update_data.title.lower())
    )

    titles = result.scalars().first()
    if titles:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Chapter with this title already exists"
        )
    
    chapter.title = update_data.title
    
    await db.commit()
    await db.refresh(chapter)
    return chapter