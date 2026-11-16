from __future__ import annotations

from tests.conftest import TestingSession, auth_headers


def test_register_creates_student_and_hashes_password(client):
    response = client.post(
        "/api/auth/register",
        json={
            "full_name": "Meera Iyer",
            "email": "Meera@Example.com",
            "password": "MeeraPass1!",
        },
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["user"]["role"] == "student"
    assert body["user"]["email"] == "meera@example.com"
    assert body["access_token"]

    session = TestingSession()
    from app.models import User

    user = session.query(User).filter_by(email="meera@example.com").one()
    assert user.password_hash != "MeeraPass1!"
    assert user.password_hash.startswith("$2")
    session.close()


def test_duplicate_email_is_rejected(client, student):
    response = client.post(
        "/api/auth/register",
        json={
            "full_name": "Someone Else",
            "email": student["email"],
            "password": "AnotherPass1!",
        },
    )
    assert response.status_code == 409


def test_login_success_and_me(client, student):
    headers = auth_headers(client, student["email"], student["password"])
    response = client.get("/api/auth/me", headers=headers)
    assert response.status_code == 200
    assert response.json()["email"] == student["email"]


def test_login_wrong_password(client, student):
    response = client.post(
        "/api/auth/login", json={"email": student["email"], "password": "WrongPass1!"}
    )
    assert response.status_code == 401
    assert "incorrect" in response.json()["detail"].lower()


def test_login_rate_limit(client, student):
    for _ in range(8):
        client.post("/api/auth/login", json={"email": student["email"], "password": "WrongPass1!"})
    response = client.post(
        "/api/auth/login", json={"email": student["email"], "password": "WrongPass1!"}
    )
    assert response.status_code == 429
    assert "Retry-After" in response.headers


def test_tampered_token_is_rejected(client, student):
    response = client.get(
        "/api/auth/me", headers={"Authorization": "Bearer definitely.not.a.token"}
    )
    assert response.status_code == 401


def test_password_rules(client):
    response = client.post(
        "/api/auth/register",
        json={"full_name": "No Digits", "email": "nodigits@example.com", "password": "onlyletters"},
    )
    assert response.status_code == 422


def test_health(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json()["service"] == "ok"
