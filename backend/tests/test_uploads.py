from __future__ import annotations

import io
import os

os.environ.setdefault("UPLOAD_DIR", str(__import__("pathlib").Path(__file__).parent / "_uploads"))

from PIL import Image  # noqa: E402

from app.core.security import decrypt_bytes  # noqa: E402
from app.services import storage  # noqa: E402
from app.models import Document  # noqa: E402
from tests.conftest import TestingSession  # noqa: E402
from tests.payloads import application_payload  # noqa: E402

PAYLOAD = application_payload()


def make_png(size: tuple[int, int] = (360, 480), colour=(220, 210, 190)) -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", size, colour).save(buffer, format="PNG")
    return buffer.getvalue()


def create_application(client, headers) -> int:
    response = client.post("/api/applications", json=PAYLOAD, headers=headers)
    assert response.status_code == 201, response.text
    return response.json()["id"]


def upload(client, headers, application_id: int, data: bytes, name: str, kind: str = "marksheet"):
    return client.post(
        f"/api/applications/{application_id}/documents",
        headers=headers,
        data={"kind": kind},
        files={"file": (name, data, "image/png")},
    )


def test_upload_is_encrypted_at_rest(client, student_headers):
    application_id = create_application(client, student_headers)
    original = make_png()
    response = upload(client, student_headers, application_id, original, "sheet.png")
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["document"]["width"] == 360
    assert body["document"]["height"] == 480

    session = TestingSession()
    document = session.query(Document).one()
    path = storage.document_path(document)
    assert path.exists()
    assert path.read_bytes() != original
    assert decrypt_bytes(path.read_bytes()) == original
    session.close()


def test_magic_bytes_not_extension(client, student_headers):
    application_id = create_application(client, student_headers)
    disguised = b"this is plain prose pretending to be a scan\n" * 40
    response = upload(client, student_headers, application_id, disguised, "fake.png")
    assert response.status_code == 422
    assert "not a PDF" in response.json()["detail"]


def test_exact_duplicate_is_flagged(client, student_headers):
    application_id = create_application(client, student_headers)
    png = make_png()
    first = upload(client, student_headers, application_id, png, "sheet.png")
    second = upload(client, student_headers, application_id, png, "sheet-copy.png")
    assert first.status_code == 201 and second.status_code == 201
    assert second.json()["document"]["duplicate_of_id"] == first.json()["document"]["id"]
    assert second.json()["warnings"]


def test_near_duplicate_is_flagged(client, student_headers):
    application_id = create_application(client, student_headers)
    first = upload(client, student_headers, application_id, make_png(colour=(220, 210, 190)), "a.png")
    second = upload(client, student_headers, application_id, make_png(colour=(221, 211, 191)), "b.png")
    assert first.status_code == 201 and second.status_code == 201
    assert second.json()["document"]["duplicate_of_id"] is not None


def test_photo_replaces_previous(client, student_headers):
    application_id = create_application(client, student_headers)
    first = upload(client, student_headers, application_id, make_png((300, 400)), "one.png", "photo")
    second = upload(client, student_headers, application_id, make_png((320, 420)), "two.png", "photo")
    assert first.status_code == 201 and second.status_code == 201
    detail = client.get(f"/api/applications/{application_id}", headers=student_headers).json()
    photos = [doc for doc in detail["documents"] if doc["kind"] == "photo"]
    assert len(photos) == 1
    assert photos[0]["original_filename"] == "two.png"


def test_document_is_private(client, student_headers, other_headers, admin_headers):
    application_id = create_application(client, student_headers)
    uploaded = upload(client, student_headers, application_id, make_png(), "sheet.png").json()
    document_id = uploaded["document"]["id"]

    own = client.get(f"/api/documents/{document_id}/file", headers=student_headers)
    assert own.status_code == 200
    assert own.headers["cache-control"] == "private, no-store"

    other = client.get(f"/api/documents/{document_id}/file", headers=other_headers)
    assert other.status_code == 403

    admin = client.get(f"/api/documents/{document_id}/file", headers=admin_headers)
    assert admin.status_code == 200


def test_delete_removes_file(client, student_headers):
    application_id = create_application(client, student_headers)
    uploaded = upload(client, student_headers, application_id, make_png(), "sheet.png").json()
    document_id = uploaded["document"]["id"]

    session = TestingSession()
    document = session.get(Document, document_id)
    path = storage.document_path(document)
    session.close()
    assert path.exists()

    response = client.delete(f"/api/documents/{document_id}", headers=student_headers)
    assert response.status_code == 204
    assert not path.exists()
