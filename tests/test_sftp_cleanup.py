"""Tests for SFTP background cleanup task."""

import asyncio
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from aero_pi_cam.core.config import SftpConfig
from aero_pi_cam.upload import sftp_cleanup


def _make_sftp_config() -> SftpConfig:
    return SftpConfig(
        host="test.example.com",
        port=22,
        user="testuser",
        password="testpass",
        remote_path="/test/path",
        timeout_seconds=30,
    )


def _mock_sftp_connection(file_list: list[str]) -> tuple[AsyncMock, AsyncMock]:
    """Build mock asyncssh connection + sftp client returning given file_list."""
    mock_sftp = AsyncMock()
    mock_sftp.listdir = AsyncMock(return_value=file_list)
    mock_sftp.remove = AsyncMock()
    mock_sftp.__aenter__ = AsyncMock(return_value=mock_sftp)
    mock_sftp.__aexit__ = AsyncMock(return_value=None)

    mock_sftp_cm = AsyncMock()
    mock_sftp_cm.__aenter__ = AsyncMock(return_value=mock_sftp)
    mock_sftp_cm.__aexit__ = AsyncMock(return_value=None)

    mock_conn = AsyncMock()
    mock_conn.start_sftp_client = MagicMock(return_value=mock_sftp_cm)
    mock_conn.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_conn.__aexit__ = AsyncMock(return_value=None)

    return mock_conn, mock_sftp


@pytest.mark.asyncio
async def test_run_cleanup_deletes_expired() -> None:
    """Test that _run_cleanup deletes expired files."""
    now = datetime(2026, 3, 10, 18, 0, 0, tzinfo=UTC)
    keep = timedelta(hours=1)
    base = "cam-clean.jpg"
    files = [
        "cam-clean.jpg",
        "cam-clean.20260310T173000Z.jpg",
        "cam-clean.20260310T165000Z.jpg",
    ]

    mock_conn, mock_sftp = _mock_sftp_connection(files)

    with patch("asyncssh.connect", return_value=mock_conn):
        await sftp_cleanup._run_cleanup(_make_sftp_config(), base, keep, now)

    mock_sftp.remove.assert_called_once_with("/test/path/cam-clean.20260310T165000Z.jpg")


@pytest.mark.asyncio
async def test_run_cleanup_no_expired() -> None:
    """Test that _run_cleanup does nothing when no files are expired."""
    now = datetime(2026, 3, 10, 17, 35, 0, tzinfo=UTC)
    keep = timedelta(hours=1)
    base = "cam-clean.jpg"
    files = [
        "cam-clean.20260310T173000Z.jpg",
    ]

    mock_conn, mock_sftp = _mock_sftp_connection(files)

    with patch("asyncssh.connect", return_value=mock_conn):
        await sftp_cleanup._run_cleanup(_make_sftp_config(), base, keep, now)

    mock_sftp.remove.assert_not_called()


@pytest.mark.asyncio
async def test_run_cleanup_delete_failure_logs_warning() -> None:
    """Test that a failed delete is logged but doesn't crash."""
    now = datetime(2026, 3, 10, 18, 0, 0, tzinfo=UTC)
    keep = timedelta(minutes=30)
    base = "cam-clean.jpg"
    files = [
        "cam-clean.20260310T170000Z.jpg",
    ]

    mock_conn, mock_sftp = _mock_sftp_connection(files)
    mock_sftp.remove = AsyncMock(side_effect=Exception("Permission denied"))

    with patch("asyncssh.connect", return_value=mock_conn):
        await sftp_cleanup._run_cleanup(_make_sftp_config(), base, keep, now)

    mock_sftp.remove.assert_called_once()


@pytest.mark.asyncio
async def test_guarded_cleanup_skips_when_locked() -> None:
    """Test that overlapping cleanups are skipped."""
    now = datetime(2026, 3, 10, 18, 0, 0, tzinfo=UTC)
    keep = timedelta(hours=1)
    base = "cam-clean.jpg"
    config = _make_sftp_config()

    call_count = 0

    async def slow_cleanup(*args: object, **kwargs: object) -> None:
        nonlocal call_count
        call_count += 1
        await asyncio.sleep(0.2)

    with patch.object(sftp_cleanup, "_run_cleanup", side_effect=slow_cleanup):
        task1 = asyncio.create_task(sftp_cleanup._guarded_cleanup(config, base, keep, now))
        await asyncio.sleep(0.05)
        task2 = asyncio.create_task(sftp_cleanup._guarded_cleanup(config, base, keep, now))
        await asyncio.gather(task1, task2)

    assert call_count == 1


@pytest.mark.asyncio
async def test_guarded_cleanup_catches_exceptions() -> None:
    """Test that exceptions in cleanup are caught and logged."""
    now = datetime(2026, 3, 10, 18, 0, 0, tzinfo=UTC)
    keep = timedelta(hours=1)
    base = "cam-clean.jpg"
    config = _make_sftp_config()

    with patch.object(sftp_cleanup, "_run_cleanup", side_effect=Exception("Connection refused")):
        await sftp_cleanup._guarded_cleanup(config, base, keep, now)


@pytest.mark.asyncio
async def test_schedule_cleanup_creates_task() -> None:
    """Test that schedule_cleanup fires a background task."""
    now = datetime(2026, 3, 10, 18, 0, 0, tzinfo=UTC)
    keep = timedelta(hours=1)
    base = "cam-clean.jpg"
    config = _make_sftp_config()

    with patch.object(sftp_cleanup, "_guarded_cleanup", new_callable=AsyncMock) as mock_gc:
        sftp_cleanup.schedule_cleanup(config, base, keep, now)
        await asyncio.sleep(0.05)

    mock_gc.assert_called_once_with(config, base, keep, now)
