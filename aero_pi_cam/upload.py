"""Upload interface and implementations for API and SFTP."""

from dataclasses import dataclass
from typing import Any, Protocol

from .config import Config
from .upload_api import ApiUploader
from .upload_sftp import SftpUploader

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
    ) -> UploadResult:
        """Upload image data.

        Args:
            image_bytes: Image data to upload
            metadata: Metadata dictionary with timestamp, location, is_day
            config: Full configuration object

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
    if config.upload_method == "API":
        if config.api is None:
            raise ValueError("api configuration is required when upload_method is 'API'")
        return ApiUploader(config.api)
    elif config.upload_method == "SFTP":
        if config.sftp is None:
            raise ValueError("sftp configuration is required when upload_method is 'SFTP'")
        return SftpUploader(config.sftp)
    else:
        raise ValueError(f"Unknown upload method: {config.upload_method}")


async def upload_image(
    image_bytes: bytes,
    metadata: dict[str, str],
    config: Config,
) -> UploadResult:
    """Upload image using configured upload method.

    Args:
        image_bytes: Image data to upload
        metadata: Metadata dictionary with timestamp, location, is_day
        config: Full configuration object

    Returns:
        UploadResult with success status and response details
    """
    uploader = create_uploader(config)
    return await uploader.upload(image_bytes, metadata, config)
