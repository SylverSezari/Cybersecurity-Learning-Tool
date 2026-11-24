# Cybersecurity Learning Tool

A web-based learning tool for cybersecurity topics, developed as a bachelor's
thesis project. FastAPI and Jinja2  usage were learned and inspired by this guide from Corey Schafer:
[Youtube-Playlist](https://www.youtube.com/playlist?list=PL-osiE80TeTsak-c-QsVeg0YYG_0TeyXI)

## How to use it

These instructions use the terminal and assume Git is installed.

Install [uv](https://docs.astral.sh/uv/):

```powershell
winget install --id=astral-sh.uv -e
```

Open a new terminal after installation, then clone the project and install its
dependencies:

### Clone the project and install dependencies

```powershell
git clone https://github.com/SylverSezari/Cybersecurity-Learning-Tool.git
Set-Location Cybersecurity-Learning-Tool
uv sync
```

### Configure `.env`

Create your local configuration by copying the example:

```powershell
Copy-Item .env.example .env
```

Generate a strong secret key in the terminal:

```powershell
uv run python -c "import secrets; print(secrets.token_hex(32))"
```

Copy the printed value into the `SECRET_KEY` setting in `.env`. This generates
32 random bytes (shown as 64 hexadecimal characters). Keep `.env` private and
do not commit it to source control.

Configure the remaining values in `.env` as needed:

| Setting | Default/example | Description |
| --- | --- | --- |
| `SECRET_KEY` | Generate a value in the terminal (above) | Secret used to sign authentication tokens; required. |
| `DATABASE_URL` | `sqlite+aiosqlite:///./LearningTool.db` | SQLAlchemy database connection URL. The SQLite database is created relative to the project directory when run from there. |
| `ADMIN` | `name-of-admin-account` | Username for the administrator account. |
| `ADMIN_PASSWORD` | `replace-with-a-secure-password` | Password for the administrator account. |
| `GERMAN_WORDS_FILE` | `words_german.txt` | German vocabulary used to generate account passwords. |
| `ENGLISH_WORDS_FILE` | `words_english.txt` | English vocabulary used to generate account passwords. |
| `GERMAN_8_LETTER_WORDS_FILE` | `words_8letters_german.txt` | Eight-letter words used in randomized cipher challenges. |
| `GERMAN_4_LETTER_WORDS_FILE` | `words_4letters_german.txt` | Four-letter words used as randomized Vigenère keys. |

Relative word-list paths are resolved from the project root. Absolute paths are
also supported. The application requires `SECRET_KEY`, `DATABASE_URL`, `ADMIN`,
and `ADMIN_PASSWORD`; the other settings have defaults.

### Add the word lists

Place the files at the paths configured above, or update those settings to point
to your files:

- The German and English password lists should contain one word per line.
- The four-letter and eight-letter challenge lists must contain one ASCII
  alphabetic word of the corresponding length per line.

### Seed the database with chapters, exercises, and challenges

From the project directory, initialize the database and seed the learning
content:

```powershell
uv run python seed_database.py
```

You can run this command again to update the seeded content.

### Run the program

Start the development server from the project directory:

```powershell
uv run fastapi dev main.py
```

Open the local address printed by FastAPI in your browser. Use the `ADMIN` and
`ADMIN_PASSWORD` values from `.env` to sign in as the administrator.




## How is the project structured

### Schemas.py and models.py

- `models.py` defines the application's database entities and their relationships.
- `schemas.py` defines the validated request and response structures used by the
  HTTP API.

### Routers

- `routers/` contains the FastAPI route modules. Each module groups endpoints
  by responsibility, including accounts, chapters, exercises, challenges, and
  learner progress.

### Templates

- `templates/` contains Jinja2 pages for the web interface. Its `challenges/`
  and `exercises/` directories provide the content templates used for timed
  challenges and learning exercises.

### Static

- `static/` contains assets delivered directly to the browser:
  - `css/` provides the layout, theme, and exercise styles.
  - `js/` implements client-side interaction and API calls.
  - `pictures/` contains the application logo and chapter imagery.


## How to extend the project

The seeded configuration is the recommended way to add permanent chapters,
exercises, and challenges. It can be reapplied safely and keeps the initial
database in sync. Chapters and exercises can also be changed in the
administrator interface after the application is running.

### Add a chapter

1. Add or choose an image in `static/pictures/chapters/`.
2. Add an entry to `CHAPTERS` in `seed_database.py`:

```python
{
    "title": "Mein neues Kapitel",
    "picture": "Mein_Neues_Kapitel.png",
    "position": 4,
    "active": True,
},
```

- `title` is the name shown in the application.
- `picture` is the filename of the chapter image.
- `position` controls the chapter order, starting at `0`.
- `active` controls whether learners can see the chapter.

After saving the file, seed the database:

```powershell
uv run python seed_database.py
```

To change chapters through the browser instead, sign in as the administrator,
open the account/administration page, and use the chapter controls. Seeded
entries are still reapplied by `seed_database.py`, so permanent changes should
be made in the seed configuration as well.

### Add an exercise

1. Create a standalone HTML file in `templates/exercises/`, for example
   `templates/exercises/my_exercise.html`.
2. Use the existing lesson templates as a starting point. Add
   `theme.css`, `exercises.css`, and `exercise-theme.js` to keep the lesson
   consistent with the rest of the application.
3. Add the exercise to `EXERCISES` in `seed_database.py`:

```python
{
    "title": "Meine neue Übung",
    "html_filename": "my_exercise.html",
    "solution": [],
    "requires_previous": True,
    "position": 0,
    "chapter_title": "Mein neues Kapitel",
},
```

- `chapter_title` must exactly match an entry in `CHAPTERS`.
- `position` controls the order within that chapter, starting at `0`.
- `requires_previous` makes the exercise depend on the preceding exercise.
- `solution` contains the accepted answers for interactive tasks.

For a lesson without questions, leave `solution` as `[]`. For a lesson with
tasks, include `exercise-tasks.js` and give each task a
`data-solution-index` matching the index in `solution`. For example:

```html
<article class="exercise-task" data-solution-index="0">
  <div class="task-answer-row">
    <input class="task-answer" type="text" aria-label="Antwort eingeben">
    <button class="check-answer" type="button" disabled>Prüfen</button>
  </div>
  <p class="task-feedback" role="status" aria-live="polite"></p>
</article>
```

The corresponding answer key might be:

```python
"solution": ["Beispielantwort"]
```

Answers may be strings, numbers, or booleans. They must appear in the same
order as the task indexes. String comparisons ignore case and surrounding
whitespace; number answers are parsed numerically.

Re-run the seed command after creating the template:

```powershell
uv run python seed_database.py
```

An exercise can remain unassigned in the administrator interface. Permanent
assignment to a chapter belongs in `EXERCISES` in `seed_database.py`.

### Add a timed challenge

Timed challenges are an ordered sequence and use randomized puzzle data. Before
adding a new challenge type, create or adapt its HTML template and register the
type in the challenge randomizer.

1. Create the challenge HTML in `templates/challenges/`.
2. Reuse `exercise-tasks.js` so the challenge can submit answer types to the
   parent challenge player. Add `randomized-cipher.js` only for the existing
   Caesar and Vigenère prompt format.
3. Register the HTML filename in `RANDOMIZED_CHALLENGES` in
   `randomized_challenges.py`. Existing entries map a filename to a cipher and
   operation, for example:

```python
"my_challenge.html": ("MyCipher", "operation"),
```

4. Add or extend the random-puzzle generation logic in
   `generate_randomized_challenge()`. It must return a
   `RandomizedChallenge` containing a prompt and a list of expected answers.
5. Add the challenge to `CHALLENGES` in `seed_database.py`:

```python
{
    "title": "Mein neues Rätsel",
    "html_filename": "my_challenge.html",
},
```

Challenge answers are intentionally not stored in the HTML or database. The
server recreates the same randomized prompt for a learner and compares the
submitted values against the calculated expected answers.

After registering everything, run:

```powershell
uv run python seed_database.py
```

Challenge order can be changed from the administrator interface. The new
challenge will be available to timed runs after the seed step and after
its HTML filename has passed the `is_randomized_challenge()` registration check.

### Test an extension

1. Start or restart the application.
2. Sign in as the administrator and open the challenge page to practice the
   randomized run.
3. Add a test learner account and complete the chapter or challenge as that
   learner.
4. Verify that images, tasks, answer types, prerequisite locks, ordering, and
   database seeding behave as intended.

Run the automated test suite after structural or server-side changes:

```powershell
uv run pytest
```