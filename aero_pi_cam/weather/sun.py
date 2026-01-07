"""Sun calculation for day/night detection.

All times are in UTC (Coordinated Universal Time) for aeronautical compliance.
No timezone conversions or daylight saving time adjustments are applied.
"""

from datetime import UTC, datetime

from suncalc import get_times  # type: ignore[import-untyped]

from ..core.config import LocationConfig


def get_sun_times(date: datetime, location: LocationConfig) -> dict[str, datetime]:
    """Get sunrise and sunset times for a given date and location.

    All times are returned in UTC (aeronautical requirement).

    Args:
        date: UTC datetime for which to calculate sun times
        location: Location configuration (latitude/longitude used for calculations)

    Returns:
        Dictionary with 'sunrise' and 'sunset' as UTC datetime objects
    """
    # Ensure input datetime is UTC (naive datetimes are assumed UTC)
    if date.tzinfo is None:
        date = date.replace(tzinfo=UTC)
    elif date.tzinfo != UTC:
        date = date.astimezone(UTC)

    times = get_times(date, location.longitude, location.latitude)
    sunrise = times["sunrise"]
    sunset = times["sunset"]

    # suncalc returns naive datetimes - treat them as UTC (astronomical calculations are in UTC)
    if sunrise.tzinfo is None:
        sunrise = sunrise.replace(tzinfo=UTC)
    elif sunrise.tzinfo != UTC:
        sunrise = sunrise.astimezone(UTC)

    if sunset.tzinfo is None:
        sunset = sunset.replace(tzinfo=UTC)
    elif sunset.tzinfo != UTC:
        sunset = sunset.astimezone(UTC)

    return {
        "sunrise": sunrise,
        "sunset": sunset,
    }


def is_day(date: datetime, location: LocationConfig) -> bool:
    """Check if current time is during daylight hours.

    All times are in UTC. The date parameter should be a UTC datetime.
    """
    times = get_sun_times(date, location)
    return times["sunrise"] <= date < times["sunset"]


def get_next_capture_interval(
    date: datetime,
    location: LocationConfig,
    day_interval_seconds: int,
    night_interval_seconds: int,
) -> int:
    """Get the appropriate capture interval based on day/night.

    All times are in UTC. The date parameter should be a UTC datetime.
    Returns interval in seconds.
    """
    return day_interval_seconds if is_day(date, location) else night_interval_seconds
