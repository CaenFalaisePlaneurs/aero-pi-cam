"""Tests for day_night module."""

from datetime import UTC, datetime

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
from aero_pi_cam.weather.day_night import get_day_night_mode


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


def test_get_day_night_mode_forced_day(monkeypatch, mock_config) -> None:
    """Test get_day_night_mode with DEBUG_DAY_NIGHT_MODE=day."""
    monkeypatch.setenv("DEBUG_DAY_NIGHT_MODE", "day")

    capture_time = datetime(2026, 1, 2, 3, 0, 0, tzinfo=UTC)  # Night time
    result = get_day_night_mode(capture_time, mock_config)

    assert result is True  # Should be forced to day


def test_get_day_night_mode_forced_night(monkeypatch, mock_config) -> None:
    """Test get_day_night_mode with DEBUG_DAY_NIGHT_MODE=night."""
    monkeypatch.setenv("DEBUG_DAY_NIGHT_MODE", "night")

    capture_time = datetime(2026, 6, 21, 12, 0, 0, tzinfo=UTC)  # Day time
    result = get_day_night_mode(capture_time, mock_config)

    assert result is False  # Should be forced to night


def test_get_day_night_mode_actual_day(monkeypatch, mock_config) -> None:
    """Test get_day_night_mode uses actual sun calculation when no override."""
    monkeypatch.delenv("DEBUG_DAY_NIGHT_MODE", raising=False)

    capture_time = datetime(2026, 6, 21, 12, 0, 0, tzinfo=UTC)  # Day time
    result = get_day_night_mode(capture_time, mock_config)

    assert result is True  # Should be day based on actual sun calculation


def test_get_day_night_mode_actual_night(monkeypatch, mock_config) -> None:
    """Test get_day_night_mode uses actual sun calculation for night."""
    monkeypatch.delenv("DEBUG_DAY_NIGHT_MODE", raising=False)

    capture_time = datetime(2026, 1, 2, 3, 0, 0, tzinfo=UTC)  # Night time
    result = get_day_night_mode(capture_time, mock_config)

    assert result is False  # Should be night based on actual sun calculation


def test_get_day_night_mode_no_config_defaults_to_day(monkeypatch) -> None:
    """Test get_day_night_mode defaults to day when no config."""
    monkeypatch.delenv("DEBUG_DAY_NIGHT_MODE", raising=False)

    capture_time = datetime(2026, 1, 2, 3, 0, 0, tzinfo=UTC)
    result = get_day_night_mode(capture_time, None)

    assert result is True  # Should default to day
