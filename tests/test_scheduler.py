"""Tests for scheduler module."""

from unittest.mock import AsyncMock

import pytest
from apscheduler.schedulers.asyncio import AsyncIOScheduler

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
from aero_pi_cam.core.scheduler import log_countdown, schedule_next_capture


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
