"""Tests for capture module."""

import subprocess
from unittest.mock import MagicMock

from aero_pi_cam.capture.capture import capture_frame, reset_subprocess_run, set_subprocess_run


def test_capture_success() -> None:
    """Test successful frame capture."""
    fake_image = b"fake-jpeg-data"

    def mock_run(*args, **kwargs):  # noqa: ARG001
        result = MagicMock()
        result.stdout = fake_image
        result.returncode = 0
        return result

    set_subprocess_run(mock_run)

    try:
        result = capture_frame("rtsp://test:test@localhost:554/stream")
        assert result.success is True
        assert result.image == fake_image
        assert result.error is None
    finally:
        reset_subprocess_run()


def test_capture_spawn_failure() -> None:
    """Test capture failure on spawn error."""

    def mock_run(*args, **kwargs):  # noqa: ARG001
        raise FileNotFoundError("ffmpeg not found")

    set_subprocess_run(mock_run)

    try:
        result = capture_frame("rtsp://test:test@localhost:554/stream")
        assert result.success is False
        assert "spawn error" in result.error.lower()
        assert result.image is None
    finally:
        reset_subprocess_run()


def test_capture_non_zero_exit() -> None:
    """Test capture failure on non-zero exit code."""

    def mock_run(*args, **kwargs):  # noqa: ARG001
        result = MagicMock()
        result.stdout = b""
        result.stderr = b"Connection refused"
        result.returncode = 1
        raise subprocess.CalledProcessError(1, "ffmpeg", result.stdout, result.stderr)

    set_subprocess_run(mock_run)

    try:
        result = capture_frame("rtsp://test:test@localhost:554/stream")
        assert result.success is False
        assert "exited with code 1" in result.error
        assert "Connection refused" in result.error
    finally:
        reset_subprocess_run()


def test_capture_no_output() -> None:
    """Test capture failure when no output produced."""

    def mock_run(*args, **kwargs):  # noqa: ARG001
        result = MagicMock()
        result.stdout = b""
        result.returncode = 0
        return result

    set_subprocess_run(mock_run)

    try:
        result = capture_frame("rtsp://test:test@localhost:554/stream")
        assert result.success is False
        assert "no output" in result.error.lower()
    finally:
        reset_subprocess_run()


def test_capture_calls_ffmpeg_with_correct_args() -> None:
    """Test that capture calls ffmpeg with correct arguments."""
    captured_args = None

    def mock_run(args, **kwargs):  # noqa: ARG001
        nonlocal captured_args
        captured_args = args
        result = MagicMock()
        result.stdout = b"fake-data"
        result.returncode = 0
        return result

    set_subprocess_run(mock_run)

    try:
        rtsp_url = "rtsp://user:pass@192.168.0.60:554/stream1"
        capture_frame(rtsp_url)

        assert captured_args is not None
        assert captured_args[0] == "ffmpeg"
        assert "-rtsp_transport" in captured_args
        assert "tcp" in captured_args
        assert "-i" in captured_args
        assert rtsp_url in captured_args
        assert "-frames:v" in captured_args
        assert "1" in captured_args
        assert "-q:v" in captured_args
        assert "2" in captured_args
        assert "-f" in captured_args
        assert "image2" in captured_args
        assert "pipe:1" in captured_args
    finally:
        reset_subprocess_run()


def test_capture_with_separate_credentials() -> None:
    """Test capture with separate username and password."""
    captured_args = None

    def mock_run(args, **kwargs):  # noqa: ARG001
        nonlocal captured_args
        captured_args = args
        result = MagicMock()
        result.stdout = b"fake-data"
        result.returncode = 0
        return result

    set_subprocess_run(mock_run)

    try:
        rtsp_url = "rtsp://192.168.0.60:554/stream1"
        capture_frame(rtsp_url, rtsp_user="testuser", rtsp_password="testpass")

        assert captured_args is not None
        assert "-i" in captured_args
        url_index = captured_args.index("-i")
        url_with_auth = captured_args[url_index + 1]
        assert "testuser" in url_with_auth
        assert "testpass" in url_with_auth
        assert "@192.168.0.60" in url_with_auth
    finally:
        reset_subprocess_run()


def test_capture_with_special_chars_in_username() -> None:
    """Test capture with special characters in username."""
    captured_args = None

    def mock_run(args, **kwargs):  # noqa: ARG001
        nonlocal captured_args
        captured_args = args
        result = MagicMock()
        result.stdout = b"fake-data"
        result.returncode = 0
        return result

    set_subprocess_run(mock_run)

    try:
        rtsp_url = "rtsp://192.168.0.60:554/stream1"
        capture_frame(rtsp_url, rtsp_user="user@domain", rtsp_password="pass")

        assert captured_args is not None
        assert "-i" in captured_args
        url_index = captured_args.index("-i")
        url_with_auth = captured_args[url_index + 1]
        # Username with @ should be URL-encoded
        assert "%40" in url_with_auth or "user@domain" in url_with_auth
    finally:
        reset_subprocess_run()


def test_capture_with_port_in_url() -> None:
    """Test capture with port in URL."""
    captured_args = None

    def mock_run(args, **kwargs):  # noqa: ARG001
        nonlocal captured_args
        captured_args = args
        result = MagicMock()
        result.stdout = b"fake-data"
        result.returncode = 0
        return result

    set_subprocess_run(mock_run)

    try:
        rtsp_url = "rtsp://192.168.0.60:8554/stream1"
        capture_frame(rtsp_url, rtsp_user="user", rtsp_password="pass")

        assert captured_args is not None
        assert "-i" in captured_args
        url_index = captured_args.index("-i")
        url_with_auth = captured_args[url_index + 1]
        assert ":8554" in url_with_auth
    finally:
        reset_subprocess_run()


def test_capture_timeout() -> None:
    """Test capture timeout handling."""

    def mock_run(*args, **kwargs):  # noqa: ARG001
        raise subprocess.TimeoutExpired("ffmpeg", 30)

    set_subprocess_run(mock_run)

    try:
        result = capture_frame("rtsp://test:test@localhost:554/stream")
        assert result.success is False
        assert "timeout" in result.error.lower()
        assert result.image is None
    finally:
        reset_subprocess_run()


def test_capture_with_query_parameters() -> None:
    """Test capture with query parameters in URL."""
    captured_args = None

    def mock_run(args, **kwargs):  # noqa: ARG001
        nonlocal captured_args
        captured_args = args
        result = MagicMock()
        result.stdout = b"fake-data"
        result.returncode = 0
        return result

    set_subprocess_run(mock_run)

    try:
        rtsp_url = "rtsp://192.168.0.60:554/stream1?param=value"
        capture_frame(rtsp_url, rtsp_user="user", rtsp_password="pass")

        assert captured_args is not None
        assert "-i" in captured_args
        url_index = captured_args.index("-i")
        url_with_auth = captured_args[url_index + 1]
        assert "?param=value" in url_with_auth
    finally:
        reset_subprocess_run()
