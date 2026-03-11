"""SFTP upload implementation."""

import asyncio
import logging
from datetime import UTC, datetime
from typing import TYPE_CHECKING

import asyncssh

from ..core.config import Config, SftpConfig
from .dummy_api import get_image_filename
from .sftp_cleanup import schedule_cleanup
from .sftp_history import build_timestamped_filename, collect_history_images
from .sftp_meta_json import generate_metadata_json

if TYPE_CHECKING:
    from .upload import UploadResult

logger = logging.getLogger(__name__)


class SftpUploader:
    """SFTP upload implementation."""

    def __init__(self, sftp_config: SftpConfig) -> None:
        """Initialize SFTP uploader.

        Args:
            sftp_config: SFTP configuration
        """
        self.sftp_config = sftp_config

    async def upload(
        self,
        image_bytes: bytes,
        metadata: dict[str, str],
        config: Config,
        filename: str | None = None,
    ) -> "UploadResult":
        """Upload image via SFTP.

        Args:
            image_bytes: Image data to upload
            metadata: Metadata dictionary with timestamp, location, is_day
            config: Full configuration object (used for filename generation)
            filename: Optional custom filename (if None, uses default from config)

        Returns:
            UploadResult with success status and error details
        """
        from .upload import UploadResult

        try:
            if filename is None:
                filename = get_image_filename(config)
            remote_file_path = f"{self.sftp_config.remote_path.rstrip('/')}/{filename}"

            is_clean_image = filename.endswith("-clean.jpg")
            keep_duration = self.sftp_config.keep_history_duration
            history_active = is_clean_image and keep_duration is not None

            image_base_url = self.sftp_config.image_base_url
            image_with_metar_url: str | None = None
            no_metar_image_url: str | None = None

            if is_clean_image:
                if image_base_url is None:
                    no_metar_image_url = filename
                    image_with_metar_url = filename.replace("-clean.jpg", ".jpg")
                else:
                    base = image_base_url.rstrip("/")
                    no_metar_image_url = f"{base}/{filename}"
                    image_with_metar_url = f"{base}/{filename.replace('-clean.jpg', '.jpg')}"

            capture_time = self._parse_capture_time(metadata)

            async def _upload_operation() -> "UploadResult":
                """Perform SFTP upload operation."""
                async with asyncssh.connect(
                    self.sftp_config.host,
                    port=self.sftp_config.port,
                    username=self.sftp_config.user,
                    password=self.sftp_config.password,
                    known_hosts=None,
                ) as conn:
                    async with conn.start_sftp_client() as sftp:
                        remote_dir = self.sftp_config.remote_path.rstrip("/")
                        try:
                            await sftp.listdir(remote_dir)
                        except Exception:
                            try:
                                await sftp.makedirs(remote_dir, exist_ok=True)
                            except Exception as e:
                                return UploadResult(
                                    success=False,
                                    error=f"Failed to create remote directory: {str(e)}",
                                )

                        try:
                            async with sftp.open(remote_file_path, "wb") as remote_file:
                                await remote_file.write(image_bytes)
                        except Exception as e:
                            return UploadResult(
                                success=False,
                                error=f"Failed to write image file to SFTP server: {str(e)}",
                            )

                        images_map: dict[str, str] | None = None

                        if history_active:
                            assert keep_duration is not None
                            ts_filename = build_timestamped_filename(filename, capture_time)
                            ts_remote = f"{remote_dir}/{ts_filename}"
                            try:
                                async with sftp.open(ts_remote, "wb") as remote_file:
                                    await remote_file.write(image_bytes)
                            except Exception as e:
                                logger.warning(
                                    "Failed to write timestamped copy %s: %s",
                                    ts_remote,
                                    e,
                                )

                            try:
                                file_list = await sftp.listdir(remote_dir)
                            except Exception:
                                file_list = []

                            history = collect_history_images(file_list, filename)
                            images_map = self._build_images_map(
                                history, filename, capture_time, image_base_url
                            )

                        if is_clean_image:
                            assert image_with_metar_url is not None
                            json_bytes = generate_metadata_json(
                                metadata,
                                config,
                                image_with_metar_url,
                                no_metar_image_url=no_metar_image_url,
                                images_map=images_map,
                            )
                            json_remote = f"{remote_dir}/cam.json"
                            try:
                                async with sftp.open(json_remote, "wb") as remote_file:
                                    await remote_file.write(json_bytes)
                            except Exception as e:
                                return UploadResult(
                                    success=False,
                                    error=f"Failed to write JSON metadata file to SFTP server: {str(e)}",
                                )

                return UploadResult(success=True)

            result = await asyncio.wait_for(
                _upload_operation(),
                timeout=self.sftp_config.timeout_seconds,
            )

            if result.success and history_active:
                assert keep_duration is not None
                schedule_cleanup(self.sftp_config, filename, keep_duration, capture_time)

            return result

        except TimeoutError:
            return UploadResult(
                success=False,
                error=f"SFTP operation timeout after {self.sftp_config.timeout_seconds}s",
            )
        except asyncssh.Error as e:
            return UploadResult(
                success=False,
                error=f"SFTP error: {str(e)}",
            )
        except Exception as e:
            return UploadResult(
                success=False,
                error=f"Unexpected error during SFTP upload: {str(e)}",
            )

    @staticmethod
    def _parse_capture_time(metadata: dict[str, str]) -> datetime:
        """Extract UTC capture time from metadata, falling back to now."""
        ts_str = metadata.get("timestamp", "")
        if ts_str:
            try:
                if ts_str.endswith("Z"):
                    ts_str = ts_str[:-1] + "+00:00"
                dt = datetime.fromisoformat(ts_str)
                if dt.tzinfo is None:
                    return dt.replace(tzinfo=UTC)
                return dt.astimezone(UTC)
            except (ValueError, AttributeError):
                pass
        return datetime.now(UTC)

    @staticmethod
    def _build_images_map(
        history: dict[datetime, str],
        base_filename: str,
        capture_time: datetime,
        image_base_url: str | None,
    ) -> dict[str, str]:
        """Build {timestamp_iso: url} map from history + current image.

        Args:
            history: Dict of timestamp->filename from collect_history_images
            base_filename: Current clean image filename
            capture_time: Current capture UTC time
            image_base_url: Optional base URL prefix

        Returns:
            Ordered dict of ISO timestamps to image URLs (most recent first)
        """
        prefix = f"{image_base_url.rstrip('/')}/" if image_base_url else ""

        result: dict[str, str] = {}
        ts_iso = capture_time.isoformat().replace("+00:00", "Z")
        result[ts_iso] = f"{prefix}{base_filename}"

        for ts, fname in history.items():
            iso = ts.isoformat().replace("+00:00", "Z")
            if iso not in result:
                result[iso] = f"{prefix}{fname}"

        return result
