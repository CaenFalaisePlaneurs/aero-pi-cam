"""Timestamp-based filename helpers for SFTP image history."""

import re
from collections.abc import Sequence
from datetime import UTC, datetime, timedelta

# Compact ISO 8601 timestamp format embedded in filenames
_TIMESTAMP_FORMAT = "%Y%m%dT%H%M%SZ"

# Regex to extract the timestamp portion from a history filename
# Matches: {stem}.{YYYYMMDDTHHmmSSZ}.{ext}
_TIMESTAMP_FILENAME_PATTERN = re.compile(r"^(.+)\.(\d{8}T\d{6}Z)\.(\w+)$")


def build_timestamped_filename(base_filename: str, timestamp: datetime) -> str:
    """Build a history filename by inserting a compact timestamp before the extension.

    Example: "LFAS-cam-clean.jpg" + 2026-03-10T17:16:32Z -> "LFAS-cam-clean.20260310T171632Z.jpg"

    Args:
        base_filename: Original filename (e.g., "camera-clean.jpg")
        timestamp: UTC capture timestamp

    Returns:
        Filename with embedded timestamp (e.g., "camera-clean.20260310T171632Z.jpg")
    """
    dot_idx = base_filename.rfind(".")
    if dot_idx == -1:
        return f"{base_filename}.{timestamp.strftime(_TIMESTAMP_FORMAT)}"
    stem = base_filename[:dot_idx]
    ext = base_filename[dot_idx + 1 :]
    return f"{stem}.{timestamp.strftime(_TIMESTAMP_FORMAT)}.{ext}"


def parse_timestamp_from_filename(base_filename: str, candidate: str) -> datetime | None:
    """Extract the embedded UTC timestamp from a history filename.

    Only matches files that share the same stem and extension as base_filename.

    Args:
        base_filename: The base filename to match against (e.g., "camera-clean.jpg")
        candidate: Filename to parse (e.g., "camera-clean.20260310T171632Z.jpg")

    Returns:
        Parsed UTC datetime, or None if the candidate doesn't match the pattern
    """
    match = _TIMESTAMP_FILENAME_PATTERN.match(candidate)
    if not match:
        return None

    cand_stem = match.group(1)
    ts_str = match.group(2)
    cand_ext = match.group(3)

    dot_idx = base_filename.rfind(".")
    if dot_idx == -1:
        base_stem = base_filename
        base_ext = ""
    else:
        base_stem = base_filename[:dot_idx]
        base_ext = base_filename[dot_idx + 1 :]

    if cand_stem != base_stem or cand_ext != base_ext:
        return None

    try:
        return datetime.strptime(ts_str, _TIMESTAMP_FORMAT).replace(tzinfo=UTC)
    except ValueError:
        return None


def collect_history_images(file_list: Sequence[str], base_filename: str) -> dict[datetime, str]:
    """From a directory listing, extract all timestamped copies matching the base filename.

    Args:
        file_list: List of filenames in the remote directory
        base_filename: The base filename pattern (e.g., "camera-clean.jpg")

    Returns:
        Dict mapping UTC timestamps to filenames, sorted most recent first
    """
    history: dict[datetime, str] = {}
    for fname in file_list:
        ts = parse_timestamp_from_filename(base_filename, fname)
        if ts is not None:
            history[ts] = fname

    return dict(sorted(history.items(), reverse=True))


def find_expired_images(
    history: dict[datetime, str], keep_duration: timedelta, now: datetime
) -> list[str]:
    """Return filenames of images that have exceeded the retention period.

    Args:
        history: Dict mapping timestamps to filenames
        keep_duration: How long to keep images
        now: Current UTC time

    Returns:
        List of filenames to delete
    """
    cutoff = now - keep_duration
    return [fname for ts, fname in history.items() if ts < cutoff]
