"""Tests for EXIF metadata module."""

from datetime import UTC, datetime
from io import BytesIO

import piexif
import pytest
from PIL import Image

from aero_pi_cam.config import (
    ApiConfig,
    CameraConfig,
    Config,
    LocationConfig,
    MetadataConfig,
    MetarConfig,
    OverlayConfig,
    ScheduleConfig,
)
from aero_pi_cam.exif import (
    build_exif_dict,
    build_xmp_xml,
    convert_gps_coordinates,
    embed_exif_in_jpeg,
)


@pytest.fixture
def mock_config() -> Config:
    """Create a mock configuration for testing."""
    return Config(
        camera=CameraConfig(rtsp_url="rtsp://example.com/stream"),
        location=LocationConfig(
            name="LFAS", latitude=48.9267952, longitude=-0.1477169, camera_heading="060° RWY 06"
        ),
        schedule=ScheduleConfig(day_interval_minutes=5, night_interval_minutes=60),
        api=ApiConfig(key="test-key", timeout_seconds=30),
        overlay=OverlayConfig(
            provider_name="LFAS - caenfalaiseplaneurs.fr/cam",
            provider_logo="images/logo-cgaf.png",
            camera_name="hangar 2",
        ),
        metar=MetarConfig(icao_code="LFAS", enabled=False),
        metadata=MetadataConfig(
            github_repo="https://github.com/CaenFalaisePlaneurs/aero-pi-cam",
            webcam_url="https://caenfalaiseplaneurs.fr/cam",
            license="CC BY-SA 4.0",
            license_url="https://creativecommons.org/licenses/by-sa/4.0/",
            license_mark="This work is licensed under CC BY-SA 4.0. To view a copy of this license, visit https://creativecommons.org/licenses/by-sa/4.0/",
        ),
    )


def test_convert_gps_coordinates_positive() -> None:
    """Test GPS coordinate conversion for positive coordinates (North, East)."""
    result = convert_gps_coordinates(48.9267952, 0.1477169)

    # Check latitude (48°55'36.46" N)
    assert "GPSLatitude" in result
    assert "GPSLatitudeRef" in result
    assert result["GPSLatitudeRef"] == "N"
    lat = result["GPSLatitude"]
    assert lat[0] == (48, 1)  # degrees
    assert lat[1] == (55, 1)  # minutes
    # seconds should be approximately 36.46
    assert abs(lat[2][0] / lat[2][1] - 36.46) < 1.0

    # Check longitude (0°8'51.78" E)
    assert "GPSLongitude" in result
    assert "GPSLongitudeRef" in result
    assert result["GPSLongitudeRef"] == "E"
    lon = result["GPSLongitude"]
    assert lon[0] == (0, 1)  # degrees
    assert lon[1] == (8, 1)  # minutes
    # seconds should be approximately 51.78
    assert abs(lon[2][0] / lon[2][1] - 51.78) < 1.0


def test_convert_gps_coordinates_negative() -> None:
    """Test GPS coordinate conversion for negative coordinates (South, West)."""
    result = convert_gps_coordinates(-48.9267952, -0.1477169)

    assert result["GPSLatitudeRef"] == "S"
    assert result["GPSLongitudeRef"] == "W"


def test_convert_gps_coordinates_zero() -> None:
    """Test GPS coordinate conversion for zero coordinates."""
    result = convert_gps_coordinates(0.0, 0.0)

    assert result["GPSLatitudeRef"] == "N"
    assert result["GPSLongitudeRef"] == "E"
    assert result["GPSLatitude"][0] == (0, 1)
    assert result["GPSLongitude"][0] == (0, 1)


def test_build_exif_dict_standard_tags(mock_config: Config) -> None:
    """Test building EXIF dictionary with standard tags."""
    sunrise = datetime(2026, 1, 2, 7, 23, 0, tzinfo=UTC)
    sunset = datetime(2026, 1, 2, 17, 45, 0, tzinfo=UTC)

    exif_dict = build_exif_dict(mock_config, sunrise, sunset)

    # Check standard tags
    assert piexif.ImageIFD.ImageDescription in exif_dict["0th"]
    assert exif_dict["0th"][piexif.ImageIFD.ImageDescription] == "hangar 2"

    assert piexif.ImageIFD.Copyright in exif_dict["0th"]
    copyright_text = exif_dict["0th"][piexif.ImageIFD.Copyright]
    assert "LFAS - caenfalaiseplaneurs.fr/cam" in copyright_text
    assert "CC BY-SA 4.0" in copyright_text

    # Check GPS tags
    assert piexif.GPSIFD.GPSLatitude in exif_dict["GPS"]
    assert piexif.GPSIFD.GPSLatitudeRef in exif_dict["GPS"]
    assert exif_dict["GPS"][piexif.GPSIFD.GPSLatitudeRef] == "N"
    assert piexif.GPSIFD.GPSLongitude in exif_dict["GPS"]
    assert piexif.GPSIFD.GPSLongitudeRef in exif_dict["GPS"]
    assert exif_dict["GPS"][piexif.GPSIFD.GPSLongitudeRef] == "W"


def test_build_exif_dict_with_metar_taf(mock_config: Config) -> None:
    """Test building EXIF dictionary with METAR and TAF data."""
    import json

    sunrise = datetime(2026, 1, 2, 7, 23, 0, tzinfo=UTC)
    sunset = datetime(2026, 1, 2, 17, 45, 0, tzinfo=UTC)
    raw_metar = "LFAS 021530Z AUTO 25008KT 9999 OVC030 12/08 Q1012"
    raw_taf = "LFAS 021200Z 0212/0312 25010KT 9999 OVC030"

    exif_dict = build_exif_dict(
        mock_config, sunrise, sunset, raw_metar=raw_metar, raw_taf=raw_taf, metar_icao="LFAS"
    )

    # Check UserComment contains structured JSON
    assert piexif.ExifIFD.UserComment in exif_dict["Exif"]
    user_comment = exif_dict["Exif"][piexif.ExifIFD.UserComment]
    assert isinstance(user_comment, bytes)

    # Decode UserComment (skip encoding byte and null terminator)
    comment_text = user_comment[1:-1].decode("utf-8")
    metadata = json.loads(comment_text)

    # Verify structured key-value pairs
    assert metadata["camera_name"] == "hangar 2"
    assert metadata["provider_name"] == "LFAS - caenfalaiseplaneurs.fr/cam"
    assert metadata["airfield_oaci"] == "LFAS"
    assert metadata["metar"] == "LFAS 021530Z AUTO 25008KT 9999 OVC030 12/08 Q1012"
    assert metadata["taf"] == "LFAS 021200Z 0212/0312 25010KT 9999 OVC030"
    assert metadata["sunrise"] == "2026-01-02T07:23:00Z"
    assert metadata["sunset"] == "2026-01-02T17:45:00Z"
    # Verify new fields
    assert metadata["github_repo"] == "https://github.com/CaenFalaisePlaneurs/aero-pi-cam"
    assert metadata["webcam_url"] == "https://caenfalaiseplaneurs.fr/cam"
    assert metadata["license"] == "CC BY-SA 4.0"
    assert metadata["license_url"] == "https://creativecommons.org/licenses/by-sa/4.0/"
    assert "This work is licensed under CC BY-SA 4.0" in metadata["license_mark"]


def test_build_exif_dict_without_optional_data(mock_config: Config) -> None:
    """Test building EXIF dictionary without optional METAR/TAF data."""
    import json

    sunrise = datetime(2026, 1, 2, 7, 23, 0, tzinfo=UTC)
    sunset = datetime(2026, 1, 2, 17, 45, 0, tzinfo=UTC)

    exif_dict = build_exif_dict(mock_config, sunrise, sunset)

    # Standard tags should still be present
    assert piexif.ImageIFD.ImageDescription in exif_dict["0th"]
    assert piexif.ImageIFD.Copyright in exif_dict["0th"]
    assert piexif.GPSIFD.GPSLatitude in exif_dict["GPS"]

    # UserComment should still contain structured JSON with required fields
    assert piexif.ExifIFD.UserComment in exif_dict["Exif"]
    user_comment = exif_dict["Exif"][piexif.ExifIFD.UserComment]
    comment_text = user_comment[1:-1].decode("utf-8")
    metadata = json.loads(comment_text)

    # Required fields should be present
    assert "camera_name" in metadata
    assert "provider_name" in metadata
    assert "sunrise" in metadata
    assert "sunset" in metadata
    assert metadata["sunrise"] == "2026-01-02T07:23:00Z"
    assert metadata["sunset"] == "2026-01-02T17:45:00Z"
    # License and URL fields should always be present
    assert "github_repo" in metadata
    assert "webcam_url" in metadata
    assert "license" in metadata
    assert "license_url" in metadata
    assert "license_mark" in metadata
    # Optional fields should not be present
    assert "metar" not in metadata
    assert "taf" not in metadata
    assert "airfield_oaci" not in metadata


def test_embed_exif_in_jpeg(mock_config: Config) -> None:
    """Test embedding EXIF metadata into JPEG bytes."""
    # Create a test JPEG image
    test_img = Image.new("RGB", (800, 600), (128, 128, 128))
    img_bytes = BytesIO()
    test_img.save(img_bytes, format="JPEG")
    jpeg_bytes = img_bytes.getvalue()

    # Build EXIF dictionary
    sunrise = datetime(2026, 1, 2, 7, 23, 0, tzinfo=UTC)
    sunset = datetime(2026, 1, 2, 17, 45, 0, tzinfo=UTC)
    exif_dict = build_exif_dict(mock_config, sunrise, sunset)

    # Embed EXIF
    result_bytes = embed_exif_in_jpeg(jpeg_bytes, exif_dict)

    # Verify result is still valid JPEG
    assert len(result_bytes) > 0
    img = Image.open(BytesIO(result_bytes))
    assert img.size == (800, 600)

    # Verify EXIF data is present
    exif_data = piexif.load(result_bytes)
    assert "0th" in exif_data
    assert piexif.ImageIFD.ImageDescription in exif_data["0th"]
    # piexif returns bytes for string fields
    assert exif_data["0th"][piexif.ImageIFD.ImageDescription].decode("utf-8") == "hangar 2"
    assert piexif.ImageIFD.Copyright in exif_data["0th"]
    copyright_text = exif_data["0th"][piexif.ImageIFD.Copyright].decode("utf-8")
    assert "LFAS - caenfalaiseplaneurs.fr/cam" in copyright_text
    assert "CC BY-SA 4.0" in copyright_text
    assert "GPS" in exif_data
    assert piexif.GPSIFD.GPSLatitude in exif_data["GPS"]


def test_embed_exif_verifies_custom_tags(mock_config: Config) -> None:
    """Test that custom tags (METAR, TAF, OACI, sunrise/sunset) are embedded correctly."""
    import json

    # Create a test JPEG image
    test_img = Image.new("RGB", (800, 600), (128, 128, 128))
    img_bytes = BytesIO()
    test_img.save(img_bytes, format="JPEG")
    jpeg_bytes = img_bytes.getvalue()

    # Build EXIF dictionary with all custom data
    sunrise = datetime(2026, 1, 2, 7, 23, 0, tzinfo=UTC)
    sunset = datetime(2026, 1, 2, 17, 45, 0, tzinfo=UTC)
    raw_metar = "LFAS 021530Z AUTO 25008KT 9999 OVC030 12/08 Q1012"
    raw_taf = "LFAS 021200Z 0212/0312 25010KT 9999 OVC030"
    exif_dict = build_exif_dict(
        mock_config, sunrise, sunset, raw_metar=raw_metar, raw_taf=raw_taf, metar_icao="LFAS"
    )

    # Embed EXIF
    result_bytes = embed_exif_in_jpeg(jpeg_bytes, exif_dict)

    # Verify custom tags in UserComment (structured JSON)
    exif_data = piexif.load(result_bytes)
    assert "Exif" in exif_data
    assert piexif.ExifIFD.UserComment in exif_data["Exif"]

    user_comment = exif_data["Exif"][piexif.ExifIFD.UserComment]
    comment_text = user_comment[1:-1].decode("utf-8")
    metadata = json.loads(comment_text)

    assert metadata["airfield_oaci"] == "LFAS"
    assert metadata["metar"] == "LFAS 021530Z AUTO 25008KT 9999 OVC030 12/08 Q1012"
    assert metadata["taf"] == "LFAS 021200Z 0212/0312 25010KT 9999 OVC030"
    assert metadata["sunrise"] == "2026-01-02T07:23:00Z"
    assert metadata["sunset"] == "2026-01-02T17:45:00Z"


def test_build_xmp_xml(mock_config: Config) -> None:
    """Test building XMP XML with custom schema."""
    sunrise = datetime(2026, 1, 2, 7, 23, 0, tzinfo=UTC)
    sunset = datetime(2026, 1, 2, 17, 45, 0, tzinfo=UTC)
    raw_metar = "LFAS 021530Z AUTO 25008KT 9999 OVC030 12/08 Q1012"
    raw_taf = "LFAS 021200Z 0212/0312 25010KT 9999 OVC030"

    xmp_xml = build_xmp_xml(
        mock_config, sunrise, sunset, raw_metar=raw_metar, raw_taf=raw_taf, metar_icao="LFAS"
    )

    # Verify XMP structure
    assert '<?xpacket begin="" id="W5M0MpCehiHzreSzNTczkc9d"?>' in xmp_xml
    assert 'xmlns:aero="http://aero-pi-cam.org/xmp/1.0/"' in xmp_xml
    assert "<aero:camera_name>hangar 2</aero:camera_name>" in xmp_xml
    assert "<aero:provider_name>LFAS - caenfalaiseplaneurs.fr/cam</aero:provider_name>" in xmp_xml
    assert "<aero:airfield_oaci>LFAS</aero:airfield_oaci>" in xmp_xml
    assert "<aero:metar>LFAS 021530Z AUTO 25008KT 9999 OVC030 12/08 Q1012</aero:metar>" in xmp_xml
    assert "<aero:taf>LFAS 021200Z 0212/0312 25010KT 9999 OVC030</aero:taf>" in xmp_xml
    assert "<aero:sunrise>2026-01-02T07:23:00Z</aero:sunrise>" in xmp_xml
    assert "<aero:sunset>2026-01-02T17:45:00Z</aero:sunset>" in xmp_xml
    # Verify new fields
    assert "<aero:github_repo>https://github.com/CaenFalaisePlaneurs/aero-pi-cam</aero:github_repo>" in xmp_xml
    assert "<aero:webcam_url>https://caenfalaiseplaneurs.fr/cam</aero:webcam_url>" in xmp_xml
    assert "<aero:license>CC BY-SA 4.0</aero:license>" in xmp_xml
    assert "<aero:license_url>https://creativecommons.org/licenses/by-sa/4.0/</aero:license_url>" in xmp_xml
    assert "This work is licensed under CC BY-SA 4.0" in xmp_xml
    assert "</x:xmpmeta>" in xmp_xml
    assert '<?xpacket end="w"?>' in xmp_xml


def test_build_xmp_xml_without_optional_data(mock_config: Config) -> None:
    """Test building XMP XML without optional METAR/TAF data."""
    sunrise = datetime(2026, 1, 2, 7, 23, 0, tzinfo=UTC)
    sunset = datetime(2026, 1, 2, 17, 45, 0, tzinfo=UTC)

    xmp_xml = build_xmp_xml(mock_config, sunrise, sunset)

    # Required fields should be present
    assert "<aero:camera_name>hangar 2</aero:camera_name>" in xmp_xml
    assert "<aero:provider_name>LFAS - caenfalaiseplaneurs.fr/cam</aero:provider_name>" in xmp_xml
    assert "<aero:sunrise>2026-01-02T07:23:00Z</aero:sunrise>" in xmp_xml
    assert "<aero:sunset>2026-01-02T17:45:00Z</aero:sunset>" in xmp_xml
    # License and URL fields should always be present
    assert "<aero:github_repo>" in xmp_xml
    assert "<aero:webcam_url>" in xmp_xml
    assert "<aero:license>CC BY-SA 4.0</aero:license>" in xmp_xml
    assert "<aero:license_url>" in xmp_xml
    assert "<aero:license_mark>" in xmp_xml
    assert "<aero:camera_heading>060° RWY 06</aero:camera_heading>" in xmp_xml
    assert "</x:xmpmeta>" in xmp_xml
    # Optional fields should not be present
    assert "<aero:airfield_oaci>" not in xmp_xml
    assert "<aero:metar>" not in xmp_xml
    assert "<aero:taf>" not in xmp_xml


def test_embed_exif_with_xmp(mock_config: Config) -> None:
    """Test embedding both EXIF and XMP metadata."""
    # Create a test JPEG image
    test_img = Image.new("RGB", (800, 600), (128, 128, 128))
    img_bytes = BytesIO()
    test_img.save(img_bytes, format="JPEG")
    jpeg_bytes = img_bytes.getvalue()

    # Build EXIF and XMP
    sunrise = datetime(2026, 1, 2, 7, 23, 0, tzinfo=UTC)
    sunset = datetime(2026, 1, 2, 17, 45, 0, tzinfo=UTC)
    exif_dict = build_exif_dict(mock_config, sunrise, sunset)
    xmp_xml = build_xmp_xml(mock_config, sunrise, sunset)

    # Embed both
    result_bytes = embed_exif_in_jpeg(jpeg_bytes, exif_dict, xmp_xml=xmp_xml)

    # Verify result is still valid JPEG
    assert len(result_bytes) > 0
    img = Image.open(BytesIO(result_bytes))
    assert img.size == (800, 600)

    # Verify XMP is embedded (check for XMP identifier in JPEG)
    assert b"http://ns.adobe.com/xap/1.0/" in result_bytes


def test_embed_exif_gps_coordinates(mock_config: Config) -> None:
    """Test that GPS coordinates are correctly embedded and readable."""
    # Create a test JPEG image
    test_img = Image.new("RGB", (800, 600), (128, 128, 128))
    img_bytes = BytesIO()
    test_img.save(img_bytes, format="JPEG")
    jpeg_bytes = img_bytes.getvalue()

    # Build EXIF dictionary
    sunrise = datetime(2026, 1, 2, 7, 23, 0, tzinfo=UTC)
    sunset = datetime(2026, 1, 2, 17, 45, 0, tzinfo=UTC)
    exif_dict = build_exif_dict(mock_config, sunrise, sunset)

    # Embed EXIF
    result_bytes = embed_exif_in_jpeg(jpeg_bytes, exif_dict)

    # Verify GPS data
    exif_data = piexif.load(result_bytes)
    assert "GPS" in exif_data
    assert piexif.GPSIFD.GPSLatitude in exif_data["GPS"]
    assert piexif.GPSIFD.GPSLatitudeRef in exif_data["GPS"]
    # piexif returns bytes for string fields
    assert exif_data["GPS"][piexif.GPSIFD.GPSLatitudeRef].decode("utf-8") == "N"
    assert piexif.GPSIFD.GPSLongitude in exif_data["GPS"]
    assert piexif.GPSIFD.GPSLongitudeRef in exif_data["GPS"]
    assert exif_data["GPS"][piexif.GPSIFD.GPSLongitudeRef].decode("utf-8") == "W"

    # Verify GPS coordinates are approximately correct
    lat = exif_data["GPS"][piexif.GPSIFD.GPSLatitude]
    # Convert back to decimal: 48°55'36.46" ≈ 48.9268
    lat_decimal = lat[0][0] / lat[0][1] + (lat[1][0] / lat[1][1]) / 60 + (lat[2][0] / lat[2][1]) / 3600
    assert abs(lat_decimal - 48.9267952) < 0.01

    lon = exif_data["GPS"][piexif.GPSIFD.GPSLongitude]
    # Convert back to decimal: 0°8'51.78" ≈ 0.1477 (but it's negative/West)
    lon_decimal = lon[0][0] / lon[0][1] + (lon[1][0] / lon[1][1]) / 60 + (lon[2][0] / lon[2][1]) / 3600
    # Since it's West, the decimal should be negative
    assert abs(abs(lon_decimal) - 0.1477169) < 0.01


def test_embed_exif_handles_invalid_jpeg() -> None:
    """Test that embed_exif_in_jpeg raises exception for invalid JPEG."""
    invalid_bytes = b"not a jpeg"
    exif_dict = {"0th": {}, "Exif": {}, "GPS": {}, "1st": {}}

    with pytest.raises(Exception):
        embed_exif_in_jpeg(invalid_bytes, exif_dict)

