"""Seed the chapter and exercise catalog without creating user accounts."""

import asyncio

from sqlalchemy import select, update

from database import AsyncSessionLocal, engine, init_db
from models import Account, Challenge, Chapter, Exercise
from randomized_challenges import is_randomized_challenge

CHAPTERS = (
    {
        "title": "Kryptografie",
        "picture": "Kryptografie.png",
        "position": 0,
        "active": True,
    },
    {
        "title": "Symmetrische Verschlüsselung",
        "picture": "Symmetrische_Verschlüsselung.png",
        "position": 1,
        "active": True,
    },
    {
        "title": "Asymmetrische Verschlüsselung",
        "picture": "Asymmetrische_Verschlüsselung.jpg",
        "position": 2,
        "active": True,
    },
    {
        "title": "Passwörter",
        "picture": "Passwörter.jpg",
        "position": 3,
        "active": True,
    },
)

REMOVED_CHAPTERS = ("Phishing",)

CHALLENGES = (
    {
        "title": "Caesar verschlüsseln",
        "html_filename": "caesar_encrypt.html",
    },
    {
        "title": "Caesar entschlüsseln",
        "html_filename": "caesar_decrypt.html",
    },
    {
        "title": "Vigenère verschlüsseln",
        "html_filename": "vigenere_encrypt.html",
    },
    {
        "title": "Vigenère entschlüsseln",
        "html_filename": "vigenere_decrypt.html",
    },
    {
        "title": "RSA-Schlüssel berechnen",
        "html_filename": "rsa_key_generation.html",
    },
    {
        "title": "RSA verschlüsseln",
        "html_filename": "rsa_encrypt.html",
    },
    {
        "title": "RSA entschlüsseln",
        "html_filename": "rsa_decrypt.html",
    },
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
        "position": 0,
        "chapter_title": "Symmetrische Verschlüsselung",
    },
    {
        "title": "Caesar-Verschlüsselung",
        "html_filename": "caesar.html",
        "solution": ["UEBER DIE ALPEN", "KDQQLEDO", 7],
        "requires_previous": True,
        "position": 1,
        "chapter_title": "Symmetrische Verschlüsselung",
    },
    {
        "title": "Caesar Python",
        "html_filename": "caesar_python.html",
        "solution": ["JODGLDWRU", "AVE CAESAR"],
        "requires_previous": True,
        "position": 2,
        "chapter_title": "Symmetrische Verschlüsselung",
    },
    {
        "title": "Vigenère-Verschlüsselung",
        "html_filename": "vigenere.html",
        "solution": ["EQURWCYDPS", "SUPER", True],
        "requires_previous": True,
        "position": 3,
        "chapter_title": "Symmetrische Verschlüsselung",
    },
    {
        "title": "Vigenère Python",
        "html_filename": "vigenere_python.html",
        "solution": ["FRWMFEUEK", "GIB MIR DETAILS"],
        "requires_previous": True,
        "position": 4,
        "chapter_title": "Symmetrische Verschlüsselung",
    },
    {
        "title": "Moderne Anwendungen symmetrischer Verschlüsselung",
        "html_filename": "symmetric_uses.html",
        "solution": [
            "TLS",
            "Festplattenverschlüsselung",
            "Sender und Empfänger",
            "Schlüsselmanagement",
        ],
        "requires_previous": True,
        "position": 5,
        "chapter_title": "Symmetrische Verschlüsselung",
    },
    {
        "title": "Asymmetrische Verschlüsselung",
        "html_filename": "asymmetric.html",
        "solution": [
            "key-pair",
            "Miras öffentlicher Schlüssel",
            "shared-secret",
        ],
        "requires_previous": True,
        "position": 0,
        "chapter_title": "Asymmetrische Verschlüsselung",
    },
    {
        "title": "RSA",
        "html_filename": "RSA.html",
        "solution": [
            "Zwei Primzahlen",
            "Miras privater Schlüssel",
            "signature",
        ],
        "requires_previous": True,
        "position": 1,
        "chapter_title": "Asymmetrische Verschlüsselung",
    },
    {
        "title": "RSA mit Zahlen",
        "html_filename": "rsa_math.html",
        "solution": [120, 13, 39],
        "requires_previous": True,
        "position": 2,
        "chapter_title": "Asymmetrische Verschlüsselung",
    },
    {
        "title": "RSA mit Python",
        "html_filename": "rsa_python.html",
        "solution": ["13", "7", "5 1596269 7990271"],
        "requires_previous": True,
        "position": 3,
        "chapter_title": "Asymmetrische Verschlüsselung",
    },
    {
        "title": "Moderne Anwendungen asymmetrischer Verschlüsselung",
        "html_filename": "asymmetric_uses.html",
        "solution": [
            "Serverzertifikat prüfen",
            "Privater Schlüssel bleibt beim Gerät",
            "Gemeinsamen Schlüssel vereinbaren",
            "Öffentlicher Schlüssel",
            "Langsamer",
        ],
        "requires_previous": True,
        "position": 5,
        "chapter_title": "Asymmetrische Verschlüsselung",
    },
    {
        "title": "Digitale Schlüssel",
        "html_filename": "digital_keys.html",
        "solution": [
            "Beide Wissensfaktor",
            "Nicht austauschen",
            "Gerät",
            "Verhaltensanalyse",
            "Kombinationen",
            "BioBesitzWissen",
        ],
        "requires_previous": False,
        "position": 0,
        "chapter_title": "Passwörter",
    },
    {
        "title": "Passwörter",
        "html_filename": "passwords.html",
        "solution": ["Salts", "credential-stuffing", "Angriffsprogramme"],
        "requires_previous": True,
        "position": 1,
        "chapter_title": "Passwörter",
    },
    {
        "title": "Passwort Managers",
        "html_filename": "password_managers.html",
        "solution": [],
        "requires_previous": True,
        "position": 4,
        "chapter_title": "Passwörter",
    },
)


async def seed_content() -> None:
    """Synchronize the configured chapter, exercise, and challenge catalog."""
    await init_db()

    async with AsyncSessionLocal() as session, session.begin():
        # Retired chapters can be removed only when no exercise still references them.
        for chapter_title in REMOVED_CHAPTERS:
            result = await session.execute(
                select(Chapter).where(Chapter.title == chapter_title)
            )
            removed_chapter = result.scalar_one_or_none()
            if removed_chapter is None:
                continue

            result = await session.execute(
                select(Exercise.id)
                .where(Exercise.chapter_id == removed_chapter.id)
                .limit(1)
            )
            if result.first():
                raise ValueError(
                    f"Cannot remove chapter {chapter_title!r} while it contains exercises"
                )
            await session.delete(removed_chapter)

        # Upsert chapter metadata so rerunning the seed is safe.
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

        # Match seeded exercises by either stable filename or display title.
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

        # Move seeded exercises temporarily to avoid unique-position collisions.
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

        # Remove unsupported challenges and clear any learner run pointing to them.
        result = await session.execute(select(Challenge))
        existing_challenges = result.scalars().all()
        unsupported_challenges = [
            challenge
            for challenge in existing_challenges
            if not is_randomized_challenge(challenge.html_filename)
        ]
        if unsupported_challenges:
            unsupported_ids = [challenge.id for challenge in unsupported_challenges]
            await session.execute(
                update(Account)
                .where(Account.current_challenge_id.in_(unsupported_ids))
                .values(
                    start_time=None,
                    end_time=None,
                    previous_record_time=None,
                    current_challenge_id=None,
                    current_challenge_complete=False,
                )
            )
            for challenge in unsupported_challenges:
                await session.delete(challenge)

        existing_challenges = [
            challenge
            for challenge in existing_challenges
            if is_randomized_challenge(challenge.html_filename)
        ]
        challenges_by_filename = {
            challenge.html_filename: challenge for challenge in existing_challenges
        }
        challenges_by_title = {
            challenge.title: challenge for challenge in existing_challenges
        }
        next_position = max(
            (challenge.position for challenge in existing_challenges),
            default=-1,
        ) + 1

        for challenge_data in CHALLENGES:
            filename_match = challenges_by_filename.get(
                challenge_data["html_filename"]
            )
            title_match = challenges_by_title.get(challenge_data["title"])
            if filename_match and title_match and filename_match is not title_match:
                raise ValueError(
                    "Challenge title and filename refer to different database rows: "
                    f"{challenge_data['title']}"
                )

            challenge = filename_match or title_match
            if challenge is None:
                challenge = Challenge(
                    title=challenge_data["title"],
                    html_filename=challenge_data["html_filename"],
                    position=next_position,
                )
                next_position += 1
                session.add(challenge)
            else:
                challenge.title = challenge_data["title"]
                challenge.html_filename = challenge_data["html_filename"]

    print(
        f"Seeded {len(CHAPTERS)} chapters, {len(EXERCISES)} exercises, "
        f"and {len(CHALLENGES)} randomized challenges."
    )


async def main() -> None:
    """Seed content and always release the shared database engine."""
    try:
        await seed_content()
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())