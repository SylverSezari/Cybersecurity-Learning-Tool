"""Rank challenge records for learner-facing leaderboards."""

from typing import TypedDict

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

import models


class LeaderboardEntry(TypedDict):
    rank: int
    username: str
    record_time: int
    formatted_time: str
    is_current: bool


def format_time(milliseconds: int | None) -> str:
    """Display integer millisecond durations as a stable clock value."""
    if milliseconds is None:
        return "—"
    total_seconds, fraction = divmod(milliseconds, 1000)
    minutes, seconds = divmod(total_seconds, 60)
    hours, minutes = divmod(minutes, 60)
    if hours:
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}.{fraction:03d}"
    return f"{minutes:02d}:{seconds:02d}.{fraction:03d}"


def _ranked_accounts():
    ordering = (
        models.Account.record_time,
        func.lower(models.Account.username),
        models.Account.id,
    )
    return (
        select(
            models.Account.id.label("account_id"),
            models.Account.username.label("username"),
            models.Account.record_time.label("record_time"),
            func.row_number().over(order_by=ordering).label("rank"),
        )
        .where(models.Account.record_time.is_not(None))
        .cte("ranked_accounts")
    )


def _entry(
    rank: int,
    username: str,
    record_time: int,
    current_account_id: int | None,
    account_id: int,
) -> LeaderboardEntry:
    return {
        "rank": rank,
        "username": username,
        "record_time": record_time,
        "formatted_time": format_time(record_time),
        "is_current": account_id == current_account_id,
    }


async def home_leaderboard(
    db: AsyncSession,
    current_account_id: int | None,
) -> list[LeaderboardEntry]:
    """Show the top five and include the current learner when ranked lower."""
    ranked = _ranked_accounts()
    criteria = [ranked.c.rank <= 5]
    if current_account_id is not None:
        criteria.append(ranked.c.account_id == current_account_id)
    result = await db.execute(
        select(ranked)
        .where(or_(*criteria))
        .order_by(ranked.c.rank)
    )
    return [
        _entry(
            row.rank,
            row.username,
            row.record_time,
            current_account_id,
            row.account_id,
        )
        for row in result.all()
    ]


async def challenge_end_leaderboard(
    db: AsyncSession,
    current_account_id: int | None,
) -> list[LeaderboardEntry]:
    """Show the top ten and, when ranked, the current learner and adjacent ranks."""
    ranked = _ranked_accounts()
    criteria = [ranked.c.rank <= 10]
    if current_account_id is not None:
        current_rank = (
            select(ranked.c.rank)
            .where(ranked.c.account_id == current_account_id)
            .scalar_subquery()
        )
        criteria.append(ranked.c.rank.between(current_rank - 1, current_rank + 1))
    return [
        _entry(
            row.rank,
            row.username,
            row.record_time,
            current_account_id,
            row.account_id,
        )
        for row in (
            await db.execute(
                select(ranked)
                .where(or_(*criteria))
                .order_by(ranked.c.rank)
            )
        ).all()
    ]
