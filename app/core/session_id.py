from __future__ import annotations

import re

BUSINESS_SESSION_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,127}$")


def validate_business_session_id(value: str) -> str:
    if not BUSINESS_SESSION_ID_PATTERN.fullmatch(value):
        raise ValueError(
            "business_session_id must contain only letters, numbers, hyphens, and underscores"
        )
    return value
