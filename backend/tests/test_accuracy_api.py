from __future__ import annotations

from datetime import datetime, timezone

from app.api.routes import admin as admin_routes
from app.models.accuracy import AccuracyRun


def test_accuracy_endpoint_is_admin_only(client, student_headers, admin_headers, db):
    response = client.get("/api/admin/accuracy", headers=student_headers)
    assert response.status_code == 403

    empty = client.get("/api/admin/accuracy", headers=admin_headers)
    assert empty.status_code == 200
    assert empty.json()["latest"] is None
    assert empty.json()["history"] == []

    run = AccuracyRun(
        dataset="synthetic-v1",
        total_cases=24,
        summary={
            "status": "completed",
            "field_accuracy": 1.0,
            "mismatch": {"recall": 1.0},
            "photos": {"rule_accuracy": 1.0},
        },
        report_md="# report",
        created_at=datetime.now(timezone.utc),
    )
    db.add(run)
    db.commit()

    latest = client.get("/api/admin/accuracy", headers=admin_headers)
    body = latest.json()
    assert body["latest"]["dataset"] == "synthetic-v1"
    assert body["latest"]["total_cases"] == 24
    assert body["latest"]["summary"]["field_accuracy"] == 1.0
    assert body["history"][0]["photo_accuracy"] == 1.0
    assert body["running"] is False


def test_starting_an_accuracy_run_rejects_a_second_request(
    client, admin_headers, monkeypatch
):
    calls: list[tuple[int, int | None]] = []

    def fake_run(run_id: int, created_by: int | None = None) -> int:
        calls.append((run_id, created_by))
        return run_id

    monkeypatch.setattr(admin_routes, "run_evaluation", fake_run)

    started = client.post("/api/admin/accuracy/run", headers=admin_headers)
    assert started.status_code == 202, started.text
    assert started.json()["status"] == "running"
    assert len(calls) == 1

    second = client.post("/api/admin/accuracy/run", headers=admin_headers)
    assert second.status_code == 409

    status = client.get("/api/admin/accuracy", headers=admin_headers)
    assert status.json()["running"] is True
    assert status.json()["latest"]["status"] == "running"
