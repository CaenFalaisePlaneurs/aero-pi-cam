"""JSON metadata generation for SFTP uploads."""

import json
import os
from datetime import UTC, datetime, timedelta
from urllib.parse import urlparse

from .. import __version__
from ..core.config import Config


def generate_metadata_json(
    metadata: dict[str, str],
    config: Config,
    image_url: str,
    no_metar_image_url: str | None = None,
    images_map: dict[str, str] | None = None,
) -> bytes:
    """Generate JSON metadata file for SFTP upload.

    Produces v1 format when images_map is None (backward compatible),
    or v2 format when images_map is provided (history active).

    Args:
        metadata: Metadata dictionary with timestamp, location, is_day, raw_metar, raw_taf
        config: Full configuration object
        image_url: Full URL to the image with METAR overlay (if enabled)
        no_metar_image_url: Optional URL to the clean image without METAR overlay
        images_map: Optional {timestamp_iso: url} map for v2 history format

    Returns:
        JSON bytes ready to upload
    """
    common = _build_common_fields(metadata, config)

    if images_map is not None:
        json_data = _build_v2(common, metadata, config, image_url, images_map)
    else:
        json_data = _build_v1(common, metadata, config, image_url, no_metar_image_url)

    return json.dumps(json_data, indent=2).encode("utf-8")


def _compute_ttl(config: Config, is_day_time: bool) -> int:
    """Compute TTL in seconds based on day/night mode and debug flag."""
    debug_enabled = os.getenv("DEBUG_MODE", "false").lower() == "true"
    if debug_enabled:
        if config.debug:
            return (
                config.debug.day_interval_seconds
                if is_day_time
                else config.debug.night_interval_seconds
            )
        return 10 if is_day_time else 30
    return (
        config.schedule.day_interval_seconds
        if is_day_time
        else config.schedule.night_interval_seconds
    )


def _build_common_fields(metadata: dict[str, str], config: Config) -> dict[str, object]:
    """Build fields shared by both v1 and v2 formats."""
    is_day_time = metadata.get("is_day", "true").lower() == "true"
    debug_enabled = os.getenv("DEBUG_MODE", "false").lower() == "true"
    ttl_seconds = _compute_ttl(config, is_day_time)

    timestamp_str = metadata.get("timestamp", "")
    if timestamp_str:
        try:
            if timestamp_str.endswith("Z"):
                timestamp_str = timestamp_str[:-1] + "+00:00"
            update_time = datetime.fromisoformat(timestamp_str)
            if update_time.tzinfo is None:
                update_time = update_time.replace(tzinfo=UTC)
            elif update_time.tzinfo != UTC:
                update_time = update_time.astimezone(UTC)
        except (ValueError, AttributeError):
            update_time = datetime.now(UTC)
    else:
        update_time = datetime.now(UTC)

    update_time_iso = update_time.isoformat().replace("+00:00", "Z")
    next_update_time = update_time + timedelta(seconds=ttl_seconds)

    return {
        "software_version": f"aero-pi-cam {__version__}",
        "software_source": f"{config.metadata.github_repo}/releases/tag/{__version__}",
        "day_night_mode": "day" if is_day_time else "night",
        "debug_mode": debug_enabled,
        "last_update": update_time_iso,
        "last_update_timestamp": int(update_time.timestamp()),
        "next_update": next_update_time.isoformat().replace("+00:00", "Z"),
        "next_update_timestamp": int(next_update_time.timestamp()),
        "ttl_seconds": ttl_seconds,
    }


def _build_camera_metadata(metadata: dict[str, str], config: Config) -> dict[str, object]:
    """Build camera-level metadata (location, metar, etc.)."""
    raw_metar = metadata.get("raw_metar", "")
    raw_taf = metadata.get("raw_taf", "")
    sunrise = metadata.get("sunrise", "")
    sunset = metadata.get("sunset", "")
    camera_heading = metadata.get("camera_heading", config.location.camera_heading)

    return {
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
            "icao_code": config.metar.icao_code if config.metar.enabled else None,
            "source": (urlparse(config.metar.api_url).netloc if config.metar.enabled else None),
            "raw_metar": raw_metar if (config.metar.enabled and raw_metar) else None,
            "raw_taf": raw_taf if (config.metar.enabled and raw_taf) else None,
        },
    }


def _build_v1(
    common: dict[str, object],
    metadata: dict[str, str],
    config: Config,
    image_url: str,
    no_metar_image_url: str | None,
) -> dict[str, object]:
    """Build v1 JSON structure (backward compatible, no history)."""
    ttl_seconds = common.pop("ttl_seconds")
    cam_meta = _build_camera_metadata(metadata, config)

    image_entry: dict[str, object] = {
        "path": image_url,
        "no_metar_path": no_metar_image_url if no_metar_image_url else image_url,
        "TTL": str(ttl_seconds),
        **cam_meta,
    }

    return {
        "version": 1,
        **common,
        "images": [image_entry],
    }


def _build_v2(
    common: dict[str, object],
    metadata: dict[str, str],
    config: Config,
    image_url: str,
    images_map: dict[str, str],
) -> dict[str, object]:
    """Build v2 JSON structure (history active, cameras array)."""
    ttl_seconds = common.pop("ttl_seconds")
    cam_meta = _build_camera_metadata(metadata, config)

    camera_entry: dict[str, object] = {
        "path": image_url,
        "TTL": str(ttl_seconds),
        **cam_meta,
        "images": images_map,
    }

    return {
        "version": 2,
        **common,
        "cameras": [camera_entry],
    }
