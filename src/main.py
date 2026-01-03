"""Main entry point for webcam capture service."""

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
    from .overlay import add_comprehensive_overlay, generate_overlay_only
    from .sun import get_sun_times, is_day
    from .upload import upload_image
except ImportError:
    # Allow running as script: python src/main.py
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).parent.parent))
    from src.capture import capture_frame
    from src.config import Config, load_config
    from src.metar import fetch_metar, get_raw_metar, get_raw_taf
    from src.overlay import add_comprehensive_overlay, generate_overlay_only
    from src.sun import get_sun_times, is_day
    from src.upload import upload_image

CONFIG_PATH = os.getenv("CONFIG_PATH", "config.yaml")

scheduler: AsyncIOScheduler | None = None
is_running = False
config: Config | None = None
_camera_connected = False
_api_connected = False
_shutdown_event: asyncio.Event | None = None


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
    global is_running, _camera_connected, _api_connected
    if is_running:
        print("\nCapture skipped: already running")
        return

    if config is None:
        print("\nCapture skipped: no config")
        return

    is_running = True
    # Clear countdown line and print newline when capture starts
    print()  # Newline to clear countdown
    capture_time = datetime.now(UTC)
    is_day_time = get_day_night_mode(capture_time)

    try:
        # Capture frame (use separate credentials if provided, otherwise use URL-embedded)
        result = capture_frame(
            config.camera.rtsp_url,
            rtsp_user=config.camera.rtsp_user,
            rtsp_password=config.camera.rtsp_password,
        )
        if not result.success or not result.image:
            if result.error:
                print(f"Capture failed: {result.error}")
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
            f"Captured image at {time_str} ({mode_str} mode) - Day: {sunrise_str} to {sunset_str}"
        )
        image_bytes = result.image

        # Get image dimensions (needed for overlay-only debug image)
        img_width, img_height = 2560, 1440  # Default fallback
        try:
            from io import BytesIO

            from PIL import Image

            img = Image.open(BytesIO(image_bytes))
            img_width, img_height = img.size
            print(f"Captured image size: {img_width}x{img_height}")
        except Exception:
            pass

        # In debug mode: save 3 images (capture, overlay, composited)
        # In normal mode: only use composited image (upload, no disk save)
        debug_mode = os.getenv("DEBUG_MODE", "false").lower() == "true"
        if debug_mode:
            # Use project root for local dev, /opt/webcam-cfp for production
            project_root = Path(__file__).parent.parent
            debug_dir = project_root / ".debug"
            os.makedirs(debug_dir, exist_ok=True)
            timestamp_str = capture_time.strftime("%Y%m%d_%H%M%S")

            # Save captured image (original, before overlay)
            debug_filename = str(debug_dir / f"capture_{timestamp_str}.jpg")
            try:
                with open(debug_filename, "wb") as f:
                    f.write(image_bytes)
                print(f"Saved capture image to {debug_filename}")
            except Exception:
                pass

        # Add comprehensive overlay with logo, provider info, camera name, UTC timestamp, sunrise/sunset, and METAR
        try:
            raw_metar_text = None
            raw_taf_text = None
            metar_icao_code = None

            # Fetch METAR if enabled
            if config.metar.enabled:
                metar_result = await fetch_metar(config.metar.icao_code, config.metar.api_url)
                if metar_result.success and metar_result.data:
                    raw_metar_text = get_raw_metar(metar_result.data)
                    raw_taf_text = get_raw_taf(metar_result.data)
                    metar_icao_code = metar_result.data.get("icaoId", config.metar.icao_code)

            # Add comprehensive overlay (composites overlay on camera image)
            image_bytes = add_comprehensive_overlay(
                image_bytes,
                config,
                capture_time,
                sun_times["sunrise"],
                sun_times["sunset"],
                raw_metar=raw_metar_text,
                raw_taf=raw_taf_text,
                metar_icao=metar_icao_code,
            )

            # In debug mode: save overlay-only and composited images
            if debug_mode:
                try:
                    # Save overlay-only image (transparent background)
                    overlay_only_bytes = generate_overlay_only(
                        img_width,
                        img_height,
                        config,
                        capture_time,
                        sun_times["sunrise"],
                        sun_times["sunset"],
                        raw_metar=raw_metar_text,
                        raw_taf=raw_taf_text,
                        metar_icao=metar_icao_code,
                    )
                    overlay_debug_filename = str(debug_dir / f"overlay_{timestamp_str}.png")
                    with open(overlay_debug_filename, "wb") as f:
                        f.write(overlay_only_bytes)
                    print(f"Saved overlay-only image to {overlay_debug_filename}")

                    # Save composited image (camera + overlay)
                    composited_filename = str(debug_dir / f"composited_{timestamp_str}.jpg")
                    with open(composited_filename, "wb") as f:
                        f.write(image_bytes)
                    print(f"Saved composited image (camera + overlay) to {composited_filename}")
                except Exception as e:
                    print(f"Failed to generate debug images: {e}")
        except Exception as e:
            # Log overlay errors for debugging
            print(f"Overlay failed: {e}")
            import traceback

            traceback.print_exc()
            # Continue with original image if overlay fails
            pass

        # Upload composited image (camera + overlay)
        # In debug mode: skip upload (images saved locally)
        # In normal mode: upload only the composited image
        debug_enabled = os.getenv("DEBUG_MODE", "false").lower() == "true"

        if not debug_enabled:
            metadata = {
                "timestamp": capture_time.isoformat().replace("+00:00", "Z"),
                "location": config.location.name,
                "is_day": str(is_day_time),
            }
            upload_result = await upload_image(image_bytes, metadata, config.api)

            # Log first API connection
            if not _api_connected and upload_result.success:
                print("Connected to API")
                _api_connected = True

            if upload_result.success:
                print("Pushed image to API")
            else:
                print(f"Failed to push image: {upload_result.error}")
        else:
            # In debug mode, skip upload since images are saved locally
            pass

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
        print(f"Schedule mode: {mode_str} (DEBUG), capture timer: {timer_str}")

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
        )

        # Re-evaluate schedule every 30 seconds for day/night transitions in debug mode
        scheduler.add_job(
            schedule_next_capture,
            trigger=IntervalTrigger(seconds=30),
            id="schedule_check",
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
        print(f"Schedule mode: {mode_str}, capture timer: {timer_str}")

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
        )

        # Re-evaluate schedule every 5 minutes for day/night transitions
        scheduler.add_job(
            schedule_next_capture,
            trigger=IntervalTrigger(minutes=5),
            id="schedule_check",
        )


def shutdown(signum: int, frame: object) -> None:  # noqa: ARG001
    """Graceful shutdown handler."""
    global _shutdown_event
    # Print newline to clear countdown line, then shutdown message
    print()  # Newline to clear the countdown
    print("Stopping service")
    if _shutdown_event:
        _shutdown_event.set()


async def run_service() -> None:
    """Run the service in an async context."""
    global config, _shutdown_event, scheduler
    _shutdown_event = asyncio.Event()

    print("Webcam Capture Service starting...")

    # Check for required external dependencies
    check_external_dependencies()

    print(f"Loading config from: {CONFIG_PATH}")

    try:
        config = load_config(CONFIG_PATH)
    except Exception as e:
        print(f"Failed to load config: {e}")
        sys.exit(1)

    # Check debug mode status
    debug_enabled = os.getenv("DEBUG_MODE", "false").lower() == "true"

    # Log configuration summary
    print("\nConfiguration:")
    print(f"  Debug mode: {'enabled' if debug_enabled else 'disabled'}")

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
    print(f"  Day interval: {day_interval}")
    print(f"  Night interval: {night_interval}")

    print(f"  Airfield (ICAO): {config.location.name}")
    print(f"  Location: {config.location.latitude}, {config.location.longitude}")

    # Log camera URL without credentials for security
    camera_url = config.camera.rtsp_url
    # Remove credentials from URL if present (rtsp://user:pass@host -> rtsp://host)
    if "@" in camera_url:
        parts = camera_url.split("@", 1)
        if len(parts) == 2:
            scheme_and_host = parts[0].split("://", 1)
            if len(scheme_and_host) == 2:
                camera_url = f"{scheme_and_host[0]}://***@{parts[1]}"
    print(f"  Camera: {camera_url}")

    # Log API URL without credentials
    api_url = config.api.url
    # Remove query parameters and fragments that might contain secrets
    if "?" in api_url:
        api_url = api_url.split("?")[0]
    if "#" in api_url:
        api_url = api_url.split("#")[0]
    print(f"  Upload API: {api_url}")

    # METAR configuration
    print(f"  METAR overlay: {'enabled' if config.metar.enabled else 'disabled'}")
    if config.metar.enabled:
        print(f"  METAR ICAO code: {config.metar.icao_code}")

    print()  # Empty line for readability

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
        if scheduler:
            try:
                scheduler.shutdown()
            except Exception:
                pass


def main() -> None:
    """Main entry point."""
    # Register shutdown handlers
    signal.signal(signal.SIGTERM, shutdown)
    signal.signal(signal.SIGINT, shutdown)

    try:
        asyncio.run(run_service())
    except KeyboardInterrupt:
        # Signal handler will handle this
        pass


if __name__ == "__main__":
    main()
