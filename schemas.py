# Validated request and response shapes for the HTTP API.

from datetime import datetime

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


class ExerciseOrder(BaseModel):
    exercise_ids: list[int]


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
    picture: str | None = Field(default=None)
    position: int
    active: bool
    exercises: list[ExerciseResponse] = Field(default_factory=list)


### for post requests
class ChapterPost(BaseModel):
    title: str = Field(min_length=1, max_length=100)
    picture: str | None = Field(default=None)


### for put requests
class ChapterPut(BaseModel):
    title: str = Field(min_length=1, max_length=100)
    picture: str | None = Field(default=None)


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
    klasse: str


### for post requests
class AccountCreate(BaseModel):
    username: str = Field(min_length=1, max_length=40)
    password: str = Field(min_length=4, max_length=20)
    klasse: str | None = Field(default=None, min_length=1, max_length=50)


class AccountPut(BaseModel):
    username: str | None = Field(default=None, min_length=1, max_length=40)
    password: str | None = Field(default=None, min_length=4, max_length=20)
    klasse: str | None = Field(default=None, min_length=1, max_length=50)


class AccountLogin(BaseModel):
    username: str
    password: str


## token to remember user
class Token(BaseModel):
    access_token: str
    token_type: str


## Challenges


# Challenge answer keys are generated per run and are never part of challenge metadata.
class ChallengeResponse(BaseModel):
    id: int
    title: str = Field(min_length=1, max_length=100)
    html_filename: str = Field(min_length=1, max_length=100)
    position: int


class ChallengeCreate(BaseModel):
    title: str = Field(min_length=1, max_length=100)
    html_filename: str = Field(min_length=1, max_length=100)


class ChallengeOrder(BaseModel):
    # The API accepts a full permutation, not a partial move operation.
    challenge_ids: list[int]


class ChallengeUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=100)
    html_filename: str | None = Field(default=None, min_length=1, max_length=100)


class ChallengeCheckRequest(BaseModel):
    # Strict scalar types keep JSON booleans distinct from numeric answers.
    answers: SolutionList


class ChallengeCheckResponse(BaseModel):
    # Completion unlocks the separate next/finish form; it does not advance by itself.
    completed: bool
    is_last: bool


class AccountChallengeTiming(BaseModel):
    # Timestamps are UTC-aware; record_time is a non-negative millisecond duration.
    start_time: datetime | None = None
    end_time: datetime | None = None
    record_time: int | None = Field(default=None, ge=0)