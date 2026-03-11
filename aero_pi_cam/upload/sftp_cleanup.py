"""Background SFTP cleanup task for deleting expired history images."""

import asyncio
import logging
from datetime import UTC, datetime, timedelta

import asyncssh

from ..core.config import SftpConfig
from .sftp_history import collect_history_images, find_expired_images

logger = logging.getLogger(__name__)

# Module-level lock prevents overlapping cleanup runs
_cleanup_lock = asyncio.Lock()


async def _run_cleanup(
    sftp_config: SftpConfig,
    base_filename: str,
    keep_duration: timedelta,
    now: datetime,
) -> None:
    """Connect to SFTP, list files, and delete expired history images.

    Opens its own SFTP connection so the main upload connection is not held open.

    Args:
        sftp_config: SFTP connection settings
        base_filename: Clean image base filename (e.g., "LFAS-cam-clean.jpg")
        keep_duration: How long to retain historical images
        now: Current UTC time (from capture metadata)
    """
    async with asyncssh.connect(
        sftp_config.host,
        port=sftp_config.port,
        username=sftp_config.user,
        password=sftp_config.password,
        known_hosts=None,
    ) as conn:
        async with conn.start_sftp_client() as sftp:
            remote_dir = sftp_config.remote_path.rstrip("/")
            file_list = await sftp.listdir(remote_dir)
            history = collect_history_images(file_list, base_filename)

            expired = find_expired_images(history, keep_duration, now)
            if not expired:
                return

            logger.info("Cleaning up %d expired history image(s)", len(expired))
            for fname in expired:
                remote_path = f"{remote_dir}/{fname}"
                try:
                    await sftp.remove(remote_path)
                except Exception as e:
                    logger.warning("Failed to delete %s: %s", remote_path, e)


def schedule_cleanup(
    sftp_config: SftpConfig,
    base_filename: str,
    keep_duration: timedelta,
    now: datetime | None = None,
) -> None:
    """Fire a background cleanup task if one isn't already running.

    Safe to call from any async context. If a previous cleanup is still in
    progress, this call is silently skipped.

    Args:
        sftp_config: SFTP connection settings
        base_filename: Clean image base filename
        keep_duration: How long to retain historical images
        now: Current UTC time (defaults to datetime.now(UTC))
    """
    if now is None:
        now = datetime.now(UTC)

    asyncio.create_task(_guarded_cleanup(sftp_config, base_filename, keep_duration, now))


async def _guarded_cleanup(
    sftp_config: SftpConfig,
    base_filename: str,
    keep_duration: timedelta,
    now: datetime,
) -> None:
    """Run cleanup under the module lock, skipping if already running."""
    if _cleanup_lock.locked():
        logger.info("Cleanup already in progress, skipping this cycle")
        return

    async with _cleanup_lock:
        try:
            await _run_cleanup(sftp_config, base_filename, keep_duration, now)
        except Exception:
            logger.exception("Background cleanup failed")
