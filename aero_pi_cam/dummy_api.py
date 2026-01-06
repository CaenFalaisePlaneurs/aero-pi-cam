"""Dummy API server for debug mode and testing."""

import os
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated

from fastapi import FastAPI, HTTPException, Query, Request, Response
from fastapi.responses import JSONResponse

from .config import Config

app = FastAPI(title="Dummy Webcam Upload API", version="1.0.0")

# Global config (set when server starts)
_server_config: Config | None = None


@app.get("/")
async def root() -> dict[str, str]:
    """Health check endpoint."""
    return {"status": "ok", "service": "dummy-webcam-upload-api"}


def sanitize_filename(text: str) -> str:
    """Sanitize filename by replacing spaces with underscores and removing non-ASCII characters.

    Args:
        text: Input text to sanitize

    Returns:
        Sanitized text with spaces replaced by underscores, non-ASCII removed,
        and trailing/leading hyphens/underscores cleaned
    """
    # Replace spaces with underscores
    text = text.replace(" ", "_")
    # Remove non-ASCII characters (keep only ASCII)
    text = re.sub(r"[^\x00-\x7F]", "", text)
    # Clean up trailing/leading hyphens and underscores
    text = text.strip("-_")
    return text


def get_image_filename(config: Config) -> str:
    """Generate sanitized image filename from config.

    Args:
        config: Configuration object

    Returns:
        Sanitized filename in format: {location.name}-{camera_name}.jpg
    """
    location_name = sanitize_filename(config.location.name)
    camera_name = sanitize_filename(config.overlay.camera_name)
    return f"{location_name}-{camera_name}.jpg"


@app.put("/api/webcam/image")
async def upload_image(
    request: Request,
    error: Annotated[int | None, Query(description="Error code to simulate")] = None,
) -> Response:
    """Upload webcam image with metadata.

    Matches OpenAPI spec for /api/webcam/image endpoint.
    """
    global _server_config

    if _server_config is None:
        raise HTTPException(status_code=500, detail="Server configuration not set")

    # Get headers from request (FastAPI Header() doesn't support aliases easily)
    headers = request.headers
    x_capture_timestamp = headers.get("X-Capture-Timestamp")
    x_location = headers.get("X-Location")
    x_is_day = headers.get("X-Is-Day")
    authorization = headers.get("Authorization")

    # Log request (debug only)
    debug_mode = os.getenv("DEBUG_MODE", "false").lower() == "true"
    if debug_mode:
        timestamp = datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S UTC")
        print(f"\n[{timestamp}] Dummy API: PUT /api/webcam/image")

    # Read image body (needed for error simulation and saving)
    image_bytes = await request.body()
    image_size = len(image_bytes)
    if debug_mode:
        print(f"  Image size: {image_size} bytes")

    # Handle error simulation (takes precedence over validation)
    if error is not None:
        error_messages = {
            400: "Invalid image format or missing required headers",
            401: "Invalid or missing authentication token",
            403: "Insufficient permissions to upload images",
            413: "Image size exceeds maximum allowed size",
            429: "Rate limit exceeded. Please retry after some time",
            500: "Internal server error occurred while processing the image",
            502: "Bad gateway - upstream service unavailable",
            503: "Service temporarily unavailable",
            504: "Gateway timeout - request took too long to process",
        }
        error_msg = error_messages.get(error, "Error occurred")
        if debug_mode:
            print(f"  Simulating error: HTTP {error}")
        response = JSONResponse(status_code=error, content={"error": error_msg})
        if error == 429:
            response.headers["Retry-After"] = "60"
        return response

    # Validate required headers (only if not simulating error)
    if not x_capture_timestamp:
        if debug_mode:
            print("  Error: Missing X-Capture-Timestamp header")
        return JSONResponse(
            status_code=400,
            content={"error": "Missing required header: X-Capture-Timestamp"},
        )
    if not x_location:
        if debug_mode:
            print("  Error: Missing X-Location header")
        return JSONResponse(
            status_code=400,
            content={"error": "Missing required header: X-Location"},
        )
    if not x_is_day:
        if debug_mode:
            print("  Error: Missing X-Is-Day header")
        return JSONResponse(
            status_code=400,
            content={"error": "Missing required header: X-Is-Day"},
        )

    # Validate authorization
    if not authorization or not authorization.startswith("Bearer "):
        if debug_mode:
            print("  Error: Missing or invalid Authorization header")
        return JSONResponse(
            status_code=401,
            content={"error": "Invalid or missing authentication token"},
        )

    # Log headers (debug only)
    if debug_mode:
        print("  Headers:")
        print(f"    X-Capture-Timestamp: {x_capture_timestamp}")
        print(f"    X-Location: {x_location}")
        print(f"    X-Is-Day: {x_is_day}")
        print("    Authorization: Bearer ***")

    # Save image to .debug/cam/ directory
    project_root = Path(__file__).parent.parent
    debug_dir = project_root / ".debug" / "cam"
    os.makedirs(debug_dir, exist_ok=True)

    filename = get_image_filename(_server_config)
    filepath = debug_dir / filename

    try:
        with open(filepath, "wb") as f:
            f.write(image_bytes)
        # Always log saved image location (useful for debugging even in normal mode)
        print(f"  Saved image to: {filepath}", flush=True)
    except Exception as e:
        if debug_mode:
            print(f"  Error saving image: {e}")
        return JSONResponse(
            status_code=500,
            content={"error": "Failed to save image"},
        )

    # Return success response matching OpenAPI spec
    received_at = datetime.now(UTC).isoformat().replace("+00:00", "Z")
    response_data = {
        "id": f"img_{int(datetime.now(UTC).timestamp())}",
        "received_at": received_at,
        "size_bytes": image_size,
    }
    if debug_mode:
        print("  Response: HTTP 201 Created")
    return JSONResponse(status_code=201, content=response_data)


def set_config(config: Config) -> None:
    """Set the server configuration.

    Args:
        config: Configuration object to use
    """
    global _server_config
    _server_config = config


def get_config() -> Config | None:
    """Get the current server configuration.

    Returns:
        Current configuration or None if not set
    """
    return _server_config
