"""SFTP upload implementation."""

import asyncio
from typing import TYPE_CHECKING

import asyncssh

from ..core.config import Config, SftpConfig
from .dummy_api import get_image_filename
from .sftp_meta_json import generate_metadata_json

if TYPE_CHECKING:
    from .upload import UploadResult


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
        # Import here to avoid circular dependency
        from .upload import UploadResult

        try:
            # Generate filename from config or use provided filename
            if filename is None:
                filename = get_image_filename(config)
            remote_file_path = f"{self.sftp_config.remote_path.rstrip('/')}/{filename}"

            # Only generate JSON metadata file for clean image (without METAR overlay)
            # The clean image is used on our own site where METAR is displayed from cam.json
            is_clean_image = filename.endswith("-clean.jpg")
            json_bytes = None
            json_remote_path = None
            if is_clean_image:
                # Determine image base URL (primary image server domain)
                image_base_url = self.sftp_config.image_base_url
                if image_base_url is None:
                    # If not configured, use relative paths (no base URL)
                    no_metar_image_url = filename
                    image_with_metar_filename = filename.replace("-clean.jpg", ".jpg")
                    image_with_metar_url = image_with_metar_filename
                else:
                    # Ensure base URL doesn't end with /
                    image_base_url = image_base_url.rstrip("/")
                    # Construct URLs for both images
                    # Clean image URL (without METAR overlay)
                    no_metar_image_url = f"{image_base_url}/{filename}"
                    # Image with METAR overlay URL (remove "-clean" suffix)
                    image_with_metar_filename = filename.replace("-clean.jpg", ".jpg")
                    image_with_metar_url = f"{image_base_url}/{image_with_metar_filename}"

                # Generate JSON metadata file
                # path points to image with METAR overlay, no_metar_path points to clean image
                json_bytes = generate_metadata_json(
                    metadata, config, image_with_metar_url, no_metar_image_url=no_metar_image_url
                )
                json_filename = "cam.json"
                json_remote_path = f"{self.sftp_config.remote_path.rstrip('/')}/{json_filename}"

            async def _upload_operation() -> "UploadResult":
                """Perform SFTP upload operation."""
                # Connect to SFTP server
                async with asyncssh.connect(
                    self.sftp_config.host,
                    port=self.sftp_config.port,
                    username=self.sftp_config.user,
                    password=self.sftp_config.password,
                    known_hosts=None,  # Disable host key checking (for flexibility)
                ) as conn:
                    async with conn.start_sftp_client() as sftp:
                        # Ensure remote directory exists
                        # Try to list it first - if it works, directory exists and is accessible
                        remote_dir = self.sftp_config.remote_path.rstrip("/")
                        try:
                            # Try to list the directory to verify it exists and is accessible
                            await sftp.listdir(remote_dir)
                            # Directory exists and is accessible, no need to create it
                        except Exception:
                            # Directory doesn't exist or we can't access it, try to create it
                            # makedirs with exist_ok=True will not error if directory already exists
                            try:
                                await sftp.makedirs(remote_dir, exist_ok=True)
                            except Exception as e:
                                return UploadResult(
                                    success=False,
                                    error=f"Failed to create remote directory: {str(e)}",
                                )

                        # Upload image file
                        try:
                            async with sftp.open(remote_file_path, "wb") as remote_file:
                                await remote_file.write(image_bytes)
                        except Exception as e:
                            return UploadResult(
                                success=False,
                                error=f"Failed to write image file to SFTP server: {str(e)}",
                            )

                        # Upload JSON metadata file (only for clean image)
                        if json_bytes is not None and json_remote_path is not None:
                            try:
                                async with sftp.open(json_remote_path, "wb") as remote_file:
                                    await remote_file.write(json_bytes)
                            except Exception as e:
                                return UploadResult(
                                    success=False,
                                    error=f"Failed to write JSON metadata file to SFTP server: {str(e)}",
                                )

                return UploadResult(success=True)

            # Wrap entire operation in timeout
            return await asyncio.wait_for(
                _upload_operation(),
                timeout=self.sftp_config.timeout_seconds,
            )

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
