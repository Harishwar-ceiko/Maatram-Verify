"""Restore the demo corpus after a run of DEMO.md.

The three-minute walkthrough changes two records:

* application 1 (the clean application) is validated and its report is
  downloaded;
* one review item is approved with a note.

This script returns both to the seeded state, removes the resulting audit
entries and clears the sign-in/download noise created by the demo browser
sessions. The other seeded applications, their runs and the queue are left
untouched, so the references stay stable between rehearsals.

Usage:
    python scripts/reset_demo.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import delete, select  # noqa: E402

from app.db.session import SessionLocal  # noqa: E402
from app.models.application import Application  # noqa: E402
from app.models.enums import ApplicationStatus, ReviewStatus  # noqa: E402
from app.models.review import AuditLog  # noqa: E402


def main() -> int:
    db = SessionLocal()
    clean = db.get(Application, 1)
    if clean is None:
        print("Application 1 is missing; run scripts/seed.py --reset first.")
        db.close()
        return 1

    runs = list(clean.runs)
    for run in runs:
        db.delete(run)

    ocr_rows = 0
    extracted_rows = 0
    for document in clean.documents:
        if document.ocr_result is not None:
            db.delete(document.ocr_result)
            ocr_rows += 1
        for mark in list(document.extracted_marks):
            db.delete(mark)
            extracted_rows += 1

    clean.status = ApplicationStatus.submitted.value

    reopened = 0
    decisions = 0
    for application in db.scalars(select(Application)).all():
        item = application.review_item
        if item is None or item.status not in (
            ReviewStatus.approved.value,
            ReviewStatus.rejected.value,
        ):
            continue
        item.status = ReviewStatus.open.value
        item.decision_comment = None
        item.decided_by = None
        item.decided_at = None
        item.assigned_to = None
        application.status = ApplicationStatus.needs_review.value
        decisions += 1
        reopened += 1

    app1_audit = db.execute(
        delete(AuditLog).where(AuditLog.application_id == clean.id)
    ).rowcount
    review_audit = db.execute(
        delete(AuditLog).where(
            AuditLog.action.in_(("review.approved", "review.rejected"))
        )
    ).rowcount
    downloads = db.execute(
        delete(AuditLog).where(AuditLog.action == "report.downloaded")
    ).rowcount
    logins = db.execute(delete(AuditLog).where(AuditLog.action == "auth.login")).rowcount

    db.commit()
    print(
        "Reset demo:",
        f"app 1 {clean.reference} back to submitted",
        f"({len(runs)} run(s), {ocr_rows} OCR cache row(s), {extracted_rows} extracted row(s) removed)",
    )
    if reopened:
        print(f"Reopened {reopened} decided review item(s); {decisions} decision(s) cleared")
    print(
        "Audit noise removed:",
        f"{app1_audit} app-1 entries, {review_audit} review entries,",
        f"{downloads} downloads, {logins} sign-ins",
    )
    print("Demo state ready. The review queue should show four open items.")
    db.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
