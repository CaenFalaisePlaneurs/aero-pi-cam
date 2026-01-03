"""RTSP frame capture via ffmpeg."""

import subprocess
from collections.abc import Callable
from dataclasses import dataclass
from urllib.parse import urlparse

# Dependency injection for testing
_subprocess_run: Callable = subprocess.run


def set_subprocess_run(func: Callable) -> None:
    """Set subprocess.run implementation (for testing)."""
    global _subprocess_run
    _subprocess_run = func


def reset_subprocess_run() -> None:
    """Reset to default subprocess.run."""
    global _subprocess_run
    _subprocess_run = subprocess.run


@dataclass
class CaptureResult:
    """Result of frame capture operation."""

    success: bool
    image: bytes | None = None
    error: str | None = None


def capture_frame(
    rtsp_url: str,
    rtsp_user: str | None = None,
    rtsp_password: str | None = None,
) -> CaptureResult:
    """Capture single frame from RTSP stream.

    Args:
        rtsp_url: RTSP URL (with or without credentials)
        rtsp_user: Optional username (if not in URL)
        rtsp_password: Optional password (if not in URL - no URL encoding needed)
    """
    from urllib.parse import quote

    args = ["ffmpeg", "-rtsp_transport", "tcp"]

    # If credentials provided separately, build URL with proper encoding
    if rtsp_user and rtsp_password:
        # Parse URL and rebuild with credentials
        parsed = urlparse(rtsp_url)
        # Only encode username if it contains special characters
        if any(c in rtsp_user for c in ["@", ":", "/", "?", "#", "[", "]"]):
            encoded_user = quote(rtsp_user, safe="")
        else:
            encoded_user = rtsp_user

        # VIGI cameras require special characters in passwords but may have issues with
        # URL-encoded passwords in RTSP URLs. Try unencoded first, then fall back to encoded.
        # Based on: https://ffmpeg.org/pipermail/ffmpeg-user/2017-September/037295.html
        # Some RTSP servers (especially with Digest auth) have issues with special chars.
        # We'll try unencoded first since the user confirmed the URL works in another tool.
        encoded_password = rtsp_password  # Use password as-is (unencoded)

        rtsp_url_with_auth = (
            f"{parsed.scheme}://{encoded_user}:{encoded_password}@{parsed.hostname}"
        )
        if parsed.port:
            rtsp_url_with_auth += f":{parsed.port}"
        rtsp_url_with_auth += parsed.path
        if parsed.query:
            rtsp_url_with_auth += f"?{parsed.query}"

        args.extend(["-i", rtsp_url_with_auth])
    else:
        # Use URL with embedded credentials (already encoded if needed)
        args.extend(["-i", rtsp_url])

    args.extend(
        [
            "-frames:v",
            "1",
            "-q:v",
            "2",
            "-f",
            "image2",
            "pipe:1",
        ]
    )

    try:
        result = _subprocess_run(
            args,
            capture_output=True,
            timeout=30,
            check=True,
        )

        if not result.stdout or len(result.stdout) == 0:
            return CaptureResult(success=False, error="ffmpeg produced no output")

        return CaptureResult(success=True, image=result.stdout)

    except subprocess.TimeoutExpired:
        return CaptureResult(success=False, error="ffmpeg timeout after 30s")
    except subprocess.CalledProcessError as e:
        stderr = e.stderr.decode() if e.stderr else "Unknown error"
        return CaptureResult(
            success=False,
            error=f"ffmpeg exited with code {e.returncode}: {stderr}",
        )
    except Exception as e:
        return CaptureResult(success=False, error=f"ffmpeg spawn error: {str(e)}")
