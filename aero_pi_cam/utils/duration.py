"""Parse human-readable duration strings into timedelta objects."""

import re
from datetime import timedelta

# Matches patterns like "1h", "30m", "2h30m", "1h0m"
_DURATION_PATTERN = re.compile(r"^(?:(\d+)h)?(?:(\d+)m)?$")


def parse_duration(value: str) -> timedelta | None:
    """Parse a human-readable duration string into a timedelta.

    Supported formats: "1h", "30m", "2h30m", "90m", "0".
    Returns None for "0" or empty string (meaning history is disabled).

    Args:
        value: Duration string (e.g., "1h", "30m", "2h30m")

    Returns:
        timedelta for valid non-zero durations, None for "0" or empty string

    Raises:
        ValueError: If the format is invalid or results in zero duration
    """
    stripped = value.strip()
    if stripped in ("", "0"):
        return None

    match = _DURATION_PATTERN.match(stripped)
    if not match:
        raise ValueError(
            f"Invalid duration format: '{value}'. " 'Expected format like "1h", "30m", or "2h30m".'
        )

    hours = int(match.group(1)) if match.group(1) else 0
    minutes = int(match.group(2)) if match.group(2) else 0

    if hours == 0 and minutes == 0:
        return None

    return timedelta(hours=hours, minutes=minutes)
