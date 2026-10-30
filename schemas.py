# Validated request and response shapes for the HTTP API.

from pydantic import BaseModel, Field, StrictBool, StrictFloat, StrictInt, StrictStr

# Strict scalar members prevent JSON booleans and numbers from being coerced silently.
SolutionValue = StrictStr | StrictInt | StrictFloat | StrictBool
SolutionList = list[SolutionValue]

# Schemas for the http requests

## Exercises


### for get requests
class ExerciseResponse(BaseModel):
    id: int
    title: str = Field(min_length=1, max_length=100)
    html_filename: str = Field(min_length=1, max_length=100)
    solution: SolutionList = Field(default_factory=list)
    requires_previous: bool = False
    chapter_id: int | None = Field(default=None)
    position: int | None = Field(default=None)


### for post requests
class ExercisePost(BaseModel):
    title: str = Field(min_length=1, max_length=100)
    html_filename: str = Field(min_length=1, max_length=100)
    solution: SolutionList = Field(default_factory=list)
    requires_previous: bool = False


### for exercise assignments
class ExerciseAssignment(BaseModel):
    chapter_id: int
    position: int


class ExerciseCompletionRequest(BaseModel):
    answers: SolutionList


### for updating exercises
class ExercisePut(BaseModel):
    # Partial exercise update; omitted fields stay unchanged at the route layer.
    title: str | None = Field(default=None, min_length=1, max_length=100)
    html_filename: str | None = Field(default=None, min_length=1, max_length=100)
    solution: SolutionList = Field(default_factory=list)
    requires_previous: bool | None = Field(default=None)


## Chapters


### for get requests
class ChapterResponse(BaseModel):
    id: int
    title: str
    position: int
    active: bool
    exercises: list[ExerciseResponse] = Field(default_factory=list)


### for post requests
class ChapterPost(BaseModel):
    title: str = Field(min_length=1, max_length=100)


### for put requests
class ChapterPut(BaseModel):
    title: str = Field(min_length=1, max_length=100)


class ChapterActivation(BaseModel):
    chapter_id: int
    position: int
    active: bool


class ChapterActivationChange(BaseModel):
    chapters: list[ChapterActivation]


## Accounts


### for get requests
class AccountResponse(BaseModel):
    id: int
    username: str


### for post requests
class AccountCreate(BaseModel):
    username: str = Field(min_length=1, max_length=20)
    password: str = Field(min_length=4)


class AccountPut(BaseModel):
    username: str | None = Field(default=None, min_length=1, max_length=20)
    password: str | None = Field(default=None, min_length=4)


class AccountLogin(BaseModel):
    username: str
    password: str


## token to remember user
class Token(BaseModel):
    access_token: str
    token_type: str
