"""Render and advance timed challenge pages while keeping run state in the database."""

from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

import models
from account_access import require_user_account
from database import get_db
from leaderboard import challenge_end_leaderboard, format_time
from randomized_challenges import (
    generate_practice_challenge,
    generate_randomized_challenge,
    is_randomized_challenge,
)
from security import Principal, get_current_principal, get_page_principal

router = APIRouter()
templates = Jinja2Templates(directory=str(Path(__file__).resolve().parent / "templates"))
CHALLENGES_DIRECTORY = Path(__file__).resolve().parent / "templates" / "challenges"


async def abandon_active_run(
    db: AsyncSession,
    principal: Principal | None,
) -> None:
    """Clear unfinished progress without changing the learner's best record."""
    if principal is None or principal["role"] != "user":
        return

    account_id = principal["account_id"]
    if account_id is None:
        return
    result = await db.execute(
        select(models.Account).where(models.Account.id == account_id)
    )
    account = result.scalar_one_or_none()
    if account is None or account.start_time is None or account.end_time is not None:
        return

    account.start_time = None
    account.end_time = None
    account.previous_record_time = None
    account.current_challenge_id = None
    account.current_challenge_complete = False
    await db.commit()


async def ordered_challenges(db: AsyncSession) -> list[models.Challenge]:
    """Return the one canonical sequence used by pages and API endpoints."""
    result = await db.execute(
        select(models.Challenge).order_by(
            models.Challenge.position,
            models.Challenge.id,
        )
    )
    return list(result.scalars().all())


def _resolve_challenge_file(relative_path: str) -> Path | None:
    """Resolve an asset only if it exists beneath the challenge content directory."""
    challenge_root = CHALLENGES_DIRECTORY.resolve()
    try:
        file_path = (challenge_root / relative_path).resolve()
        file_path.relative_to(challenge_root)
    except (OSError, RuntimeError, ValueError):
        return None
    return file_path if file_path.is_file() else None


@router.get("/challenge", name="challenge_intro", include_in_schema=False)
async def challenge_intro(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    principal: Annotated[Principal, Depends(get_page_principal)],
):
    """Show run instructions, or resume the active run at its saved challenge."""
    account = None
    if principal["role"] == "user":
        account = await require_user_account(db, principal)
        if account.start_time is not None and account.end_time is None:
            if account.current_challenge_id is not None:
                return RedirectResponse(
                    url=request.url_for(
                        "challenge_play",
                        challenge_id=str(account.current_challenge_id),
                    ),
                    status_code=status.HTTP_303_SEE_OTHER,
                )
            await abandon_active_run(db, principal)

    challenges = await ordered_challenges(db)
    return templates.TemplateResponse(
        request,
        "challenge_intro.html",
        {
            "title": "Herausforderung",
            "challenge_count": len(challenges),
            "record_time": format_time(account.record_time) if account else None,
            "has_record": account is not None and account.record_time is not None,
            "is_admin": principal["role"] == "admin",
        },
    )


@router.post("/challenge/start", name="challenge_start", include_in_schema=False)
async def start_challenge(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    principal: Annotated[Principal, Depends(get_page_principal)],
):
    """Start a learner's timed run or open the first admin practice challenge."""
    account = (
        await require_user_account(db, principal)
        if principal["role"] == "user"
        else None
    )
    challenges = await ordered_challenges(db)
    if not challenges:
        return RedirectResponse(
            url=request.url_for("challenge_intro"),
            status_code=status.HTTP_303_SEE_OTHER,
        )

    if principal["role"] == "admin":
        return RedirectResponse(
            url=request.url_for("challenge_play", challenge_id=str(challenges[0].id)),
            status_code=status.HTTP_303_SEE_OTHER,
        )

    if account is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account required",
        )
    if account.start_time is not None and account.end_time is None:
        if account.current_challenge_id is not None:
            return RedirectResponse(
                url=request.url_for(
                    "challenge_play",
                    challenge_id=str(account.current_challenge_id),
                ),
                status_code=status.HTTP_303_SEE_OTHER,
            )

    account.start_time = datetime.now(UTC)
    account.end_time = None
    account.previous_record_time = account.record_time
    account.current_challenge_id = challenges[0].id
    account.current_challenge_complete = False
    await db.commit()
    return RedirectResponse(
        url=request.url_for("challenge_play", challenge_id=str(challenges[0].id)),
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.post("/challenge/abandon", name="challenge_abandon", include_in_schema=False)
async def abandon_challenge(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    principal: Annotated[Principal, Depends(get_page_principal)],
):
    """Let the learner give up and return to the challenge introduction."""
    if principal["role"] == "user":
        await require_user_account(db, principal)
    await abandon_active_run(db, principal)
    return RedirectResponse(
        url=request.url_for("challenge_intro"),
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.get("/challenge/victory", name="challenge_victory", include_in_schema=False)
async def challenge_victory(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    principal: Annotated[Principal, Depends(get_page_principal)],
):
    """Show a learner's finished time or the leaderboard after admin practice."""
    if principal["role"] == "admin":
        return templates.TemplateResponse(
            request,
            "challenge_victory.html",
            {
                "title": "Geschafft!",
                "current_time": None,
                "previous_record": None,
                "is_record": False,
                "is_admin": True,
                "leaderboard": await challenge_end_leaderboard(db, None),
            },
        )

    account = await require_user_account(db, principal)
    if account.start_time is None or account.end_time is None:
        return RedirectResponse(
            url=request.url_for("challenge_intro"),
            status_code=status.HTTP_303_SEE_OTHER,
        )

    elapsed_ms = int((account.end_time - account.start_time).total_seconds() * 1000)
    previous_record = account.previous_record_time
    is_record = previous_record is None or elapsed_ms < previous_record
    leaderboard = await challenge_end_leaderboard(db, account.id)
    return templates.TemplateResponse(
        request,
        "challenge_victory.html",
        {
            "title": "Geschafft!",
            "current_time": format_time(elapsed_ms),
            "previous_record": (
                format_time(previous_record) if previous_record is not None else None
            ),
            "is_record": is_record,
            "is_admin": False,
            "leaderboard": leaderboard,
        },
    )


@router.get(
    "/challenge/{challenge_id}",
    name="challenge_play",
    include_in_schema=False,
)
async def play_challenge(
    challenge_id: int,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    principal: Annotated[Principal, Depends(get_page_principal)],
):
    """Render only the currently assigned step; refreshes resume this same step."""
    is_admin = principal["role"] == "admin"
    account = None if is_admin else await require_user_account(db, principal)
    if account is not None and (
        account.start_time is None or account.end_time is not None
    ):
        return RedirectResponse(
            url=request.url_for("challenge_victory"),
            status_code=status.HTTP_303_SEE_OTHER,
        )

    challenges = await ordered_challenges(db)
    challenge_ids = [item.id for item in challenges]
    if is_admin:
        if challenge_id not in challenge_ids:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Challenge not found",
            )
        current_id = challenge_id
    else:
        if account is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User account required",
            )
        current_id = account.current_challenge_id
        if current_id not in challenge_ids:
            await abandon_active_run(db, principal)
            return RedirectResponse(
                url=request.url_for("challenge_intro"),
                status_code=status.HTTP_303_SEE_OTHER,
            )
        if challenge_id != current_id:
            return RedirectResponse(
                url=request.url_for("challenge_play", challenge_id=str(current_id)),
                status_code=status.HTTP_303_SEE_OTHER,
            )

    current_index = challenge_ids.index(current_id)
    challenge = challenges[current_index]
    challenge_prompt = None
    solution_types = []
    if is_randomized_challenge(challenge.html_filename):
        if account is None:
            randomized = generate_practice_challenge(challenge.html_filename)
        else:
            randomized = generate_randomized_challenge(
                challenge.html_filename,
                account.id,
                account.start_time,
            )
        challenge_prompt = randomized.prompt
        solution_types = [
            "number" if isinstance(answer, (int, float)) else "text"
            for answer in randomized.expected_answers
        ]

    next_challenge = (
        challenges[current_index + 1]
        if current_index + 1 < len(challenges)
        else None
    )
    challenge_path = _resolve_challenge_file(challenge.html_filename)
    error_message = (
        None
        if is_randomized_challenge(challenge.html_filename)
        else "Für diese Challenge ist kein Zufallsgenerator registriert."
    )
    if challenge_path is None or challenge_path.suffix.casefold() != ".html":
        error_message = (
            f"Die Challenge-Datei „{challenge.html_filename}“ wurde nicht gefunden."
        )

    return templates.TemplateResponse(
        request,
        "challenge_play.html",
        {
            "title": challenge.title,
            "challenge": challenge,
            "challenge_index": current_index + 1,
            "challenge_count": len(challenges),
            "next_challenge": next_challenge,
            "is_complete": is_admin
            or (account is not None and account.current_challenge_complete),
            "is_admin": is_admin,
            "error_message": error_message,
            "challenge_url": (
                request.url_for(
                    "challenge_content",
                    challenge_id=str(challenge.id),
                    relative_path=challenge.html_filename,
                )
                if error_message is None
                else None
            ),
            "solution_types": solution_types,
            "challenge_prompt": challenge_prompt,
        },
    )


@router.post(
    "/challenge/{challenge_id}/next",
    name="challenge_next",
    include_in_schema=False,
)
async def next_challenge(
    challenge_id: int,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    principal: Annotated[Principal, Depends(get_page_principal)],
):
    """Advance only after the current challenge has been marked correct."""
    if principal["role"] == "admin":
        challenges = await ordered_challenges(db)
        challenge_ids = [item.id for item in challenges]
        if challenge_id not in challenge_ids:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Challenge not found",
            )
        current_index = challenge_ids.index(challenge_id)
        if current_index + 1 >= len(challenges):
            return RedirectResponse(
                url=request.url_for("challenge_play", challenge_id=str(challenge_id)),
                status_code=status.HTTP_303_SEE_OTHER,
            )
        next_id = challenges[current_index + 1].id
        return RedirectResponse(
            url=request.url_for("challenge_play", challenge_id=str(next_id)),
            status_code=status.HTTP_303_SEE_OTHER,
        )

    account = await require_user_account(db, principal)
    if (
        account.start_time is None
        or account.end_time is not None
        or account.current_challenge_id != challenge_id
        or not account.current_challenge_complete
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Challenge is not ready to continue",
        )

    challenges = await ordered_challenges(db)
    challenge_ids = [item.id for item in challenges]
    if challenge_id not in challenge_ids:
        await abandon_active_run(db, principal)
        return RedirectResponse(
            url=request.url_for("challenge_intro"),
            status_code=status.HTTP_303_SEE_OTHER,
        )
    current_index = challenge_ids.index(challenge_id)
    if current_index + 1 >= len(challenges):
        return RedirectResponse(
            url=request.url_for("challenge_play", challenge_id=str(challenge_id)),
            status_code=status.HTTP_303_SEE_OTHER,
        )

    next_id = challenges[current_index + 1].id
    account.current_challenge_id = next_id
    account.current_challenge_complete = False
    await db.commit()
    return RedirectResponse(
        url=request.url_for("challenge_play", challenge_id=str(next_id)),
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.post(
    "/challenge/{challenge_id}/finish",
    name="challenge_finish",
    include_in_schema=False,
)
async def finish_challenge(
    challenge_id: int,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    principal: Annotated[Principal, Depends(get_page_principal)],
):
    """Stop the clock on the final step and update the best time if improved."""
    if principal["role"] == "admin":
        challenges = await ordered_challenges(db)
        if not challenges or challenges[-1].id != challenge_id:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="The last challenge has not been reached",
            )
        return RedirectResponse(
            url=request.url_for("challenge_victory"),
            status_code=status.HTTP_303_SEE_OTHER,
        )

    account = await require_user_account(db, principal)
    if (
        account.start_time is None
        or account.end_time is not None
        or account.current_challenge_id != challenge_id
        or not account.current_challenge_complete
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Challenge is not ready to finish",
        )

    challenges = await ordered_challenges(db)
    if not challenges or challenges[-1].id != challenge_id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="The last challenge has not been completed",
        )

    end_time = datetime.now(UTC)
    elapsed_ms = int((end_time - account.start_time).total_seconds() * 1000)
    if elapsed_ms < 0:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Challenge run clock moved backwards",
        )

    account.end_time = end_time
    # Preserve the old value for the victory screen before possibly replacing it.
    account.previous_record_time = account.record_time
    if account.record_time is None or elapsed_ms < account.record_time:
        account.record_time = elapsed_ms
    await db.commit()
    return RedirectResponse(
        url=request.url_for("challenge_victory"),
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.get(
    "/challenge-content/{challenge_id}/{relative_path:path}",
    name="challenge_content",
    include_in_schema=False,
)
async def challenge_content(
    challenge_id: int,
    relative_path: str,
    db: Annotated[AsyncSession, Depends(get_db)],
    principal: Annotated[Principal, Depends(get_current_principal)],
):
    """Serve assets only for the learner's current challenge and its HTML entrypoint."""
    if principal["role"] == "user":
        account = await require_user_account(db, principal)
        if (
            account.start_time is None
            or account.end_time is not None
            or account.current_challenge_id != challenge_id
        ):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Challenge is not current",
            )
    result = await db.execute(
        select(models.Challenge).where(models.Challenge.id == challenge_id)
    )
    challenge = result.scalar_one_or_none()
    if challenge is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Challenge not found",
        )

    requested_file = _resolve_challenge_file(relative_path)
    challenge_file = _resolve_challenge_file(challenge.html_filename)
    if requested_file is None or (
        requested_file.suffix.casefold() == ".html"
        and requested_file != challenge_file
    ):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Challenge file not found",
        )
    return FileResponse(requested_file)
