# Database tables and relationships for lessons, accounts, and completion state.
from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import TypeDecorator

from account_helpers import random_klasse
from database import Base


class UTCDateTime(TypeDecorator[datetime]):
    """Store challenge timestamps in UTC and restore timezone data on reads."""

    impl = DateTime(timezone=True)
    cache_ok = True

    def process_bind_param(self, value: datetime | None, dialect) -> datetime | None:
        if value is None:
            return None
        # Reject naive values so duration calculations always compare real instants.
        if value.utcoffset() is None:
            raise ValueError("Challenge timestamps must be timezone-aware")
        return value.astimezone(UTC)

    def process_result_value(self, value: datetime | None, dialect) -> datetime | None:
        if value is None:
            return None
        # SQLite drops timezone metadata; values read back without it were stored UTC.
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value.astimezone(UTC)


class Exercise(Base):
    # A lesson file, optionally assigned a unique position within a chapter.

    __tablename__ = "exercises"
    __table_args__ = (UniqueConstraint("chapter_id", "position"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    title: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    html_filename: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    solution: Mapped[list[str | int | float | bool]] = mapped_column(
        JSON, nullable=True, default=list
    )
    requires_previous: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    position: Mapped[int] = mapped_column(Integer, nullable=True)
    chapter_id: Mapped[int] = mapped_column(
        ForeignKey("chapters.id"),
        nullable=True,
        index=True,
    )
    chapter: Mapped[Chapter] = relationship(back_populates="exercises")


class Chapter(Base):
    # An ordered, optionally published collection of exercises.

    __tablename__ = "chapters"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    title: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    picture: Mapped[str]= mapped_column(String, nullable=True)
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=-1)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    exercises: Mapped[list[Exercise]] = relationship(
        back_populates="chapter",
        order_by="Exercise.position",
        lazy="selectin",
    )


class Account(Base):
    # A learner account; only a password hash is persisted.

    __tablename__ = "accounts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    username: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(200), nullable=False)
    klasse: Mapped[str] = mapped_column(
        String(50), nullable=False, default=random_klasse
    )
    # Best and active-run times are milliseconds and UTC timestamps, respectively.
    record_time: Mapped[int | None] = mapped_column(Integer, nullable=True)
    start_time: Mapped[datetime | None] = mapped_column(
        UTCDateTime(), nullable=True
    )
    end_time: Mapped[datetime | None] = mapped_column(
        UTCDateTime(), nullable=True
    )
    # Snapshot the previous best so the victory page can compare this finished run.
    previous_record_time: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # This pointer lets a learner resume the same step after refreshing the page.
    current_challenge_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    current_challenge_complete: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )


class ExerciseCompletion(Base):
    # A composite-key record that marks one exercise complete for one account.

    __tablename__ = "exercise_completions"

    # saves id of account and exercise, if either gets deleted, deletes all records with it in it
    account_id: Mapped[int] = mapped_column(
        ForeignKey("accounts.id", ondelete="CASCADE"), primary_key=True
    )
    exercise_id: Mapped[int] = mapped_column(
        ForeignKey("exercises.id", ondelete="CASCADE"), primary_key=True
    )


class Challenge(Base):
    """One randomized HTML-based challenge in the global sequence."""

    __tablename__ = "challenges"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    title: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    html_filename: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    # Positions define the order learners must follow.
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=-1)