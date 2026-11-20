"""Generate account defaults and memorable passwords from local word lists."""

from functools import lru_cache
from pathlib import Path
import secrets


RANDOM_CLASSES = tuple(
    f"{grade}{section}"
    for grade in range(1, 5)
    for section in "ABC"
)


def random_klasse() -> str:
    """Choose a fallback class for accounts created without an imported class."""
    return secrets.choice(RANDOM_CLASSES)


@lru_cache(maxsize=1)
def _german_words() -> tuple[str, ...]:
    """Load the German password vocabulary once for reuse across imports."""
    word_list = Path(__file__).resolve().parent / "german_words.txt"
    words = tuple(
        word.strip()
        for word in word_list.read_text(encoding="utf-8-sig").splitlines()
        if word.strip()
    )
    if not words:
        raise ValueError(f"No words found in password word list: {word_list}")
    return words


@lru_cache(maxsize=1)
def _english_words() -> tuple[str, ...]:
    """Load the English password vocabulary once for reuse across imports."""
    word_list = Path(__file__).resolve().parent / "english_words.txt"
    words = tuple(
        word.strip().lower()
        for word in word_list.read_text(encoding="utf-8-sig").splitlines()
        if word.strip()
    )
    if not words:
        raise ValueError(f"No words found in password word list: {word_list}")
    return words


def generate_password() -> str:
    """Return a shuffled, mixed-language passphrase that meets login constraints."""
    german_words = _german_words()
    english_words = _english_words()
    word_lists = (german_words, english_words)
    words = [secrets.choice(german_words), secrets.choice(english_words)]
    while len(words) < 4 or len("-".join(words)) < 20:
        words.append(secrets.choice(secrets.choice(word_lists)))
    secrets.SystemRandom().shuffle(words)
    words = [word.capitalize() for word in words]
    return "-".join(words)
