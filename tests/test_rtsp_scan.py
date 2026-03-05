"""Tests for RTSP scan module (wildcard expansion and capture with cache)."""

from unittest.mock import patch

from aero_pi_cam.capture.capture import CaptureResult
from aero_pi_cam.capture.rtsp_scan import (
    capture_frame_with_scan,
    expand_rtsp_url_candidates,
)


def test_expand_rtsp_url_candidates_static_url() -> None:
    """Static URL without wildcard is returned as single candidate."""
    url = "rtsp://192.168.0.100:554/stream1"
    assert expand_rtsp_url_candidates(url, max_attempts=5) == [url]


def test_expand_rtsp_url_candidates_wildcard_single_octet() -> None:
    """Wildcard 10* expands to 100, 101, 102, 103, 104 for max_attempts=5."""
    url = "rtsp://192.168.0.10*:554/stream1"
    got = expand_rtsp_url_candidates(url, max_attempts=5)
    assert len(got) == 5
    assert got[0] == "rtsp://192.168.0.100:554/stream1"
    assert got[1] == "rtsp://192.168.0.101:554/stream1"
    assert got[4] == "rtsp://192.168.0.104:554/stream1"


def test_expand_rtsp_url_candidates_wildcard_order() -> None:
    """Candidates are in order 0, 1, 2, ... max_attempts-1."""
    url = "rtsp://192.168.0.1*:554/path"
    got = expand_rtsp_url_candidates(url, max_attempts=3)
    assert got == [
        "rtsp://192.168.0.10:554/path",
        "rtsp://192.168.0.11:554/path",
        "rtsp://192.168.0.12:554/path",
    ]


def test_expand_rtsp_url_candidates_no_wildcard_in_hostname() -> None:
    """URL with no asterisk in hostname returns single candidate."""
    url = "rtsp://192.168.0.100:554/stream1"
    assert expand_rtsp_url_candidates(url, max_attempts=5) == [url]


def test_expand_rtsp_url_candidates_multiple_wildcards_unchanged() -> None:
    """URL with more than one * in hostname returns single candidate (no expansion)."""
    url = "rtsp://192.168.0.*.*:554/stream1"
    got = expand_rtsp_url_candidates(url, max_attempts=5)
    assert got == [url]


def test_capture_frame_with_scan_static_url_passes_through() -> None:
    """Static URL calls capture once with default timeout."""
    with patch("aero_pi_cam.capture.rtsp_scan.capture_frame") as mock_capture:
        mock_capture.return_value = CaptureResult(success=True, image=b"ok")
        result = capture_frame_with_scan(
            "rtsp://192.168.0.100:554/stream1",
            max_attempts=5,
        )
        assert result.success is True
        assert result.image == b"ok"
        mock_capture.assert_called_once()
        call_kw = mock_capture.call_args[1]
        assert call_kw["timeout_seconds"] == 30


def test_capture_frame_with_scan_cached_ip_succeeds() -> None:
    """When cached IP is set and capture succeeds, no scan is performed."""
    ref: dict[str, str | None] = {"value": "192.168.0.102"}
    with patch("aero_pi_cam.capture.rtsp_scan.capture_frame") as mock_capture:
        mock_capture.return_value = CaptureResult(success=True, image=b"cached")
        result = capture_frame_with_scan(
            "rtsp://192.168.0.10*:554/stream1",
            max_attempts=5,
            last_camera_ip_ref=ref,
        )
        assert result.success is True
        assert result.image == b"cached"
        mock_capture.assert_called_once()
        assert mock_capture.call_args[0][0] == "rtsp://192.168.0.102:554/stream1"
        assert ref["value"] == "192.168.0.102"


def test_capture_frame_with_scan_cached_ip_fails_then_scan_succeeds() -> None:
    """When cached IP fails, scan tries other candidates and updates cache."""
    ref: dict[str, str | None] = {"value": "192.168.0.102"}
    call_count = 0

    def side_effect(url: str, **kwargs: object) -> CaptureResult:  # noqa: ARG001
        nonlocal call_count
        call_count += 1
        if "192.168.0.102" in url:
            return CaptureResult(success=False, error="timeout")
        if "192.168.0.103" in url:
            return CaptureResult(success=True, image=b"scan-ok")
        return CaptureResult(success=False, error="fail")

    with patch("aero_pi_cam.capture.rtsp_scan.capture_frame", side_effect=side_effect):
        result = capture_frame_with_scan(
            "rtsp://192.168.0.10*:554/stream1",
            max_attempts=5,
            last_camera_ip_ref=ref,
        )
        assert result.success is True
        assert result.image == b"scan-ok"
        assert ref["value"] == "192.168.0.103"
        # First call: cached 102 (fail). Then 100, 101, 103 (success)
        assert call_count >= 2


def test_capture_frame_with_scan_all_fail() -> None:
    """When all candidates fail, returns last error."""
    ref: dict[str, str | None] = {"value": None}

    with patch("aero_pi_cam.capture.rtsp_scan.capture_frame") as mock_capture:
        mock_capture.return_value = CaptureResult(success=False, error="Connection refused")
        result = capture_frame_with_scan(
            "rtsp://192.168.0.10*:554/stream1",
            max_attempts=3,
            last_camera_ip_ref=ref,
        )
        assert result.success is False
        assert result.error == "Connection refused"
        assert mock_capture.call_count == 3


def test_capture_frame_with_scan_cache_updated_after_scan_success() -> None:
    """Cache is updated with hostname when scan finds working IP."""
    ref: dict[str, str | None] = {"value": None}

    def side_effect(url: str, **kwargs: object) -> CaptureResult:  # noqa: ARG001
        if "192.168.0.101" in url:
            return CaptureResult(success=True, image=b"ok")
        return CaptureResult(success=False, error="fail")

    with patch("aero_pi_cam.capture.rtsp_scan.capture_frame", side_effect=side_effect):
        result = capture_frame_with_scan(
            "rtsp://192.168.0.10*:554/stream1",
            max_attempts=5,
            last_camera_ip_ref=ref,
        )
        assert result.success is True
        assert ref["value"] == "192.168.0.101"
