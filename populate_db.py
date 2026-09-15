import asyncio

from sqlalchemy import select

from database import AsyncSessionLocal, engine, init_db
from models import Chapter, Exercise


TEST_DATA = [
	{
		"title": "Cybersecurity Fundamentals",
		"exercises": [
			("What Is Cybersecurity?", "cybersecurity_fundamentals_01.html", True),
			("The CIA Triad", "cybersecurity_fundamentals_02.html", True),
			("Identifying Common Threats", "cybersecurity_fundamentals_03.html", True),
			("Fundamentals Review", "cybersecurity_fundamentals_04.html", False),
		],
	},
	{
		"title": "Network Security",
		"exercises": [
			("Network Security Basics", "network_security_01.html", True),
			("Firewalls and Filtering", "network_security_02.html", True),
			("Secure Network Protocols", "network_security_03.html", True),
			("Network Security Review", "network_security_04.html", False),
		],
	},
	{
		"title": "Authentication and Access Control",
		"exercises": [
			("Authentication Factors", "access_control_01.html", True),
			("Passwords and Passphrases", "access_control_02.html", True),
			("Authorization Principles", "access_control_03.html", True),
			("Access Control Review", "access_control_04.html", False),
		],
	},
]


async def populate_db():
	await init_db()

	async with AsyncSessionLocal() as session:
		for chapter_data in TEST_DATA:
			chapter_result = await session.execute(
				select(Chapter).where(
					Chapter.title == chapter_data["title"]
				)
			)
			chapter = chapter_result.scalar_one_or_none()

			if chapter is None:
				chapter = Chapter(title=chapter_data["title"])
				session.add(chapter)
				await session.flush()

			for position, (title, html_filename, task) in enumerate(
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
							task=task,
							position=position,
							chapter=chapter,
						)
					)

		await session.commit()

	print("Test chapters and exercises are ready.")


if __name__ == "__main__":
	try:
		asyncio.run(populate_db())
	finally:
		asyncio.run(engine.dispose())
