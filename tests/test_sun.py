"""Tests for sun module.

All tests use UTC timezone for aeronautical compliance.
"""

from datetime import UTC, datetime

from src.config import LocationConfig
from src.sun import get_next_capture_interval, get_sun_times, is_day


def test_get_sun_times() -> None:
    """Test that get_sun_times returns sunrise and sunset."""
    location: LocationConfig = LocationConfig(
        name="LFAS",
        latitude=48.9267952,
        longitude=-0.1477169,
    )

    date = datetime(2026, 6, 21, 12, 0, 0, tzinfo=UTC)  # Summer solstice UTC
    times = get_sun_times(date, location)

    assert "sunrise" in times
    assert "sunset" in times
    assert isinstance(times["sunrise"], datetime)
    assert isinstance(times["sunset"], datetime)
    assert times["sunset"] > times["sunrise"]


def test_is_day_during_daytime() -> None:
    """Test is_day returns True during daytime in summer."""
    location: LocationConfig = LocationConfig(
        name="LFAS",
        latitude=48.9267952,
        longitude=-0.1477169,
    )

    # June 21, 2026 at noon UTC - definitely daytime in France
    noon_in_summer = datetime(2026, 6, 21, 12, 0, 0, tzinfo=UTC)
    assert is_day(noon_in_summer, location) is True


def test_is_day_during_nighttime() -> None:
    """Test is_day returns False during nighttime."""
    location: LocationConfig = LocationConfig(
        name="LFAS",
        latitude=48.9267952,
        longitude=-0.1477169,
    )

    # January 2, 2026 at 3 AM UTC - definitely night in France
    night_time = datetime(2026, 1, 2, 3, 0, 0, tzinfo=UTC)
    assert is_day(night_time, location) is False


def test_is_day_at_midnight() -> None:
    """Test is_day returns False at midnight."""
    location: LocationConfig = LocationConfig(
        name="LFAS",
        latitude=48.9267952,
        longitude=-0.1477169,
    )

    midnight = datetime(2026, 6, 21, 0, 0, 0, tzinfo=UTC)
    assert is_day(midnight, location) is False


def test_get_next_capture_interval_day() -> None:
    """Test get_next_capture_interval returns day interval during daytime."""
    location: LocationConfig = LocationConfig(
        name="LFAS",
        latitude=48.9267952,
        longitude=-0.1477169,
    )

    day_interval = 5
    night_interval = 60

    daytime = datetime(2026, 6, 21, 12, 0, 0, tzinfo=UTC)
    interval = get_next_capture_interval(daytime, location, day_interval, night_interval)
    assert interval == day_interval


def test_get_next_capture_interval_night() -> None:
    """Test get_next_capture_interval returns night interval during nighttime."""
    location: LocationConfig = LocationConfig(
        name="LFAS",
        latitude=48.9267952,
        longitude=-0.1477169,
    )

    day_interval = 5
    night_interval = 60

    nighttime = datetime(2026, 1, 2, 3, 0, 0, tzinfo=UTC)
    interval = get_next_capture_interval(nighttime, location, day_interval, night_interval)
    assert interval == night_interval


def test_get_sun_times_with_naive_datetime() -> None:
    """Test get_sun_times handles naive datetime (assumes UTC)."""
    location: LocationConfig = LocationConfig(
        name="LFAS",
        latitude=48.9267952,
        longitude=-0.1477169,
    )

    # Naive datetime (no timezone)
    date = datetime(2026, 6, 21, 12, 0, 0)
    times = get_sun_times(date, location)

    assert "sunrise" in times
    assert "sunset" in times
    assert times["sunrise"].tzinfo is not None
    assert times["sunset"].tzinfo is not None


def test_get_sun_times_with_non_utc_timezone() -> None:
    """Test get_sun_times converts non-UTC timezone to UTC."""
    from datetime import timedelta, timezone

    location: LocationConfig = LocationConfig(
        name="LFAS",
        latitude=48.9267952,
        longitude=-0.1477169,
    )

    # Date with non-UTC timezone (e.g., EST = UTC-5)
    est = timezone(timedelta(hours=-5))
    date = datetime(2026, 6, 21, 12, 0, 0, tzinfo=est)
    times = get_sun_times(date, location)

    assert "sunrise" in times
    assert "sunset" in times
    # Times should be in UTC
    assert times["sunrise"].tzinfo == UTC
    assert times["sunset"].tzinfo == UTC


def test_get_sun_times_sunrise_non_utc() -> None:
    """Test get_sun_times handles sunrise with non-UTC timezone."""
    from datetime import timedelta, timezone
    from unittest.mock import patch

    location: LocationConfig = LocationConfig(
        name="LFAS",
        latitude=48.9267952,
        longitude=-0.1477169,
    )

    date = datetime(2026, 6, 21, 12, 0, 0, tzinfo=UTC)

    # Mock suncalc to return times with non-UTC timezone
    est = timezone(timedelta(hours=-5))
    mock_sunrise = datetime(2026, 6, 21, 7, 0, 0, tzinfo=est)
    mock_sunset = datetime(2026, 6, 21, 17, 0, 0, tzinfo=est)

    with patch("src.sun.get_times", return_value={"sunrise": mock_sunrise, "sunset": mock_sunset}):
        times = get_sun_times(date, location)

    assert times["sunrise"].tzinfo == UTC
    assert times["sunset"].tzinfo == UTC


def test_get_sun_times_sunset_non_utc() -> None:
    """Test get_sun_times handles sunset with non-UTC timezone."""
    from datetime import timedelta, timezone
    from unittest.mock import patch

    location: LocationConfig = LocationConfig(
        name="LFAS",
        latitude=48.9267952,
        longitude=-0.1477169,
    )

    date = datetime(2026, 6, 21, 12, 0, 0, tzinfo=UTC)

    # Mock suncalc to return sunset with non-UTC timezone
    est = timezone(timedelta(hours=-5))
    mock_sunrise = datetime(2026, 6, 21, 7, 0, 0, tzinfo=UTC)
    mock_sunset = datetime(2026, 6, 21, 17, 0, 0, tzinfo=est)

    with patch("src.sun.get_times", return_value={"sunrise": mock_sunrise, "sunset": mock_sunset}):
        times = get_sun_times(date, location)

    assert times["sunset"].tzinfo == UTC
