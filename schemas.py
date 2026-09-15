from pydantic import BaseModel

# Schemas for the http requests

## Exercises

class ExerciseResponse(BaseModel):
    id: int
    title: str
    html_file: str
    task: bool
    chapter_id: int
    position: int
    
    

## Chapters

class ChapterResponse(BaseModel):
    id: int
    title: str
    exercises: list[ExerciseResponse]