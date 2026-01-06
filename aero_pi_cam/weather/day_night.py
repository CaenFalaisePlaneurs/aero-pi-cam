"""Day/night mode detection with debug override."""

import os
from datetime import datetime

from ..core.config import Config
from .sun import is_day


def get_day_night_mode(capture_time: datetime, config: Config | None) -> bool:
    """Get day/night mode with optional debug override.

    Checks DEBUG_DAY_NIGHT_MODE env var first. If set to "day" or "night",
    returns that mode. Otherwise uses actual sun calculation.

    Args:
        capture_time: UTC datetime for which to determine day/night mode
        config: Configuration object (required for sun calculation if debug override not set)

    Returns:
        True if day time, False if night time
    """
    debug_mode = os.getenv("DEBUG_DAY_NIGHT_MODE", "").lower()
    if debug_mode == "day":
        return True
    if debug_mode == "night":
        return False
    # Use actual sun calculation
    if config is None:
        return True  # Default to day if no config
    return is_day(capture_time, config.location)
