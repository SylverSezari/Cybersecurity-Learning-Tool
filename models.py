from __future__ import annotations

from sqlalchemy import Boolean, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database import Base

# define which tables exist in the database


## the exercises are defined here
class Exercise(Base):
    __tablename__ = "exercises"
    __table_args__ = (UniqueConstraint("chapter_id", "position"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    title: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    html_filename: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    task: Mapped[bool] = mapped_column(Boolean, nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=True)
    chapter_id: Mapped[int] = mapped_column(
        ForeignKey("chapters.id"),
        nullable=True,
        index=True,
    )
    chapter: Mapped[Chapter] = relationship(back_populates="exercises")


## the chapters are defined here
class Chapter(Base):
    __tablename__ = "chapters"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    title: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False)
    exercises: Mapped[list[Exercise]] = relationship(
        back_populates="chapter",
        order_by="Exercise.position",
        lazy="selectin",
    )


## the accountse are defined here
class Account(Base):
    __tablename__= "accounts"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    username: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(200), nullable=False)