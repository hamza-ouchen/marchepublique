"""Explicit times attached to French dates in notices and documents."""
import re
from datetime import time


def clock_after_date(text: str) -> str | None:
    match = re.match(
        r"\s*[,–-]?\s*(?:à\s+|a\s+|T)?([01]?\d|2[0-3])\s*[:hH]\s*([0-5]\d)(?!\d)",
        text,
    )
    if match:
        return time(int(match[1]), int(match[2])).isoformat(timespec="minutes")
    return None
