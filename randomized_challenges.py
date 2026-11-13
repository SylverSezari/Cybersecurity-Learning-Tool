"""Generate stable, per-run cipher puzzles without storing answer keys."""

import hashlib
import hmac
import random
import string
from dataclasses import dataclass
from datetime import datetime

from config import settings

ALPHABET = string.ascii_uppercase
RANDOMIZED_CHALLENGES = {
    "caesar_encrypt.html": ("Caesar", "encrypt"),
    "caesar_decrypt.html": ("Caesar", "decrypt"),
    "vigenere_encrypt.html": ("Vigenère", "encrypt"),
    "vigenere_decrypt.html": ("Vigenère", "decrypt"),
}


@dataclass(frozen=True)
class RandomizedChallenge:
    prompt: dict[str, str | int]
    expected_answers: list[str]


def is_randomized_challenge(filename: str) -> bool:
    """Return whether a challenge file is one of the generated cipher puzzles."""
    return filename in RANDOMIZED_CHALLENGES


def generate_randomized_challenge(
    filename: str,
    account_id: int,
    started_at: datetime,
) -> RandomizedChallenge:
    """Recreate the same random puzzle for a learner throughout one timed run."""
    try:
        cipher, operation = RANDOMIZED_CHALLENGES[filename]
    except KeyError as error:
        raise ValueError(f"Unknown randomized challenge file: {filename}") from error

    seed_material = (
        f"{account_id}:{filename}:{started_at.isoformat(timespec='microseconds')}"
    ).encode("utf-8")
    seed = hmac.new(
        settings.secret_key.get_secret_value().encode("utf-8"),
        seed_material,
        hashlib.sha256,
    ).digest()
    generator = random.Random(int.from_bytes(seed, "big"))

    plaintext = "".join(generator.sample(ALPHABET, 8))
    if cipher == "Caesar":
        key: str | int = generator.randint(1, 25)
    else:
        key = "".join(generator.choice(ALPHABET) for _ in range(4))

    ciphertext = _transform(plaintext, key)
    prompt = {
        "cipher": cipher,
        "operation": operation,
        "text": ciphertext if operation == "decrypt" else plaintext,
        "key": key,
    }
    answer = plaintext if operation == "decrypt" else ciphertext
    return RandomizedChallenge(prompt=prompt, expected_answers=[answer])


def _transform(text: str, key: str | int) -> str:
    """Encrypt an uppercase alphabetic string with Caesar or Vigenère."""
    if isinstance(key, int):
        shifts = [key] * len(text)
    else:
        shifts = [ord(key[index % len(key)]) - ord("A") for index in range(len(text))]

    return "".join(
        chr((ord(character) - ord("A") + shift) % 26 + ord("A"))
        for character, shift in zip(text, shifts)
    )
