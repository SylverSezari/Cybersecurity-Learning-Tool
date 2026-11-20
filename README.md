# Cybersecurity-Learning-Tool
Bachelor Thesis project to create a learning tool for schools in the topics of cybersecurity

## Seed the content database

With dependencies installed and the required settings configured in `.env`, run:

```powershell
uv run python seed_database.py
```

The script creates or updates the chapter and exercise catalog, including order, prerequisites, pictures, and answer keys. It also seeds four randomized Caesar and Vigenère timed challenges; their 8-letter puzzles and keys are generated for each learner's run, and challenge answers are not stored. Database initialization removes the legacy `challenges.solution` column. The seed script is safe to run again and does not create or delete accounts. Existing exercises not listed in the seed data are left untouched; challenge entries without a registered randomizer are deleted, and any active run on one of those entries is cleared. Chapters named in `REMOVED_CHAPTERS` are deleted only when they contain no exercises; the script stops with an error otherwise.

## Import student accounts

In the account administration page, upload a semicolon-separated UTF-8 CSV with `Name`, `Vorname`, and `Klasse` columns (the other columns in the provided export are ignored). Each student gets a username made from the shortest available prefix of their first name and their full surname, plus a random password of at least 20 characters. Passwords contain at least four hyphen-separated words, including at least one German and one English word; each word starts with an uppercase letter. The English word list is derived from a swear-filtered frequency list and is licensed for educational, personal, or research use; see [ENGLISH_WORDS_LICENSE.txt](./ENGLISH_WORDS_LICENSE.txt). The import downloads a text file containing each username, password, and class. Keep this file private and distribute each student's credentials securely.
