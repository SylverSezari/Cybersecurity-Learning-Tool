# Legacy sample-data loader retained for local development and migration testing.

import asyncio

from sqlalchemy import select

from database import AsyncSessionLocal, engine, init_db
from models import Chapter, Exercise

TEST_DATA = [
    {
        "title": "Cybersecurity Fundamentals",
        "exercises": [
            ("What Is Cybersecurity?", "cybersecurity_fundamentals_01.html"),
            ("The CIA Triad", "cybersecurity_fundamentals_02.html"),
            ("Identifying Common Threats", "cybersecurity_fundamentals_03.html"),
            ("Fundamentals Review", "cybersecurity_fundamentals_04.html"),
        ],
    },
    {
        "title": "Network Security",
        "exercises": [
            ("Network Security Basics", "network_security_01.html"),
            ("Firewalls and Filtering", "network_security_02.html"),
            ("Secure Network Protocols", "network_security_03.html"),
            ("Network Security Review", "network_security_04.html"),
        ],
    },
    {
        "title": "Authentication and Access Control",
        "exercises": [
            ("Authentication Factors", "access_control_01.html"),
            ("Passwords and Passphrases", "access_control_02.html"),
            ("Authorization Principles", "access_control_03.html"),
            ("Access Control Review", "access_control_04.html"),
        ],
    },
]

CRYPTOGRAPHY_LESSONS = [
    ("Einführung", "intro.html", []),
    ("Symmetrische Verschlüsselung", "exercise2.html", ["same-key", "AES", True]),
    ("Caesar-Verschlüsselung", "caesar.html", ["HALLO", "YWJKKJS", 3]),
    ("Vigenère-Verschlüsselung", "vigenere.html", ["TOYOA", "HALLO", True]),
]


async def populate_cryptography_lessons():
    # Create or refresh the cryptography chapter and its lesson records.
    await init_db()

    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(Chapter).where(Chapter.title == "Kryptografie")
        )
        chapter = result.scalar_one_or_none()
        if chapter is None:
            chapter = Chapter(title="Kryptografie", position=0, active=True)
            session.add(chapter)
            await session.flush()

        for position, (title, html_filename, solution) in enumerate(CRYPTOGRAPHY_LESSONS):
            result = await session.execute(
                select(Exercise).where(Exercise.html_filename == html_filename)
            )
            exercise = result.scalar_one_or_none()
            if exercise is None:
                exercise = Exercise(
                    title=title,
                    html_filename=html_filename,
                    solution=solution,
                    position=position,
                    chapter=chapter,
                )
                session.add(exercise)
                continue

            exercise.title = title
            exercise.chapter = chapter
            exercise.position = position
            exercise.solution = solution

        await session.commit()


async def populate_db():
    # Populate the database with sample chapters and cryptography exercises.
    await init_db()

    async with AsyncSessionLocal() as session:
        for chapter_data in TEST_DATA:
            chapter_result = await session.execute(
                select(Chapter).where(Chapter.title == chapter_data["title"])
            )
            chapter = chapter_result.scalar_one_or_none()

            if chapter is None:
                chapter = Chapter(title=chapter_data["title"])
                session.add(chapter)
                await session.flush()

            for position, (title, html_filename) in enumerate(
                chapter_data["exercises"], start=1
            ):
                exercise_result = await session.execute(
                    select(Exercise).where(Exercise.title == title)
                )
                exercise = exercise_result.scalar_one_or_none()

                if exercise is None:
                    session.add(
                        Exercise(
                            title=title,
                            html_filename=html_filename,
                            position=position,
                            chapter=chapter,
                        )
                    )

        await session.commit()

    await populate_cryptography_lessons()

    print("Test chapters and cryptography lessons are ready.")


if __name__ == "__main__":
    try:
        asyncio.run(populate_db())
    finally:
        asyncio.run(engine.dispose())
