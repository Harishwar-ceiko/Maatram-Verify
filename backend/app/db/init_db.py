
from __future__ import annotations

from sqlalchemy import inspect

from app.db.session import engine
from app.models import Base


def init_db() -> None:
    import app.models  # noqa: F401

    # Create any missing tables without deleting existing data.
    Base.metadata.create_all(bind=engine)

    # Safely add new optional student-profile columns to existing databases.
    inspector = inspect(engine)
    existing_columns = {
        column["name"] for column in inspector.get_columns("users")
    }

    migrations = {
        "volunteer_activities": "TEXT",
        "achievements": "TEXT",
    }

    with engine.begin() as connection:
        for column_name, column_type in migrations.items():
            if column_name not in existing_columns:
                connection.exec_driver_sql(
                    f"ALTER TABLE users ADD COLUMN {column_name} {column_type}"
                )
