"""Import every model so SQLAlchemy's registry resolves relationships."""

from app.models.accuracy import AccuracyRun
from app.models.application import Application, EducationRecord, EnteredMark
from app.models.base import Base
from app.models.document import AadhaarRecord, Document, ExtractedMark, OcrResult
from app.models.review import AuditLog, ReviewItem
from app.models.user import User
from app.models.validation import Finding, ValidationRun

__all__ = [
    "AccuracyRun",
    "Application",
    "AuditLog",
    "Base",
    "Document",
    "EducationRecord",
    "EnteredMark",
    "ExtractedMark",
    "Finding",
    "OcrResult",
    "ReviewItem",
    "User",
    "ValidationRun",
]
