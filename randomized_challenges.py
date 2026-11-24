"""Generate stable, per-run cipher puzzles without storing answer keys."""

import hashlib
import hmac
import random
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from config import settings


def _read_word_list(word_list: Path, word_length: int) -> tuple[str, ...]:
    path = settings.resolve_path(word_list)
    words = tuple(
        word.strip().upper()
        for word in path.read_text(encoding="utf-8").splitlines()
        if word.strip()
    )
    if any(
        len(word) != word_length or not word.isascii() or not word.isalpha()
        for word in words
    ):
        raise ValueError(f"{path} must contain only {word_length}-letter words")
    return words


GERMAN_8_LETTER_WORDS = _read_word_list(settings.german_8_letter_words_file, 8)
GERMAN_4_LETTER_WORDS = _read_word_list(settings.german_4_letter_words_file, 4)
RANDOMIZED_CHALLENGES = {
    "caesar_encrypt.html": ("Caesar", "encrypt"),
    "caesar_decrypt.html": ("Caesar", "decrypt"),
    "vigenere_encrypt.html": ("Vigenère", "encrypt"),
    "vigenere_decrypt.html": ("Vigenère", "decrypt"),
    "rsa_key_generation.html": ("RSA", "key_generation"),
    "rsa_encrypt.html": ("RSA", "encrypt"),
    "rsa_decrypt.html": ("RSA", "decrypt"),
}


@dataclass(frozen=True)
class RandomizedChallenge:
    prompt: dict[str, str | int]
    expected_answers: list[str | int]


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

    if cipher == "RSA":
        return _generate_rsa_challenge(operation, generator)

    plaintext = generator.choice(GERMAN_8_LETTER_WORDS)
    if cipher == "Caesar":
        key: str | int = generator.randint(1, 25)
    else:
        key = generator.choice(GERMAN_4_LETTER_WORDS)

    ciphertext = encrypt_cipher_text(plaintext, key)
    if operation == "encrypt":
        prompt_text = plaintext
        answer = ciphertext
    else:
        prompt_text = ciphertext
        answer = plaintext

    prompt = {
        "cipher": cipher,
        "operation": operation,
        "text": prompt_text,
        "key": key,
    }
    return RandomizedChallenge(prompt=prompt, expected_answers=[answer])


def _generate_rsa_challenge(
    operation: str,
    generator: random.Random,
) -> RandomizedChallenge:
    """Create a small, valid RSA puzzle with parameters suitable for hand calculation."""
    primes = [3, 5, 7, 11, 13, 17, 19, 23, 29, 31]
    p, q = generator.sample(primes, 2)
    modulus = p * q
    phi = (p - 1) * (q - 1)

    if operation == "key_generation":
        return RandomizedChallenge(
            prompt={"operation": operation, "p": p, "q": q},
            expected_answers=[modulus, phi],
        )

    valid_exponents = [
        exponent for exponent in range(3, phi) if _gcd(exponent, phi) == 1
    ]
    exponent = generator.choice(valid_exponents)
    private_exponent = pow(exponent, -1, phi)

    message = generator.randint(2, modulus - 1)
    if operation == "encrypt":
        ciphertext = pow(message, exponent, modulus)
        return RandomizedChallenge(
            prompt={
                "operation": operation,
                "message": message,
                "e": exponent,
                "n": modulus,
            },
            expected_answers=[ciphertext],
        )

    ciphertext = pow(message, exponent, modulus)
    return RandomizedChallenge(
        prompt={
            "operation": operation,
            "ciphertext": ciphertext,
            "d": private_exponent,
            "n": modulus,
        },
        expected_answers=[message],
    )


def _gcd(left: int, right: int) -> int:
    while right:
        left, right = right, left % right
    return left


def generate_practice_challenge(filename: str) -> RandomizedChallenge:
    """Generate a stable puzzle for admin practice without starting a timed run."""
    return generate_randomized_challenge(
        filename,
        account_id=0,
        started_at=datetime(1970, 1, 1, tzinfo=UTC),
    )


def encrypt_cipher_text(text: str, key: str | int) -> str:
    """Encrypt uppercase alphabetic text with Caesar or Vigenère."""
    if isinstance(key, int):
        shifts = [key] * len(text)
    else:
        shifts = [ord(key[index % len(key)]) - ord("A") for index in range(len(text))]

    return "".join(
        chr((ord(character) - ord("A") + shift) % 26 + ord("A"))
        for character, shift in zip(text, shifts)
    )


def decrypt_cipher_text(text: str, key: str | int) -> str:
    """Decrypt uppercase alphabetic text with Caesar or Vigenère."""
    if isinstance(key, int):
        shifts = [key] * len(text)
    else:
        shifts = [ord(key[index % len(key)]) - ord("A") for index in range(len(text))]

    return "".join(
        chr((ord(character) - ord("A") - shift) % 26 + ord("A"))
        for character, shift in zip(text, shifts)
    )
