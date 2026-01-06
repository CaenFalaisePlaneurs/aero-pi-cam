"""Shared test fixtures and helpers."""

from unittest.mock import AsyncMock

from aero_pi_cam.config import (
    ApiConfig,
    CameraConfig,
    Config,
    LocationConfig,
    MetadataConfig,
    MetarConfig,
    OverlayConfig,
    ScheduleConfig,
    SftpConfig,
)


def _create_test_config(
    upload_method: str = "API",
    api_config: ApiConfig | None = None,
    sftp_config: SftpConfig | None = None,
) -> Config:
    """Create a minimal test config."""
    return Config(
        camera=CameraConfig(rtsp_url="rtsp://test"),
        location=LocationConfig(
            name="TEST", latitude=48.9, longitude=-0.1, camera_heading="060° RWY 06"
        ),
        schedule=ScheduleConfig(day_interval_minutes=5, night_interval_minutes=60),
        upload_method=upload_method,
        api=api_config,
        sftp=sftp_config,
        overlay=OverlayConfig(
            provider_name="Test",
            provider_logo="test.svg",
            camera_name="test_camera",
        ),
        metar=MetarConfig(icao_code="TEST"),
        metadata=MetadataConfig(
            github_repo="https://github.com/test",
            webcam_url="https://test.com",
        ),
    )


class MockFileContextManager:
    """Mock async context manager for SFTP file operations."""

    def __init__(self, write_side_effect: Exception | None = None) -> None:
        """Initialize mock file context manager.

        Args:
            write_side_effect: Optional exception to raise on write
        """
        self.write = AsyncMock(side_effect=write_side_effect)

    async def __aenter__(self) -> "MockFileContextManager":
        """Enter async context."""
        return self

    async def __aexit__(self, *args: object) -> None:
        """Exit async context."""
        return None
