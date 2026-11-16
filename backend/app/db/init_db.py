from __future__ import annotations

from app.db.session import engine
from app.models import Base


def init_db() -> None:
    import app.models  # noqa: F401  (register all mappers)

    Base.metadata.create_all(bind=engine)
