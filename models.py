# Database tables and relationships for lessons, accounts, and completion state.

from __future__ import annotations

from sqlalchemy import Boolean, ForeignKey, Integer, JSON, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database import Base

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
    requires_previous: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
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
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=-1)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    exercises: Mapped[list[Exercise]] = relationship(
        back_populates="chapter",
        order_by="Exercise.position",
        lazy="selectin",
    )


class Account(Base):
    # A learner account; only a password hash is persisted.

    __tablename__= "accounts"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    username: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(200), nullable=False)


class ExerciseCompletion(Base):
    # A composite-key record that marks one exercise complete for one account.

    __tablename__ = "exercise_completions"

    account_id: Mapped[int] = mapped_column(
        ForeignKey("accounts.id", ondelete="CASCADE"), primary_key=True
    )
    exercise_id: Mapped[int] = mapped_column(
        ForeignKey("exercises.id", ondelete="CASCADE"), primary_key=True
    )