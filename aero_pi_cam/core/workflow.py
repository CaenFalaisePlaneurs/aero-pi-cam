"""Capture and upload workflow orchestration."""

import asyncio
from datetime import UTC, datetime
from io import BytesIO

from PIL import Image

from ..capture.capture import capture_frame
from ..overlay.overlay import add_comprehensive_overlay
from ..upload.dummy_api import get_image_filename
from ..upload.upload import upload_image
from ..weather.day_night import get_day_night_mode
from ..weather.metar import fetch_metar, get_raw_metar, get_raw_taf
from ..weather.sun import get_sun_times
from .config import Config
from .debug import _is_debug_mode, debug_print


async def capture_and_upload(
    config: Config,
    shutdown_event: asyncio.Event | None,
    is_running_ref: dict[str, bool],
    camera_connected_ref: dict[str, bool],
    api_connected_ref: dict[str, bool],
    running_task_ref: dict[str, asyncio.Task | None],
) -> None:
    """Main capture and upload workflow.

    Args:
        config: Configuration object
        shutdown_event: Event to check for shutdown requests
        is_running_ref: Dictionary with 'value' key to track if capture is running
        camera_connected_ref: Dictionary with 'value' key to track camera connection status
        api_connected_ref: Dictionary with 'value' key to track API connection status
        running_task_ref: Dictionary with 'value' key to store current running task
    """
    if is_running_ref.get("value", False):
        print("Capture skipped: already running (previous capture still in progress)")
        return

    if config is None:
        debug_print("\nCapture skipped: no config")
        return

    # Check for shutdown before starting
    if shutdown_event and shutdown_event.is_set():
        return

    is_running_ref["value"] = True
    task = asyncio.current_task()
    if task:
        running_task_ref["value"] = task
    # Clear countdown line and print newline when capture starts
    print()  # Newline to clear countdown
    capture_time = datetime.now(UTC)
    is_day_time = get_day_night_mode(capture_time, config)

    try:
        # Check for shutdown before capture
        if shutdown_event and shutdown_event.is_set():
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
        if shutdown_event and shutdown_event.is_set():
            return

        # Log first camera connection
        if not camera_connected_ref.get("value", False):
            print("Connected to camera")
            camera_connected_ref["value"] = True

        # Log image capture with date/time and schedule mode (UTC)
        time_str = capture_time.strftime("%Y-%m-%dT%H:%M:%SZ")
        mode_str = "day" if is_day_time else "night"

        # Get current interval based on mode and debug settings
        if _is_debug_mode():
            if config.debug:
                interval_seconds = (
                    config.debug.day_interval_seconds
                    if is_day_time
                    else config.debug.night_interval_seconds
                )
            else:
                interval_seconds = 10 if is_day_time else 30
        else:
            interval_seconds = (
                config.schedule.day_interval_seconds
                if is_day_time
                else config.schedule.night_interval_seconds
            )

        # Get sunrise and sunset times for the day
        sun_times = get_sun_times(capture_time, config.location)
        sunrise_str = sun_times["sunrise"].strftime("%H:%M:%SZ")
        sunset_str = sun_times["sunset"].strftime("%H:%M:%SZ")

        print(
            f"Captured image at {time_str} ({mode_str} mode - {interval_seconds}s) - Day: {sunrise_str} to {sunset_str}",
            flush=True,
        )
        image_bytes = result.image

        # Get image dimensions for logging
        img_width, img_height = 2560, 1440  # Default fallback
        try:
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

            # Generate two versions of the image:
            # 1. With METAR overlay (if enabled) - for publishing on other sites
            # 2. Without METAR overlay - for our own site (METAR still in metadata)
            include_metar_overlay = config.metar.enabled and config.metar.raw_metar_enabled

            # Image 1: With METAR overlay (if enabled)
            image_bytes_with_metar = add_comprehensive_overlay(
                image_bytes,
                config,
                capture_time,
                sun_times["sunrise"],
                sun_times["sunset"],
                raw_metar=raw_metar_text,
                raw_taf=raw_taf_text,
                include_metar_overlay=include_metar_overlay,
            )

            # Image 2: Without METAR overlay and without sun info overlay (but all still in metadata)
            image_bytes_clean = add_comprehensive_overlay(
                image_bytes,
                config,
                capture_time,
                sun_times["sunrise"],
                sun_times["sunset"],
                raw_metar=raw_metar_text,
                raw_taf=raw_taf_text,
                include_metar_overlay=False,
                include_sun_info=False,
            )
        except Exception as e:
            # Log overlay errors for debugging
            debug_print(f"Overlay failed: {e}")
            if _is_debug_mode():
                import traceback

                traceback.print_exc()
            # Continue with original image if overlay fails (use same image for both)
            image_bytes_with_metar = image_bytes
            image_bytes_clean = image_bytes

        # Check for shutdown before upload
        if shutdown_event and shutdown_event.is_set():
            return

        # Prepare metadata
        metadata = {
            "timestamp": capture_time.isoformat().replace("+00:00", "Z"),
            "location": config.location.name,
            "is_day": str(is_day_time),
            "raw_metar": raw_metar_text or "",
            "raw_taf": raw_taf_text or "",
            "sunrise": sun_times["sunrise"].isoformat().replace("+00:00", "Z"),
            "sunset": sun_times["sunset"].isoformat().replace("+00:00", "Z"),
            "camera_heading": config.location.camera_heading,
        }

        # Upload both images
        # Image 1: With METAR overlay (default filename)
        filename_with_metar = get_image_filename(config, clean=False)
        upload_result = await upload_image(
            image_bytes_with_metar, metadata, config=config, filename=filename_with_metar
        )

        # Log first connection
        if not api_connected_ref.get("value", False) and upload_result.success:
            print(f"Connected to {config.upload.method}")
            api_connected_ref["value"] = True

        if upload_result.success:
            print(f"Pushed image to {config.upload.method}", flush=True)
        else:
            debug_print(f"Failed to push image: {upload_result.error}")

        # Image 2: Without METAR overlay (clean filename)
        filename_clean = get_image_filename(config, clean=True)
        upload_result_clean = await upload_image(
            image_bytes_clean, metadata, config=config, filename=filename_clean
        )

        if upload_result_clean.success:
            debug_print(f"Pushed clean image to {config.upload.method}", flush=True)
        else:
            debug_print(f"Failed to push clean image: {upload_result_clean.error}")

    except asyncio.CancelledError:
        # Task was cancelled during shutdown
        raise
    except Exception:
        pass
    finally:
        is_running_ref["value"] = False
        running_task_ref["value"] = None
