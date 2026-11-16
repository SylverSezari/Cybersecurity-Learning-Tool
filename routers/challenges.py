from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

import models
from account_access import require_user_account
from answer_validation import answers_match
from challenge_pages import abandon_active_run, ordered_challenges
from database import get_db
from randomized_challenges import (
    generate_practice_challenge,
    generate_randomized_challenge,
    is_randomized_challenge,
)
from schemas import (
    ChallengeCheckRequest,
    ChallengeCheckResponse,
    ChallengeCreate,
    ChallengeOrder,
    ChallengeResponse,
    ChallengeUpdate,
)
from security import Principal, get_current_principal, require_admin

router = APIRouter()


@router.post("/run/abandon", status_code=status.HTTP_204_NO_CONTENT)
async def abandon_challenge_run(
    db: Annotated[AsyncSession, Depends(get_db)],
    principal: Annotated[Principal, Depends(get_current_principal)],
):
    """Abandon an active run when the learner navigates away from the player."""
    if principal["role"] == "user":
        await require_user_account(db, principal)
    await abandon_active_run(db, principal)


@router.get("", response_model=list[ChallengeResponse])
async def get_challenges(
    db: Annotated[AsyncSession, Depends(get_db)],
    principal: Annotated[Principal, Depends(get_current_principal)],
):
    """List randomized challenge definitions for admins only."""
    require_admin(principal)
    return await ordered_challenges(db)


@router.get("/{challenge_id}", response_model=ChallengeResponse)
async def get_challenge(
    challenge_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    principal: Annotated[Principal, Depends(get_current_principal)],
):
    """Return one editable challenge definition to an administrator."""
    require_admin(principal)
    result = await db.execute(
        select(models.Challenge).where(models.Challenge.id == challenge_id)
    )
    challenge = result.scalar_one_or_none()
    if challenge is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Challenge not found",
        )
    return challenge


@router.post("", response_model=ChallengeResponse, status_code=status.HTTP_201_CREATED)
async def create_challenge(
    challenge_data: ChallengeCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    principal: Annotated[Principal, Depends(get_current_principal)],
):
    """Create a registered randomized challenge after the current final item."""
    require_admin(principal)
    if not is_randomized_challenge(challenge_data.html_filename):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Challenge file has no registered randomizer",
        )

    result = await db.execute(
        select(models.Challenge).where(
            func.lower(models.Challenge.title) == challenge_data.title.lower()
        )
    )
    if result.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Challenge with this title already exists",
        )

    result = await db.execute(
        select(models.Challenge).where(
            func.lower(models.Challenge.html_filename)
            == challenge_data.html_filename.lower()
        )
    )
    if result.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Challenge with this filename already exists",
        )

    highest_position = await db.scalar(
        select(func.max(models.Challenge.position))
    )
    challenge = models.Challenge(
        title=challenge_data.title,
        html_filename=challenge_data.html_filename,
        position=(highest_position if highest_position is not None else -1) + 1,
    )
    db.add(challenge)
    await db.commit()
    await db.refresh(challenge)
    return challenge


@router.put("/order", response_model=list[ChallengeResponse])
async def reorder_challenges(
    order: ChallengeOrder,
    db: Annotated[AsyncSession, Depends(get_db)],
    principal: Annotated[Principal, Depends(get_current_principal)],
):
    """Save a complete ordering snapshot so no challenge is accidentally omitted."""
    require_admin(principal)
    challenges = await ordered_challenges(db)
    challenge_by_id = {challenge.id: challenge for challenge in challenges}
    if (
        len(order.challenge_ids) != len(set(order.challenge_ids))
        or set(order.challenge_ids) != set(challenge_by_id)
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Include each challenge exactly once",
        )

    for position, challenge_id in enumerate(order.challenge_ids):
        challenge_by_id[challenge_id].position = position
    await db.commit()
    return [challenge_by_id[challenge_id] for challenge_id in order.challenge_ids]


@router.put("/update/{challenge_id}", response_model=ChallengeResponse)
async def update_challenge(
    challenge_id: int,
    update_data: ChallengeUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    principal: Annotated[Principal, Depends(get_current_principal)],
):
    """Update a randomized challenge's title or registered puzzle type."""
    require_admin(principal)
    result = await db.execute(
        select(models.Challenge).where(models.Challenge.id == challenge_id)
    )
    challenge = result.scalar_one_or_none()
    if challenge is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Challenge not found",
        )

    data = update_data.model_dump(exclude_unset=True)
    filename = data.get("html_filename", challenge.html_filename)
    if not is_randomized_challenge(filename):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Challenge file has no registered randomizer",
        )
    if data.get("title") is not None:
        result = await db.execute(
            select(models.Challenge).where(
                func.lower(models.Challenge.title) == data["title"].lower(),
                models.Challenge.id != challenge_id,
            )
        )
        if result.scalar_one_or_none() is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Challenge with this title already exists",
            )

    if data.get("html_filename") is not None:
        result = await db.execute(
            select(models.Challenge).where(
                func.lower(models.Challenge.html_filename)
                == data["html_filename"].lower(),
                models.Challenge.id != challenge_id,
            )
        )
        if result.scalar_one_or_none() is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Challenge with this filename already exists",
            )

    for field in ("title", "html_filename"):
        if data.get(field) is not None:
            setattr(challenge, field, data[field])
    await db.commit()
    await db.refresh(challenge)
    return challenge


@router.delete("/delete/{challenge_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_challenge(
    challenge_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    principal: Annotated[Principal, Depends(get_current_principal)],
):
    """Delete a challenge and abandon runs that point at the removed item."""
    require_admin(principal)
    result = await db.execute(
        select(models.Challenge).where(models.Challenge.id == challenge_id)
    )
    challenge = result.scalar_one_or_none()
    if challenge is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Challenge not found",
        )

    await db.execute(
        update(models.Account)
        .where(models.Account.current_challenge_id == challenge_id)
        .values(
            start_time=None,
            end_time=None,
            previous_record_time=None,
            current_challenge_id=None,
            current_challenge_complete=False,
        )
    )
    await db.delete(challenge)
    await db.commit()


@router.post(
    "/{challenge_id}/check",
    response_model=ChallengeCheckResponse,
)
async def check_challenge_answer(
    challenge_id: int,
    completion: ChallengeCheckRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    principal: Annotated[Principal, Depends(get_current_principal)],
):
    """Check answers against the current item; progression is a separate action."""
    is_admin = principal["role"] == "admin"
    if is_admin:
        account = None
    else:
        account = await require_user_account(db, principal)
        if account.start_time is None or account.end_time is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="No active challenge run",
            )
        if account.current_challenge_id != challenge_id:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Challenge is not current",
            )

    challenges = await ordered_challenges(db)
    current_index = next(
        (index for index, item in enumerate(challenges) if item.id == challenge_id),
        None,
    )
    if current_index is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Challenge not found",
        )
    if account is not None and account.current_challenge_complete:
        return ChallengeCheckResponse(
            completed=True,
            is_last=current_index == len(challenges) - 1,
        )

    challenge = challenges[current_index]
    if not is_randomized_challenge(challenge.html_filename):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Challenge file has no registered randomizer",
        )
    if account is None:
        randomized = generate_practice_challenge(challenge.html_filename)
    else:
        randomized = generate_randomized_challenge(
            challenge.html_filename,
            account.id,
            account.start_time,
        )

    if not answers_match(randomized.expected_answers, completion.answers):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Challenge answers are incorrect",
        )

    if account is not None:
        account.current_challenge_complete = True
        await db.commit()
    return ChallengeCheckResponse(
        completed=True,
        is_last=current_index == len(challenges) - 1,
    )
