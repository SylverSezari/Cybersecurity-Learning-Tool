from pydantic import BaseModel, Field

# Schemas for the http requests

## Exercises


### for get requests
class ExerciseResponse(BaseModel):
    id: int
    title: str = Field(min_length=1, max_length=100)
    html_filename: str = Field(min_length=1, max_length=100)
    task: bool
    chapter_id: int | None = Field(default=None)
    position: int | None = Field(default=None)


### for post requests
class ExercisePost(BaseModel):
    title: str = Field(min_length=1, max_length=100)
    html_filename: str = Field(min_length=1, max_length=100)
    task: bool


### for exercise assignments
class ExerciseAssignment(BaseModel):
    chapter_id: int
    position: int


### for updating exercises
class ExercisePut(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=100)
    html_filename: str | None = Field(default=None, min_length=1, max_length=100)
    task: bool | None = Field(default=None)


## Chapters


### for get requests
class ChapterResponse(BaseModel):
    id: int
    title: str = Field(min_length=1, max_length=100)
    exercises: list[ExerciseResponse] = Field(default_factory=list)


### for post requests
class ChapterPost(BaseModel):
    title: str = Field(min_length=1, max_length=100)


### for put requests
class ChapterPut(BaseModel):
    title: str= Field(min_length=1, max_length=100)
