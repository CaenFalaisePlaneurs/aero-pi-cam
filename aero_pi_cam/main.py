"""Main entry point for webcam capture service."""

import argparse
import asyncio
import os
import shutil
import signal
import sys
from datetime import UTC, datetime
from pathlib import Path

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

try:
    from .capture import capture_frame
    from .config import Config, load_config
    from .metar import fetch_metar, get_raw_metar, get_raw_taf
    from .overlay import add_comprehensive_overlay
    from .sun import get_sun_times, is_day
    from .upload import upload_image
except ImportError:
    # Allow running as script: python aero_pi_cam/main.py
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).parent.parent))
    from aero_pi_cam.capture import capture_frame
    from aero_pi_cam.config import Config, load_config
    from aero_pi_cam.metar import fetch_metar, get_raw_metar, get_raw_taf
    from aero_pi_cam.overlay import add_comprehensive_overlay
    from aero_pi_cam.sun import get_sun_times, is_day
    from aero_pi_cam.upload import upload_image

# Default config path (can be overridden by command-line argument or CONFIG_PATH env var)

scheduler: AsyncIOScheduler | None = None
is_running = False
config: Config | None = None
_camera_connected = False
_api_connected = False
_shutdown_event: asyncio.Event | None = None


def _is_debug_mode() -> bool:
    """Check if debug mode is enabled."""
    return os.getenv("DEBUG_MODE", "false").lower() == "true"


def debug_print(*args: object, **kwargs: object) -> None:
    """Print only if DEBUG_MODE is enabled."""
    if _is_debug_mode():
        print(*args, **kwargs)  # type: ignore[call-overload]


def check_external_dependencies() -> None:
    """Check for required external dependencies and exit if missing."""
    missing_deps: list[str] = []

    # Check for ffmpeg (required for RTSP capture)
    if not shutil.which("ffmpeg"):
        missing_deps.append("ffmpeg")

    # Check for cairo library (required for cairosvg/SVG icon support)
    # This is a system library, so we check if cairosvg can import properly
    try:
        import cairosvg  # noqa: F401
    except OSError as e:
        error_msg = str(e).lower()
        if "cairo" in error_msg or "libcairo" in error_msg or "no library called" in error_msg:
            missing_deps.append("cairo (system library)")
    except ImportError:
        # cairosvg not installed, but that's a Python dependency issue
        pass

    if missing_deps:
        print("ERROR: Required external dependencies are missing:")
        for dep in missing_deps:
            print(f"  - {dep}")
        print("\nInstallation instructions:")
        if "ffmpeg" in missing_deps:
            print("  macOS: brew install ffmpeg")
            print("  Linux/Debian: sudo apt install ffmpeg")
            print("  Raspberry Pi: sudo apt install ffmpeg")
        if "cairo (system library)" in missing_deps:
            print("  macOS: brew install cairo")
            print("  Linux/Debian: sudo apt install libcairo2-dev")
            print("  Raspberry Pi: sudo apt install libcairo2-dev")
        sys.exit(1)


def get_day_night_mode(capture_time: datetime) -> bool:
    """Get day/night mode with optional debug override.

    Checks DEBUG_DAY_NIGHT_MODE env var first. If set to "day" or "night",
    returns that mode. Otherwise uses actual sun calculation.
    """
    debug_mode = os.getenv("DEBUG_DAY_NIGHT_MODE", "").lower()
    if debug_mode == "day":
        return True
    if debug_mode == "night":
        return False
    # Use actual sun calculation
    if config is None:
        return True  # Default to day if no config
    return is_day(capture_time, config.location)


async def capture_and_upload() -> None:
    """Main capture and upload workflow."""
    global is_running, _camera_connected, _api_connected, _shutdown_event
    if is_running:
        print("Capture skipped: already running (previous capture still in progress)")
        return

    if config is None:
        debug_print("\nCapture skipped: no config")
        return

    # Check for shutdown before starting
    if _shutdown_event and _shutdown_event.is_set():
        return

    is_running = True
    # Clear countdown line and print newline when capture starts
    print()  # Newline to clear countdown
    capture_time = datetime.now(UTC)
    is_day_time = get_day_night_mode(capture_time)

    try:
        # Check for shutdown before capture
        if _shutdown_event and _shutdown_event.is_set():
            return

        # Capture frame (use separate credentials if provided, otherwise use URL-embedded)
        result = capture_frame(
            config.camera.rtsp_url,
            rtsp_user=config.camera.rtsp_user,
            rtsp_password=config.camera.rtsp_password,
        )
        if not result.success or not result.image:
            if result.error:
                debug_print(f"Capture failed: {result.error}")
            return

        # Check for shutdown after capture
        if _shutdown_event and _shutdown_event.is_set():
            return

        # Log first camera connection
        if not _camera_connected:
            print("Connected to camera")
            _camera_connected = True

        # Log image capture with date/time and schedule mode (UTC)
        time_str = capture_time.strftime("%Y-%m-%d %H:%M:%S UTC")
        mode_str = "day" if is_day_time else "night"

        # Get sunrise and sunset times for the day
        sun_times = get_sun_times(capture_time, config.location)
        sunrise_str = sun_times["sunrise"].strftime("%H:%M:%S UTC")
        sunset_str = sun_times["sunset"].strftime("%H:%M:%S UTC")

        print(
            f"Captured image at {time_str} ({mode_str} mode) - Day: {sunrise_str} to {sunset_str}",
            flush=True,
        )
        image_bytes = result.image

        # Get image dimensions for logging
        img_width, img_height = 2560, 1440  # Default fallback
        try:
            from io import BytesIO

            from PIL import Image

            img = Image.open(BytesIO(image_bytes))
            img_width, img_height = img.size
            debug_print(f"Captured image size: {img_width}x{img_height}")
        except Exception:
            pass

        # Add comprehensive overlay with logo, provider info, camera name, UTC timestamp, sunrise/sunset, and METAR
        try:
            raw_metar_text = None
            raw_taf_text = None

            # Fetch METAR if enabled
            if config.metar.enabled:
                metar_result = await fetch_metar(config.metar.icao_code, config.metar.api_url)
                if metar_result.success and metar_result.data:
                    raw_metar_text = get_raw_metar(metar_result.data)
                    raw_taf_text = get_raw_taf(metar_result.data)

            # Add comprehensive overlay (composites overlay on camera image)
            image_bytes = add_comprehensive_overlay(
                image_bytes,
                config,
                capture_time,
                sun_times["sunrise"],
                sun_times["sunset"],
                raw_metar=raw_metar_text,
                raw_taf=raw_taf_text,
            )
        except Exception as e:
            # Log overlay errors for debugging
            debug_print(f"Overlay failed: {e}")
            if _is_debug_mode():
                import traceback

                traceback.print_exc()
            # Continue with original image if overlay fails
            pass

        # Check for shutdown before upload
        if _shutdown_event and _shutdown_event.is_set():
            return

        # Upload composited image (camera + overlay)
        # Always upload (dummy server will be used in debug mode or if API URL is not set)
        metadata = {
            "timestamp": capture_time.isoformat().replace("+00:00", "Z"),
            "location": config.location.name,
            "is_day": str(is_day_time),
        }
        upload_result = await upload_image(image_bytes, metadata, config=config)

        # Log first connection
        if not _api_connected and upload_result.success:
            print(f"Connected to {config.upload_method}")
            _api_connected = True

        if upload_result.success:
            print(f"Pushed image to {config.upload_method}", flush=True)
        else:
            debug_print(f"Failed to push image: {upload_result.error}")

    except Exception:
        pass
    finally:
        is_running = False


async def log_countdown() -> None:
    """Log countdown until next capture in debug mode."""
    global scheduler, config
    if scheduler is None:
        return

    # Double-check debug mode is enabled (safety check)
    if config is None:
        return
    debug_enabled = os.getenv("DEBUG_MODE", "false").lower() == "true"
    if not debug_enabled:
        return

    try:
        job = scheduler.get_job("capture_job")
        if not job:
            return

        if not job.next_run_time:
            # Job exists but next run time not set yet
            print("Next capture in: scheduling...", end="\r", flush=True)
            return

        now = datetime.now(UTC)
        # Ensure next_run_time is timezone-aware
        next_run = job.next_run_time
        if next_run.tzinfo is None:
            next_run = next_run.replace(tzinfo=UTC)
        elif next_run.tzinfo != UTC:
            next_run = next_run.astimezone(UTC)

        remaining = (next_run - now).total_seconds()
        # Add small buffer to account for timing precision
        if remaining > 0.5:
            remaining_int = int(remaining)
            hours = remaining_int // 3600
            minutes = (remaining_int % 3600) // 60
            seconds = remaining_int % 60
            countdown_str = f"{hours}:{minutes:02d}:{seconds:02d}"
            print(f"Next capture in: {countdown_str}", end="\r", flush=True)
        else:
            # Job is executing or about to execute
            print("Next capture in: executing...", end="\r", flush=True)
    except Exception:
        # Silently ignore errors (job might not exist yet)
        pass


async def schedule_next_capture() -> None:
    """Schedule captures with dynamic interval based on day/night."""
    global scheduler
    if config is None:
        return

    now = datetime.now(UTC)
    time_str = now.strftime("%Y-%m-%d %H:%M:%S UTC")
    print(f"Re-evaluating schedule at {time_str}")
    is_day_time = get_day_night_mode(now)
    mode_str = "day" if is_day_time else "night"

    # Check if debug mode override is active
    debug_override = os.getenv("DEBUG_DAY_NIGHT_MODE", "").lower()
    if debug_override in ("day", "night"):
        mode_str += f" (forced via DEBUG_DAY_NIGHT_MODE={debug_override})"

    # Check if debug mode is enabled (via env var)
    debug_enabled = os.getenv("DEBUG_MODE", "false").lower() == "true"

    # Use debug intervals if enabled, otherwise use normal intervals
    if debug_enabled:
        # Get debug intervals from config if available, otherwise use defaults
        if config.debug:
            interval_seconds = (
                config.debug.day_interval_seconds
                if is_day_time
                else config.debug.night_interval_seconds
            )
        else:
            # Default debug intervals if config not provided
            interval_seconds = 10 if is_day_time else 30

        # Format timer as h:m:s
        hours = interval_seconds // 3600
        minutes = (interval_seconds % 3600) // 60
        seconds = interval_seconds % 60
        timer_str = f"{hours}:{minutes:02d}:{seconds:02d}"
        debug_print(f"Schedule mode: {mode_str} (DEBUG), capture timer: {timer_str}")

        # Update or create scheduler
        if scheduler is None:
            scheduler = AsyncIOScheduler()
            scheduler.start()
        else:
            # Remove existing jobs if they exist
            try:
                scheduler.remove_job("capture_job")
            except Exception:
                pass
            try:
                scheduler.remove_job("schedule_check")
            except Exception:
                pass
            try:
                scheduler.remove_job("countdown_log")
            except Exception:
                pass

        scheduler.add_job(
            capture_and_upload,
            trigger=IntervalTrigger(seconds=interval_seconds),
            id="capture_job",
            max_instances=1,  # Prevent concurrent executions
            coalesce=True,  # Run at most once if multiple runs are missed
            misfire_grace_time=60,  # Ignore missed runs if more than 60 seconds late
        )

        # Re-evaluate schedule every 30 seconds for day/night transitions in debug mode
        scheduler.add_job(
            schedule_next_capture,
            trigger=IntervalTrigger(seconds=30),
            id="schedule_check",
            coalesce=True,  # Run at most once if multiple runs are missed
            misfire_grace_time=30,  # Ignore missed runs if more than 30 seconds late
        )

        # Log countdown every second in debug mode (with coalesce and misfire_grace_time to avoid missed run warnings)
        scheduler.add_job(
            log_countdown,
            trigger=IntervalTrigger(seconds=1),
            id="countdown_log",
            coalesce=True,  # Run at most once if multiple runs are missed
            misfire_grace_time=5,  # Ignore missed runs if more than 5 seconds late
            max_instances=1,
        )
    else:
        # Use the already-calculated is_day_time to select interval
        interval_minutes = (
            config.schedule.day_interval_minutes
            if is_day_time
            else config.schedule.night_interval_minutes
        )
        # Format timer as h:m:s
        hours = interval_minutes // 60
        minutes = interval_minutes % 60
        seconds = 0
        timer_str = f"{hours}:{minutes:02d}:{seconds:02d}"
        debug_print(f"Schedule mode: {mode_str}, capture timer: {timer_str}")

        # Update or create scheduler
        if scheduler is None:
            scheduler = AsyncIOScheduler()
            scheduler.start()
        else:
            # Remove existing jobs if they exist
            try:
                scheduler.remove_job("capture_job")
            except Exception:
                pass
            try:
                scheduler.remove_job("schedule_check")
            except Exception:
                pass
            try:
                scheduler.remove_job("countdown_log")
            except Exception:
                pass

        scheduler.add_job(
            capture_and_upload,
            trigger=IntervalTrigger(minutes=interval_minutes),
            id="capture_job",
            max_instances=1,  # Prevent concurrent executions
            coalesce=True,  # Run at most once if multiple runs are missed
            misfire_grace_time=600,  # Ignore missed runs if more than 10 minutes late
        )

        # Re-evaluate schedule every 5 minutes for day/night transitions
        scheduler.add_job(
            schedule_next_capture,
            trigger=IntervalTrigger(minutes=5),
            id="schedule_check",
            coalesce=True,  # Run at most once if multiple runs are missed
            misfire_grace_time=300,  # Ignore missed runs if more than 5 minutes late
        )


def shutdown(signum: int, frame: object) -> None:  # noqa: ARG001
    """Graceful shutdown handler."""
    global _shutdown_event
    # Print newline to clear countdown line, then shutdown message
    print()  # Newline to clear the countdown
    debug_print("Stopping service")
    if _shutdown_event:
        _shutdown_event.set()


async def run_service(config_path: str | None = None) -> None:
    """Run the service in an async context.

    Args:
        config_path: Path to configuration file. If None, uses CONFIG_PATH env var or default.
    """
    global config, _shutdown_event, scheduler
    _shutdown_event = asyncio.Event()

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
        day_interval = f"{config.schedule.day_interval_minutes}min"
        night_interval = f"{config.schedule.night_interval_minutes}min"
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
    debug_print(f"  Upload method: {config.upload_method}")
    if config.upload_method == "API" and config.api is not None:
        api_url = config.api.url
        if api_url:
            # Remove query parameters and fragments that might contain secrets
            if "?" in api_url:
                api_url = api_url.split("?")[0]
            if "#" in api_url:
                api_url = api_url.split("#")[0]
            debug_print(f"  Upload API: {api_url}")
        else:
            debug_print("  Upload API: (not set, will use dummy server)")
    elif config.upload_method == "SFTP" and config.sftp is not None:
        debug_print(
            f"  Upload SFTP: {config.sftp.host}:{config.sftp.port}{config.sftp.remote_path}"
        )
    else:
        debug_print(f"  Upload: {config.upload_method} (configuration not available)")

    # METAR configuration
    debug_print(f"  METAR overlay: {'enabled' if config.metar.enabled else 'disabled'}")
    if config.metar.enabled:
        debug_print(f"  METAR ICAO code: {config.metar.icao_code}")

    debug_print()  # Empty line for readability

    # Run initial capture
    await capture_and_upload()

    # Start scheduled captures
    await schedule_next_capture()

    # Keep the event loop running until shutdown event is set
    try:
        await _shutdown_event.wait()
    except asyncio.CancelledError:
        pass
    finally:
        # Shutdown scheduler gracefully
        # Use wait=False to avoid blocking if a job is stuck, but give it a short timeout
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

    # Register shutdown handlers
    signal.signal(signal.SIGTERM, shutdown)
    signal.signal(signal.SIGINT, shutdown)

    try:
        asyncio.run(run_service(config_path=args.config))
    except KeyboardInterrupt:
        # Signal handler will handle this
        pass


if __name__ == "__main__":
    main()
