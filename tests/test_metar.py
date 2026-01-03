"""Tests for metar module."""

from unittest.mock import AsyncMock, patch

import httpx
import pytest

from src.metar import fetch_metar, format_metar_overlay


@pytest.mark.asyncio
async def test_fetch_metar_success() -> None:
    """Test successful METAR fetch with raw format."""
    raw_response = """METAR LFRK 021530Z AUTO 33009KT 9999 FEW041 04/M01 Q1008 NOSIG
METAR LFRK 021500Z AUTO 33010KT 9999 FEW041 04/M01 Q1008 NOSIG
TAF LFRK 021400Z 0215/0224 34010KT 9999 BKN030
  TEMPO 0215/0216 34015G25KT 3000 SHRA BKN008
  BECMG 0216/0218 VRB05KT"""

    mock_response = AsyncMock()
    mock_response.status_code = 200
    mock_response.is_success = True
    mock_response.text = raw_response

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch("httpx.AsyncClient", return_value=mock_client):
        result = await fetch_metar("LFRK", "https://aviationweather.gov/api/data/metar")

    assert result.success is True
    assert result.data is not None
    assert result.data["icaoId"] == "LFRK"
    assert result.data["rawOb"] == "METAR LFRK 021530Z AUTO 33009KT 9999 FEW041 04/M01 Q1008 NOSIG"
    assert "TAF LFRK" in result.data["rawTaf"]
    assert "TEMPO" in result.data["rawTaf"]
    assert "BECMG" in result.data["rawTaf"]


@pytest.mark.asyncio
async def test_fetch_metar_calls_api_with_correct_url() -> None:
    """Test that fetch_metar calls API with correct URL and headers."""
    mock_response = AsyncMock()
    mock_response.status_code = 200
    mock_response.is_success = True
    mock_response.text = "METAR LFRK 021530Z AUTO 33009KT 9999 FEW041 04/M01 Q1008 NOSIG"

    mock_client = AsyncMock()
    mock_get = AsyncMock(return_value=mock_response)
    mock_client.get = mock_get
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    api_url = "https://aviationweather.gov/api/data/metar"
    with patch("httpx.AsyncClient", return_value=mock_client):
        await fetch_metar("LFRK", api_url)

        call_args, call_kwargs = mock_get.call_args
        url = call_args[0] if call_args else call_kwargs.get("url", "")
        assert f"{api_url}?ids=LFRK&format=raw&taf=true&hours=1" in url
        assert (
            call_kwargs["headers"]["User-Agent"] == "aero-pi-cam/1.0 (Raspberry Pi webcam capture)"
        )


@pytest.mark.asyncio
async def test_fetch_metar_handles_204() -> None:
    """Test handling of 204 No Content."""
    mock_response = AsyncMock()
    mock_response.status_code = 204

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch("httpx.AsyncClient", return_value=mock_client):
        result = await fetch_metar("XXXX", "https://aviationweather.gov/api/data/metar")

    assert result.success is False
    assert "No METAR data available" in result.error


@pytest.mark.asyncio
async def test_fetch_metar_handles_429() -> None:
    """Test handling of 429 rate limiting."""
    mock_response = AsyncMock()
    mock_response.status_code = 429
    mock_response.headers = {"Retry-After": "120"}

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch("httpx.AsyncClient", return_value=mock_client):
        result = await fetch_metar("LFRK", "https://aviationweather.gov/api/data/metar")

    assert result.success is False
    assert "Rate limited" in result.error
    assert result.retry_after_seconds == 120


@pytest.mark.asyncio
async def test_fetch_metar_handles_400() -> None:
    """Test handling of 400 Bad Request."""
    mock_response = AsyncMock()
    mock_response.status_code = 400

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch("httpx.AsyncClient", return_value=mock_client):
        result = await fetch_metar("XX", "https://aviationweather.gov/api/data/metar")

    assert result.success is False
    assert "Invalid METAR request" in result.error


@pytest.mark.asyncio
async def test_fetch_metar_handles_empty_response() -> None:
    """Test handling of empty response."""
    mock_response = AsyncMock()
    mock_response.status_code = 200
    mock_response.is_success = True
    mock_response.text = ""

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch("httpx.AsyncClient", return_value=mock_client):
        result = await fetch_metar("LFRK", "https://aviationweather.gov/api/data/metar")

    assert result.success is False
    assert "No METAR data in response" in result.error


@pytest.mark.asyncio
async def test_fetch_metar_handles_network_errors() -> None:
    """Test handling of network errors."""
    mock_client = AsyncMock()
    mock_client.get = AsyncMock(side_effect=httpx.RequestError("Network error"))
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch("httpx.AsyncClient", return_value=mock_client):
        result = await fetch_metar("LFRK", "https://aviationweather.gov/api/data/metar")

    assert result.success is False
    assert "Network error" in result.error


@pytest.mark.asyncio
async def test_fetch_metar_handles_no_metar_or_taf() -> None:
    """Test handling of response with no METAR or TAF."""
    mock_response = AsyncMock()
    mock_response.status_code = 200
    mock_response.is_success = True
    mock_response.text = "Some other text without METAR or TAF"

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch("httpx.AsyncClient", return_value=mock_client):
        result = await fetch_metar("LFRK", "https://aviationweather.gov/api/data/metar")

    assert result.success is False
    assert "No METAR or TAF data found" in result.error


def test_format_metar_overlay() -> None:
    """Test METAR formatting for overlay."""
    metar_data = {
        "icaoId": "LFRK",
        "receiptTime": "2026-01-02T15:34:14.873Z",
        "obsTime": 1767367800,
        "reportTime": "2026-01-02T15:30:00.000Z",
        "temp": 4,
        "dewp": -1,
        "wdir": 330,
        "wspd": 9,
        "visib": "6+",
        "altim": 1008,
        "metarType": "METAR",
        "rawOb": "METAR LFRK 021530Z AUTO 33009KT 9999 FEW041 04/M01 Q1008 NOSIG",
        "lat": 49.18,
        "lon": -0.456,
        "elev": 66,
        "name": "Caen/Carpiquet Arpt, NO, FR",
        "clouds": [],
        "fltCat": "VFR",
    }

    overlay = format_metar_overlay(metar_data)

    assert "LFRK" in overlay
    assert "021530Z" in overlay
    assert "330/9kt" in overlay
    assert "VFR" in overlay
    assert "4°C" in overlay


def test_get_raw_metar_empty() -> None:
    """Test get_raw_metar with empty value."""
    from src.metar import get_raw_metar

    result = get_raw_metar({"rawOb": ""})
    assert result == ""


def test_get_raw_metar_none() -> None:
    """Test get_raw_metar with None value."""
    from src.metar import get_raw_metar

    result = get_raw_metar({"rawOb": None})
    assert result == ""


def test_get_raw_taf_empty() -> None:
    """Test get_raw_taf with empty value."""
    from src.metar import get_raw_taf

    result = get_raw_taf({"rawTaf": ""})
    assert result == ""


def test_get_raw_taf_none() -> None:
    """Test get_raw_taf with None value."""
    from src.metar import get_raw_taf

    result = get_raw_taf({"rawTaf": None})
    assert result == ""


def test_format_metar_overlay_no_time_match() -> None:
    """Test format_metar_overlay when rawOb has no time pattern."""
    from src.metar import format_metar_overlay

    metar_data = {
        "icaoId": "LFRK",
        "rawOb": "METAR LFRK AUTO 33009KT",  # No time pattern
    }

    overlay = format_metar_overlay(metar_data)
    assert "LFRK" in overlay


@pytest.mark.asyncio
async def test_fetch_metar_debug_mode() -> None:
    """Test fetch_metar with debug mode enabled."""
    import os
    from unittest.mock import patch

    original_debug = os.environ.get("DEBUG_MODE")
    try:
        os.environ["DEBUG_MODE"] = "true"

        mock_response = AsyncMock()
        mock_response.status_code = 200
        mock_response.is_success = True
        mock_response.text = '{"icaoId": "LFRK", "rawOb": "METAR LFRK 021200Z 33009KT"}'

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        with (
            patch("httpx.AsyncClient", return_value=mock_client),
            patch("builtins.print") as mock_print,
        ):
            await fetch_metar("LFRK", "https://aviationweather.gov/api/data/metar")

            # Verify debug prints were called
            assert mock_print.called
    finally:
        if original_debug:
            os.environ["DEBUG_MODE"] = original_debug
        elif "DEBUG_MODE" in os.environ:
            del os.environ["DEBUG_MODE"]


@pytest.mark.asyncio
async def test_fetch_metar_non_success_response() -> None:
    """Test fetch_metar handles non-success HTTP response."""
    mock_response = AsyncMock()
    mock_response.status_code = 403
    mock_response.is_success = False

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch("httpx.AsyncClient", return_value=mock_client):
        result = await fetch_metar("LFRK", "https://aviationweather.gov/api/data/metar")

    assert result.success is False
    assert "HTTP 403" in result.error


@pytest.mark.asyncio
async def test_fetch_metar_empty_line_handling() -> None:
    """Test fetch_metar handles empty lines in response."""
    mock_response = AsyncMock()
    mock_response.status_code = 200
    mock_response.is_success = True
    mock_response.text = "\n\nMETAR LFRK 021200Z 33009KT\n\n"

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch("httpx.AsyncClient", return_value=mock_client):
        result = await fetch_metar("LFRK", "https://aviationweather.gov/api/data/metar")

    assert result.success is True
    assert result.data is not None
