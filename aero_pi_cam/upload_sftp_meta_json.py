"""JSON metadata generation for SFTP uploads."""

import json
import os
from datetime import UTC, datetime, timedelta

from .config import Config


def generate_metadata_json(
    metadata: dict[str, str],
    config: Config,
    image_url: str,
    no_metar_image_url: str | None = None,
) -> bytes:
    """Generate JSON metadata file for SFTP upload.

    Args:
        metadata: Metadata dictionary with timestamp, location, is_day, raw_metar, raw_taf
        config: Full configuration object
        image_url: Full URL to the image with METAR overlay (if enabled)
        no_metar_image_url: Optional URL to the clean image without METAR overlay

    Returns:
        JSON bytes ready to upload
    """
    # Determine day/night mode
    is_day_time = metadata.get("is_day", "true").lower() == "true"
    mode_str = "day" if is_day_time else "night"

    # Check debug mode
    debug_enabled = os.getenv("DEBUG_MODE", "false").lower() == "true"

    # Calculate TTL based on day/night mode and debug mode
    if debug_enabled:
        # Use debug intervals (in seconds)
        if config.debug:
            ttl_seconds = (
                config.debug.day_interval_seconds
                if is_day_time
                else config.debug.night_interval_seconds
            )
        else:
            # Default debug intervals if config not provided
            ttl_seconds = 10 if is_day_time else 30
    else:
        # Use normal intervals (already in seconds)
        ttl_seconds = (
            config.schedule.day_interval_seconds
            if is_day_time
            else config.schedule.night_interval_seconds
        )

    # Get capture timestamp from metadata (use this as base time, not current time)
    # This ensures last_update matches the actual capture time
    timestamp_str = metadata.get("timestamp", "")
    if timestamp_str:
        # Parse ISO format timestamp (e.g., "2026-01-02T15:30:00Z")
        try:
            # Remove 'Z' suffix and parse
            if timestamp_str.endswith("Z"):
                timestamp_str = timestamp_str[:-1] + "+00:00"
            update_time = datetime.fromisoformat(timestamp_str)
            # Ensure UTC timezone
            if update_time.tzinfo is None:
                update_time = update_time.replace(tzinfo=UTC)
            elif update_time.tzinfo != UTC:
                update_time = update_time.astimezone(UTC)
        except (ValueError, AttributeError):
            # Fallback to current time if parsing fails
            update_time = datetime.now(UTC)
    else:
        # Fallback to current time if timestamp not in metadata
        update_time = datetime.now(UTC)

    update_time_iso = update_time.isoformat().replace("+00:00", "Z")
    update_timestamp = int(update_time.timestamp())

    # Calculate next update time based on TTL (from capture time)
    next_update_time = update_time + timedelta(seconds=ttl_seconds)
    next_update_iso = next_update_time.isoformat().replace("+00:00", "Z")
    next_update_timestamp = int(next_update_time.timestamp())

    # Get METAR/TAF data from metadata
    raw_metar = metadata.get("raw_metar", "")
    raw_taf = metadata.get("raw_taf", "")
    sunrise = metadata.get("sunrise", "")
    sunset = metadata.get("sunset", "")
    camera_heading = metadata.get("camera_heading", config.location.camera_heading)

    # Create JSON metadata with all requested fields
    json_data = {
        "day_night_mode": mode_str,
        "debug_mode": debug_enabled,
        "last_update": update_time_iso,
        "last_update_timestamp": update_timestamp,
        "next_update": next_update_iso,
        "next_update_timestamp": next_update_timestamp,
        "images": [
            {
                "path": image_url,
                "no_metar_path": no_metar_image_url if no_metar_image_url else image_url,
                "TTL": str(ttl_seconds),
                "provider_name": config.overlay.provider_name,
                "camera_name": config.overlay.camera_name,
                "license_mark": config.metadata.license_mark,
                "location": {
                    "name": config.location.name,
                    "latitude": config.location.latitude,
                    "longitude": config.location.longitude,
                    "camera_heading": camera_heading,
                },
                "sunrise": sunrise if sunrise else None,
                "sunset": sunset if sunset else None,
                "metar": {
                    "enabled": config.metar.enabled,
                    "icao_code": config.metar.icao_code if config.metar.enabled else None,
                    "raw_metar": raw_metar if (config.metar.enabled and raw_metar) else None,
                    "raw_taf": raw_taf if (config.metar.enabled and raw_taf) else None,
                },
            }
        ],
    }
    return json.dumps(json_data, indent=2).encode("utf-8")
