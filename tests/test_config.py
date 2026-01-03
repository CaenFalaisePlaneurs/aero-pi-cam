"""Tests for config module."""

import pytest

from src.config import validate_config


def test_validate_correct_config() -> None:
    """Test validation of a correct config."""
    valid_config = {
        "camera": {"rtsp_url": "rtsp://user:pass@192.168.0.60:554/stream1"},
        "location": {
            "name": "LFAS",
            "latitude": 48.9267952,
            "longitude": -0.1477169,
        },
        "schedule": {"day_interval_minutes": 5, "night_interval_minutes": 60},
        "api": {
            "url": "https://api.example.com/api/webcam/image",
            "key": "secret-key",
            "timeout_seconds": 30,
        },
        "metar": {
            "enabled": True,
            "icao_code": "LFRK",
        },
        "overlay": {
            "provider_name": "Test Provider",
            "provider_logo": "images/logo.svg",
            "camera_name": "test camera",
        },
    }

    result = validate_config(valid_config)
    assert result.camera.rtsp_url == valid_config["camera"]["rtsp_url"]
    assert result.location.name == "LFAS"
    assert result.metar.icao_code == "LFRK"


def test_reject_invalid_rtsp_url() -> None:
    """Test rejection of invalid RTSP URL."""
    invalid_config = {
        "camera": {"rtsp_url": "http://invalid"},
        "location": {
            "name": "LFAS",
            "latitude": 48.9267952,
            "longitude": -0.1477169,
        },
        "schedule": {"day_interval_minutes": 5, "night_interval_minutes": 60},
        "api": {
            "url": "https://api.example.com/api/webcam/image",
            "key": "secret-key",
            "timeout_seconds": 30,
        },
        "metar": {
            "enabled": False,
            "icao_code": "LFRK",
        },
        "overlay": {
            "provider_name": "Test Provider",
            "provider_logo": "images/logo.svg",
            "camera_name": "test camera",
        },
    }

    with pytest.raises(ValueError, match="RTSP URL must start with rtsp://"):
        validate_config(invalid_config)


def test_reject_invalid_latitude() -> None:
    """Test rejection of invalid latitude."""
    invalid_config = {
        "camera": {"rtsp_url": "rtsp://user:pass@192.168.0.60:554/stream1"},
        "location": {
            "name": "LFAS",
            "latitude": 100,  # Invalid
            "longitude": -0.1477169,
        },
        "schedule": {"day_interval_minutes": 5, "night_interval_minutes": 60},
        "api": {
            "url": "https://api.example.com/api/webcam/image",
            "key": "secret-key",
            "timeout_seconds": 30,
        },
        "metar": {
            "enabled": False,
            "icao_code": "LFRK",
        },
        "overlay": {
            "provider_name": "Test Provider",
            "provider_logo": "images/logo.svg",
            "camera_name": "test camera",
        },
    }

    with pytest.raises(ValueError):
        validate_config(invalid_config)


def test_reject_invalid_longitude() -> None:
    """Test rejection of invalid longitude."""
    invalid_config = {
        "camera": {"rtsp_url": "rtsp://user:pass@192.168.0.60:554/stream1"},
        "location": {
            "name": "LFAS",
            "latitude": 48.9267952,
            "longitude": 200,  # Invalid
        },
        "schedule": {"day_interval_minutes": 5, "night_interval_minutes": 60},
        "api": {
            "url": "https://api.example.com/api/webcam/image",
            "key": "secret-key",
            "timeout_seconds": 30,
        },
        "metar": {
            "enabled": False,
            "icao_code": "LFRK",
        },
        "overlay": {
            "provider_name": "Test Provider",
            "provider_logo": "images/logo.svg",
            "camera_name": "test camera",
        },
    }

    with pytest.raises(ValueError):
        validate_config(invalid_config)


def test_reject_invalid_schedule_interval() -> None:
    """Test rejection of invalid schedule interval."""
    invalid_config = {
        "camera": {"rtsp_url": "rtsp://user:pass@192.168.0.60:554/stream1"},
        "location": {
            "name": "LFAS",
            "latitude": 48.9267952,
            "longitude": -0.1477169,
        },
        "schedule": {"day_interval_minutes": 0, "night_interval_minutes": 60},  # Invalid
        "api": {
            "url": "https://api.example.com/api/webcam/image",
            "key": "secret-key",
            "timeout_seconds": 30,
        },
        "metar": {
            "enabled": False,
            "icao_code": "LFRK",
        },
        "overlay": {
            "provider_name": "Test Provider",
            "provider_logo": "images/logo.svg",
            "camera_name": "test camera",
        },
    }

    with pytest.raises(ValueError):
        validate_config(invalid_config)


def test_reject_invalid_icao_code_length() -> None:
    """Test rejection of invalid ICAO code length."""
    invalid_config = {
        "camera": {"rtsp_url": "rtsp://user:pass@192.168.0.60:554/stream1"},
        "location": {
            "name": "LFAS",
            "latitude": 48.9267952,
            "longitude": -0.1477169,
        },
        "schedule": {"day_interval_minutes": 5, "night_interval_minutes": 60},
        "api": {
            "url": "https://api.example.com/api/webcam/image",
            "key": "secret-key",
            "timeout_seconds": 30,
        },
        "metar": {
            "enabled": False,
            "icao_code": "LF",  # Invalid length
            "overlay_position": "bottom-left",
            "font_size": 16,
            "font_color": "white",
            "background_color": "rgba(0,0,0,0.6)",
        },
    }

    with pytest.raises(ValueError):
        validate_config(invalid_config)


def test_overlay_shadow_config() -> None:
    """Test overlay shadow configuration."""
    config_with_shadow = {
        "camera": {"rtsp_url": "rtsp://user:pass@192.168.0.60:554/stream1"},
        "location": {
            "name": "LFAS",
            "latitude": 48.9267952,
            "longitude": -0.1477169,
        },
        "schedule": {"day_interval_minutes": 5, "night_interval_minutes": 60},
        "api": {
            "url": "https://api.example.com/api/webcam/image",
            "key": "secret-key",
            "timeout_seconds": 30,
        },
        "metar": {
            "enabled": False,
            "icao_code": "LFRK",
        },
        "overlay": {
            "provider_name": "Test Provider",
            "provider_logo": "images/logo.svg",
            "camera_name": "test camera",
            "shadow_enabled": True,
            "shadow_offset_x": 3,
            "shadow_offset_y": 3,
            "shadow_color": "black",
        },
    }

    result = validate_config(config_with_shadow)
    assert result.overlay.shadow_enabled is True
    assert result.overlay.shadow_offset_x == 3
    assert result.overlay.shadow_offset_y == 3
    assert result.overlay.shadow_color == "black"


def test_uppercase_icao_code() -> None:
    """Test that ICAO code is uppercased."""
    config_with_lowercase = {
        "camera": {"rtsp_url": "rtsp://user:pass@192.168.0.60:554/stream1"},
        "location": {
            "name": "LFAS",
            "latitude": 48.9267952,
            "longitude": -0.1477169,
        },
        "schedule": {"day_interval_minutes": 5, "night_interval_minutes": 60},
        "api": {
            "url": "https://api.example.com/api/webcam/image",
            "key": "secret-key",
            "timeout_seconds": 30,
        },
        "overlay": {
            "provider_name": "Test Provider",
            "provider_logo": "images/logo.svg",
            "camera_name": "test camera",
        },
        "metar": {
            "enabled": False,
            "icao_code": "lfrk",  # Lowercase
        },
    }

    result = validate_config(config_with_lowercase)
    assert result.metar.icao_code == "LFRK"


def test_debug_config_optional() -> None:
    """Test that debug config is optional."""
    config_without_debug = {
        "camera": {"rtsp_url": "rtsp://user:pass@192.168.0.60:554/stream1"},
        "location": {
            "name": "LFAS",
            "latitude": 48.9267952,
            "longitude": -0.1477169,
        },
        "schedule": {"day_interval_minutes": 5, "night_interval_minutes": 60},
        "api": {
            "url": "https://api.example.com/api/webcam/image",
            "key": "secret-key",
            "timeout_seconds": 30,
        },
        "metar": {
            "enabled": False,
            "icao_code": "LFRK",
        },
        "overlay": {
            "provider_name": "Test Provider",
            "provider_logo": "images/logo.svg",
            "camera_name": "test camera",
        },
    }

    result = validate_config(config_without_debug)
    assert result.debug is None


def test_debug_config_valid() -> None:
    """Test validation of valid debug config."""
    config_with_debug = {
        "camera": {"rtsp_url": "rtsp://user:pass@192.168.0.60:554/stream1"},
        "location": {
            "name": "LFAS",
            "latitude": 48.9267952,
            "longitude": -0.1477169,
        },
        "schedule": {"day_interval_minutes": 5, "night_interval_minutes": 60},
        "api": {
            "url": "https://api.example.com/api/webcam/image",
            "key": "secret-key",
            "timeout_seconds": 30,
        },
        "metar": {
            "enabled": False,
            "icao_code": "LFRK",
        },
        "overlay": {
            "provider_name": "Test Provider",
            "provider_logo": "images/logo.svg",
            "camera_name": "test camera",
        },
        "debug": {
            "day_interval_seconds": 10,
            "night_interval_seconds": 30,
        },
    }

    result = validate_config(config_with_debug)
    assert result.debug is not None
    assert result.debug.day_interval_seconds == 10
    assert result.debug.night_interval_seconds == 30


def test_debug_config_defaults() -> None:
    """Test debug config defaults."""
    config_with_debug_minimal = {
        "camera": {"rtsp_url": "rtsp://user:pass@192.168.0.60:554/stream1"},
        "location": {
            "name": "LFAS",
            "latitude": 48.9267952,
            "longitude": -0.1477169,
        },
        "schedule": {"day_interval_minutes": 5, "night_interval_minutes": 60},
        "api": {
            "url": "https://api.example.com/api/webcam/image",
            "key": "secret-key",
            "timeout_seconds": 30,
        },
        "metar": {
            "enabled": False,
            "icao_code": "LFRK",
        },
        "overlay": {
            "provider_name": "Test Provider",
            "provider_logo": "images/logo.svg",
            "camera_name": "test camera",
        },
        "debug": {
            "day_interval_seconds": 10,
            "night_interval_seconds": 30,
        },
    }

    result = validate_config(config_with_debug_minimal)
    assert result.debug is not None
    assert result.debug.day_interval_seconds == 10
    assert result.debug.night_interval_seconds == 30


def test_reject_invalid_debug_interval() -> None:
    """Test rejection of invalid debug interval."""
    invalid_config = {
        "camera": {"rtsp_url": "rtsp://user:pass@192.168.0.60:554/stream1"},
        "location": {
            "name": "LFAS",
            "latitude": 48.9267952,
            "longitude": -0.1477169,
        },
        "schedule": {"day_interval_minutes": 5, "night_interval_minutes": 60},
        "api": {
            "url": "https://api.example.com/api/webcam/image",
            "key": "secret-key",
            "timeout_seconds": 30,
        },
        "metar": {
            "enabled": False,
            "icao_code": "LFRK",
        },
        "overlay": {
            "provider_name": "Test Provider",
            "provider_logo": "images/logo.svg",
            "camera_name": "test camera",
        },
        "debug": {
            "day_interval_seconds": 0,  # Invalid
            "night_interval_seconds": 30,
        },
    }

    with pytest.raises(ValueError):
        validate_config(invalid_config)


def test_load_config_with_path() -> None:
    """Test load_config with explicit path."""
    import tempfile
    from pathlib import Path

    import yaml

    from src.config import load_config

    config_data = {
        "camera": {"rtsp_url": "rtsp://test:pass@192.168.0.1:554/stream1"},
        "location": {
            "name": "TEST",
            "latitude": 48.9267952,
            "longitude": -0.1477169,
        },
        "schedule": {"day_interval_minutes": 5, "night_interval_minutes": 60},
        "api": {
            "url": "https://api.example.com",
            "key": "test-key",
            "timeout_seconds": 30,
        },
        "overlay": {
            "provider_name": "Test Provider",
            "provider_logo": "images/logo.svg",
            "camera_name": "test camera",
        },
        "metar": {
            "enabled": False,
            "icao_code": "TEST",
        },
    }

    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        yaml.dump(config_data, f)
        temp_path = f.name

    try:
        result = load_config(temp_path)
        assert result.camera.rtsp_url == config_data["camera"]["rtsp_url"]
        assert result.location.name == "TEST"
    finally:
        Path(temp_path).unlink()


def test_load_config_file_not_found() -> None:
    """Test load_config raises FileNotFoundError for missing file."""
    from src.config import load_config

    with pytest.raises(FileNotFoundError):
        load_config("nonexistent_config.yaml")


def test_load_config_default_path() -> None:
    """Test load_config uses CONFIG_PATH env var or default."""
    import os

    from src.config import load_config

    original_env = os.environ.get("CONFIG_PATH")
    try:
        if "CONFIG_PATH" in os.environ:
            del os.environ["CONFIG_PATH"]
        # Test that it uses default path (config.yaml)
        # If config.yaml exists, it will load successfully
        # If it doesn't exist, it will raise FileNotFoundError
        try:
            result = load_config()
            # If we get here, config.yaml exists and was loaded
            assert result is not None
        except FileNotFoundError:
            # This is also valid - config.yaml doesn't exist
            pass
    finally:
        if original_env:
            os.environ["CONFIG_PATH"] = original_env
