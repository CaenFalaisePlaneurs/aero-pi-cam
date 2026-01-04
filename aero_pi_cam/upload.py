"""API upload with retry logic."""

import asyncio
from dataclasses import dataclass
from typing import Any

import httpx

from .config import ApiConfig

MAX_RETRIES = 3
INITIAL_BACKOFF_MS = 1000


@dataclass
class UploadResult:
    """Result of upload operation."""

    success: bool
    status_code: int | None = None
    response_body: dict[str, Any] | None = None
    error: str | None = None


async def upload_image(
    image_bytes: bytes,
    metadata: dict[str, str],
    api_config: ApiConfig,
) -> UploadResult:
    """Upload image with retry logic and exponential backoff."""
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
                    api_config.url,
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
