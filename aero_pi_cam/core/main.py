"""Main entry point for webcam capture service."""

import argparse
import asyncio
import os
import signal
import sys
from pathlib import Path

from apscheduler.schedulers.asyncio import AsyncIOScheduler

try:
    from .config import Config, load_config
    from .debug import debug_print
    from .dependencies import check_external_dependencies
    from .scheduler import schedule_next_capture
    from .workflow import capture_and_upload
except ImportError:
    # Allow running as script: python aero_pi_cam/core/main.py
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).parent.parent.parent))
    from aero_pi_cam.core.config import Config, load_config
    from aero_pi_cam.core.debug import debug_print
    from aero_pi_cam.core.dependencies import check_external_dependencies
    from aero_pi_cam.core.scheduler import schedule_next_capture
    from aero_pi_cam.core.workflow import capture_and_upload

# Global state
scheduler: AsyncIOScheduler | None = None
config: Config | None = None
_shutdown_event: asyncio.Event | None = None
_running_task: asyncio.Task | None = None

# State references for workflow
_is_running = {"value": False}
_camera_connected = {"value": False}
_api_connected = {"value": False}
_running_task_ref: dict[str, asyncio.Task | None] = {"value": None}


def shutdown(signum: int, frame: object) -> None:  # noqa: ARG001
    """Graceful shutdown handler."""
    global _shutdown_event
    # Print newline to clear countdown line, then shutdown message
    print()  # Newline to clear the countdown
    print("Stopping service...")
    if _shutdown_event:
        _shutdown_event.set()
    else:
        # If event not created yet, force exit
        sys.exit(0)


async def _capture_and_upload_wrapper() -> None:
    """Wrapper for capture_and_upload to pass state references."""
    global config, _shutdown_event
    if config is None:
        return
    await capture_and_upload(
        config=config,
        shutdown_event=_shutdown_event,
        is_running_ref=_is_running,
        camera_connected_ref=_camera_connected,
        api_connected_ref=_api_connected,
        running_task_ref=_running_task_ref,
    )


async def _schedule_next_capture_wrapper() -> None:
    """Wrapper for schedule_next_capture to handle recursive scheduling."""
    global scheduler, config
    if config is None:
        return
    scheduler = await schedule_next_capture(
        scheduler=scheduler,
        config=config,
        capture_and_upload_func=_capture_and_upload_wrapper,
        schedule_func=_schedule_next_capture_wrapper,
    )


async def run_service(config_path: str | None = None) -> None:
    """Run the service in an async context.

    Args:
        config_path: Path to configuration file. If None, uses CONFIG_PATH env var or default.
    """
    global config, _shutdown_event, scheduler, _running_task
    _shutdown_event = asyncio.Event()

    # Register signal handlers in the event loop (works better than registering before asyncio.run)
    loop = asyncio.get_running_loop()
    if hasattr(loop, "add_signal_handler"):
        # Unix-like systems
        try:
            loop.add_signal_handler(signal.SIGINT, shutdown, signal.SIGINT, None)
            loop.add_signal_handler(signal.SIGTERM, shutdown, signal.SIGTERM, None)
        except (ValueError, OSError):
            # Signal handlers may already be set or not available
            pass

    print("Webcam Capture Service starting...")

    # Check for required external dependencies
    check_external_dependencies()

    # Determine config path: command-line arg > env var > default
    if config_path is None:
        config_path = os.getenv("CONFIG_PATH", "config.yaml")

    print(f"Loading config from: {config_path}")

    try:
        config = load_config(config_path)
    except Exception as e:
        print(f"Failed to load config: {e}")
        sys.exit(1)

    # Check debug mode status
    debug_enabled = os.getenv("DEBUG_MODE", "false").lower() == "true"

    # Log configuration summary (debug only)
    debug_print("\nConfiguration:")
    debug_print(f"  Debug mode: {'enabled' if debug_enabled else 'disabled'}")

    # Show intervals (debug values if in debug mode, otherwise normal values)
    if debug_enabled:
        if config.debug:
            day_interval = f"{config.debug.day_interval_seconds}s"
            night_interval = f"{config.debug.night_interval_seconds}s"
        else:
            day_interval = "10s (default)"
            night_interval = "30s (default)"
    else:
        # Format intervals as h:m:s or just seconds if < 60
        day_hours = config.schedule.day_interval_seconds // 3600
        day_mins = (config.schedule.day_interval_seconds % 3600) // 60
        day_secs = config.schedule.day_interval_seconds % 60
        if day_hours > 0:
            day_interval = f"{day_hours}h{day_mins:02d}m{day_secs:02d}s"
        elif day_mins > 0:
            day_interval = f"{day_mins}m{day_secs:02d}s"
        else:
            day_interval = f"{day_secs}s"

        night_hours = config.schedule.night_interval_seconds // 3600
        night_mins = (config.schedule.night_interval_seconds % 3600) // 60
        night_secs = config.schedule.night_interval_seconds % 60
        if night_hours > 0:
            night_interval = f"{night_hours}h{night_mins:02d}m{night_secs:02d}s"
        elif night_mins > 0:
            night_interval = f"{night_mins}m{night_secs:02d}s"
        else:
            night_interval = f"{night_secs}s"
    debug_print(f"  Day interval: {day_interval}")
    debug_print(f"  Night interval: {night_interval}")

    debug_print(f"  Airfield (ICAO): {config.location.name}")
    debug_print(f"  Location: {config.location.latitude}, {config.location.longitude}")

    # Log camera URL without credentials for security
    camera_url = config.camera.rtsp_url
    # Remove credentials from URL if present (rtsp://user:pass@host -> rtsp://host)
    if "@" in camera_url:
        parts = camera_url.split("@", 1)
        if len(parts) == 2:
            scheme_and_host = parts[0].split("://", 1)
            if len(scheme_and_host) == 2:
                camera_url = f"{scheme_and_host[0]}://***@{parts[1]}"
    debug_print(f"  Camera: {camera_url}")

    # Log upload method and URL without credentials
    debug_print(f"  Upload method: {config.upload.method}")
    if config.upload.method == "API" and config.upload.api is not None:
        api_url = config.upload.api.url
        if api_url:
            # Remove query parameters and fragments that might contain secrets
            if "?" in api_url:
                api_url = api_url.split("?")[0]
            if "#" in api_url:
                api_url = api_url.split("#")[0]
            debug_print(f"  Upload API: {api_url}")
        else:
            debug_print("  Upload API: (not set, will use dummy server)")
    elif config.upload.method == "SFTP" and config.upload.sftp is not None:
        debug_print(
            f"  Upload SFTP: {config.upload.sftp.host}:{config.upload.sftp.port}{config.upload.sftp.remote_path}"
        )
    else:
        debug_print(f"  Upload: {config.upload.method} (configuration not available)")

    # METAR configuration
    debug_print(f"  METAR overlay: {'enabled' if config.metar.enabled else 'disabled'}")
    if config.metar.enabled:
        debug_print(f"  METAR ICAO code: {config.metar.icao_code}")

    debug_print()  # Empty line for readability

    # Run initial capture
    await _capture_and_upload_wrapper()

    # Start scheduled captures
    await _schedule_next_capture_wrapper()

    # Keep the event loop running until shutdown event is set
    # Use a loop that periodically checks for shutdown to ensure responsiveness
    try:
        while not _shutdown_event.is_set():
            try:
                # Wait with timeout to allow periodic checks and signal handling
                await asyncio.wait_for(_shutdown_event.wait(), timeout=0.5)
                break
            except asyncio.TimeoutError:
                # Continue loop to check again (allows signals to be processed)
                continue
    except asyncio.CancelledError:
        pass
    finally:
        # Cancel any running capture task
        _running_task = _running_task_ref.get("value")
        if _running_task and not _running_task.done():
            _running_task.cancel()
            try:
                await asyncio.wait_for(_running_task, timeout=1.0)
            except (TimeoutError, asyncio.CancelledError, Exception):
                pass

        # Cancel all other running tasks (scheduler jobs, etc.)
        tasks = [t for t in asyncio.all_tasks() if t is not asyncio.current_task() and not t.done()]
        if tasks:
            for task in tasks:
                task.cancel()
            # Wait briefly for tasks to cancel (with timeout)
            try:
                await asyncio.wait_for(asyncio.gather(*tasks, return_exceptions=True), timeout=1.0)
            except (TimeoutError, Exception):
                pass

        # Shutdown scheduler gracefully
        # Use wait=False to avoid blocking if a job is stuck
        if scheduler:
            try:
                # Remove all jobs first to prevent new ones from starting
                scheduler.remove_all_jobs()
                # Shutdown without waiting (jobs will check shutdown event and return early)
                scheduler.shutdown(wait=False)
            except Exception:
                pass


def main() -> None:
    """Main entry point."""
    # Parse command-line arguments
    parser = argparse.ArgumentParser(
        description="Webcam Capture Service for aeronautical webcam capture and upload"
    )
    parser.add_argument(
        "--config",
        "-c",
        type=str,
        default=None,
        help="Path to configuration file (overrides CONFIG_PATH environment variable)",
    )
    args = parser.parse_args()

    # Register shutdown handlers (fallback for systems where add_signal_handler doesn't work)
    # The async context will also register handlers, but this ensures they work on all platforms
    if hasattr(signal, "SIGTERM"):
        signal.signal(signal.SIGTERM, shutdown)
    if hasattr(signal, "SIGINT"):
        signal.signal(signal.SIGINT, shutdown)

    try:
        asyncio.run(run_service(config_path=args.config))
    except KeyboardInterrupt:
        # Handle Ctrl+C if signal handler didn't work
        print("\nStopping service...")
        sys.exit(0)


if __name__ == "__main__":
    main()
