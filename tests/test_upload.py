"""Tests for upload module."""

from unittest.mock import AsyncMock, MagicMock, patch

import asyncssh
import pytest

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
from aero_pi_cam.upload import ApiUploader, SftpUploader, create_uploader, upload_image


# Helper function to create minimal config for testing
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


@pytest.mark.asyncio
async def test_upload_success() -> None:
    """Test successful upload with 201 response."""
    api_config = ApiConfig(
        url="https://api.example.com/api/webcam/image",
        key="test-api-key",
        timeout_seconds=30,
    )
    config = _create_test_config(api_config=api_config)

    metadata = {
        "timestamp": "2026-01-02T15:30:00Z",
        "location": "LFAS",
        "is_day": "true",
    }

    response_body = {
        "id": "test-uuid",
        "received_at": "2026-01-02T15:30:05Z",
        "size_bytes": 245000,
    }

    mock_response = AsyncMock()
    mock_response.status_code = 201
    mock_response.json = lambda: response_body

    mock_client = AsyncMock()
    mock_client.put = AsyncMock(return_value=mock_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch("httpx.AsyncClient", return_value=mock_client):
        result = await upload_image(b"fake-jpeg-data", metadata, config)

    assert result.success is True
    assert result.status_code == 201
    assert result.response_body == response_body


@pytest.mark.asyncio
async def test_upload_sends_correct_headers() -> None:
    """Test that upload sends correct headers."""
    api_config = ApiConfig(
        url="https://api.example.com/api/webcam/image",
        key="test-api-key",
        timeout_seconds=30,
    )
    config = _create_test_config(api_config=api_config)

    metadata = {
        "timestamp": "2026-01-02T15:30:00Z",
        "location": "LFAS",
        "is_day": "true",
    }

    mock_response = AsyncMock()
    mock_response.status_code = 201
    mock_response.json = lambda: {"id": "test", "received_at": "", "size_bytes": 0}

    mock_client = AsyncMock()
    mock_client.put = AsyncMock(return_value=mock_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch("httpx.AsyncClient", return_value=mock_client):
        await upload_image(b"fake-jpeg-data", metadata, config)

        call_kwargs = mock_client.put.call_args[1]
        assert call_kwargs["headers"]["Authorization"] == "Bearer test-api-key"
        assert call_kwargs["headers"]["Content-Type"] == "image/jpeg"
        assert call_kwargs["headers"]["X-Capture-Timestamp"] == "2026-01-02T15:30:00Z"
        assert call_kwargs["headers"]["X-Location"] == "LFAS"
        assert call_kwargs["headers"]["X-Is-Day"] == "true"


@pytest.mark.asyncio
async def test_upload_4xx_no_retry() -> None:
    """Test that 4xx errors don't trigger retry."""
    api_config = ApiConfig(
        url="https://api.example.com/api/webcam/image",
        key="test-api-key",
        timeout_seconds=30,
    )
    config = _create_test_config(api_config=api_config)

    metadata = {
        "timestamp": "2026-01-02T15:30:00Z",
        "location": "LFAS",
        "is_day": "true",
    }

    mock_response = AsyncMock()
    mock_response.status_code = 400
    mock_response.text = "Bad Request"

    mock_client = AsyncMock()
    mock_client.put = AsyncMock(return_value=mock_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch("httpx.AsyncClient", return_value=mock_client):
        result = await upload_image(b"fake-jpeg-data", metadata, config)

    assert result.success is False
    assert result.status_code == 400
    assert "HTTP 400" in result.error


@pytest.mark.asyncio
async def test_upload_retry_on_5xx() -> None:
    """Test retry on 5xx response."""
    api_config = ApiConfig(
        url="https://api.example.com/api/webcam/image",
        key="test-api-key",
        timeout_seconds=30,
    )
    config = _create_test_config(api_config=api_config)

    metadata = {
        "timestamp": "2026-01-02T15:30:00Z",
        "location": "LFAS",
        "is_day": "true",
    }

    mock_response_500 = AsyncMock()
    mock_response_500.status_code = 500
    mock_response_500.text = "Internal Server Error"

    mock_response_201 = AsyncMock()
    mock_response_201.status_code = 201
    mock_response_201.json = lambda: {"id": "test", "received_at": "", "size_bytes": 0}

    mock_client = AsyncMock()
    mock_client.put = AsyncMock(side_effect=[mock_response_500, mock_response_201])
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch("httpx.AsyncClient", return_value=mock_client):
        result = await upload_image(b"fake-jpeg-data", metadata, config)

    assert result.success is True


@pytest.mark.asyncio
async def test_upload_retry_on_429() -> None:
    """Test retry on 429 response."""
    api_config = ApiConfig(
        url="https://api.example.com/api/webcam/image",
        key="test-api-key",
        timeout_seconds=30,
    )
    config = _create_test_config(api_config=api_config)

    metadata = {
        "timestamp": "2026-01-02T15:30:00Z",
        "location": "LFAS",
        "is_day": "true",
    }

    mock_response_429 = AsyncMock()
    mock_response_429.status_code = 429
    mock_response_429.text = "Too Many Requests"

    mock_response_201 = AsyncMock()
    mock_response_201.status_code = 201
    mock_response_201.json = lambda: {"id": "test", "received_at": "", "size_bytes": 0}

    mock_client = AsyncMock()
    mock_client.put = AsyncMock(side_effect=[mock_response_429, mock_response_201])
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch("httpx.AsyncClient", return_value=mock_client):
        result = await upload_image(b"fake-jpeg-data", metadata, config)

    assert result.success is True


@pytest.mark.asyncio
async def test_upload_fails_after_max_retries() -> None:
    """Test that upload fails after max retries."""
    api_config = ApiConfig(
        url="https://api.example.com/api/webcam/image",
        key="test-api-key",
        timeout_seconds=30,
    )
    config = _create_test_config(api_config=api_config)

    metadata = {
        "timestamp": "2026-01-02T15:30:00Z",
        "location": "LFAS",
        "is_day": "true",
    }

    mock_response = AsyncMock()
    mock_response.status_code = 500
    mock_response.text = "Internal Server Error"

    mock_client = AsyncMock()
    mock_client.put = AsyncMock(return_value=mock_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch("httpx.AsyncClient", return_value=mock_client):
        result = await upload_image(b"fake-jpeg-data", metadata, config)

    assert result.success is False
    assert "All 3 upload attempts failed" in result.error


@pytest.mark.asyncio
async def test_upload_timeout() -> None:
    """Test upload timeout handling."""
    import httpx

    api_config = ApiConfig(
        url="https://api.example.com/api/webcam/image",
        key="test-api-key",
        timeout_seconds=30,
    )
    config = _create_test_config(api_config=api_config)

    metadata = {
        "timestamp": "2026-01-02T15:30:00Z",
        "location": "LFAS",
        "is_day": "true",
    }

    mock_client = AsyncMock()
    mock_client.put = AsyncMock(side_effect=httpx.TimeoutException("Request timeout"))
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch("httpx.AsyncClient", return_value=mock_client):
        result = await upload_image(b"fake-jpeg-data", metadata, config)

    assert result.success is False
    assert "timeout" in result.error.lower()


@pytest.mark.asyncio
async def test_upload_cancelled_during_request() -> None:
    """Test upload cancellation during request."""
    import asyncio

    api_config = ApiConfig(
        url="https://api.example.com/api/webcam/image",
        key="test-api-key",
        timeout_seconds=30,
    )
    config = _create_test_config(api_config=api_config)

    metadata = {
        "timestamp": "2026-01-02T15:30:00Z",
        "location": "LFAS",
        "is_day": "true",
    }

    mock_client = AsyncMock()
    mock_client.put = AsyncMock(side_effect=asyncio.CancelledError())
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch("httpx.AsyncClient", return_value=mock_client):
        result = await upload_image(b"fake-jpeg-data", metadata, config)

    assert result.success is False
    assert "cancelled" in result.error.lower()


@pytest.mark.asyncio
async def test_upload_cancelled_during_backoff() -> None:
    """Test upload cancellation during backoff sleep."""
    import asyncio

    api_config = ApiConfig(
        url="https://api.example.com/api/webcam/image",
        key="test-api-key",
        timeout_seconds=30,
    )
    config = _create_test_config(api_config=api_config)

    metadata = {
        "timestamp": "2026-01-02T15:30:00Z",
        "location": "LFAS",
        "is_day": "true",
    }

    mock_response = AsyncMock()
    mock_response.status_code = 500
    mock_response.text = "Internal Server Error"

    mock_client = AsyncMock()
    mock_client.put = AsyncMock(return_value=mock_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with (
        patch("httpx.AsyncClient", return_value=mock_client),
        patch("asyncio.sleep", side_effect=asyncio.CancelledError()),
    ):
        result = await upload_image(b"fake-jpeg-data", metadata, config)

    assert result.success is False
    assert "cancelled" in result.error.lower()


@pytest.mark.asyncio
async def test_upload_request_error() -> None:
    """Test upload handles RequestError."""
    import httpx

    api_config = ApiConfig(
        url="https://api.example.com/api/webcam/image",
        key="test-api-key",
        timeout_seconds=30,
    )
    config = _create_test_config(api_config=api_config)

    metadata = {
        "timestamp": "2026-01-02T15:30:00Z",
        "location": "LFAS",
        "is_day": "true",
    }

    mock_client = AsyncMock()
    mock_client.put = AsyncMock(side_effect=httpx.RequestError("Connection error"))
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch("httpx.AsyncClient", return_value=mock_client):
        result = await upload_image(b"fake-jpeg-data", metadata, config)

    assert result.success is False
    assert "Connection error" in result.error


# Tests for ApiUploader
@pytest.mark.asyncio
async def test_api_uploader_success() -> None:
    """Test ApiUploader successful upload."""
    api_config = ApiConfig(
        url="https://api.example.com/api/webcam/image",
        key="test-api-key",
        timeout_seconds=30,
    )
    config = _create_test_config(api_config=api_config)

    metadata = {
        "timestamp": "2026-01-02T15:30:00Z",
        "location": "TEST",
        "is_day": "true",
    }

    response_body = {
        "id": "test-uuid",
        "received_at": "2026-01-02T15:30:05Z",
        "size_bytes": 245000,
    }

    mock_response = AsyncMock()
    mock_response.status_code = 201
    mock_response.json = lambda: response_body

    mock_client = AsyncMock()
    mock_client.put = AsyncMock(return_value=mock_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    uploader = ApiUploader(api_config)
    with patch("httpx.AsyncClient", return_value=mock_client):
        result = await uploader.upload(b"fake-jpeg-data", metadata, config)

    assert result.success is True
    assert result.status_code == 201
    assert result.response_body == response_body


# Tests for SftpUploader
@pytest.mark.asyncio
async def test_sftp_uploader_success() -> None:
    """Test SftpUploader successful upload."""
    sftp_config = SftpConfig(
        host="test.example.com",
        port=22,
        user="testuser",
        password="testpass",
        remote_path="/test/path",
        timeout_seconds=30,
    )
    config = _create_test_config(upload_method="SFTP", sftp_config=sftp_config)

    metadata = {
        "timestamp": "2026-01-02T15:30:00Z",
        "location": "TEST",
        "is_day": "true",
    }

    # Mock SFTP connection and file operations
    mock_file = MockFileContextManager()

    mock_sftp = AsyncMock()
    # listdir succeeds - directory exists, so makedirs won't be called
    mock_sftp.listdir = AsyncMock(return_value=[])
    mock_sftp.makedirs = AsyncMock()
    # sftp.open() returns an async context manager (not a coroutine)
    mock_sftp.open = MagicMock(return_value=mock_file)
    mock_sftp.__aenter__ = AsyncMock(return_value=mock_sftp)
    mock_sftp.__aexit__ = AsyncMock(return_value=None)

    # start_sftp_client() returns an async context manager
    mock_sftp_client_cm = AsyncMock()
    mock_sftp_client_cm.__aenter__ = AsyncMock(return_value=mock_sftp)
    mock_sftp_client_cm.__aexit__ = AsyncMock(return_value=None)

    mock_conn = AsyncMock()
    mock_conn.start_sftp_client = MagicMock(return_value=mock_sftp_client_cm)
    mock_conn.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_conn.__aexit__ = AsyncMock(return_value=None)

    uploader = SftpUploader(sftp_config)
    with patch("asyncssh.connect", return_value=mock_conn):
        result = await uploader.upload(b"fake-jpeg-data", metadata, config)

    assert result.success is True
    # Directory exists, so makedirs should not be called
    mock_sftp.makedirs.assert_not_called()
    mock_file.write.assert_called_once_with(b"fake-jpeg-data")


@pytest.mark.asyncio
async def test_sftp_uploader_connection_failure() -> None:
    """Test SftpUploader connection failure."""
    sftp_config = SftpConfig(
        host="test.example.com",
        port=22,
        user="testuser",
        password="testpass",
        remote_path="/test/path",
        timeout_seconds=30,
    )
    config = _create_test_config(upload_method="SFTP", sftp_config=sftp_config)

    metadata = {
        "timestamp": "2026-01-02T15:30:00Z",
        "location": "TEST",
        "is_day": "true",
    }

    uploader = SftpUploader(sftp_config)
    # Create a proper asyncssh.Error instance
    error = asyncssh.Error("Connection failed", "CONNECTION_ERROR")
    with patch("asyncssh.connect", side_effect=error):
        result = await uploader.upload(b"fake-jpeg-data", metadata, config)

    assert result.success is False
    assert "SFTP error" in result.error


@pytest.mark.asyncio
async def test_sftp_uploader_timeout() -> None:
    """Test SftpUploader timeout handling."""
    import asyncio

    sftp_config = SftpConfig(
        host="test.example.com",
        port=22,
        user="testuser",
        password="testpass",
        remote_path="/test/path",
        timeout_seconds=1,
    )
    config = _create_test_config(upload_method="SFTP", sftp_config=sftp_config)

    metadata = {
        "timestamp": "2026-01-02T15:30:00Z",
        "location": "TEST",
        "is_day": "true",
    }

    async def _slow_operation() -> None:
        await asyncio.sleep(2)

    uploader = SftpUploader(sftp_config)
    with patch("asyncssh.connect", side_effect=_slow_operation):
        result = await uploader.upload(b"fake-jpeg-data", metadata, config)

    assert result.success is False
    assert "timeout" in result.error.lower()


@pytest.mark.asyncio
async def test_sftp_uploader_directory_creation_failure() -> None:
    """Test SftpUploader directory creation failure."""
    sftp_config = SftpConfig(
        host="test.example.com",
        port=22,
        user="testuser",
        password="testpass",
        remote_path="/test/path",
        timeout_seconds=30,
    )
    config = _create_test_config(upload_method="SFTP", sftp_config=sftp_config)

    metadata = {
        "timestamp": "2026-01-02T15:30:00Z",
        "location": "TEST",
        "is_day": "true",
    }

    mock_sftp = AsyncMock()
    # listdir fails - directory doesn't exist, so we'll try to create it
    mock_sftp.listdir = AsyncMock(side_effect=FileNotFoundError("No such file"))
    # makedirs fails with permission denied
    mock_sftp.makedirs = AsyncMock(side_effect=Exception("Permission denied"))
    mock_sftp.open = MagicMock()  # Not used in this test, but needs to exist
    mock_sftp.__aenter__ = AsyncMock(return_value=mock_sftp)
    mock_sftp.__aexit__ = AsyncMock(return_value=None)

    # start_sftp_client() returns an async context manager
    mock_sftp_client_cm = AsyncMock()
    mock_sftp_client_cm.__aenter__ = AsyncMock(return_value=mock_sftp)
    mock_sftp_client_cm.__aexit__ = AsyncMock(return_value=None)

    mock_conn = AsyncMock()
    mock_conn.start_sftp_client = MagicMock(return_value=mock_sftp_client_cm)
    mock_conn.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_conn.__aexit__ = AsyncMock(return_value=None)

    uploader = SftpUploader(sftp_config)
    with patch("asyncssh.connect", return_value=mock_conn):
        result = await uploader.upload(b"fake-jpeg-data", metadata, config)

    assert result.success is False
    assert "Failed to create remote directory" in result.error


@pytest.mark.asyncio
async def test_sftp_uploader_file_write_failure() -> None:
    """Test SftpUploader file write failure."""
    sftp_config = SftpConfig(
        host="test.example.com",
        port=22,
        user="testuser",
        password="testpass",
        remote_path="/test/path",
        timeout_seconds=30,
    )
    config = _create_test_config(upload_method="SFTP", sftp_config=sftp_config)

    metadata = {
        "timestamp": "2026-01-02T15:30:00Z",
        "location": "TEST",
        "is_day": "true",
    }

    # Create a proper async context manager for the file that raises on write
    mock_file = MockFileContextManager(write_side_effect=Exception("Disk full"))

    mock_sftp = AsyncMock()
    mock_sftp.makedirs = AsyncMock()
    # sftp.open() returns an async context manager (not a coroutine)
    mock_sftp.open = MagicMock(return_value=mock_file)
    mock_sftp.__aenter__ = AsyncMock(return_value=mock_sftp)
    mock_sftp.__aexit__ = AsyncMock(return_value=None)

    # start_sftp_client() returns an async context manager
    mock_sftp_client_cm = AsyncMock()
    mock_sftp_client_cm.__aenter__ = AsyncMock(return_value=mock_sftp)
    mock_sftp_client_cm.__aexit__ = AsyncMock(return_value=None)

    mock_conn = AsyncMock()
    mock_conn.start_sftp_client = MagicMock(return_value=mock_sftp_client_cm)
    mock_conn.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_conn.__aexit__ = AsyncMock(return_value=None)

    uploader = SftpUploader(sftp_config)
    with patch("asyncssh.connect", return_value=mock_conn):
        result = await uploader.upload(b"fake-jpeg-data", metadata, config)

    assert result.success is False
    assert "Failed to write file" in result.error


# Tests for factory function
def test_create_uploader_api() -> None:
    """Test factory creates ApiUploader for API method."""
    api_config = ApiConfig(
        url="https://api.example.com/api/webcam/image",
        key="test-api-key",
        timeout_seconds=30,
    )
    config = _create_test_config(upload_method="API", api_config=api_config)

    uploader = create_uploader(config)
    assert isinstance(uploader, ApiUploader)
    assert uploader.api_config == api_config


def test_create_uploader_sftp() -> None:
    """Test factory creates SftpUploader for SFTP method."""
    sftp_config = SftpConfig(
        host="test.example.com",
        port=22,
        user="testuser",
        password="testpass",
        remote_path="/test/path",
        timeout_seconds=30,
    )
    config = _create_test_config(upload_method="SFTP", sftp_config=sftp_config)

    uploader = create_uploader(config)
    assert isinstance(uploader, SftpUploader)
    assert uploader.sftp_config == sftp_config


def test_create_uploader_invalid_method() -> None:
    """Test factory raises error for invalid upload method."""
    api_config = ApiConfig(
        url="https://api.example.com/api/webcam/image",
        key="test-api-key",
        timeout_seconds=30,
    )
    config = _create_test_config(upload_method="API", api_config=api_config)
    # Use model_construct to bypass validation and set invalid upload_method
    config_dict = config.model_dump()
    config_dict["upload_method"] = "INVALID"  # type: ignore[assignment]
    config = Config.model_construct(**config_dict)

    with pytest.raises(ValueError, match="Unknown upload method"):
        create_uploader(config)


def test_create_uploader_missing_api_config() -> None:
    """Test factory raises error when API config is missing."""
    # Create config with API method but no api config
    # Use model_construct to bypass validation
    base_config = _create_test_config(
        upload_method="API",
        api_config=ApiConfig(
            url="https://api.example.com/api/webcam/image",
            key="test-api-key",
            timeout_seconds=30,
        ),
    )
    config_dict = base_config.model_dump()
    config_dict["api"] = None
    config = Config.model_construct(**config_dict)

    with pytest.raises(ValueError, match="api configuration is required"):
        create_uploader(config)


def test_create_uploader_missing_sftp_config() -> None:
    """Test factory raises error when SFTP config is missing."""
    # Create config with SFTP method but no sftp config
    # Use model_construct to bypass validation
    base_config = _create_test_config(
        upload_method="SFTP",
        sftp_config=SftpConfig(
            host="test.example.com",
            port=22,
            user="testuser",
            password="testpass",
            remote_path="/test/path",
            timeout_seconds=30,
        ),
    )
    config_dict = base_config.model_dump()
    config_dict["sftp"] = None
    config = Config.model_construct(**config_dict)

    with pytest.raises(ValueError, match="sftp configuration is required"):
        create_uploader(config)


# Tests for upload_image with config
@pytest.mark.asyncio
async def test_upload_image_with_config_api() -> None:
    """Test upload_image with config for API method."""
    api_config = ApiConfig(
        url="https://api.example.com/api/webcam/image",
        key="test-api-key",
        timeout_seconds=30,
    )
    config = _create_test_config(upload_method="API", api_config=api_config)

    metadata = {
        "timestamp": "2026-01-02T15:30:00Z",
        "location": "TEST",
        "is_day": "true",
    }

    response_body = {
        "id": "test-uuid",
        "received_at": "2026-01-02T15:30:05Z",
        "size_bytes": 245000,
    }

    mock_response = AsyncMock()
    mock_response.status_code = 201
    mock_response.json = lambda: response_body

    mock_client = AsyncMock()
    mock_client.put = AsyncMock(return_value=mock_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch("httpx.AsyncClient", return_value=mock_client):
        result = await upload_image(b"fake-jpeg-data", metadata, config=config)

    assert result.success is True
    assert result.status_code == 201


@pytest.mark.asyncio
async def test_upload_image_with_config_sftp() -> None:
    """Test upload_image with config for SFTP method."""
    sftp_config = SftpConfig(
        host="test.example.com",
        port=22,
        user="testuser",
        password="testpass",
        remote_path="/test/path",
        timeout_seconds=30,
    )
    config = _create_test_config(upload_method="SFTP", sftp_config=sftp_config)

    metadata = {
        "timestamp": "2026-01-02T15:30:00Z",
        "location": "TEST",
        "is_day": "true",
    }

    # Create a proper async context manager for the file
    mock_file = MockFileContextManager()

    mock_sftp = AsyncMock()
    mock_sftp.makedirs = AsyncMock()
    # sftp.open() returns an async context manager (not a coroutine)
    mock_sftp.open = MagicMock(return_value=mock_file)
    mock_sftp.__aenter__ = AsyncMock(return_value=mock_sftp)
    mock_sftp.__aexit__ = AsyncMock(return_value=None)

    # start_sftp_client() returns an async context manager
    mock_sftp_client_cm = AsyncMock()
    mock_sftp_client_cm.__aenter__ = AsyncMock(return_value=mock_sftp)
    mock_sftp_client_cm.__aexit__ = AsyncMock(return_value=None)

    mock_conn = AsyncMock()
    mock_conn.start_sftp_client = MagicMock(return_value=mock_sftp_client_cm)
    mock_conn.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_conn.__aexit__ = AsyncMock(return_value=None)

    with patch("asyncssh.connect", return_value=mock_conn):
        result = await upload_image(b"fake-jpeg-data", metadata, config=config)

    assert result.success is True
