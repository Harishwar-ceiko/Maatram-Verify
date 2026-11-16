"""Seed the prototype database.

Creates one admin, two students and five applications that exercise every
validation state: all match, mark mismatch, bad photo, missing subject and a
duplicate upload. Mark sheets and portraits are generated deterministically;
the mismatch and photo cases are validated once so the review queue and the
dashboard have real results on a fresh demo.

Usage:
    python scripts/seed.py [--reset]

`--reset` drops every table and clears stored uploads before seeding.
"""

from __future__ import annotations

import shutil
import sys
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PIL import Image, ImageEnhance, ImageOps  # noqa: E402
from sqlalchemy import func, select  # noqa: E402

from app.core.config import get_settings  # noqa: E402
from app.core.security import hash_password  # noqa: E402
from app.db.init_db import init_db  # noqa: E402
from app.db.session import SessionLocal  # noqa: E402
from app.models import Base  # noqa: E402
from app.models.application import Application, EnteredMark  # noqa: E402
from app.models.document import Document  # noqa: E402
from app.models.enums import ApplicationStatus, DocumentKind, Role  # noqa: E402
from app.models.review import ReviewItem  # noqa: E402
from app.models.user import User  # noqa: E402
from app.models.validation import ValidationRun  # noqa: E402
from app.services import storage  # noqa: E402
from app.services.references import new_reference  # noqa: E402
from app.services.synthetic import _base_portrait, _grade, _render_sheet  # noqa: E402
from app.services.validation import run_validation  # noqa: E402

ADMIN = {"email": "admin@maatram.example", "password": "Admin@2026", "full_name": "Priya Raghavan"}
STUDENTS = [
    {
        "email": "ananya@student.example",
        "password": "Student@2026",
        "full_name": "Ananya Subramanian",
        "register_number": "REG2026A014",
    },
    {
        "email": "rohan@student.example",
        "password": "Student@2026",
        "full_name": "Rohan Kumaravel",
        "register_number": "REG2026B027",
    },
]

APPLICATIONS = [
    {
        "student": 0,
        "program": "B.Sc. Computer Science",
        "applicant_name": "Ananya Subramanian",
        "register_number": "REG2026A014",
        "exam_year": 2026,
        "board": "State Board of Examinations",
        "status": ApplicationStatus.submitted.value,
        "marks": [
            ("Mathematics", 92, 100),
            ("English", 88, 100),
            ("Physics", 90, 100),
            ("Chemistry", 86, 100),
        ],
        "sheet": [
            ("Mathematics", 92, 100),
            ("English", 88, 100),
            ("Physics", 90, 100),
            ("Chemistry", 86, 100),
        ],
        "photo": "good",
    },
    {
        "student": 0,
        "program": "B.E. Electronics and Communication",
        "applicant_name": "Ananya Subramanian",
        "register_number": "REG2026A014",
        "exam_year": 2026,
        "board": "State Board of Examinations",
        "status": ApplicationStatus.needs_review.value,
        "marks": [
            ("Mathematics", 85, 100),
            ("English", 92, 100),
            ("Physics", 78, 100),
            ("Chemistry", 81, 100),
        ],
        "sheet": [
            ("Mathematics", 88, 100),
            ("English", 92, 100),
            ("Physics", 81, 100),
            ("Chemistry", 78, 100),
        ],
        "photo": "mirror",
        "fallback_reasons": [
            "Entered 85 for Mathematics but the sheet reads 88.",
            "Entered 78 for Physics but the sheet reads 81.",
            "Entered 81 for Chemistry but the sheet reads 78.",
        ],
        "validate": True,
    },
    {
        "student": 1,
        "program": "B.Sc. Computer Science",
        "applicant_name": "Rohan Kumaravel",
        "register_number": "REG2026B027",
        "exam_year": 2026,
        "board": "Central Board of Secondary Education",
        "status": ApplicationStatus.needs_review.value,
        "marks": [
            ("Mathematics", 74, 100),
            ("English", 69, 100),
            ("Physics", 72, 100),
            ("Chemistry", 70, 100),
        ],
        "sheet": [
            ("Mathematics", 74, 100),
            ("English", 69, 100),
            ("Physics", 72, 100),
            ("Chemistry", 70, 100),
        ],
        "photo": "dark",
        "fallback_reasons": [
            "The photograph is too dark to check; brightness falls below the accepted floor."
        ],
        "validate": True,
    },
    {
        "student": 1,
        "program": "B.Sc. Physical Sciences",
        "applicant_name": "Rohan Kumaravel",
        "register_number": "REG2026B027",
        "exam_year": 2026,
        "board": "Central Board of Secondary Education",
        "status": ApplicationStatus.submitted.value,
        "marks": [
            ("Mathematics", 81, 100),
            ("English", 77, 100),
            ("Physics", 84, 100),
            ("Chemistry", 80, 100),
        ],
        "sheet": [
            ("Mathematics", 81, 100),
            ("English", 77, 100),
            ("Chemistry", 80, 100),
        ],
        "photo": "crop",
        "fallback_reasons": [
            "Entered Physics 84 but the subject is missing from the mark sheet."
        ],
        "validate": True,
    },
    {
        "student": 0,
        "program": "B.Sc. Data Science",
        "applicant_name": "Ananya Subramanian",
        "register_number": "REG2026A014",
        "exam_year": 2025,
        "board": "State Board of Examinations",
        "status": ApplicationStatus.submitted.value,
        "marks": [
            ("Mathematics", 88, 100),
            ("English", 90, 100),
            ("Physics", 93, 100),
            ("Chemistry", 92, 100),
        ],
        "sheet": [
            ("Mathematics", 88, 100),
            ("English", 90, 100),
            ("Physics", 93, 100),
            ("Chemistry", 92, 100),
        ],
        "photo": "duplicate",
        "fallback_reasons": [
            "The uploaded photograph duplicates another file on this account."
        ],
        "validate": True,
    },
]


def _png(image: Image.Image) -> bytes:
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def _portrait(kind: str) -> bytes:
    base = _base_portrait()
    if kind == "mirror":
        return _png(ImageOps.mirror(base))
    if kind == "crop":
        return _png(base.crop((28, 36, 452, 566)).resize((480, 600), Image.Resampling.LANCZOS))
    if kind == "dark":
        dark = ImageEnhance.Brightness(
            base.crop((16, 24, 464, 584)).resize((480, 600), Image.Resampling.LANCZOS)
        ).enhance(0.35)
        return _png(dark)
    return _png(base)


def _sheet_bytes(spec: dict) -> bytes:
    subjects = [
        {
            "subject": subject,
            "marks": marks,
            "max_marks": max_marks,
            "grade": _grade(marks),
        }
        for subject, marks, max_marks in spec["sheet"]
    ]
    return _png(
        _render_sheet(
            spec["applicant_name"],
            spec["register_number"],
            spec["exam_year"],
            spec["board"],
            subjects,
        )
    )


def _attach(
    db,
    application: Application,
    kind: str,
    data: bytes,
    filename: str,
    uploaded_by_id: int,
    duplicate_of: Document | None = None,
) -> Document:
    fmt, pages, size = storage.validate_upload(data, kind)
    stored_name, _path = storage.store_bytes(application.id, data)
    phash, width, height = storage.phash_bytes(data, fmt)
    document = Document(
        application_id=application.id,
        kind=kind,
        original_filename=filename,
        stored_name=stored_name,
        mime_type=storage.MIME[fmt],
        size_bytes=size,
        sha256=storage.checksum(data),
        phash=phash,
        page_count=pages,
        width=width,
        height=height,
        encrypted=True,
        duplicate_of_id=duplicate_of.id if duplicate_of is not None else None,
        uploaded_by_id=uploaded_by_id,
    )
    db.add(document)
    db.flush()
    return document


def _run_once(db, application: Application) -> bool:
    run = ValidationRun(
        application_id=application.id,
        status="pending",
        summary={},
    )
    db.add(run)
    db.commit()
    try:
        run_validation(run.id, SessionLocal)
    except Exception as exc:  # noqa: BLE001 - seeding must finish even without OCR
        print(f"  validation skipped for {application.reference}: {exc}")
        db.rollback()
        db.expire_all()
        return False
    db.expire_all()
    finished = db.get(ValidationRun, run.id)
    if finished is None or finished.status != "completed":
        print(f"  validation failed for {application.reference}; review left for a person")
        return False
    print(f"  validated {application.reference}")
    return True


def main() -> None:
    reset = "--reset" in sys.argv[1:]
    init_db()
    if reset:
        db = SessionLocal()
        try:
            Base.metadata.drop_all(bind=db.get_bind())
        finally:
            db.close()
        uploads = get_settings().resolved_upload_dir()
        if uploads.exists():
            shutil.rmtree(uploads)
        init_db()
        print("Reset: dropped all tables and stored uploads.")

    db = SessionLocal()
    try:
        if not db.scalar(select(User).where(User.email == ADMIN["email"])):
            db.add(
                User(
                    email=ADMIN["email"],
                    password_hash=hash_password(ADMIN["password"]),
                    full_name=ADMIN["full_name"],
                    role=Role.admin.value,
                )
            )
        users: list[User] = []
        for record in STUDENTS:
            user = db.scalar(select(User).where(User.email == record["email"]))
            if user is None:
                user = User(
                    email=record["email"],
                    password_hash=hash_password(record["password"]),
                    full_name=record["full_name"],
                    role=Role.student.value,
                )
                db.add(user)
            users.append(user)
        db.flush()

        created: list[tuple[dict, Application]] = []
        if not db.scalar(select(Application.id)):
            for spec in APPLICATIONS:
                application = Application(
                    reference=new_reference(),
                    student_id=users[spec["student"]].id,
                    program=spec["program"],
                    applicant_name=spec["applicant_name"],
                    register_number=spec["register_number"],
                    exam_year=spec["exam_year"],
                    board=spec["board"],
                    status=spec["status"],
                    submitted_at=datetime.now(timezone.utc),
                )
                application.entered_marks = [
                    EnteredMark(subject=subject, marks_obtained=marks, max_marks=max_marks)
                    for subject, marks, max_marks in spec["marks"]
                ]
                db.add(application)
                db.flush()

                sheet_bytes = _sheet_bytes(spec)
                _attach(
                    db,
                    application,
                    DocumentKind.marksheet.value,
                    sheet_bytes,
                    f"marksheet-{spec['register_number'].lower()}.png",
                    users[spec["student"]].id,
                )
                photo_bytes = _portrait(spec["photo"])
                photo_doc = _attach(
                    db,
                    application,
                    DocumentKind.photo.value,
                    photo_bytes,
                    "photo-portrait.png",
                    users[spec["student"]].id,
                )
                created.append((spec, application))
                if spec["photo"] == "duplicate":
                    original = next(
                        item
                        for item in db.scalars(
                            select(Document).where(
                                Document.kind == DocumentKind.photo.value,
                                Document.application_id == created[0][1].id,
                            )
                        )
                    )
                    photo_doc.duplicate_of_id = original.id
            db.commit()

            for spec, application in created:
                if spec.get("validate"):
                    if not _run_once(db, application):
                        db.expire_all()
                        fresh = db.get(Application, application.id)
                        if fresh is not None and fresh.review_item is None:
                            fresh.status = ApplicationStatus.needs_review.value
                            fresh.review_item = ReviewItem(
                                application_id=fresh.id,
                                status="open",
                                priority=20,
                                reasons=spec.get("fallback_reasons", []),
                            )
                            db.commit()

        open_reviews = (
            db.scalar(
                select(func.count())
                .select_from(ReviewItem)
                .where(ReviewItem.status == "open")
            )
            or 0
        )
        print("Seed complete.")
        print(f"  admin   {ADMIN['email']} / {ADMIN['password']}")
        for record in STUDENTS:
            print(f"  student {record['email']} / {record['password']}")
        for spec, application in created:
            print(f"  {application.reference}  {application.program}  ({application.status})")
        print(f"  review queue populated: {open_reviews} open item(s)")
    finally:
        db.close()


if __name__ == "__main__":
    main()
