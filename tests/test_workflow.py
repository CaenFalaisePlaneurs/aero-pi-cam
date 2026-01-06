"""Tests for workflow module."""

import pytest

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
from aero_pi_cam.core.workflow import capture_and_upload


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
async def test_capture_and_upload_already_running(mock_config) -> None:
    """Test capture_and_upload skips when already running."""
    is_running_ref = {"value": True}
    camera_connected_ref = {"value": False}
    api_connected_ref = {"value": False}
    running_task_ref = {"value": None}

    await capture_and_upload(
        mock_config,
        None,
        is_running_ref,
        camera_connected_ref,
        api_connected_ref,
        running_task_ref,
    )

    # Should return early without doing anything


@pytest.mark.asyncio
async def test_capture_and_upload_no_config() -> None:
    """Test capture_and_upload skips when config is None."""
    is_running_ref = {"value": False}
    camera_connected_ref = {"value": False}
    api_connected_ref = {"value": False}
    running_task_ref = {"value": None}

    await capture_and_upload(
        None,
        None,
        is_running_ref,
        camera_connected_ref,
        api_connected_ref,
        running_task_ref,
    )

    # Should return early
