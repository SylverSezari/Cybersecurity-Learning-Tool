"""Shared answer comparison for lessons and server-checked challenges."""

import unicodedata

from schemas import SolutionValue


def answers_match(
    expected_answers: list[str | int | float | bool],
    submitted_answers: list[SolutionValue],
) -> bool:
    """Compare answers by position while preserving each value's JSON type."""
    if len(expected_answers) != len(submitted_answers):
        return False

    # Check booleans first because Python treats bool as a subclass of int.
    for expected, submitted in zip(expected_answers, submitted_answers):
        if isinstance(expected, bool):
            if not isinstance(submitted, bool) or submitted is not expected:
                return False
        elif isinstance(expected, (int, float)):
            if isinstance(submitted, bool) or not isinstance(submitted, (int, float)):
                return False
            if submitted != expected:
                return False
        elif isinstance(expected, str):
            if not isinstance(submitted, str):
                return False
            if _normalize_text_answer(submitted) != _normalize_text_answer(expected):
                return False
        else:
            return False

    return True


def _normalize_text_answer(answer: str) -> str:
    """Ignore Unicode composition, surrounding spaces, and letter case."""
    return unicodedata.normalize("NFC", answer).strip().upper()
