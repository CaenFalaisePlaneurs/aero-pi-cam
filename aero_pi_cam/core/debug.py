"""Debug utilities for conditional printing."""

import os


def _is_debug_mode() -> bool:
    """Check if debug mode is enabled."""
    return os.getenv("DEBUG_MODE", "false").lower() == "true"


def debug_print(*args: object, **kwargs: object) -> None:
    """Print only if DEBUG_MODE is enabled."""
    if _is_debug_mode():
        print(*args, **kwargs)  # type: ignore[call-overload]
