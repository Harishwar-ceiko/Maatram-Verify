from __future__ import annotations

import os
import sys
from pathlib import Path

os.environ["APP_ENV"] = "test"
os.environ.setdefault("DATABASE_URL", "sqlite://")
os.environ.setdefault("SECRET_KEY", "test-only-secret-key-not-used-in-production")
os.environ.setdefault(
    "UPLOAD_DIR", str(Path(__file__).resolve().parent / "_uploads")
)

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.security import hash_password  # noqa: E402
from app.db.session import get_db, get_session_factory  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Base, User  # noqa: E402

engine = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSession = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


@pytest.fixture(autouse=True)
def _fresh_database():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    from app.api.routes.auth import login_limiter

    login_limiter.reset()
    yield
    Base.metadata.drop_all(bind=engine)


def _override_db():
    db = TestingSession()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = _override_db
app.dependency_overrides[get_session_factory] = lambda: TestingSession


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def db():
    session = TestingSession()
    try:
        yield session
    finally:
        session.close()


def make_user(email: str, password: str, role: str = "student", name: str = "Test Student"):
    session = TestingSession()
    user = User(
        email=email,
        password_hash=hash_password(password),
        full_name=name,
        role=role,
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    session.close()
    return {"id": user.id, "email": user.email, "password": password, "role": role}


@pytest.fixture
def student():
    return make_user("student@test.example", "Student@2026", "student", "Test Student")


@pytest.fixture
def other_student():
    return make_user("other@test.example", "Student@2026", "student", "Other Student")


@pytest.fixture
def admin():
    return make_user("admin@test.example", "Admin@2026", "admin", "Test Admin")


def auth_headers(client: TestClient, email: str, password: str) -> dict[str, str]:
    response = client.post("/api/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


@pytest.fixture
def student_headers(client, student):
    return auth_headers(client, student["email"], student["password"])


@pytest.fixture
def other_headers(client, other_student):
    return auth_headers(client, other_student["email"], other_student["password"])


@pytest.fixture
def admin_headers(client, admin):
    return auth_headers(client, admin["email"], admin["password"])
