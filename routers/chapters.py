from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

import models
from database import get_db
from schemas import ChapterResponse

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
async def get_single_chapter(chapter_id: int, db: Annotated[AsyncSession, Depends(get_db)]):
    result = await db.execute(select(models.Chapter)
                              .options(selectinload(list[models.Chapter.exercises]))
                              .where(models.Chapter.id == chapter_id))
    
    chapter = result.scalars().first() 
    if chapter:
        return chapter
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chapter not found")