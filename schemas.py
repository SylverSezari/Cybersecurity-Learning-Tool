from pydantic import BaseModel

# Schemas for the http requests

## Exercises

### for get requests
class ExerciseResponse(BaseModel):
    id: int
    title: str
    html_filename: str
    task: bool
    chapter_id: int
    position: int
    

### for post requests
class ExercisePost(BaseModel):
    title: str
    html_filename: str
    task: bool


## Chapters

### for get requests
class ChapterResponse(BaseModel):
    id: int
    title: str
    exercises: list[ExerciseResponse]
    

### for post requests
class ChapterPost(BaseModel):
    title: str
    

### for put requests
class ChapterExerciseAssignment(BaseModel):
    chapter_id: int
    exercise_id: int
    position: int