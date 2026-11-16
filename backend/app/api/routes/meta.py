from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.deps import get_current_user
from app.core.config import rules
from app.models.user import User

router = APIRouter(prefix="/api/meta", tags=["meta"])


@router.get("/config")
def public_config(_: User = Depends(get_current_user)) -> dict:
    config = rules()
    photo = config["photo"]
    return {
        "app": config["app"],
        "subjects": {
            "required": config["subjects"]["required"],
            "known": list(config["subjects"]["aliases"].keys()),
            "fuzzy_threshold": config["subjects"]["fuzzy_threshold"],
        },
        "uploads": {
            "max_mb": config["uploads"]["max_mb"],
            "extensions": config["uploads"]["allowed_extensions"],
            "max_pages": config["uploads"]["max_pages"],
        },
        "photo": {
            "min_width": photo["min_width"],
            "min_height": photo["min_height"],
            "max_width": photo["max_width"],
            "max_height": photo["max_height"],
            "min_aspect_ratio": photo["min_aspect_ratio"],
            "max_aspect_ratio": photo["max_aspect_ratio"],
            "min_size_kb": photo["min_size_kb"],
            "max_size_kb": photo["max_size_kb"],
            "allowed_formats": photo["allowed_formats"],
            "min_sharpness": photo["min_sharpness"],
            "min_brightness": photo["min_brightness"],
            "max_brightness": photo["max_brightness"],
            "face_check": photo["face_check"],
        },
        "ocr": {
            "engine": config["ocr"]["engine"],
            "low_confidence": config["ocr"]["low_confidence"],
        },
    }
