"""Aviation Weather API client for METAR data."""

import os
import re
from dataclasses import dataclass
from typing import Any

import httpx

USER_AGENT = "aero-pi-cam/1.0 (Raspberry Pi webcam capture)"


@dataclass
class MetarResult:
    """Result of METAR fetch operation."""

    success: bool
    data: dict[str, Any] | None = None
    error: str | None = None
    retry_after_seconds: int | None = None


async def fetch_metar(icao_code: str, api_url: str) -> MetarResult:
    """Fetch latest METAR and TAF from Aviation Weather API in raw format."""
    url = f"{api_url}?ids={icao_code}&format=raw&taf=true&hours=1"

    # Log request in debug mode
    debug_mode = os.getenv("DEBUG_MODE", "false").lower() == "true"
    if debug_mode:
        print(f"METAR request: {url}")

    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                url,
                headers={"User-Agent": USER_AGENT},
            )

            # Log response in debug mode
            if debug_mode:
                print(f"METAR response: HTTP {response.status_code}")
                if response.is_success:
                    print(f"METAR response body (raw): {response.text[:500]}")
                else:
                    print(f"METAR response error: {response.text[:500]}")

            # Handle 204 No Content
            if response.status_code == 204:
                return MetarResult(success=False, error="No METAR data available")

            # Handle 429 Too Many Requests
            if response.status_code == 429:
                retry_after = response.headers.get("Retry-After", "60")
                wait_seconds = int(retry_after) if retry_after.isdigit() else 60
                return MetarResult(
                    success=False,
                    error="Rate limited by Aviation Weather API",
                    retry_after_seconds=wait_seconds,
                )

            # Handle 400 Bad Request
            if response.status_code == 400:
                return MetarResult(success=False, error="Invalid METAR request")

            # Handle other non-success responses
            if not response.is_success:
                return MetarResult(
                    success=False,
                    error=f"METAR API error: HTTP {response.status_code}",
                )

            # Parse raw text response
            raw_text = response.text.strip()
            if not raw_text:
                return MetarResult(success=False, error="No METAR data in response")

            # Extract first METAR line and full TAF
            lines = raw_text.split("\n")
            metar_line = None
            taf_lines = []
            in_taf = False

            for line in lines:
                # Only strip trailing whitespace to preserve leading spaces (for TAF indentation)
                line_rstripped = line.rstrip()
                if not line_rstripped:
                    continue
                # First METAR line (starts with "METAR") - strip for METAR since it shouldn't have leading spaces
                if line_rstripped.startswith("METAR") and metar_line is None:
                    metar_line = line_rstripped
                # TAF starts with "TAF" and continues until end - preserve leading spaces
                elif line_rstripped.startswith("TAF"):
                    in_taf = True
                    taf_lines.append(line_rstripped)
                elif in_taf:
                    # Preserve leading spaces for TAF continuation lines
                    taf_lines.append(line_rstripped)

            # Build result data structure
            result_data: dict[str, Any] = {
                "icaoId": icao_code,
                "rawOb": metar_line or "",
                "rawTaf": "\n".join(taf_lines) if taf_lines else "",
            }

            if not metar_line and not taf_lines:
                return MetarResult(success=False, error="No METAR or TAF data found in response")

            return MetarResult(success=True, data=result_data)

    except Exception as e:
        return MetarResult(success=False, error=str(e))


def get_raw_metar(metar_data: dict[str, Any]) -> str:
    """Extract raw METAR text from API response."""
    result = metar_data.get("rawOb", "")
    return str(result) if result else ""


def get_raw_taf(metar_data: dict[str, Any]) -> str:
    """Extract raw TAF text from API response."""
    result = metar_data.get("rawTaf", "")
    return str(result) if result else ""


def format_metar_overlay(metar_data: dict[str, Any]) -> str:
    """Format METAR data for overlay display."""
    parts = []

    # Extract time from rawOb (e.g., "021530Z")
    raw_ob = metar_data.get("rawOb", "")
    icao_id = metar_data.get("icaoId", "")

    time_match = re.search(r"\d{6}Z", raw_ob)
    if time_match:
        parts.append(f"{icao_id} {time_match.group()}")
    else:
        parts.append(icao_id)

    # Wind
    wdir = metar_data.get("wdir")
    wspd = metar_data.get("wspd")
    if wdir is not None and wspd is not None:
        parts.append(f"{str(wdir).zfill(3)}/{wspd}kt")

    # Flight category
    flt_cat = metar_data.get("fltCat", "")
    if flt_cat:
        parts.append(flt_cat)

    # Temperature
    temp = metar_data.get("temp")
    if temp is not None:
        parts.append(f"{temp}°C")

    return " | ".join(parts)
