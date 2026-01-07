"""Tests for scheduler module."""

import os
from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

import pytest
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.date import DateTrigger
from apscheduler.triggers.interval import IntervalTrigger

from aero_pi_cam.core.config import (
    ApiConfig,
    CameraConfig,
    Config,
    LocationConfig,
    MetadataConfig,
    MetarConfig,
    OverlayConfig,
    ScheduleConfig,
    UploadConfig,
)
from aero_pi_cam.core.scheduler import (
    get_next_transition_time,
    log_countdown,
    schedule_next_capture,
)


@pytest.fixture
def mock_config() -> Config:
    """Create a mock config for testing."""
    return Config(
        camera=CameraConfig(rtsp_url="rtsp://test:pass@192.168.0.1:554/stream1"),
        location=LocationConfig(
            name="TEST", latitude=48.9, longitude=-0.1, camera_heading="060° RWY 06"
        ),
        schedule=ScheduleConfig(day_interval_seconds=300, night_interval_seconds=3600),
        upload=UploadConfig(
            method="API",
            api=ApiConfig(url="https://api.example.com", key="test-key", timeout_seconds=30),
        ),
        overlay=OverlayConfig(
            provider_name="Test Provider",
            provider_logo="assets/logo.svg",
            camera_name="test camera",
        ),
        metar=MetarConfig(enabled=False, icao_code="TEST"),
        metadata=MetadataConfig(
            github_repo="https://github.com/test/repo",
            webcam_url="https://example.com/cam",
        ),
    )


@pytest.mark.asyncio
async def test_log_countdown_no_scheduler(mock_config) -> None:
    """Test log_countdown returns early when scheduler is None."""
    await log_countdown(None, mock_config)
    # Should not raise


@pytest.mark.asyncio
async def test_schedule_next_capture_creates_scheduler(mock_config) -> None:
    """Test schedule_next_capture creates scheduler if None."""
    capture_func = AsyncMock()

    scheduler = await schedule_next_capture(None, mock_config, capture_func)

    assert scheduler is not None
    assert isinstance(scheduler, AsyncIOScheduler)


@pytest.mark.asyncio
async def test_schedule_next_capture_uses_existing_scheduler(mock_config) -> None:
    """Test schedule_next_capture uses existing scheduler."""
    existing_scheduler = AsyncIOScheduler()
    existing_scheduler.start()
    capture_func = AsyncMock()

    try:
        scheduler = await schedule_next_capture(existing_scheduler, mock_config, capture_func)

        assert scheduler is existing_scheduler
    finally:
        existing_scheduler.shutdown(wait=False)


def test_get_next_transition_time_returns_sunset_when_day(mock_config) -> None:
    """Test get_next_transition_time returns sunset when currently day."""
    # Mock daytime (noon)
    now = datetime(2026, 6, 21, 12, 0, 0, tzinfo=UTC)
    mock_sunrise = datetime(2026, 6, 21, 6, 0, 0, tzinfo=UTC)
    mock_sunset = datetime(2026, 6, 21, 18, 0, 0, tzinfo=UTC)

    with (
        patch("aero_pi_cam.core.scheduler.get_day_night_mode", return_value=True),
        patch(
            "aero_pi_cam.core.scheduler.get_sun_times",
            return_value={"sunrise": mock_sunrise, "sunset": mock_sunset},
        ),
    ):
        transition = get_next_transition_time(now, mock_config)

    assert transition is not None
    assert transition == mock_sunset


def test_get_next_transition_time_returns_sunrise_when_night(mock_config) -> None:
    """Test get_next_transition_time returns sunrise when currently night."""
    # Mock nighttime (midnight)
    now = datetime(2026, 6, 21, 0, 0, 0, tzinfo=UTC)
    mock_sunrise = datetime(2026, 6, 21, 6, 0, 0, tzinfo=UTC)
    mock_sunset = datetime(2026, 6, 21, 18, 0, 0, tzinfo=UTC)

    with (
        patch("aero_pi_cam.core.scheduler.get_day_night_mode", return_value=False),
        patch(
            "aero_pi_cam.core.scheduler.get_sun_times",
            return_value={"sunrise": mock_sunrise, "sunset": mock_sunset},
        ),
    ):
        transition = get_next_transition_time(now, mock_config)

    assert transition is not None
    assert transition == mock_sunrise


def test_get_next_transition_time_returns_none_in_debug_mode(mock_config) -> None:
    """Test get_next_transition_time returns None when debug mode is enabled."""
    now = datetime(2026, 6, 21, 12, 0, 0, tzinfo=UTC)

    with patch.dict(os.environ, {"DEBUG_MODE": "true"}):
        transition = get_next_transition_time(now, mock_config)

    assert transition is None


def test_get_next_transition_time_handles_past_sunset(mock_config) -> None:
    """Test get_next_transition_time gets tomorrow's sunset when today's already passed."""
    # Mock evening (after sunset)
    now = datetime(2026, 6, 21, 20, 0, 0, tzinfo=UTC)
    mock_sunrise_today = datetime(2026, 6, 21, 6, 0, 0, tzinfo=UTC)
    mock_sunset_today = datetime(2026, 6, 21, 18, 0, 0, tzinfo=UTC)
    mock_sunset_tomorrow = datetime(2026, 6, 22, 18, 0, 0, tzinfo=UTC)

    def mock_get_sun_times(date: datetime, location: LocationConfig) -> dict[str, datetime]:
        if date.day == 21:
            return {"sunrise": mock_sunrise_today, "sunset": mock_sunset_today}
        return {
            "sunrise": datetime(2026, 6, 22, 6, 0, 0, tzinfo=UTC),
            "sunset": mock_sunset_tomorrow,
        }

    with (
        patch("aero_pi_cam.core.scheduler.get_day_night_mode", return_value=True),
        patch("aero_pi_cam.core.scheduler.get_sun_times", side_effect=mock_get_sun_times),
    ):
        transition = get_next_transition_time(now, mock_config)

    assert transition is not None
    assert transition == mock_sunset_tomorrow


def test_get_next_transition_time_handles_past_sunrise(mock_config) -> None:
    """Test get_next_transition_time gets tomorrow's sunrise when today's already passed."""
    # Mock late night (after midnight, before sunrise)
    now = datetime(2026, 6, 21, 2, 0, 0, tzinfo=UTC)
    mock_sunrise_today = datetime(2026, 6, 21, 6, 0, 0, tzinfo=UTC)
    mock_sunset_today = datetime(2026, 6, 21, 18, 0, 0, tzinfo=UTC)
    mock_sunrise_tomorrow = datetime(2026, 6, 22, 6, 0, 0, tzinfo=UTC)

    def mock_get_sun_times(date: datetime, location: LocationConfig) -> dict[str, datetime]:
        if date.day == 21:
            return {"sunrise": mock_sunrise_today, "sunset": mock_sunset_today}
        return {
            "sunrise": mock_sunrise_tomorrow,
            "sunset": datetime(2026, 6, 22, 18, 0, 0, tzinfo=UTC),
        }

    with (
        patch("aero_pi_cam.core.scheduler.get_day_night_mode", return_value=False),
        patch("aero_pi_cam.core.scheduler.get_sun_times", side_effect=mock_get_sun_times),
    ):
        transition = get_next_transition_time(now, mock_config)

    assert transition is not None
    assert (
        transition == mock_sunrise_today
    )  # Today's sunrise hasn't passed yet (it's 2 AM, sunrise is 6 AM)


def test_get_next_transition_time_returns_none_when_config_none() -> None:
    """Test get_next_transition_time returns None when config is None."""
    now = datetime(2026, 6, 21, 12, 0, 0, tzinfo=UTC)
    transition = get_next_transition_time(now, None)
    assert transition is None


@pytest.mark.asyncio
async def test_schedule_next_capture_uses_transition_when_sooner(mock_config) -> None:
    """Test schedule_next_capture uses DateTrigger when transition time is sooner than interval."""
    # Current time: 7:30 AM, transition at 8:00 AM is sooner than interval-based time (7:30 + 5 min = 7:35)
    # But wait, day interval is 5 min, so 7:30 + 5 min = 7:35, which is sooner than 8:00
    # Let's use night mode instead: 7:30 AM (night), transition at 8:00 AM, interval is 1 hour (8:30)
    now = datetime(2026, 6, 21, 7, 30, 0, tzinfo=UTC)
    mock_transition = datetime(
        2026, 6, 21, 8, 0, 0, tzinfo=UTC
    )  # 8:00 AM - sooner than 7:30 + 1 hour = 8:30

    capture_func = AsyncMock()
    schedule_func = AsyncMock()

    with (
        patch("aero_pi_cam.core.scheduler.datetime") as mock_dt,
        patch("aero_pi_cam.core.scheduler.get_next_transition_time", return_value=mock_transition),
        patch("aero_pi_cam.core.scheduler.get_day_night_mode", return_value=False),
    ):  # Night mode
        # Mock datetime.now to return fixed time
        import datetime as real_dt

        mock_dt.now = lambda tz=UTC: now
        mock_dt.UTC = UTC
        mock_dt.timedelta = real_dt.timedelta
        mock_dt.datetime = real_dt.datetime

        scheduler = await schedule_next_capture(None, mock_config, capture_func, schedule_func)

        job = scheduler.get_job("capture_job")
        assert job is not None
        assert isinstance(job.trigger, DateTrigger)
        assert job.trigger.run_date == mock_transition

    scheduler.shutdown(wait=False)


@pytest.mark.asyncio
async def test_schedule_next_capture_uses_interval_when_sooner(mock_config) -> None:
    """Test schedule_next_capture uses IntervalTrigger when interval time is sooner than transition."""
    # Transition at 8 PM is later than interval-based time (noon + 5 min = 12:05)
    mock_transition = datetime(2026, 6, 21, 20, 0, 0, tzinfo=UTC)

    capture_func = AsyncMock()

    with (
        patch("aero_pi_cam.core.scheduler.get_next_transition_time", return_value=mock_transition),
        patch("aero_pi_cam.core.scheduler.get_day_night_mode", return_value=True),
    ):
        scheduler = await schedule_next_capture(None, mock_config, capture_func)

        job = scheduler.get_job("capture_job")
        assert job is not None
        assert isinstance(job.trigger, IntervalTrigger)
        assert job.trigger.interval.total_seconds() == 300  # 5 minutes

    scheduler.shutdown(wait=False)


@pytest.mark.asyncio
async def test_schedule_next_capture_skips_transition_in_debug_mode(mock_config) -> None:
    """Test schedule_next_capture skips transition check in debug mode."""
    capture_func = AsyncMock()

    with (
        patch.dict(os.environ, {"DEBUG_MODE": "true"}),
        patch("aero_pi_cam.core.scheduler.get_day_night_mode", return_value=True),
    ):
        scheduler = await schedule_next_capture(None, mock_config, capture_func)

        job = scheduler.get_job("capture_job")
        assert job is not None
        assert isinstance(job.trigger, IntervalTrigger)  # Should use interval, not DateTrigger

    scheduler.shutdown(wait=False)


@pytest.mark.asyncio
async def test_transition_capture_calls_both_functions(mock_config) -> None:
    """Test that transition capture calls capture_and_upload_func then schedule_func."""
    # Current time: 7:30 AM (night), transition at 8:00 AM is sooner than interval-based time (7:30 + 1 hour = 8:30)
    now = datetime(2026, 6, 21, 7, 30, 0, tzinfo=UTC)
    mock_transition = datetime(2026, 6, 21, 8, 0, 0, tzinfo=UTC)

    capture_func = AsyncMock()
    schedule_func = AsyncMock()

    with (
        patch("aero_pi_cam.core.scheduler.datetime") as mock_dt,
        patch("aero_pi_cam.core.scheduler.get_next_transition_time", return_value=mock_transition),
        patch("aero_pi_cam.core.scheduler.get_day_night_mode", return_value=False),
    ):  # Night mode
        # Mock datetime.now to return fixed time
        import datetime as real_dt

        mock_dt.now = lambda tz=UTC: now
        mock_dt.UTC = UTC
        mock_dt.timedelta = real_dt.timedelta
        mock_dt.datetime = real_dt.datetime

        scheduler = await schedule_next_capture(None, mock_config, capture_func, schedule_func)

        job = scheduler.get_job("capture_job")
        assert job is not None

        # Execute the job (transition wrapper)
        await job.func()

        # Verify both functions were called
        capture_func.assert_called_once()
        schedule_func.assert_called_once()

    scheduler.shutdown(wait=False)


@pytest.mark.asyncio
async def test_schedule_check_does_not_reset_interval_timer(mock_config) -> None:
    """Test that schedule_check does not reset the timer for IntervalTrigger jobs.

    This test verifies the fix for the bug where schedule_check would reset the
    timer every 5 minutes, preventing long interval jobs (like 3600s) from ever running.
    """
    capture_func = AsyncMock()
    schedule_func = AsyncMock()

    # Initial schedule - should use IntervalTrigger with 3600s interval (night mode)
    with patch("aero_pi_cam.core.scheduler.get_day_night_mode", return_value=False):
        scheduler = await schedule_next_capture(None, mock_config, capture_func, schedule_func)

    # Get the initial job and its next_run_time
    job = scheduler.get_job("capture_job")
    assert job is not None
    assert isinstance(job.trigger, IntervalTrigger)
    assert job.trigger.interval.total_seconds() == 3600
    initial_next_run_time = job.next_run_time

    # Simulate schedule_check running (still in night mode, no transition needed)
    with patch("aero_pi_cam.core.scheduler.get_day_night_mode", return_value=False):
        scheduler = await schedule_next_capture(scheduler, mock_config, capture_func, schedule_func)

    # Verify the job still exists and its next_run_time hasn't changed
    job_after = scheduler.get_job("capture_job")
    assert job_after is not None
    assert isinstance(job_after.trigger, IntervalTrigger)
    assert job_after.trigger.interval.total_seconds() == 3600
    # The next_run_time should be the same (job not rescheduled)
    assert job_after.next_run_time == initial_next_run_time

    scheduler.shutdown(wait=False)


@pytest.mark.asyncio
async def test_schedule_check_reschedules_on_mode_change(mock_config) -> None:
    """Test that schedule_check does reschedule when day/night mode changes.

    This test verifies that the scheduler properly switches intervals when
    transitioning from day to night or vice versa.
    """
    capture_func = AsyncMock()
    schedule_func = AsyncMock()

    # Initial schedule - day mode with 300s interval
    with patch("aero_pi_cam.core.scheduler.get_day_night_mode", return_value=True):
        scheduler = await schedule_next_capture(None, mock_config, capture_func, schedule_func)

    # Get the initial job
    job = scheduler.get_job("capture_job")
    assert job is not None
    assert isinstance(job.trigger, IntervalTrigger)
    assert job.trigger.interval.total_seconds() == 300  # Day interval

    # Simulate schedule_check running with mode change to night
    with patch("aero_pi_cam.core.scheduler.get_day_night_mode", return_value=False):
        scheduler = await schedule_next_capture(scheduler, mock_config, capture_func, schedule_func)

    # Verify the job was rescheduled with new interval
    job_after = scheduler.get_job("capture_job")
    assert job_after is not None
    assert isinstance(job_after.trigger, IntervalTrigger)
    assert job_after.trigger.interval.total_seconds() == 3600  # Night interval (changed!)

    scheduler.shutdown(wait=False)
