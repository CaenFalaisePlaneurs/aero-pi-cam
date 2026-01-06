"""Tests for SFTP upload functionality."""

from unittest.mock import AsyncMock, MagicMock, patch

import asyncssh
import pytest

from aero_pi_cam.config import SftpConfig
from aero_pi_cam.upload import SftpUploader, upload_image

from .conftest import MockFileContextManager, _create_test_config


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
    # Create separate mock files for image and JSON
    mock_image_file = MockFileContextManager()
    mock_json_file = MockFileContextManager()

    mock_sftp = AsyncMock()
    # listdir succeeds - directory exists, so makedirs won't be called
    mock_sftp.listdir = AsyncMock(return_value=[])
    mock_sftp.makedirs = AsyncMock()
    # sftp.open() returns different mock files for image and JSON
    mock_sftp.open = MagicMock(side_effect=[mock_image_file, mock_json_file])
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
        # Use clean image filename to trigger JSON generation
        result = await uploader.upload(
            b"fake-jpeg-data", metadata, config, filename="TEST-test_camera-clean.jpg"
        )

    assert result.success is True
    # Directory exists, so makedirs should not be called
    mock_sftp.makedirs.assert_not_called()
    # Verify both files were written
    assert mock_sftp.open.call_count == 2
    mock_image_file.write.assert_called_once_with(b"fake-jpeg-data")
    # Verify JSON file was written (contains the image URL, TTL, and metadata)
    assert mock_json_file.write.call_count == 1
    json_data = mock_json_file.write.call_args[0][0]
    assert b'"path"' in json_data
    assert b'"TTL"' in json_data
    assert b'"day_night_mode"' in json_data
    assert b'"debug_mode"' in json_data
    assert b'"last_update"' in json_data
    assert b'"images"' in json_data


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
    mock_image_file = MockFileContextManager(write_side_effect=Exception("Disk full"))

    mock_sftp = AsyncMock()
    mock_sftp.makedirs = AsyncMock()
    # sftp.open() returns different mock files for image and JSON
    # Image write fails, so JSON won't be reached
    mock_sftp.open = MagicMock(return_value=mock_image_file)
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
    assert "Failed to write image file" in result.error


@pytest.mark.asyncio
async def test_sftp_uploader_json_write_failure() -> None:
    """Test SftpUploader JSON file write failure."""
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

    # Image write succeeds, but JSON write fails
    mock_image_file = MockFileContextManager()
    mock_json_file = MockFileContextManager(write_side_effect=Exception("Disk full"))

    mock_sftp = AsyncMock()
    mock_sftp.makedirs = AsyncMock()
    # sftp.open() returns different mock files for image and JSON
    mock_sftp.open = MagicMock(side_effect=[mock_image_file, mock_json_file])
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
        # Use clean image filename to trigger JSON generation
        result = await uploader.upload(
            b"fake-jpeg-data", metadata, config, filename="TEST-test_camera-clean.jpg"
        )

    assert result.success is False
    assert "Failed to write JSON metadata file" in result.error


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
    mock_image_file = MockFileContextManager()
    mock_json_file = MockFileContextManager()

    mock_sftp = AsyncMock()
    mock_sftp.makedirs = AsyncMock()
    # sftp.open() returns different mock files for image and JSON
    mock_sftp.open = MagicMock(side_effect=[mock_image_file, mock_json_file])
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
        # Use clean image filename to trigger JSON generation
        result = await upload_image(
            b"fake-jpeg-data", metadata, config=config, filename="TEST-test_camera-clean.jpg"
        )

    assert result.success is True
    # Verify both files were written
    assert mock_sftp.open.call_count == 2
