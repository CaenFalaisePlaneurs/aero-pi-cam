"""SFTP upload implementation."""

import asyncio
from typing import TYPE_CHECKING

import asyncssh

from .config import Config, SftpConfig
from .dummy_api import get_image_filename

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
    ) -> "UploadResult":
        """Upload image via SFTP.

        Args:
            image_bytes: Image data to upload
            metadata: Metadata dictionary with timestamp, location, is_day
            config: Full configuration object (used for filename generation)

        Returns:
            UploadResult with success status and error details
        """
        # Import here to avoid circular dependency
        from .upload import UploadResult

        try:
            # Generate filename from config
            filename = get_image_filename(config)
            remote_file_path = f"{self.sftp_config.remote_path.rstrip('/')}/{filename}"

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

                        # Upload file
                        try:
                            async with sftp.open(remote_file_path, "wb") as remote_file:
                                await remote_file.write(image_bytes)
                        except Exception as e:
                            return UploadResult(
                                success=False,
                                error=f"Failed to write file to SFTP server: {str(e)}",
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
