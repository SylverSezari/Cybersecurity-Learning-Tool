"""Seed the chapter and exercise catalog without creating user accounts."""

import asyncio

from sqlalchemy import select

from database import AsyncSessionLocal, engine, init_db
from models import Chapter, Exercise

CHAPTERS = (
    {
        "title": "Kryptografie",
        "picture": "Kryptografie.png",
        "position": 0,
        "active": True,
    },
    {"title": "Passwörter", "picture": None, "position": 1, "active": True},
    {"title": "Phishing", "picture": None, "position": 2, "active": True},
)

EXERCISES = (
    {
        "title": "Einführung",
        "html_filename": "intro.html",
        "solution": [],
        "requires_previous": False,
        "position": 0,
        "chapter_title": "Kryptografie",
    },
    {
        "title": "Symmetrische Verschlüsselung",
        "html_filename": "symmetric.html",
        "solution": ["same-key", "AES", True],
        "requires_previous": False,
        "position": 1,
        "chapter_title": "Kryptografie",
    },
    {
        "title": "Caesar-Verschlüsselung",
        "html_filename": "caesar.html",
        "solution": ["UEBER DIE ALPEN", "KDQQLEDO", 7],
        "requires_previous": True,
        "position": 2,
        "chapter_title": "Kryptografie",
    },
    {
        "title": "Caesar Python",
        "html_filename": "caesar_python.html",
        "solution": ["KDOOR", "AVE CAESAR"],
        "requires_previous": True,
        "position": 3,
        "chapter_title": "Kryptografie",
    },
    {
        "title": "Vigenère-Verschlüsselung",
        "html_filename": "vigenere.html",
        "solution": ["EQURWCYDPS", "SUPER", True],
        "requires_previous": True,
        "position": 4,
        "chapter_title": "Kryptografie",
    },
    {
        "title": "Vigenère Python",
        "html_filename": "vigenere_python.html",
        "solution": ["EQURWCYDPS"],
        "requires_previous": True,
        "position": 5,
        "chapter_title": "Kryptografie",
    },
    {
        "title": "Asymmetrische Verschlüsselung",
        "html_filename": "asymmetric.html",
        "solution": ["key-pair", "Miras öffentlicher Schlüssel", "shared-secret"],
        "requires_previous": True,
        "position": 6,
        "chapter_title": "Kryptografie",
    },
    {
        "title": "RSA",
        "html_filename": "RSA.html",
        "solution": [
            "Miras öffentlicher Schlüssel",
            "Miras privater Schlüssel",
            "signature",
        ],
        "requires_previous": True,
        "position": 7,
        "chapter_title": "Kryptografie",
    },
    {
        "title": "RSA mit Zahlen",
        "html_filename": "rsa_math.html",
        "solution": [15, 13, 7],
        "requires_previous": True,
        "position": 8,
        "chapter_title": "Kryptografie",
    },
    {
        "title": "RSA mit Python",
        "html_filename": "rsa_python.html",
        "solution": ["13", "7"],
        "requires_previous": True,
        "position": 9,
        "chapter_title": "Kryptografie",
    },
)


async def seed_content() -> None:
    await init_db()

    async with AsyncSessionLocal() as session, session.begin():
        chapters_by_title = {}
        for chapter_data in CHAPTERS:
            result = await session.execute(
                select(Chapter).where(Chapter.title == chapter_data["title"])
            )
            chapter = result.scalar_one_or_none()
            if chapter is None:
                chapter = Chapter(title=chapter_data["title"])
                session.add(chapter)

            chapter.picture = chapter_data["picture"]
            chapter.position = chapter_data["position"]
            chapter.active = chapter_data["active"]
            chapters_by_title[chapter.title] = chapter

        await session.flush()

        result = await session.execute(select(Exercise))
        existing_exercises = result.scalars().all()
        by_filename = {
            exercise.html_filename: exercise for exercise in existing_exercises
        }
        by_title = {exercise.title: exercise for exercise in existing_exercises}

        seeded_exercises = []
        for exercise_data in EXERCISES:
            filename_match = by_filename.get(exercise_data["html_filename"])
            title_match = by_title.get(exercise_data["title"])
            if filename_match and title_match and filename_match is not title_match:
                raise ValueError(
                    "Exercise title and filename refer to different database rows: "
                    f"{exercise_data['title']}"
                )
            exercise = filename_match or title_match
            seeded_exercises.append((exercise_data, exercise))

        seeded_ids = {
            exercise.id for _, exercise in seeded_exercises if exercise is not None
        }
        for exercise_data, _ in seeded_exercises:
            chapter_id = chapters_by_title[exercise_data["chapter_title"]].id
            collision = next(
                (
                    exercise
                    for exercise in existing_exercises
                    if exercise.id not in seeded_ids
                    and exercise.chapter_id == chapter_id
                    and exercise.position == exercise_data["position"]
                ),
                None,
            )
            if collision:
                raise ValueError(
                    "An unseeded exercise already occupies the requested position: "
                    f"chapter={exercise_data['chapter_title']}, "
                    f"position={exercise_data['position']}"
                )

        existing_seeded = [
            exercise for _, exercise in seeded_exercises if exercise is not None
        ]
        positions_by_chapter = {}
        for exercise in existing_exercises:
            positions_by_chapter.setdefault(exercise.chapter_id, []).append(
                exercise.position
            )
        for chapter_id in {exercise.chapter_id for exercise in existing_seeded}:
            group = [
                exercise
                for exercise in existing_seeded
                if exercise.chapter_id == chapter_id
            ]
            occupied = [
                position
                for position in positions_by_chapter.get(chapter_id, [])
                if position is not None
            ]
            temporary_position = min(occupied, default=0) - len(group) - 1
            for offset, exercise in enumerate(group):
                exercise.position = temporary_position - offset
        await session.flush()

        for exercise_data, exercise in seeded_exercises:
            if exercise is None:
                exercise = Exercise(title=exercise_data["title"])
                session.add(exercise)
            exercise.title = exercise_data["title"]
            exercise.html_filename = exercise_data["html_filename"]
            exercise.solution = exercise_data["solution"]
            exercise.requires_previous = exercise_data["requires_previous"]
            exercise.position = exercise_data["position"]
            exercise.chapter = chapters_by_title[exercise_data["chapter_title"]]

    print(f"Seeded {len(CHAPTERS)} chapters and {len(EXERCISES)} exercises.")


async def main() -> None:
    try:
        await seed_content()
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())