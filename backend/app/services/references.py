from __future__ import annotations

import secrets

ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"


def new_reference() -> str:
    body = "".join(secrets.choice(ALPHABET) for _ in range(5))
    return f"MH26-{body}"
