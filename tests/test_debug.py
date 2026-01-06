"""Tests for debug module."""

import os
from unittest.mock import patch

from aero_pi_cam.core.debug import _is_debug_mode, debug_print


def test_is_debug_mode_enabled() -> None:
    """Test _is_debug_mode returns True when DEBUG_MODE=true."""
    with patch.dict(os.environ, {"DEBUG_MODE": "true"}):
        assert _is_debug_mode() is True


def test_is_debug_mode_disabled() -> None:
    """Test _is_debug_mode returns False when DEBUG_MODE=false."""
    with patch.dict(os.environ, {"DEBUG_MODE": "false"}):
        assert _is_debug_mode() is False


def test_is_debug_mode_case_insensitive() -> None:
    """Test _is_debug_mode is case insensitive."""
    with patch.dict(os.environ, {"DEBUG_MODE": "TRUE"}):
        assert _is_debug_mode() is True
    with patch.dict(os.environ, {"DEBUG_MODE": "True"}):
        assert _is_debug_mode() is True


def test_is_debug_mode_defaults_to_false() -> None:
    """Test _is_debug_mode defaults to False when not set."""
    with patch.dict(os.environ, {}, clear=True):
        assert _is_debug_mode() is False


def test_debug_print_when_enabled(capsys) -> None:
    """Test debug_print outputs when DEBUG_MODE is enabled."""
    with patch.dict(os.environ, {"DEBUG_MODE": "true"}):
        debug_print("test message")
        captured = capsys.readouterr()
        assert "test message" in captured.out


def test_debug_print_when_disabled(capsys) -> None:
    """Test debug_print does not output when DEBUG_MODE is disabled."""
    with patch.dict(os.environ, {"DEBUG_MODE": "false"}):
        debug_print("test message")
        captured = capsys.readouterr()
        assert "test message" not in captured.out
