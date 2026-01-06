"""Upload interface and implementations for API and SFTP."""

import asyncio
import os
from dataclasses import dataclass
from typing import Any, Protocol
from urllib.parse import urlparse

import asyncssh
import httpx
import uvicorn

from .config import ApiConfig, Config, SftpConfig
from .dummy_api import app, get_image_filename, set_config

MAX_RETRIES = 3
INITIAL_BACKOFF_MS = 1000

# Global state for dummy server
_dummy_server_running = False
_dummy_server_url: str | None = None
_dummy_server_task: asyncio.Task | None = None


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


async def _run_uvicorn_server(port: int) -> None:
    """Run uvicorn server in background task.

    Args:
        port: Port number to run server on
    """
    # Use 0.0.0.0 to bind to all interfaces (works with host networking in Docker)
    config = uvicorn.Config(app, host="0.0.0.0", port=port, log_level="warning")
    server = uvicorn.Server(config)
    await server.serve()


def start_dummy_api_server(config: Config, port: int = 8000) -> str:
    """Start dummy API server in background task.

    Args:
        config: Configuration object to pass to dummy server
        port: Port number to run server on (default: 8000)

    Returns:
        Server URL (e.g., "http://localhost:8000")
    """
    global _dummy_server_running, _dummy_server_url, _dummy_server_task

    if _dummy_server_running:
        return _dummy_server_url or f"http://localhost:{port}"

    # Set config in dummy API
    set_config(config)

    # Start server in background task (get running event loop)
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        # No event loop running, create one (shouldn't happen in normal usage)
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    _dummy_server_task = loop.create_task(_run_uvicorn_server(port))
    _dummy_server_url = f"http://localhost:{port}"
    _dummy_server_running = True

    print(f"Dummy API server started on {_dummy_server_url}")

    return _dummy_server_url


class ApiUploader:
    """API upload implementation."""

    def __init__(self, api_config: ApiConfig) -> None:
        """Initialize API uploader.

        Args:
            api_config: API configuration
        """
        self.api_config = api_config

    async def upload(
        self,
        image_bytes: bytes,
        metadata: dict[str, str],
        config: Config,
    ) -> UploadResult:
        """Upload image via API with retry logic and exponential backoff.

        Args:
            image_bytes: Image data to upload
            metadata: Metadata dictionary with timestamp, location, is_day
            config: Full config object (required for dummy server)

        Returns:
            UploadResult with success status and response details
        """
        # Determine if we should use dummy server
        debug_mode = os.getenv("DEBUG_MODE", "false").lower() == "true"
        use_dummy_server = debug_mode or self.api_config.url is None

        # Start dummy server if needed
        upload_url = self.api_config.url
        if use_dummy_server:
            if config is None:
                return UploadResult(
                    success=False,
                    error="Config required for dummy server but not provided",
                )
            dummy_base_url = start_dummy_api_server(config)
            # Extract path from original API URL and append to dummy server base URL
            # api_config.url is like "https://api.example.com/api/webcam/image"
            # We need to extract "/api/webcam/image" and append to dummy_base_url
            original_path = (
                urlparse(self.api_config.url or "").path
                if self.api_config.url
                else "/api/webcam/image"
            )
            upload_url = f"{dummy_base_url}{original_path}"
            # Give server a moment to start up and register routes
            # Try to connect to verify server is ready
            max_retries = 10
            for _ in range(max_retries):
                await asyncio.sleep(0.2)
                try:
                    async with httpx.AsyncClient(timeout=httpx.Timeout(1.0)) as client:
                        # Try health check endpoint to verify server is ready
                        response = await client.get(f"{dummy_base_url}/")
                        if response.status_code == 200:
                            break
                except Exception:
                    continue

        headers = {
            "Authorization": f"Bearer {self.api_config.key}",
            "Content-Type": "image/jpeg",
            "X-Capture-Timestamp": metadata["timestamp"],
            "X-Location": metadata["location"],
            "X-Is-Day": metadata["is_day"],
        }

        last_error: str | None = None

        # upload_url is guaranteed to be str here (either from config or dummy server)
        if upload_url is None:
            return UploadResult(
                success=False,
                error="Upload URL is not configured",
            )

        for attempt in range(1, MAX_RETRIES + 1):
            try:
                timeout = httpx.Timeout(self.api_config.timeout_seconds)
                async with httpx.AsyncClient(timeout=timeout) as client:
                    response = await client.put(
                        upload_url,
                        content=image_bytes,
                        headers=headers,
                    )

                    if response.status_code == 201:
                        return UploadResult(
                            success=True,
                            status_code=response.status_code,
                            response_body=response.json(),
                        )

                    # Don't retry on client errors (4xx except 429)
                    if 400 <= response.status_code < 500 and response.status_code != 429:
                        error_text = response.text
                        return UploadResult(
                            success=False,
                            status_code=response.status_code,
                            error=f"HTTP {response.status_code}: {error_text}",
                        )

                    last_error = f"HTTP {response.status_code}: {response.text}"

            except httpx.TimeoutException:
                last_error = f"Request timeout after {self.api_config.timeout_seconds}s"
            except httpx.RequestError as e:
                last_error = str(e)
            except asyncio.CancelledError:
                # Shutdown requested during upload
                return UploadResult(
                    success=False,
                    error="Upload cancelled during shutdown",
                )

            if attempt < MAX_RETRIES:
                backoff_ms = INITIAL_BACKOFF_MS * (2 ** (attempt - 1))
                try:
                    await asyncio.sleep(backoff_ms / 1000.0)
                except asyncio.CancelledError:
                    # Shutdown requested, return failure
                    return UploadResult(
                        success=False,
                        error="Upload cancelled during shutdown",
                    )

        return UploadResult(
            success=False,
            error=f"All {MAX_RETRIES} upload attempts failed. Last error: {last_error}",
        )


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
    ) -> UploadResult:
        """Upload image via SFTP.

        Args:
            image_bytes: Image data to upload
            metadata: Metadata dictionary with timestamp, location, is_day
            config: Full configuration object (used for filename generation)

        Returns:
            UploadResult with success status and error details
        """
        try:
            # Generate filename from config
            filename = get_image_filename(config)
            remote_file_path = f"{self.sftp_config.remote_path.rstrip('/')}/{filename}"

            async def _upload_operation() -> UploadResult:
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
    api_config: ApiConfig | None = None,
    config: Config | None = None,
) -> UploadResult:
    """Upload image using configured upload method.

    Args:
        image_bytes: Image data to upload
        metadata: Metadata dictionary with timestamp, location, is_day
        api_config: API configuration (deprecated, use config instead)
        config: Full configuration object (required for new upload methods)

    Returns:
        UploadResult with success status and response details
    """
    if config is None:
        # Backward compatibility: if config is None but api_config is provided
        if api_config is None:
            return UploadResult(
                success=False,
                error="Either config or api_config must be provided",
            )
        # Use ApiUploader directly for backward compatibility
        # Create minimal config for backward compatibility (API upload doesn't need full config)
        from .config import (
            CameraConfig,
            LocationConfig,
            MetadataConfig,
            MetarConfig,
            OverlayConfig,
            ScheduleConfig,
        )

        minimal_config = Config(
            camera=CameraConfig(rtsp_url="rtsp://dummy", rtsp_user=None, rtsp_password=None),
            location=LocationConfig(name="DUMMY", latitude=48.9, longitude=-0.1, camera_heading="060° RWY 06"),
            schedule=ScheduleConfig(day_interval_minutes=5, night_interval_minutes=60),
            upload_method="API",
            api=api_config,
            sftp=None,
            overlay=OverlayConfig(
                provider_name="Dummy",
                provider_logo="dummy.svg",
                logo_size=72,
                camera_name="dummy",
                font_color="white",
                font_size=16,
                font_path=None,
                sun_icon_size=24,
                line_spacing=4,
                padding=15,
                background_color="rgba(0,0,0,0.6)",
                shadow_enabled=True,
                shadow_offset_x=2,
                shadow_offset_y=2,
                shadow_color="black",
            ),
            metar=MetarConfig(
                enabled=False,
                icao_code="XXXX",
                api_url="https://aviationweather.gov/api/data/metar",
                raw_metar_enabled=True,
            ),
            metadata=MetadataConfig(
                github_repo="https://github.com/dummy",
                webcam_url="https://dummy.com",
                license="CC BY-SA 4.0",
                license_url="https://creativecommons.org/licenses/by-sa/4.0/",
                license_mark="This work is licensed under CC BY-SA 4.0.",
            ),
            debug=None,
        )
        uploader: UploadInterface = ApiUploader(api_config)
        return await uploader.upload(image_bytes, metadata, minimal_config)

    uploader = create_uploader(config)
    return await uploader.upload(image_bytes, metadata, config)
