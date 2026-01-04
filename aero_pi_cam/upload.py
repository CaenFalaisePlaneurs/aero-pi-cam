"""API upload with retry logic."""

import asyncio
import os
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse

import httpx
import uvicorn

from .config import ApiConfig, Config
from .dummy_api import app, set_config

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


async def upload_image(
    image_bytes: bytes,
    metadata: dict[str, str],
    api_config: ApiConfig,
    config: Config | None = None,
) -> UploadResult:
    """Upload image with retry logic and exponential backoff.

    Args:
        image_bytes: Image data to upload
        metadata: Metadata dictionary with timestamp, location, is_day
        api_config: API configuration
        config: Full config object (required for dummy server)

    Returns:
        UploadResult with success status and response details
    """
    # Determine if we should use dummy server
    debug_mode = os.getenv("DEBUG_MODE", "false").lower() == "true"
    use_dummy_server = debug_mode or api_config.url is None

    # Start dummy server if needed
    upload_url = api_config.url
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
        original_path = urlparse(api_config.url or "").path if api_config.url else "/api/webcam/image"
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
        "Authorization": f"Bearer {api_config.key}",
        "Content-Type": "image/jpeg",
        "X-Capture-Timestamp": metadata["timestamp"],
        "X-Location": metadata["location"],
        "X-Is-Day": metadata["is_day"],
    }

    last_error: str | None = None

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            timeout = httpx.Timeout(api_config.timeout_seconds)
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
            last_error = f"Request timeout after {api_config.timeout_seconds}s"
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
