"""Tests for duration parsing utility."""

from datetime import timedelta

import pytest

from aero_pi_cam.utils.duration import parse_duration


class TestParseDuration:
    """Tests for parse_duration function."""

    def test_hours_only(self) -> None:
        """Test parsing hours-only strings."""
        assert parse_duration("1h") == timedelta(hours=1)
        assert parse_duration("2h") == timedelta(hours=2)
        assert parse_duration("24h") == timedelta(hours=24)

    def test_minutes_only(self) -> None:
        """Test parsing minutes-only strings."""
        assert parse_duration("30m") == timedelta(minutes=30)
        assert parse_duration("90m") == timedelta(minutes=90)
        assert parse_duration("5m") == timedelta(minutes=5)

    def test_hours_and_minutes(self) -> None:
        """Test parsing combined hours and minutes."""
        assert parse_duration("1h30m") == timedelta(hours=1, minutes=30)
        assert parse_duration("2h15m") == timedelta(hours=2, minutes=15)
        assert parse_duration("1h0m") == timedelta(hours=1)

    def test_zero_returns_none(self) -> None:
        """Test that '0' disables history."""
        assert parse_duration("0") is None

    def test_empty_string_returns_none(self) -> None:
        """Test that empty string disables history."""
        assert parse_duration("") is None

    def test_whitespace_only_returns_none(self) -> None:
        """Test that whitespace-only string disables history."""
        assert parse_duration("  ") is None

    def test_zero_hours_zero_minutes_returns_none(self) -> None:
        """Test that '0h0m' is treated as disabled."""
        assert parse_duration("0h0m") is None

    def test_invalid_format_raises(self) -> None:
        """Test that invalid formats raise ValueError."""
        with pytest.raises(ValueError, match="Invalid duration format"):
            parse_duration("abc")

    def test_seconds_not_supported(self) -> None:
        """Test that seconds unit is not supported."""
        with pytest.raises(ValueError, match="Invalid duration format"):
            parse_duration("30s")

    def test_no_unit_raises(self) -> None:
        """Test that bare numbers (other than '0') raise ValueError."""
        with pytest.raises(ValueError, match="Invalid duration format"):
            parse_duration("60")

    def test_negative_not_supported(self) -> None:
        """Test that negative values raise ValueError."""
        with pytest.raises(ValueError, match="Invalid duration format"):
            parse_duration("-1h")

    def test_whitespace_trimmed(self) -> None:
        """Test that leading/trailing whitespace is trimmed."""
        assert parse_duration("  1h  ") == timedelta(hours=1)
        assert parse_duration(" 30m ") == timedelta(minutes=30)

    def test_reversed_order_raises(self) -> None:
        """Test that minutes before hours raises ValueError."""
        with pytest.raises(ValueError, match="Invalid duration format"):
            parse_duration("30m1h")
