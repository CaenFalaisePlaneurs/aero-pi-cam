"""Tests for SFTP upload metadata JSON generation."""

import json
import os
from unittest.mock import patch

from aero_pi_cam.upload.sftp_meta_json import generate_metadata_json

from .conftest import _create_test_config


def test_generate_metadata_json_day_mode() -> None:
    """Test JSON generation for day mode."""
    from aero_pi_cam.core.config import SftpConfig

    sftp_config = SftpConfig(
        host="test.example.com",
        port=22,
        user="testuser",
        password="testpass",
        remote_path="/test/path",
        timeout_seconds=30,
    )
    config = _create_test_config(upload_method="SFTP", sftp_config=sftp_config)
    metadata = {
        "timestamp": "2026-01-02T15:30:00Z",
        "location": "TEST",
        "is_day": "true",
        "raw_metar": "METAR TEST 021530Z AUTO 33009KT 9999 FEW041 04/M01 Q1008 NOSIG",
        "raw_taf": "TAF TEST 021400Z 0215/0224 34010KT 9999 BKN030",
        "sunrise": "2026-01-02T07:30:00Z",
        "sunset": "2026-01-02T17:30:00Z",
        "camera_heading": "060° RWY 06",
    }
    image_url = "https://test.com/TEST-test_camera.jpg"

    json_bytes = generate_metadata_json(metadata, config, image_url)
    json_data = json.loads(json_bytes.decode("utf-8"))

    assert json_data["day_night_mode"] == "day"
    assert json_data["debug_mode"] is False
    assert "last_update" in json_data
    assert "last_update_timestamp" in json_data
    assert "next_update" in json_data
    assert "next_update_timestamp" in json_data
    assert len(json_data["images"]) == 1

    image = json_data["images"][0]
    assert image["path"] == image_url
    assert image["no_metar_path"] == image_url  # Defaults to image_url if not provided
    assert image["TTL"] == "300"  # 5 minutes * 60 = 300 seconds
    assert image["location"]["name"] == "TEST"
    assert image["location"]["latitude"] == 48.9
    assert image["location"]["longitude"] == -0.1
    assert image["location"]["camera_heading"] == "060° RWY 06"
    assert image["sunrise"] == "2026-01-02T07:30:00Z"
    assert image["sunset"] == "2026-01-02T17:30:00Z"
    assert image["provider_name"] == "Test"
    assert image["camera_name"] == "test_camera"
    assert image["metar"]["icao_code"] is None
    assert image["metar"]["source"] is None
    assert image["metar"]["raw_metar"] is None
    assert image["metar"]["raw_taf"] is None


def test_generate_metadata_json_night_mode() -> None:
    """Test JSON generation for night mode."""
    from aero_pi_cam.core.config import SftpConfig

    sftp_config = SftpConfig(
        host="test.example.com",
        port=22,
        user="testuser",
        password="testpass",
        remote_path="/test/path",
        timeout_seconds=30,
    )
    config = _create_test_config(upload_method="SFTP", sftp_config=sftp_config)
    metadata = {
        "timestamp": "2026-01-02T03:30:00Z",
        "location": "TEST",
        "is_day": "false",
    }
    image_url = "https://test.com/TEST-test_camera.jpg"

    json_bytes = generate_metadata_json(metadata, config, image_url)
    json_data = json.loads(json_bytes.decode("utf-8"))

    assert json_data["day_night_mode"] == "night"
    assert json_data["images"][0]["TTL"] == "3600"  # 60 minutes * 60 = 3600 seconds


def test_generate_metadata_json_debug_mode_day() -> None:
    """Test JSON generation with debug mode enabled (day)."""
    from aero_pi_cam.core.config import SftpConfig

    sftp_config = SftpConfig(
        host="test.example.com",
        port=22,
        user="testuser",
        password="testpass",
        remote_path="/test/path",
        timeout_seconds=30,
    )
    config = _create_test_config(upload_method="SFTP", sftp_config=sftp_config)
    metadata = {
        "timestamp": "2026-01-02T15:30:00Z",
        "location": "TEST",
        "is_day": "true",
    }
    image_url = "https://test.com/TEST-test_camera.jpg"

    with patch.dict(os.environ, {"DEBUG_MODE": "true"}):
        json_bytes = generate_metadata_json(metadata, config, image_url)
        json_data = json.loads(json_bytes.decode("utf-8"))

        assert json_data["debug_mode"] is True
        assert json_data["day_night_mode"] == "day"
        # Default debug day interval is 10 seconds
        assert json_data["images"][0]["TTL"] == "10"


def test_generate_metadata_json_debug_mode_night() -> None:
    """Test JSON generation with debug mode enabled (night)."""
    from aero_pi_cam.core.config import SftpConfig

    sftp_config = SftpConfig(
        host="test.example.com",
        port=22,
        user="testuser",
        password="testpass",
        remote_path="/test/path",
        timeout_seconds=30,
    )
    config = _create_test_config(upload_method="SFTP", sftp_config=sftp_config)
    metadata = {
        "timestamp": "2026-01-02T03:30:00Z",
        "location": "TEST",
        "is_day": "false",
    }
    image_url = "https://test.com/TEST-test_camera.jpg"

    with patch.dict(os.environ, {"DEBUG_MODE": "true"}):
        json_bytes = generate_metadata_json(metadata, config, image_url)
        json_data = json.loads(json_bytes.decode("utf-8"))

        assert json_data["debug_mode"] is True
        assert json_data["day_night_mode"] == "night"
        # Default debug night interval is 30 seconds
        assert json_data["images"][0]["TTL"] == "30"


def test_generate_metadata_json_with_debug_config() -> None:
    """Test JSON generation with debug config intervals."""
    from aero_pi_cam.core.config import DebugConfig, SftpConfig

    sftp_config = SftpConfig(
        host="test.example.com",
        port=22,
        user="testuser",
        password="testpass",
        remote_path="/test/path",
        timeout_seconds=30,
    )
    debug_config = DebugConfig(day_interval_seconds=15, night_interval_seconds=45)
    config = _create_test_config(upload_method="SFTP", sftp_config=sftp_config)
    config.debug = debug_config

    metadata = {
        "timestamp": "2026-01-02T15:30:00Z",
        "location": "TEST",
        "is_day": "true",
    }
    image_url = "https://test.com/TEST-test_camera.jpg"

    with patch.dict(os.environ, {"DEBUG_MODE": "true"}):
        json_bytes = generate_metadata_json(metadata, config, image_url)
        json_data = json.loads(json_bytes.decode("utf-8"))

        assert json_data["images"][0]["TTL"] == "15"


def test_generate_metadata_json_with_metar_enabled() -> None:
    """Test JSON generation with METAR enabled."""
    from aero_pi_cam.core.config import MetarConfig, SftpConfig

    sftp_config = SftpConfig(
        host="test.example.com",
        port=22,
        user="testuser",
        password="testpass",
        remote_path="/test/path",
        timeout_seconds=30,
    )
    metar_config = MetarConfig(enabled=True, icao_code="LFRK")
    config = _create_test_config(upload_method="SFTP", sftp_config=sftp_config)
    config.metar = metar_config

    metadata = {
        "timestamp": "2026-01-02T15:30:00Z",
        "location": "TEST",
        "is_day": "true",
        "raw_metar": "METAR LFRK 021530Z AUTO 33009KT 9999 FEW041 04/M01 Q1008 NOSIG",
        "raw_taf": "TAF LFRK 021400Z 0215/0224 34010KT 9999 BKN030",
    }
    image_url = "https://test.com/TEST-test_camera.jpg"

    json_bytes = generate_metadata_json(metadata, config, image_url)
    json_data = json.loads(json_bytes.decode("utf-8"))

    image = json_data["images"][0]
    assert image["metar"]["icao_code"] == "LFRK"
    assert image["metar"]["source"] == "aviationweather.gov"
    assert (
        image["metar"]["raw_metar"]
        == "METAR LFRK 021530Z AUTO 33009KT 9999 FEW041 04/M01 Q1008 NOSIG"
    )
    assert image["metar"]["raw_taf"] == "TAF LFRK 021400Z 0215/0224 34010KT 9999 BKN030"


def test_generate_metadata_json_with_empty_metar() -> None:
    """Test JSON generation with empty METAR/TAF."""
    from aero_pi_cam.core.config import MetarConfig, SftpConfig

    sftp_config = SftpConfig(
        host="test.example.com",
        port=22,
        user="testuser",
        password="testpass",
        remote_path="/test/path",
        timeout_seconds=30,
    )
    metar_config = MetarConfig(enabled=True, icao_code="LFRK")
    config = _create_test_config(upload_method="SFTP", sftp_config=sftp_config)
    config.metar = metar_config

    metadata = {
        "timestamp": "2026-01-02T15:30:00Z",
        "location": "TEST",
        "is_day": "true",
        "raw_metar": "",
        "raw_taf": "",
    }
    image_url = "https://test.com/TEST-test_camera.jpg"

    json_bytes = generate_metadata_json(metadata, config, image_url)
    json_data = json.loads(json_bytes.decode("utf-8"))

    image = json_data["images"][0]
    assert image["metar"]["icao_code"] == "LFRK"
    assert image["metar"]["source"] == "aviationweather.gov"
    assert image["metar"]["raw_metar"] is None
    assert image["metar"]["raw_taf"] is None


def test_generate_metadata_json_timestamp_format() -> None:
    """Test that timestamps are in correct format."""
    from aero_pi_cam.core.config import SftpConfig

    sftp_config = SftpConfig(
        host="test.example.com",
        port=22,
        user="testuser",
        password="testpass",
        remote_path="/test/path",
        timeout_seconds=30,
    )
    config = _create_test_config(upload_method="SFTP", sftp_config=sftp_config)
    metadata = {
        "timestamp": "2026-01-02T15:30:00Z",
        "location": "TEST",
        "is_day": "true",
    }
    image_url = "https://test.com/TEST-test_camera.jpg"

    json_bytes = generate_metadata_json(metadata, config, image_url)
    json_data = json.loads(json_bytes.decode("utf-8"))

    # Check ISO format with Z suffix
    assert json_data["last_update"].endswith("Z")
    assert "T" in json_data["last_update"]
    # Check timestamp is an integer
    assert isinstance(json_data["last_update_timestamp"], int)
    assert json_data["last_update_timestamp"] > 0

    # Check next_update format and that it's after last_update
    assert json_data["next_update"].endswith("Z")
    assert "T" in json_data["next_update"]
    assert isinstance(json_data["next_update_timestamp"], int)
    assert json_data["next_update_timestamp"] > json_data["last_update_timestamp"]
    # Verify next_update is approximately TTL seconds after last_update (allow 1 second tolerance)
    ttl_seconds = int(json_data["images"][0]["TTL"])
    time_diff = json_data["next_update_timestamp"] - json_data["last_update_timestamp"]
    assert abs(time_diff - ttl_seconds) <= 1


def test_generate_metadata_json_all_fields_present() -> None:
    """Test that all required fields are present in JSON."""
    from aero_pi_cam.core.config import SftpConfig

    sftp_config = SftpConfig(
        host="test.example.com",
        port=22,
        user="testuser",
        password="testpass",
        remote_path="/test/path",
        timeout_seconds=30,
    )
    config = _create_test_config(upload_method="SFTP", sftp_config=sftp_config)
    metadata = {
        "timestamp": "2026-01-02T15:30:00Z",
        "location": "TEST",
        "is_day": "true",
    }
    image_url = "https://test.com/TEST-test_camera.jpg"

    json_bytes = generate_metadata_json(metadata, config, image_url)
    json_data = json.loads(json_bytes.decode("utf-8"))

    # Top-level fields
    assert "day_night_mode" in json_data
    assert "debug_mode" in json_data
    assert "last_update" in json_data
    assert "last_update_timestamp" in json_data
    assert "next_update" in json_data
    assert "next_update_timestamp" in json_data
    assert "images" in json_data

    # Image fields
    image = json_data["images"][0]
    assert "path" in image
    assert "no_metar_path" in image
    assert "TTL" in image
    assert "provider_name" in image
    assert "camera_name" in image
    assert "license_mark" in image
    assert "location" in image
    assert "sunrise" in image
    assert "sunset" in image
    assert "metar" in image

    # Location fields
    assert "name" in image["location"]
    assert "latitude" in image["location"]
    assert "longitude" in image["location"]
    assert "camera_heading" in image["location"]

    # METAR fields
    assert "icao_code" in image["metar"]
    assert "source" in image["metar"]
    assert "raw_metar" in image["metar"]
    assert "raw_taf" in image["metar"]


def test_generate_metadata_json_with_no_metar_path() -> None:
    """Test JSON generation with no_metar_path provided."""
    from aero_pi_cam.core.config import SftpConfig

    sftp_config = SftpConfig(
        host="test.example.com",
        port=22,
        user="testuser",
        password="testpass",
        remote_path="/test/path",
        timeout_seconds=30,
    )
    config = _create_test_config(upload_method="SFTP", sftp_config=sftp_config)
    metadata = {
        "timestamp": "2026-01-02T15:30:00Z",
        "location": "TEST",
        "is_day": "true",
    }
    image_url = "https://test.com/TEST-test_camera.jpg"
    no_metar_image_url = "https://test.com/TEST-test_camera-clean.jpg"

    json_bytes = generate_metadata_json(
        metadata, config, image_url, no_metar_image_url=no_metar_image_url
    )
    json_data = json.loads(json_bytes.decode("utf-8"))

    image = json_data["images"][0]
    assert image["path"] == image_url
    assert image["no_metar_path"] == no_metar_image_url
