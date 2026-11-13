from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

import challenge_pages
import models
from randomized_challenges import generate_randomized_challenge


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
def test_randomized_challenge_is_stable_and_uses_eight_distinct_letters(
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
    assert len(set(plaintext)) == 8
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
        assert challenge.expected_answers == [expected_ciphertext]
    else:
        assert challenge.prompt["text"] == expected_ciphertext
    assert challenge != next_run
    if cipher == "Caesar":
        assert isinstance(challenge.prompt["key"], int)
        assert 1 <= challenge.prompt["key"] <= 25
    else:
        assert isinstance(challenge.prompt["key"], str)
        assert len(challenge.prompt["key"]) == 4


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
