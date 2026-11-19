# FastAPI application, API router registration, and learning-page handlers.

import logging
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.exception_handlers import http_exception_handler
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from starlette.exceptions import HTTPException as StarletteHTTPException

import challenge_pages
import models
from database import engine, get_db, init_db
from exercise_progress import get_exercise_progress
from leaderboard import home_leaderboard
from routers import accounts, challenges, chapters, exercises
from routers import progress as progress_router
from security import (
    Principal,
    get_current_principal,
    get_optional_page_principal,
    get_page_principal,
)

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    # Initialize shared database resources and dispose of them on shutdown.
    await init_db()
    yield
    # Shutdown
    await engine.dispose()


app = FastAPI(lifespan=lifespan)

app.mount("/static", StaticFiles(directory="static"), name="static")

templates = Jinja2Templates(directory="templates")
EXERCISES_DIRECTORY = Path(__file__).resolve().parent / "templates" / "exercises"


def _is_html_page_request(request: Request) -> bool:
    return (
        "text/html" in request.headers.get("accept", "")
        and not request.url.path.startswith("/api/")
    )


@app.exception_handler(StarletteHTTPException)
async def handle_http_exception(
    request: Request,
    error: StarletteHTTPException,
):
    if not _is_html_page_request(request):
        return await http_exception_handler(request, error)

    if error.status_code == status.HTTP_401_UNAUTHORIZED:
        has_session = (
            request.cookies.get("access_token") is not None
            or request.headers.get("authorization") is not None
        )
        destination = "session_expired_page" if has_session else "login_page"
        return RedirectResponse(
            url=request.url_for(destination),
            status_code=status.HTTP_303_SEE_OTHER,
        )

    messages = {
        status.HTTP_403_FORBIDDEN: "Du hast keine Berechtigung für diese Seite.",
        status.HTTP_404_NOT_FOUND: "Die angeforderte Seite wurde nicht gefunden.",
    }
    return templates.TemplateResponse(
        request,
        "error.html",
        {
            "status_code": error.status_code,
            "message": messages.get(
                error.status_code,
                "Die Anfrage konnte nicht abgeschlossen werden.",
            ),
        },
        status_code=error.status_code,
    )


@app.exception_handler(Exception)
async def handle_unexpected_exception(request: Request, _error: Exception):
    logger.exception("Unhandled error while serving %s", request.url.path)
    if _is_html_page_request(request):
        return templates.TemplateResponse(
            request,
            "error.html",
            {
                "status_code": status.HTTP_500_INTERNAL_SERVER_ERROR,
                "message": "Ein unerwarteter Fehler ist aufgetreten. Bitte versuche es später erneut.",
            },
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )
    return JSONResponse(
        {"detail": "Internal Server Error"},
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
    )


def _resolve_exercise_file(relative_path: str) -> Path | None:
    # Resolve an exercise asset only when it remains inside the lesson directory.
    exercise_root = EXERCISES_DIRECTORY.resolve()
    try:
        file_path = (exercise_root / relative_path).resolve()
        file_path.relative_to(exercise_root)
    except (OSError, RuntimeError, ValueError):
        return None

    return file_path if file_path.is_file() else None


async def _ensure_existing_user_account(
    db: AsyncSession,
    principal: Principal,
) -> None:
    # Reject user tokens whose account was deleted after the token was issued.
    if principal["role"] != "user":
        return

    account_id = principal["account_id"]
    if account_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid account",
        )

    result = await db.execute(
        select(models.Account.id).where(models.Account.id == account_id)
    )
    if result.scalar_one_or_none() is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Account no longer exists",
        )


app.include_router(chapters.router, prefix="/api/chapters", tags=["chapters"])
app.include_router(exercises.router, prefix="/api/exercises", tags=["exercises"])
# API routes check answers; the page routes below manage learner-facing run navigation.
app.include_router(challenges.router, prefix="/api/challenges", tags=["challenges"])
app.include_router(accounts.router, prefix="/api/accounts", tags=["accounts"])
app.include_router(progress_router.router, prefix="/api/progress", tags=["progress"])
app.include_router(challenge_pages.router)


# Web functions


## home
@app.get("/", include_in_schema=False, name="home")
async def home(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    principal: Annotated[Principal | None, Depends(get_optional_page_principal)],
):
    # Render active chapters with the current learner's completion state.
    if principal is None:
        return RedirectResponse(
            url=request.url_for(
                "session_expired_page"
                if request.cookies.get("access_token")
                else "login_page"
            ),
            status_code=status.HTTP_303_SEE_OTHER,
        )
    try:
        await _ensure_existing_user_account(db, principal)
    except HTTPException as error:
        if error.status_code != status.HTTP_401_UNAUTHORIZED:
            raise
        return RedirectResponse(
            url=request.url_for("session_expired_page"),
            status_code=status.HTTP_303_SEE_OTHER,
        )
    await challenge_pages.abandon_active_run(db, principal)
    chapter_result = await db.execute(
        select(models.Chapter)
        .options(selectinload(models.Chapter.exercises))
        .where(models.Chapter.active.is_(True))
        .order_by(models.Chapter.position, models.Chapter.id)
    )
    chapters = chapter_result.scalars().all()

    completed_ids: set[int] = set()
    account_id = principal["account_id"]
    if account_id is not None:
        completion_result = await db.execute(
            select(models.ExerciseCompletion.exercise_id)
            .join(models.Exercise)
            .join(models.Chapter)
            .where(
                models.ExerciseCompletion.account_id == account_id,
                models.Chapter.active.is_(True),
            )
        )
        completed_ids = set(completion_result.scalars().all())

    leaderboard = await home_leaderboard(db, account_id)
    return templates.TemplateResponse(
        request,
        "home.html",
        {
            "chapters": chapters,
            "completed_exercise_ids": completed_ids,
            "leaderboard": leaderboard,
            "can_run_challenges": principal["role"] in {"admin", "user"},
            "is_admin": principal["role"] == "admin",
        },
    )


## login
@app.get("/login", include_in_schema=False, name="login_page")
async def login_page(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    principal: Annotated[Principal | None, Depends(get_optional_page_principal)],
):
    # Render the sign-in form.
    await challenge_pages.abandon_active_run(db, principal)
    return templates.TemplateResponse(request, "login.html", {"title": "Anmelden"})


@app.get(
    "/session-expired",
    include_in_schema=False,
    name="session_expired_page",
)
async def session_expired_page(request: Request):
    response = templates.TemplateResponse(
        request,
        "session_expired.html",
        {"title": "Sitzung abgelaufen"},
    )
    response.delete_cookie(
        "access_token",
        path="/",
        secure=request.url.scheme == "https",
        httponly=True,
        samesite="lax",
    )
    return response


@app.get("/logout", include_in_schema=False, name="logout")
async def logout(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    principal: Annotated[Principal | None, Depends(get_optional_page_principal)],
):
    # Clear the browser's HTTP-only access cookie and return to sign-in.
    await challenge_pages.abandon_active_run(db, principal)
    response = RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)
    response.delete_cookie(
        "access_token",
        path="/",
        secure=request.url.scheme == "https",
        httponly=True,
        samesite="lax",
    )
    return response


## account management
@app.get("/account", include_in_schema=False, name="account_page")
async def account_page(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    principal: Annotated[Principal | None, Depends(get_optional_page_principal)],
):
    # Render the administration interface; the client guard checks the role.
    await challenge_pages.abandon_active_run(db, principal)
    return templates.TemplateResponse(
        request, "account.html", {"title": "Kontoverwaltung"}
    )


## chapter select
@app.get("/chapters", include_in_schema=False, name="chapters")
async def chapter_select(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    principal: Annotated[Principal | None, Depends(get_optional_page_principal)],
):
    # List active chapters in their configured learning order.
    await challenge_pages.abandon_active_run(db, principal)
    result = await db.execute(
        select(models.Chapter)
        .where(models.Chapter.active.is_(True))
        .order_by(
            models.Chapter.position,
            models.Chapter.id,
        )
    )

    chapters = result.scalars().all()

    return templates.TemplateResponse(
        request,
        "chapter_select.html",
        {"chapters": chapters, "title": "Kapitel auswählen"},
    )


@app.get("/chapters/{chapter_id}", name="chapter_task")
async def chapter_task(
    chapter_id: int,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    principal: Annotated[Principal | None, Depends(get_optional_page_principal)],
):
    # Open a chapter at its first exercise, or show its empty-state message.
    await challenge_pages.abandon_active_run(db, principal)
    result = await db.execute(
        select(models.Chapter)
        .options(selectinload(models.Chapter.exercises))
        .where(
            models.Chapter.id == chapter_id,
            models.Chapter.active.is_(True),
        )
    )
    chapter = result.scalars().first()
    if chapter is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Chapter not found"
        )

    if not chapter.exercises:
        return templates.TemplateResponse(
            request,
            "exerciseframe.html",
            {
                "chapter": chapter,
                "exercises": [],
                "exercise": None,
                "error_message": "Dieses Kapitel enthält noch keine Übungen.",
                "title": chapter.title,
            },
            status_code=status.HTTP_404_NOT_FOUND,
        )

    first_exercise = chapter.exercises[0]
    return RedirectResponse(
        url=f"/chapters/{chapter.id}/exercises/{first_exercise.id}",
        status_code=status.HTTP_303_SEE_OTHER,
    )


@app.get(
    "/chapters/{chapter_id}/exercises/{exercise_id}",
    name="task_exercise",
)
async def task_exercise(
    chapter_id: int,
    exercise_id: int,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    principal: Annotated[Principal, Depends(get_page_principal)],
):
    # Render one active exercise together with the learner's lock state.
    await _ensure_existing_user_account(db, principal)
    await challenge_pages.abandon_active_run(db, principal)
    result = await db.execute(
        select(models.Chapter)
        .options(selectinload(models.Chapter.exercises))
        .where(
            models.Chapter.id == chapter_id,
            models.Chapter.active.is_(True),
        )
    )
    chapter = result.scalars().first()
    if chapter is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Chapter not found"
        )

    exercise = next(
        (item for item in chapter.exercises if item.id == exercise_id),
        None,
    )
    if exercise is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Exercise not found"
        )

    account_id = principal["account_id"] if principal["role"] == "user" else None
    completed_ids, locked_by = await get_exercise_progress(db, chapter.id, account_id)
    locked_by_id = locked_by.get(exercise.id)
    required_exercise = next(
        (item for item in chapter.exercises if item.id == locked_by_id),
        None,
    )

    exercise_path = _resolve_exercise_file(exercise.html_filename)
    error_message = None
    if exercise_path is None or exercise_path.suffix.casefold() != ".html":
        error_message = (
            f"Die Übungsdatei „{exercise.html_filename}“ wurde nicht gefunden."
        )

    return templates.TemplateResponse(
        request,
        "exerciseframe.html",
        {
            "chapter": chapter,
            "exercises": chapter.exercises,
            "exercise": exercise,
            "error_message": error_message,
            "completed_exercise_ids": completed_ids,
            "locked_by": locked_by,
            "required_exercise": required_exercise,
            "can_complete": principal["role"] == "user",
            "exercise_url": (
                request.url_for(
                    "exercise_content",
                    exercise_id=str(exercise.id),
                    relative_path=exercise.html_filename,
                )
                if error_message is None
                else None
            ),
            "title": exercise.title,
        },
        status_code=(
            status.HTTP_404_NOT_FOUND
            if error_message is not None
            else status.HTTP_200_OK
        ),
    )


@app.get(
    "/exercise-content/{exercise_id}/{relative_path:path}",
    name="exercise_content",
)
async def exercise_content(
    exercise_id: int,
    relative_path: str,
    db: Annotated[AsyncSession, Depends(get_db)],
    principal: Annotated[Principal, Depends(get_current_principal)],
):
    # Authorize and serve the selected lesson asset, enforcing progress locks.
    await _ensure_existing_user_account(db, principal)
    result = await db.execute(
        select(models.Exercise)
        .join(models.Chapter)
        .where(
            models.Exercise.id == exercise_id,
            models.Chapter.active.is_(True),
        )
    )
    exercise = result.scalars().first()
    if exercise is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Exercise not found"
        )
    if principal["role"] == "user":
        if principal["account_id"] is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid account"
            )
        _, locked_by = await get_exercise_progress(
            db, exercise.chapter_id, principal["account_id"]
        )
        if exercise_id in locked_by:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="Exercise is locked"
            )

    requested_file = _resolve_exercise_file(relative_path)
    exercise_file = _resolve_exercise_file(exercise.html_filename)
    if requested_file is None or (
        requested_file.suffix.casefold() == ".html" and requested_file != exercise_file
    ):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Exercise file not found"
        )

    return FileResponse(requested_file)
