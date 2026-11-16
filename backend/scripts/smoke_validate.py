"""Dev smoke test: run validation over HTTP and print the resulting report.

Usage (API must be running):
    python scripts/smoke_validate.py [application_id] [email] [password]
"""

from __future__ import annotations

import sys
import time

import httpx

BASE = "http://127.0.0.1:8000/api"


def main() -> int:
    application_id = int(sys.argv[1]) if len(sys.argv) > 1 else 2
    email = sys.argv[2] if len(sys.argv) > 2 else "ananya@student.example"
    password = sys.argv[3] if len(sys.argv) > 3 else "Student@2026"

    with httpx.Client(timeout=60) as client:
        login = client.post(f"{BASE}/auth/login", json={"email": email, "password": password})
        login.raise_for_status()
        headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

        application = client.get(f"{BASE}/applications/{application_id}", headers=headers)
        application.raise_for_status()
        body = application.json()
        print("documents:", [(doc["kind"], doc["original_filename"]) for doc in body["documents"]])

        started = client.post(
            f"{BASE}/applications/{application_id}/validate", headers=headers
        )
        print("validate:", started.status_code, started.json().get("status"))
        started.raise_for_status()

        deadline = time.time() + 90
        while time.time() < deadline:
            body = client.get(
                f"{BASE}/applications/{application_id}", headers=headers
            ).json()
            run = body["latest_run"]
            if run and run["status"] in {"completed", "failed"}:
                break
            time.sleep(1)
        else:
            print("timed out waiting for the run")
            return 1

        print("application status:", body["status"])
        print("run:", run["status"], "overall:", run["overall"])
        print("summary:", run["summary"])
        print("findings:")
        for finding in run["findings"]:
            print(
                f"  {finding['category']:<12} {finding['field']:<22} "
                f"{finding['result']:<14} {finding['entered_value'] or '-':<8} "
                f"{finding['uploaded_value'] or '-':<8} {finding['detail'] or ''}"
            )
        print("extracted marks:")
        for mark in body["extracted_marks"]:
            print(
                f"  {mark['subject_norm'] or mark['subject_raw']:<16} "
                f"{mark['marks_obtained']} / {mark['max_marks']} "
                f"({mark['confidence']:.1f}% confidence)"
            )
    return 0 if run["status"] == "completed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
