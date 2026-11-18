"""Seed the prototype database.

Creates one admin, two students and ten applications that exercise every
validation state: all match, mark mismatch, bad photo, missing subject,
duplicate upload, income above the limit, an expired income certificate, an
Aadhaar checksum failure, a community-certificate name conflict and a Class 11
versus Class 12 name conflict. Mark sheets, certificates and portraits are
generated deterministically; every exception is validated once so the review
queue, the document dashboard, the consistency matrix and the demo all have
real results on a fresh database.

Usage:
    python scripts/seed.py [--reset]

`--reset` drops every table and clears stored uploads before seeding.
"""

from __future__ import annotations

import shutil
import sys
from datetime import date, datetime, timedelta, timezone
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
from app.models.application import Application, EducationRecord, EnteredMark  # noqa: E402
from app.models.document import Document  # noqa: E402
from app.models.enums import ApplicationStatus, DocumentKind, Role  # noqa: E402
from app.models.review import ReviewItem  # noqa: E402
from app.models.user import User  # noqa: E402
from app.models.validation import ValidationRun  # noqa: E402
from app.services import storage  # noqa: E402
from app.services.references import new_reference  # noqa: E402
from app.services.synthetic import (  # noqa: E402
    _base_portrait,
    _grade,
    _render_aadhaar,
    _render_certificate,
    _render_sheet,
    synthetic_aadhaar,
)
from app.services.validation import run_validation  # noqa: E402

ADMIN = {"email": "admin@maatram.example", "password": "Admin@2026", "full_name": "Priya Raghavan"}

STUDENTS = [
    {
        "email": "ananya@student.example",
        "password": "Student@2026",
        "full_name": "Ananya Subramanian",
        "date_of_birth": date(2008, 6, 14),
        "father_name": "Suresh Subramanian",
        "mother_name": "Kavitha Subramanian",
        "phone": "+91 98400 22114",
        "address": "12, Bharathi Street, T. Nagar, Chennai 600017",
        "gender": "Female",
        "is_orphan": False,
        "is_first_graduate": True,
    },
    {
        "email": "rohan@student.example",
        "password": "Student@2026",
        "full_name": "Rohan Kumaravel",
        "date_of_birth": date(2007, 11, 2),
        "father_name": "Kumaravel Murugan",
        "mother_name": "Vasanthi Murugan (guardian)",
        "phone": "+91 98410 33227",
        "address": "4/27, Kamaraj Nagar, Coimbatore 641014",
        "gender": "Male",
        "is_orphan": True,
        "is_first_graduate": False,
    },
]

CLASS_10_MARKS = [
    ("Mathematics", 94, 100),
    ("Science", 91, 100),
    ("Social Science", 88, 100),
    ("English", 90, 100),
    ("Tamil", 86, 100),
]
CLASS_11_MARKS = [
    ("Mathematics", 88, 100),
    ("English", 90, 100),
    ("Physics", 85, 100),
    ("Chemistry", 84, 100),
    ("Computer Science", 92, 100),
]

APPLICATIONS = [
    {
        "scenario": "all_valid",
        "student": 0,
        "status": ApplicationStatus.submitted.value,
        "class_10": {
            "register_number": "REG2024A014",
            "exam_year": 2024,
            "board": "State Board of Examinations",
            "marks": CLASS_10_MARKS,
        },
        "class_11": {
            "register_number": "REG2025A014",
            "exam_year": 2025,
            "board": "State Board of Examinations",
            "marks": CLASS_11_MARKS,
        },
        "class_12": {
            "register_number": "REG2026A014",
            "exam_year": 2026,
            "board": "State Board of Examinations",
            "marks": [
                ("Mathematics", 92, 100),
                ("English", 88, 100),
                ("Physics", 90, 100),
                ("Chemistry", 86, 100),
            ],
        },
        "sheet": [
            ("Mathematics", 92, 100),
            ("English", 88, 100),
            ("Physics", 90, 100),
            ("Chemistry", 86, 100),
        ],
        "photo": "good",
    },
    {
        "scenario": "mark_mismatch",
        "student": 0,
        "status": ApplicationStatus.needs_review.value,
        "class_10": {
            "register_number": "REG2024A014",
            "exam_year": 2024,
            "board": "State Board of Examinations",
            "marks": CLASS_10_MARKS,
        },
        "class_11": {
            "register_number": "REG2025A014",
            "exam_year": 2025,
            "board": "State Board of Examinations",
            "marks": CLASS_11_MARKS,
        },
        "class_12": {
            "register_number": "REG2026A014",
            "exam_year": 2026,
            "board": "State Board of Examinations",
            "marks": [
                ("Mathematics", 85, 100),
                ("English", 92, 100),
                ("Physics", 78, 100),
                ("Chemistry", 81, 100),
            ],
        },
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
        "scenario": "bad_photo",
        "student": 1,
        "status": ApplicationStatus.needs_review.value,
        "class_10": {
            "register_number": "REG2024B027",
            "exam_year": 2024,
            "board": "Central Board of Secondary Education",
            "marks": CLASS_10_MARKS,
        },
        "class_11": {
            "register_number": "REG2025B027",
            "exam_year": 2025,
            "board": "Central Board of Secondary Education",
            "marks": CLASS_11_MARKS,
        },
        "class_12": {
            "register_number": "REG2026B027",
            "exam_year": 2026,
            "board": "Central Board of Secondary Education",
            "marks": [
                ("Mathematics", 74, 100),
                ("English", 69, 100),
                ("Physics", 72, 100),
                ("Chemistry", 70, 100),
            ],
        },
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
        "scenario": "missing_subject",
        "student": 1,
        "status": ApplicationStatus.submitted.value,
        "class_10": {
            "register_number": "REG2024B027",
            "exam_year": 2024,
            "board": "Central Board of Secondary Education",
            "marks": CLASS_10_MARKS,
        },
        "class_11": {
            "register_number": "REG2025B027",
            "exam_year": 2025,
            "board": "Central Board of Secondary Education",
            "marks": CLASS_11_MARKS,
        },
        "class_12": {
            "register_number": "REG2026B027",
            "exam_year": 2026,
            "board": "Central Board of Secondary Education",
            "marks": [
                ("Mathematics", 81, 100),
                ("English", 77, 100),
                ("Physics", 84, 100),
                ("Chemistry", 80, 100),
            ],
        },
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
        "scenario": "duplicate_upload",
        "student": 0,
        "status": ApplicationStatus.submitted.value,
        "class_10": {
            "register_number": "REG2023A014",
            "exam_year": 2023,
            "board": "State Board of Examinations",
            "marks": CLASS_10_MARKS,
        },
        "class_11": {
            "register_number": "REG2024A014",
            "exam_year": 2024,
            "board": "State Board of Examinations",
            "marks": CLASS_11_MARKS,
        },
        "class_12": {
            "register_number": "REG2025A014",
            "exam_year": 2025,
            "board": "State Board of Examinations",
            "marks": [
                ("Mathematics", 88, 100),
                ("English", 90, 100),
                ("Physics", 93, 100),
                ("Chemistry", 92, 100),
            ],
        },
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
    {
        "scenario": "income_above_threshold",
        "student": 0,
        "status": ApplicationStatus.needs_review.value,
        "class_10": {
            "register_number": "REG2024A014",
            "exam_year": 2024,
            "board": "State Board of Examinations",
            "marks": CLASS_10_MARKS,
        },
        "class_11": {
            "register_number": "REG2025A014",
            "exam_year": 2025,
            "board": "State Board of Examinations",
            "marks": CLASS_11_MARKS,
        },
        "class_12": {
            "register_number": "REG2026A014",
            "exam_year": 2026,
            "board": "State Board of Examinations",
            "marks": [
                ("Mathematics", 92, 100),
                ("English", 88, 100),
                ("Physics", 90, 100),
                ("Chemistry", 86, 100),
            ],
        },
        "sheet": [
            ("Mathematics", 92, 100),
            ("English", 88, 100),
            ("Physics", 90, 100),
            ("Chemistry", 86, 100),
        ],
        "photo": "good",
        "supporting": [
            {"kind": "income_certificate", "profile": "above_threshold"}
        ],
        "fallback_reasons": [
            "The income certificate records INR 320,000, above the INR 250,000 limit."
        ],
        "validate": True,
    },
    {
        "scenario": "income_expired",
        "student": 1,
        "status": ApplicationStatus.needs_review.value,
        "class_10": {
            "register_number": "REG2024B027",
            "exam_year": 2024,
            "board": "Central Board of Secondary Education",
            "marks": CLASS_10_MARKS,
        },
        "class_11": {
            "register_number": "REG2025B027",
            "exam_year": 2025,
            "board": "Central Board of Secondary Education",
            "marks": CLASS_11_MARKS,
        },
        "class_12": {
            "register_number": "REG2026B027",
            "exam_year": 2026,
            "board": "Central Board of Secondary Education",
            "marks": [
                ("Mathematics", 74, 100),
                ("English", 69, 100),
                ("Physics", 72, 100),
                ("Chemistry", 70, 100),
            ],
        },
        "sheet": [
            ("Mathematics", 74, 100),
            ("English", 69, 100),
            ("Physics", 72, 100),
            ("Chemistry", 70, 100),
        ],
        "photo": "good",
        "supporting": [{"kind": "income_certificate", "profile": "expired"}],
        "fallback_reasons": [
            "The income certificate is more than twelve months old."
        ],
        "validate": True,
    },
    {
        "scenario": "aadhaar_checksum",
        "student": 0,
        "status": ApplicationStatus.needs_review.value,
        "class_10": {
            "register_number": "REG2024A014",
            "exam_year": 2024,
            "board": "State Board of Examinations",
            "marks": CLASS_10_MARKS,
        },
        "class_11": {
            "register_number": "REG2025A014",
            "exam_year": 2025,
            "board": "State Board of Examinations",
            "marks": CLASS_11_MARKS,
        },
        "class_12": {
            "register_number": "REG2026A014",
            "exam_year": 2026,
            "board": "State Board of Examinations",
            "marks": [
                ("Mathematics", 92, 100),
                ("English", 88, 100),
                ("Physics", 90, 100),
                ("Chemistry", 86, 100),
            ],
        },
        "sheet": [
            ("Mathematics", 92, 100),
            ("English", 88, 100),
            ("Physics", 90, 100),
            ("Chemistry", 86, 100),
        ],
        "photo": "good",
        "supporting": [
            {"kind": "aadhaar", "profile": "invalid_checksum", "seed": 2601}
        ],
        "fallback_reasons": [
            "The Aadhaar number failed the Verhoeff checksum."
        ],
        "validate": True,
    },
    {
        "scenario": "community_name_mismatch",
        "student": 1,
        "status": ApplicationStatus.needs_review.value,
        "class_10": {
            "register_number": "REG2024B027",
            "exam_year": 2024,
            "board": "Central Board of Secondary Education",
            "marks": CLASS_10_MARKS,
        },
        "class_11": {
            "register_number": "REG2025B027",
            "exam_year": 2025,
            "board": "Central Board of Secondary Education",
            "marks": CLASS_11_MARKS,
        },
        "class_12": {
            "register_number": "REG2026B027",
            "exam_year": 2026,
            "board": "Central Board of Secondary Education",
            "marks": [
                ("Mathematics", 81, 100),
                ("English", 77, 100),
                ("Physics", 84, 100),
                ("Chemistry", 80, 100),
            ],
        },
        "sheet": [
            ("Mathematics", 81, 100),
            ("English", 77, 100),
            ("Physics", 84, 100),
            ("Chemistry", 80, 100),
        ],
        "photo": "good",
        "supporting": [
            {
                "kind": "community_certificate",
                "profile": "name_mismatch",
                "printed_name": "Arjun Kumaravel",
            }
        ],
        "fallback_reasons": [
            "The community certificate carries a different applicant name."
        ],
        "validate": True,
    },
    {
        "scenario": "class_11_name_mismatch",
        "student": 0,
        "status": ApplicationStatus.needs_review.value,
        "class_10": {
            "register_number": "REG2024A014",
            "exam_year": 2024,
            "board": "State Board of Examinations",
            "marks": CLASS_10_MARKS,
        },
        "class_11": {
            "register_number": "REG2025A014",
            "exam_year": 2025,
            "board": "State Board of Examinations",
            "marks": CLASS_11_MARKS,
        },
        "class_12": {
            "register_number": "REG2026A014",
            "exam_year": 2026,
            "board": "State Board of Examinations",
            "marks": [
                ("Mathematics", 92, 100),
                ("English", 88, 100),
                ("Physics", 90, 100),
                ("Chemistry", 86, 100),
            ],
        },
        "sheet": [
            ("Mathematics", 92, 100),
            ("English", 88, 100),
            ("Physics", 90, 100),
            ("Chemistry", 86, 100),
        ],
        "extra_sheets": [
            {"class_level": 11, "name": "Ananya Ramanathan"}
        ],
        "photo": "good",
        "fallback_reasons": [
            "The name on the Class 11 mark sheet does not match the application."
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


def _classification(kind: str, method: str = "keyword") -> dict:
    """Mirror the evidence shape produced by the upload-time classifier."""

    return {
        "kind": kind,
        "method": method,
        "requested": kind,
        "confidence": 96.0 if method == "keyword" else None,
        "ambiguous": False,
        "signals": [],
        "note": None,
    }


def _sheet_bytes(
    spec: dict,
    applicant_name: str,
    *,
    class_level: int = 12,
    name: str | None = None,
) -> bytes:
    record = spec[f"class_{class_level}"]
    rows = spec["sheet"] if class_level == 12 else record["marks"]
    subjects = [
        {
            "subject": subject,
            "marks": marks,
            "max_marks": max_marks,
            "grade": _grade(marks),
        }
        for subject, marks, max_marks in rows
    ]
    return _png(
        _render_sheet(
            name or applicant_name,
            record["register_number"],
            record["exam_year"],
            record["board"],
            subjects,
            class_level=class_level,
        )
    )


def _supporting_document(item: dict, details: dict) -> tuple[str, bytes, str]:
    """Render one supporting document from the same synthetic primitives the
    accuracy corpus uses, so the demo and the benchmark cannot drift apart."""

    kind = item["kind"]
    profile = item["profile"]
    name = details["full_name"]
    father = details["father_name"]
    address = details["address"]

    if kind == "aadhaar":
        number = synthetic_aadhaar(
            int(item.get("seed", 2601)),
            valid=profile not in ("invalid_checksum", "checksum_failure"),
        )
        image = _render_aadhaar(
            name,
            number,
            gender=details["gender"],
            address=address,
            date_of_birth=details["date_of_birth"].strftime("%d/%m/%Y"),
        )
        return kind, _png(image), f"aadhaar-{number[-4:]}.png"

    if kind == "income_certificate":
        if profile == "above_threshold":
            amount = "INR 3,20,000"
            issued = date.today() - timedelta(days=30)
            certificate = "INC-2026-0104"
        elif profile == "expired":
            amount = "INR 2,00,000"
            issued = date.today() - timedelta(days=500)
            certificate = "INC-2025-0077"
        else:
            raise ValueError(f"Unknown income profile: {profile}")
        image = _render_certificate(
            "Income Certificate",
            certificate_number=certificate,
            name=name,
            father_name=father,
            address=address,
            issue_date=issued.strftime("%d/%m/%Y"),
            rows=[("Annual Income", amount)],
        )
        return kind, _png(image), f"income-{certificate.lower()}.png"

    if kind == "community_certificate":
        if profile != "name_mismatch":
            raise ValueError(f"Unknown community profile: {profile}")
        certificate = "COM-2026-0031"
        image = _render_certificate(
            "Community Certificate",
            certificate_number=certificate,
            name=item.get("printed_name") or name,
            father_name=father,
            address=address,
            issue_date=(date.today() - timedelta(days=25)).strftime("%d/%m/%Y"),
            rows=[("Community", "BC")],
        )
        return kind, _png(image), f"community-{certificate.lower()}.png"

    raise ValueError(f"Unknown supporting document kind: {kind}")


def _education_record(class_level: int, spec: dict) -> EducationRecord:
    return EducationRecord(
        class_level=class_level,
        register_number=spec["register_number"],
        exam_year=spec["exam_year"],
        board=spec["board"],
        marks=[
            EnteredMark(subject=subject, marks_obtained=marks, max_marks=max_marks)
            for subject, marks, max_marks in spec["marks"]
        ],
    )


def _attach(
    db,
    application: Application,
    kind: str,
    data: bytes,
    filename: str,
    uploaded_by_id: int,
    duplicate_of: Document | None = None,
    classification: dict | None = None,
) -> Document:
    fmt, pages, size = storage.validate_upload(data, kind)
    stored_name, _path = storage.store_bytes(application.id, data)
    phash, width, height = storage.phash_bytes(data, fmt)
    document = Document(
        application_id=application.id,
        kind=kind,
        classification=classification or _classification(kind),
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


def _seed() -> None:
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
                details = STUDENTS[spec["student"]]
                student = users[spec["student"]]
                application = Application(
                    reference=new_reference(),
                    student_id=student.id,
                    applicant_name=student.full_name,
                    date_of_birth=details["date_of_birth"],
                    father_name=details["father_name"],
                    mother_name=details["mother_name"],
                    phone=details["phone"],
                    address=details["address"],
                    is_orphan=details["is_orphan"],
                    is_first_graduate=details["is_first_graduate"],
                    status=spec["status"],
                    submitted_at=datetime.now(timezone.utc),
                )
                application.education_records = [
                    _education_record(10, spec["class_10"]),
                    *(
                        [_education_record(11, spec["class_11"])]
                        if spec.get("class_11")
                        else []
                    ),
                    _education_record(12, spec["class_12"]),
                ]
                db.add(application)
                db.flush()

                sheet_bytes = _sheet_bytes(spec, student.full_name)
                _attach(
                    db,
                    application,
                    DocumentKind.marksheet_12.value,
                    sheet_bytes,
                    f"marksheet-{spec['class_12']['register_number'].lower()}.png",
                    student.id,
                )
                for extra in spec.get("extra_sheets", []):
                    level = int(extra["class_level"])
                    extra_bytes = _sheet_bytes(
                        spec,
                        student.full_name,
                        class_level=level,
                        name=extra.get("name"),
                    )
                    _attach(
                        db,
                        application,
                        f"marksheet_{level}",
                        extra_bytes,
                        f"marksheet-{level}-{spec[f'class_{level}']['register_number'].lower()}.png",
                        student.id,
                    )
                photo_bytes = _portrait(spec["photo"])
                photo_doc = _attach(
                    db,
                    application,
                    DocumentKind.photo.value,
                    photo_bytes,
                    "photo-portrait.png",
                    student.id,
                    classification=_classification("photo", "image_heuristic"),
                )
                for item in spec.get("supporting", []):
                    kind, data, filename = _supporting_document(item, details)
                    _attach(
                        db,
                        application,
                        kind,
                        data,
                        filename,
                        student.id,
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
            class_12 = spec["class_12"]
            print(
                f"  {application.reference}  {application.applicant_name} | "
                f"{spec['scenario']} | Class 12 {class_12['exam_year']}  "
                f"({application.status})"
            )
        print(f"  review queue populated: {open_reviews} open item(s)")
    finally:
        db.close()


def is_database_empty() -> bool:
    """True when a fresh database has neither users nor applications.

    Startup seeding checks both so a deploy that already holds real work is
    never touched.
    """

    db = SessionLocal()
    try:
        has_users = db.scalar(select(User.id).limit(1)) is not None
        has_applications = db.scalar(select(Application.id).limit(1)) is not None
        return not has_users and not has_applications
    finally:
        db.close()


def seed_if_empty() -> bool:
    """Seed only a completely empty database. Returns True when it ran."""

    init_db()
    if not is_database_empty():
        return False
    _seed()
    return True


def main(reset: bool | None = None) -> None:
    if reset is None:
        reset = "--reset" in sys.argv[1:]
    init_db()
    if reset:
        db = SessionLocal()
        try:
            Base.metadata.drop_all(bind=db.get_bind())
        finally:
            db.close()
        uploads = get_settings().resolved_storage_dir()
        if uploads.exists():
            shutil.rmtree(uploads)
        init_db()
        print("Reset: dropped all tables and stored uploads.")

    _seed()


if __name__ == "__main__":
    main()
