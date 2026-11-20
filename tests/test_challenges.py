from datetime import UTC, datetime, timedelta
from pathlib import Path
import re

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

import challenge_pages
import models
from answer_validation import answers_match
from randomized_challenges import (
    GERMAN_4_LETTER_WORDS,
    GERMAN_8_LETTER_WORDS,
    decrypt_cipher_text,
    encrypt_cipher_text,
    generate_practice_challenge,
    generate_randomized_challenge,
)


def test_caesar_reported_example_round_trips():
    ciphertext = encrypt_cipher_text("MEHAIXEF", 16)
    assert ciphertext == "CUXQYNUV"
    assert decrypt_cipher_text(ciphertext, 16) == "MEHAIXEF"


def test_reported_caesar_decryption_challenge_uses_original_word_as_answer():
    plaintext = decrypt_cipher_text("YLZGCRCP", 24)
    assert plaintext == "ANBIETER"
    assert plaintext in GERMAN_8_LETTER_WORDS
    assert encrypt_cipher_text(plaintext, 24) == "YLZGCRCP"
    assert answers_match([plaintext], [plaintext])
    assert not answers_match([plaintext], ["WJXEAPAN"])


def test_vigenere_word_list_example_round_trips():
    plaintext = "ABFLUGZE"
    key = "TEST"
    ciphertext = encrypt_cipher_text(plaintext, key)
    assert decrypt_cipher_text(ciphertext, key) == plaintext


async def add_challenge(
    db_session: AsyncSession,
    title: str,
    html_filename: str,
    position: int,
) -> models.Challenge:
    challenge = models.Challenge(
        title=title,
        html_filename=html_filename,
        position=position,
    )
    db_session.add(challenge)
    await db_session.commit()
    return challenge


@pytest.mark.parametrize(
    "filename, cipher, operation",
    [
        ("caesar_encrypt.html", "Caesar", "encrypt"),
        ("caesar_decrypt.html", "Caesar", "decrypt"),
        ("vigenere_encrypt.html", "Vigenère", "encrypt"),
        ("vigenere_decrypt.html", "Vigenère", "decrypt"),
    ],
)
def test_randomized_challenge_is_stable_and_uses_word_list(
    filename: str,
    cipher: str,
    operation: str,
):
    started_at = datetime(2026, 11, 13, 7, tzinfo=UTC)
    challenge = generate_randomized_challenge(filename, 12, started_at)
    resumed_challenge = generate_randomized_challenge(filename, 12, started_at)
    next_run = generate_randomized_challenge(
        filename,
        12,
        started_at + timedelta(seconds=1),
    )

    assert challenge == resumed_challenge
    assert challenge.prompt["cipher"] == cipher
    assert challenge.prompt["operation"] == operation
    assert len(challenge.prompt["text"]) == 8
    assert len(challenge.expected_answers[0]) == 8
    plaintext = (
        challenge.prompt["text"]
        if operation == "encrypt"
        else challenge.expected_answers[0]
    )
    assert plaintext in GERMAN_8_LETTER_WORDS
    key = challenge.prompt["key"]
    shifts = (
        [key] * len(plaintext)
        if isinstance(key, int)
        else [
            ord(key[index % len(key)]) - ord("A")
            for index in range(len(plaintext))
        ]
    )
    expected_ciphertext = "".join(
        chr((ord(letter) - ord("A") + shift) % 26 + ord("A"))
        for letter, shift in zip(plaintext, shifts)
    )
    if operation == "encrypt":
        assert plaintext == challenge.prompt["text"]
        assert challenge.expected_answers == [expected_ciphertext]
        assert encrypt_cipher_text(plaintext, key) == challenge.expected_answers[0]
    else:
        assert plaintext == challenge.expected_answers[0]
        assert challenge.prompt["text"] == expected_ciphertext
        assert decrypt_cipher_text(challenge.prompt["text"], key) == plaintext
    assert challenge != next_run
    if cipher == "Caesar":
        assert isinstance(challenge.prompt["key"], int)
        assert 1 <= challenge.prompt["key"] <= 25
    else:
        assert isinstance(challenge.prompt["key"], str)
        assert len(challenge.prompt["key"]) == 4
        assert challenge.prompt["key"] in GERMAN_4_LETTER_WORDS


@pytest.mark.parametrize(
    "filename, operation",
    [
        ("rsa_key_generation.html", "key_generation"),
        ("rsa_encrypt.html", "encrypt"),
        ("rsa_decrypt.html", "decrypt"),
    ],
)
def test_rsa_challenges_are_stable_and_mathematically_consistent(
    filename: str,
    operation: str,
):
    started_at = datetime(2026, 11, 13, 7, tzinfo=UTC)
    challenge = generate_randomized_challenge(filename, 12, started_at)
    assert challenge == generate_randomized_challenge(filename, 12, started_at)
    assert challenge != generate_randomized_challenge(
        filename,
        12,
        started_at + timedelta(seconds=1),
    )

    prompt = challenge.prompt
    if operation == "key_generation":
        p, q = prompt["p"], prompt["q"]
        modulus, phi = challenge.expected_answers
        assert modulus == p * q
        assert phi == (p - 1) * (q - 1)
    elif operation == "encrypt":
        assert challenge.expected_answers == [
            pow(prompt["message"], prompt["e"], prompt["n"])
        ]
    else:
        message = pow(prompt["ciphertext"], prompt["d"], prompt["n"])
        assert challenge.expected_answers == [message]


async def get_test_account(db_session: AsyncSession) -> models.Account:
    result = await db_session.execute(
        select(models.Account).where(models.Account.username == "test_user")
    )
    account = result.scalar_one()
    await db_session.refresh(account)
    return account


@pytest.mark.anyio
async def test_challenge_admin_api_exposes_no_answer_keys(
    client: AsyncClient,
    admin_auth_headers: dict[str, str],
    user_auth_headers: dict[str, str],
    db_session: AsyncSession,
):
    challenge = await add_challenge(
        db_session,
        "Caesar encryption",
        "caesar_encrypt.html",
        0,
    )

    admin_response = await client.get(
        "/api/challenges",
        headers=admin_auth_headers,
    )
    learner_response = await client.get(
        "/api/challenges",
        headers=user_auth_headers,
    )

    assert admin_response.status_code == 200
    assert "solution" not in admin_response.json()[0]
    assert learner_response.status_code == 403
    assert challenge.title == "Caesar encryption"


@pytest.mark.anyio
async def test_randomized_cipher_challenges_keep_answers_server_side_and_validate(
    client: AsyncClient,
    db_session: AsyncSession,
    user_auth_headers: dict[str, str],
):
    filenames = [
        "caesar_encrypt.html",
        "caesar_decrypt.html",
        "vigenere_encrypt.html",
        "vigenere_decrypt.html",
    ]
    challenges = [
        await add_challenge(db_session, filename, filename, index)
        for index, filename in enumerate(filenames)
    ]
    account = await get_test_account(db_session)
    account.start_time = datetime.now(UTC)

    for index, challenge in enumerate(challenges):
        account.current_challenge_id = challenge.id
        account.current_challenge_complete = False
        await db_session.commit()
        await db_session.refresh(account)

        randomized = generate_randomized_challenge(
            challenge.html_filename,
            account.id,
            account.start_time,
        )
        page_response = await client.get(
            f"/challenge/{challenge.id}",
            headers=user_auth_headers,
        )
        assert page_response.status_code == 200
        assert randomized.prompt["text"] in page_response.text
        assert randomized.expected_answers[0] not in page_response.text
        challenge_content = await client.get(
            f"/challenge-content/{challenge.id}/{challenge.html_filename}",
            headers=user_auth_headers,
        )
        assert challenge_content.status_code == 200
        assert "exercise-theme.js" in challenge_content.text
        assert "challenge-alphabet-section" in challenge_content.text
        assert 'id="caesarShift"' in challenge_content.text
        assert "challenge-vigenere-key" not in challenge_content.text
        assert "challenge-alphabet-help" not in challenge_content.text

        if index == 0:
            incorrect_response = await client.post(
                f"/api/challenges/{challenge.id}/check",
                headers=user_auth_headers,
                json={"answers": ["not the answer"]},
            )
            assert incorrect_response.status_code == 400

        correct_response = await client.post(
            f"/api/challenges/{challenge.id}/check",
            headers=user_auth_headers,
            json={"answers": randomized.expected_answers},
        )
        assert correct_response.status_code == 200
        assert correct_response.json()["completed"] is True


@pytest.mark.anyio
async def test_admin_can_create_update_and_order_randomized_challenges(
    client: AsyncClient,
    admin_auth_headers: dict[str, str],
):
    first_response = await client.post(
        "/api/challenges",
        headers=admin_auth_headers,
        json={
            "title": "First",
            "html_filename": "caesar_encrypt.html",
        },
    )
    second_response = await client.post(
        "/api/challenges",
        headers=admin_auth_headers,
        json={
            "title": "Second",
            "html_filename": "caesar_decrypt.html",
        },
    )
    assert first_response.status_code == 201
    assert second_response.status_code == 201

    first_id = first_response.json()["id"]
    second_id = second_response.json()["id"]
    update_response = await client.put(
        f"/api/challenges/update/{first_id}",
        headers=admin_auth_headers,
        json={"title": "Updated first"},
    )
    order_response = await client.put(
        "/api/challenges/order",
        headers=admin_auth_headers,
        json={"challenge_ids": [second_id, first_id]},
    )

    assert update_response.status_code == 200
    assert update_response.json()["title"] == "Updated first"
    assert "solution" not in update_response.json()
    assert order_response.status_code == 200
    assert [item["id"] for item in order_response.json()] == [second_id, first_id]


@pytest.mark.anyio
async def test_admin_can_create_only_registered_randomized_challenges(
    client: AsyncClient,
    admin_auth_headers: dict[str, str],
):
    response = await client.post(
        "/api/challenges",
        headers=admin_auth_headers,
        json={
            "title": "Randomized Caesar",
            "html_filename": "caesar_encrypt.html",
        },
    )

    assert response.status_code == 201
    assert "solution" not in response.json()

    unregistered_response = await client.post(
        "/api/challenges",
        headers=admin_auth_headers,
        json={"title": "Unregistered challenge", "html_filename": "static.html"},
    )
    assert unregistered_response.status_code == 422


@pytest.mark.anyio
async def test_admin_can_practice_challenges_without_saved_time_or_completion(
    client: AsyncClient,
    db_session: AsyncSession,
    admin_auth_headers: dict[str, str],
):
    first = await add_challenge(
        db_session,
        "Practice first",
        "caesar_encrypt.html",
        0,
    )
    last = await add_challenge(
        db_session,
        "Practice last",
        "vigenere_decrypt.html",
        1,
    )

    home_response = await client.get("/", headers=admin_auth_headers)
    intro_response = await client.get("/challenge", headers=admin_auth_headers)
    start_response = await client.post(
        "/challenge/start",
        headers=admin_auth_headers,
        follow_redirects=False,
    )
    first_page = await client.get(
        f"/challenge/{first.id}",
        headers=admin_auth_headers,
    )
    content_response = await client.get(
        f"/challenge-content/{first.id}/{first.html_filename}",
        headers=admin_auth_headers,
    )
    next_response = await client.post(
        f"/challenge/{first.id}/next",
        headers=admin_auth_headers,
        follow_redirects=False,
    )
    randomized = generate_practice_challenge(last.html_filename)
    answer_response = await client.post(
        f"/api/challenges/{last.id}/check",
        headers=admin_auth_headers,
        json={"answers": randomized.expected_answers},
    )
    finish_response = await client.post(
        f"/challenge/{last.id}/finish",
        headers=admin_auth_headers,
        follow_redirects=False,
    )

    assert "Herausforderungen" in home_response.text
    assert "ohne Zeitmessung" in home_response.text
    assert "Deine Zeit und dein Fortschritt werden nicht gespeichert" in intro_response.text
    assert start_response.status_code == 303
    assert start_response.headers["location"].endswith(f"/challenge/{first.id}")
    assert first_page.status_code == 200
    assert 'data-admin-practice="true"' in first_page.text
    assert content_response.status_code == 200
    assert next_response.status_code == 303
    assert next_response.headers["location"].endswith(f"/challenge/{last.id}")
    assert answer_response.status_code == 200
    assert answer_response.json() == {"completed": True, "is_last": True}
    assert finish_response.status_code == 303
    assert finish_response.headers["location"].endswith("/challenge/victory")

    account_result = await db_session.execute(select(models.Account))
    assert account_result.scalars().all() == []
    assert first.position == 0

    db_session.add_all(
        [
            models.Account(
                username="Fastest",
                password_hash="test-hash",
                record_time=9_000,
            ),
            models.Account(
                username="Second fastest",
                password_hash="test-hash",
                record_time=12_000,
            ),
        ]
    )
    await db_session.commit()
    victory_response = await client.get(
        "/challenge/victory",
        headers=admin_auth_headers,
    )

    assert victory_response.status_code == 200
    assert "Deine Zeit wird nicht gespeichert" in victory_response.text
    assert "Fastest" in victory_response.text
    assert "Second fastest" in victory_response.text
    assert "00:09.000" in victory_response.text


@pytest.mark.anyio
async def test_challenge_run_requires_correct_answers_and_saves_new_record(
    client: AsyncClient,
    db_session: AsyncSession,
    user_auth_headers: dict[str, str],
):
    # The current-step pointer enforces ordering and survives a page refresh.
    first = await add_challenge(
        db_session,
        "First challenge",
        "caesar_encrypt.html",
        0,
    )
    last = await add_challenge(
        db_session,
        "Last challenge",
        "vigenere_decrypt.html",
        1,
    )
    account = await get_test_account(db_session)
    account.record_time = 60_000
    await db_session.commit()

    start_response = await client.post(
        "/challenge/start",
        headers=user_auth_headers,
        follow_redirects=False,
    )
    assert start_response.status_code == 303
    assert start_response.headers["location"].endswith(f"/challenge/{first.id}")
    await db_session.refresh(account)
    assert account.start_time is not None
    assert account.end_time is None
    assert account.current_challenge_id == first.id
    first_answer_value = generate_randomized_challenge(
        first.html_filename,
        account.id,
        account.start_time,
    ).expected_answers

    resume_response = await client.get(
        "/challenge",
        headers=user_auth_headers,
        follow_redirects=False,
    )
    player_response = await client.get(
        f"/challenge/{first.id}",
        headers=user_auth_headers,
    )
    assert resume_response.status_code == 303
    assert resume_response.headers["location"].endswith(f"/challenge/{first.id}")
    assert player_response.status_code == 200
    assert "First challenge" in player_response.text
    assert "correct" not in player_response.text

    ahead_response = await client.get(
        f"/challenge/{last.id}",
        headers=user_auth_headers,
        follow_redirects=False,
    )
    assert ahead_response.status_code == 303
    assert ahead_response.headers["location"].endswith(f"/challenge/{first.id}")

    wrong_answer = await client.post(
        f"/api/challenges/{first.id}/check",
        headers=user_auth_headers,
        json={"answers": ["wrong"]},
    )
    assert wrong_answer.status_code == 400
    assert wrong_answer.json()["detail"] == "Challenge answers are incorrect"

    first_answer = await client.post(
        f"/api/challenges/{first.id}/check",
        headers=user_auth_headers,
        json={"answers": first_answer_value},
    )
    assert first_answer.status_code == 200
    assert first_answer.json() == {"completed": True, "is_last": False}

    next_response = await client.post(
        f"/challenge/{first.id}/next",
        headers=user_auth_headers,
        follow_redirects=False,
    )
    assert next_response.status_code == 303
    assert next_response.headers["location"].endswith(f"/challenge/{last.id}")

    await db_session.refresh(account)
    last_answer_value = generate_randomized_challenge(
        last.html_filename,
        account.id,
        account.start_time,
    ).expected_answers
    last_answer = await client.post(
        f"/api/challenges/{last.id}/check",
        headers=user_auth_headers,
        json={"answers": last_answer_value},
    )
    assert last_answer.status_code == 200
    assert last_answer.json() == {"completed": True, "is_last": True}

    account.start_time = datetime.now(UTC) - timedelta(seconds=20)
    await db_session.commit()
    finish_response = await client.post(
        f"/challenge/{last.id}/finish",
        headers=user_auth_headers,
        follow_redirects=False,
    )
    assert finish_response.status_code == 303
    assert finish_response.headers["location"].endswith("/challenge/victory")

    await db_session.refresh(account)
    assert account.end_time is not None
    assert account.record_time is not None and account.record_time < 60_000
    assert account.previous_record_time == 60_000
    victory_response = await client.get(
        "/challenge/victory",
        headers=user_auth_headers,
    )
    assert victory_response.status_code == 200
    assert "Neuer Rekord" in victory_response.text
    assert "01:00.000" in victory_response.text


@pytest.mark.anyio
async def test_leaving_for_another_page_abandons_an_active_run(
    client: AsyncClient,
    db_session: AsyncSession,
    user_auth_headers: dict[str, str],
):
    challenge = await add_challenge(
        db_session,
        "Active challenge",
        "caesar_decrypt.html",
        0,
    )
    account = await get_test_account(db_session)
    account.start_time = datetime.now(UTC)
    account.current_challenge_id = challenge.id
    await db_session.commit()

    response = await client.get("/chapters", headers=user_auth_headers)

    assert response.status_code == 200
    await db_session.refresh(account)
    assert account.start_time is None
    assert account.current_challenge_id is None
    assert account.current_challenge_complete is False


@pytest.mark.anyio
async def test_give_up_returns_to_intro_and_preserves_best_record(
    client: AsyncClient,
    db_session: AsyncSession,
    user_auth_headers: dict[str, str],
):
    challenge = await add_challenge(
        db_session,
        "Give-up challenge",
        "vigenere_encrypt.html",
        0,
    )
    account = await get_test_account(db_session)
    account.record_time = 12_345
    await db_session.commit()

    intro_response = await client.get("/challenge", headers=user_auth_headers)
    start_response = await client.post(
        "/challenge/start",
        headers=user_auth_headers,
        follow_redirects=False,
    )
    abandon_response = await client.post(
        "/challenge/abandon",
        headers=user_auth_headers,
        follow_redirects=False,
    )

    assert intro_response.status_code == 200
    assert "Dein bisheriger Rekord" in intro_response.text
    assert start_response.status_code == 303
    assert abandon_response.status_code == 303
    assert abandon_response.headers["location"].endswith("/challenge")
    await db_session.refresh(account)
    assert account.start_time is None
    assert account.end_time is None
    assert account.current_challenge_id is None
    assert account.record_time == 12_345
    assert challenge.position == 0


@pytest.mark.anyio
async def test_victory_leaderboard_shows_top_ten_and_current_neighbors(
    client: AsyncClient,
    db_session: AsyncSession,
    user_auth_headers: dict[str, str],
):
    account = await get_test_account(db_session)
    account.record_time = 14_000
    account.start_time = datetime.now(UTC) - timedelta(seconds=14)
    account.end_time = datetime.now(UTC)
    db_session.add_all(
        [
            models.Account(
                username=f"rank_{rank}",
                password_hash="test-hash",
                record_time=rank * 1_000,
            )
            for rank in list(range(1, 14)) + [15, 16]
        ]
    )
    await db_session.commit()

    response = await client.get("/challenge/victory", headers=user_auth_headers)

    assert response.status_code == 200
    assert [
        int(rank)
        for rank in re.findall(r'data-rank="(\d+)"', response.text)
    ] == list(range(1, 11)) + [13, 14, 15]
    assert "rank_13" in response.text
    assert "test_user" in response.text
    assert "rank_15" in response.text
    assert "rank_11" not in response.text
    assert "rank_12" not in response.text


@pytest.mark.anyio
async def test_challenge_content_serves_only_current_challenge_file(
    client: AsyncClient,
    db_session: AsyncSession,
    monkeypatch,
    tmp_path: Path,
    user_auth_headers: dict[str, str],
):
    # The HTML entrypoint is allowed, but another HTML file cannot be substituted.
    challenge = await add_challenge(
        db_session,
        "File challenge",
        "caesar_encrypt.html",
        0,
    )
    challenge_file = tmp_path / "caesar_encrypt.html"
    challenge_file.write_text("<h1>Challenge body</h1>", encoding="utf-8")
    monkeypatch.setattr(challenge_pages, "CHALLENGES_DIRECTORY", tmp_path)

    account = await get_test_account(db_session)
    account.start_time = datetime.now(UTC)
    account.current_challenge_id = challenge.id
    await db_session.commit()

    response = await client.get(
        f"/challenge-content/{challenge.id}/caesar_encrypt.html",
        headers=user_auth_headers,
    )
    other_file = await client.get(
        f"/challenge-content/{challenge.id}/other.html",
        headers=user_auth_headers,
    )

    assert response.status_code == 200
    assert response.text == "<h1>Challenge body</h1>"
    assert other_file.status_code == 404
