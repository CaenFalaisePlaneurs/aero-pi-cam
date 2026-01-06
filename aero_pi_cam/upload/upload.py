"""Upload interface and implementations for API and SFTP."""

from dataclasses import dataclass
from typing import Any, Protocol

from ..core.config import Config
from .api import ApiUploader
from .sftp import SftpUploader

# Re-export for backward compatibility
__all__ = [
    "ApiUploader",
    "SftpUploader",
    "UploadInterface",
    "UploadResult",
    "create_uploader",
    "upload_image",
]


@dataclass
class UploadResult:
    """Result of upload operation."""

    success: bool
    status_code: int | None = None
    response_body: dict[str, Any] | None = None
    error: str | None = None


class UploadInterface(Protocol):
    """Protocol for upload implementations."""

    async def upload(
        self,
        image_bytes: bytes,
        metadata: dict[str, str],
        config: Config,
        filename: str | None = None,
    ) -> UploadResult:
        """Upload image data.

        Args:
            image_bytes: Image data to upload
            metadata: Metadata dictionary with timestamp, location, is_day
            config: Full configuration object
            filename: Optional custom filename (if None, uses default from config)

        Returns:
            UploadResult with success status and response details
        """
        ...


def create_uploader(config: Config) -> UploadInterface:
    """Create appropriate uploader based on configuration.

    Args:
        config: Configuration object

    Returns:
        UploadInterface implementation

    Raises:
        ValueError: If upload_method is not supported
    """
    if config.upload.method == "API":
        if config.upload.api is None:
            raise ValueError("api configuration is required when upload_method is 'API'")
        return ApiUploader(config.upload.api)
    elif config.upload.method == "SFTP":
        if config.upload.sftp is None:
            raise ValueError("sftp configuration is required when upload_method is 'SFTP'")
        return SftpUploader(config.upload.sftp)
    else:
        raise ValueError(f"Unknown upload method: {config.upload.method}")


async def upload_image(
    image_bytes: bytes,
    metadata: dict[str, str],
    config: Config,
    filename: str | None = None,
) -> UploadResult:
    """Upload image using configured upload method.

    Args:
        image_bytes: Image data to upload
        metadata: Metadata dictionary with timestamp, location, is_day
        config: Full configuration object
        filename: Optional custom filename (if None, uses default from config)

    Returns:
        UploadResult with success status and response details
    """
    uploader = create_uploader(config)
    return await uploader.upload(image_bytes, metadata, config, filename=filename)
