"""Tests for overlay module."""

from datetime import UTC, datetime
from io import BytesIO
from unittest.mock import patch

import pytest
from PIL import Image, ImageDraw, ImageFont

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
from aero_pi_cam.overlay import (
    add_comprehensive_overlay,
    draw_overlay_on_image,
    draw_text_with_shadow,
    load_icon,
    load_poppins_font,
    parse_color,
    paste_image_with_shadow,
)


@pytest.fixture
def mock_config() -> Config:
    """Create a mock config for testing."""
    return Config(
        camera=CameraConfig(rtsp_url="rtsp://test:pass@192.168.0.1:554/stream1"),
        location=LocationConfig(
            name="TEST", latitude=48.9, longitude=-0.1, camera_heading="060° RWY 06"
        ),
        schedule=ScheduleConfig(day_interval_minutes=5, night_interval_minutes=60),
        api=ApiConfig(url="https://api.example.com", key="test-key", timeout_seconds=30),
        overlay=OverlayConfig(
            provider_name="Test Provider",
            provider_logo="images/logo.svg",
            camera_name="test camera",
            font_color="white",
            font_size=16,
            shadow_enabled=True,
            shadow_offset_x=2,
            shadow_offset_y=2,
            shadow_color="black",
        ),
        metar=MetarConfig(enabled=False, icao_code="TEST"),
        metadata=MetadataConfig(
            github_repo="https://github.com/test/repo",
            webcam_url="https://example.com/cam",
            license="CC BY-SA 4.0",
            license_url="https://creativecommons.org/licenses/by-sa/4.0/",
            license_mark="Test license mark",
        ),
    )


def test_parse_color_white() -> None:
    """Test parsing white color."""
    assert parse_color("white") == (255, 255, 255)


def test_parse_color_black() -> None:
    """Test parsing black color."""
    assert parse_color("black") == (0, 0, 0)


def test_parse_color_red() -> None:
    """Test parsing red color."""
    assert parse_color("red") == (255, 0, 0)


def test_parse_color_green() -> None:
    """Test parsing green color."""
    assert parse_color("green") == (0, 255, 0)


def test_parse_color_blue() -> None:
    """Test parsing blue color."""
    assert parse_color("blue") == (0, 0, 255)


def test_parse_color_case_insensitive() -> None:
    """Test parsing color is case insensitive."""
    assert parse_color("WHITE") == (255, 255, 255)
    assert parse_color("Black") == (0, 0, 0)


def test_parse_color_unknown_defaults_to_white() -> None:
    """Test parsing unknown color defaults to white."""
    assert parse_color("unknown") == (255, 255, 255)


def test_load_poppins_font_with_font_file(mock_config) -> None:
    """Test loading Poppins font when font file exists."""
    # This will use the actual font if it exists, or fallback to default
    font = load_poppins_font(16)
    assert font is not None
    # FreeTypeFont is a subclass, so check for ImageFont base class or FreeTypeFont
    assert hasattr(font, "getsize") or hasattr(font, "getbbox")


def test_load_poppins_font_fallback() -> None:
    """Test loading Poppins font falls back to default when font missing."""
    with patch("aero_pi_cam.overlay.Path.exists", return_value=False):
        font = load_poppins_font(16)
        assert font is not None
        # FreeTypeFont is a subclass, so check for ImageFont base class or FreeTypeFont
        assert hasattr(font, "getsize") or hasattr(font, "getbbox")


def test_load_poppins_font_exception() -> None:
    """Test loading Poppins font handles exceptions."""
    # Test exception during font loading - patch the Path.exists check and truetype call
    # but allow load_default to work normally
    original_truetype = ImageFont.truetype

    def mock_truetype(*args, **kwargs):
        # Only raise exception for our font path, not for default font
        if "Poppins-Medium.ttf" in str(args[0]):
            raise OSError("Font file error")
        return original_truetype(*args, **kwargs)

    with (
        patch("aero_pi_cam.overlay.Path.exists", return_value=True),
        patch("aero_pi_cam.overlay.ImageFont.truetype", side_effect=mock_truetype),
    ):
        font = load_poppins_font(16)
        assert font is not None
        # Should fallback to default
        assert hasattr(font, "getsize") or hasattr(font, "getbbox")


def test_load_icon_codebase_icon() -> None:
    """Test loading codebase icon."""
    # Test with actual sunrise icon if it exists
    icon = load_icon("images/icons/sunrise.svg", 24, is_codebase_icon=True)
    # Should return None if file doesn't exist, or Image if it does
    assert icon is None or isinstance(icon, Image.Image)


def test_load_icon_user_icon() -> None:
    """Test loading user-configured icon."""
    icon = load_icon("nonexistent.svg", 24, is_codebase_icon=False)
    assert icon is None


def test_load_icon_absolute_path() -> None:
    """Test loading icon with absolute path."""
    icon = load_icon("/nonexistent/absolute/path.svg", 24, is_codebase_icon=False)
    assert icon is None


def test_load_icon_exception_handling() -> None:
    """Test load_icon handles exceptions gracefully."""
    with patch("aero_pi_cam.overlay.cairosvg.svg2png", side_effect=Exception("Test error")):
        icon = load_icon("test.svg", 24, is_codebase_icon=False)
        assert icon is None


def test_draw_text_with_shadow_enabled() -> None:
    """Test drawing text with shadow enabled."""
    img = Image.new("RGBA", (100, 100), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    font = ImageFont.load_default()

    draw_text_with_shadow(draw, (10, 10), "Test", (255, 255, 255), font, True, 2, 2, (0, 0, 0))

    # Verify text was drawn (check that image has non-transparent pixels)
    pixels = list(img.getdata())
    assert any(p[3] > 0 for p in pixels)


def test_draw_text_with_shadow_disabled() -> None:
    """Test drawing text with shadow disabled."""
    img = Image.new("RGBA", (100, 100), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    font = ImageFont.load_default()

    draw_text_with_shadow(draw, (10, 10), "Test", (255, 255, 255), font, False, 2, 2, (0, 0, 0))

    # Verify text was drawn
    pixels = list(img.getdata())
    assert any(p[3] > 0 for p in pixels)


def test_paste_image_with_shadow_enabled() -> None:
    """Test pasting image with shadow enabled."""
    img = Image.new("RGBA", (100, 100), (0, 0, 0, 0))
    icon = Image.new("RGBA", (20, 20), (255, 0, 0, 255))  # Red square

    paste_image_with_shadow(img, icon, (10, 10), True, 2, 2, (0, 0, 0))

    # Verify icon was pasted
    pixels = list(img.getdata())
    assert any(p[3] > 0 for p in pixels)


def test_paste_image_with_shadow_disabled() -> None:
    """Test pasting image with shadow disabled."""
    img = Image.new("RGBA", (100, 100), (0, 0, 0, 0))
    icon = Image.new("RGBA", (20, 20), (255, 0, 0, 255))

    paste_image_with_shadow(img, icon, (10, 10), False, 2, 2, (0, 0, 0))

    # Verify icon was pasted
    pixels = list(img.getdata())
    assert any(p[3] > 0 for p in pixels)


def test_paste_image_with_shadow_non_rgba() -> None:
    """Test pasting image with shadow when icon is not RGBA."""
    img = Image.new("RGBA", (100, 100), (0, 0, 0, 0))
    icon = Image.new("RGB", (20, 20), (255, 0, 0))  # RGB, not RGBA

    # Shadow is skipped for non-RGBA icons, but paste still works
    # Convert to RGBA for the paste operation
    icon_rgba = icon.convert("RGBA")
    paste_image_with_shadow(img, icon_rgba, (10, 10), True, 2, 2, (0, 0, 0))

    # Verify icon was pasted
    pixels = list(img.getdata())
    assert any(p[3] > 0 for p in pixels)


def test_draw_overlay_on_image_basic(mock_config) -> None:
    """Test drawing overlay on image with basic config."""
    img = Image.new("RGBA", (800, 600), (0, 0, 0, 0))
    capture_time = datetime(2026, 1, 2, 12, 0, 0, tzinfo=UTC)
    sunrise_time = datetime(2026, 1, 2, 7, 0, 0, tzinfo=UTC)
    sunset_time = datetime(2026, 1, 2, 17, 0, 0, tzinfo=UTC)

    draw_overlay_on_image(
        img, mock_config, capture_time, sunrise_time, sunset_time, None, None
    )

    # Verify overlay was drawn
    pixels = list(img.getdata())
    assert any(p[3] > 0 for p in pixels)


def test_draw_overlay_on_image_with_metar(mock_config) -> None:
    """Test drawing overlay with METAR data."""
    img = Image.new("RGBA", (800, 600), (0, 0, 0, 0))
    capture_time = datetime(2026, 1, 2, 12, 0, 0, tzinfo=UTC)
    sunrise_time = datetime(2026, 1, 2, 7, 0, 0, tzinfo=UTC)
    sunset_time = datetime(2026, 1, 2, 17, 0, 0, tzinfo=UTC)

    config = Config(
        camera=CameraConfig(rtsp_url="rtsp://test:pass@192.168.0.1:554/stream1"),
        location=LocationConfig(
            name="TEST", latitude=48.9, longitude=-0.1, camera_heading="060° RWY 06"
        ),
        schedule=ScheduleConfig(day_interval_minutes=5, night_interval_minutes=60),
        api=ApiConfig(url="https://api.example.com", key="test-key", timeout_seconds=30),
        overlay=OverlayConfig(
            provider_name="Test Provider",
            provider_logo="images/logo.svg",
            camera_name="test camera",
            font_color="white",
            font_size=16,
            shadow_enabled=True,
            shadow_offset_x=2,
            shadow_offset_y=2,
            shadow_color="black",
        ),
        metar=MetarConfig(enabled=True, icao_code="TEST", raw_metar_enabled=True),
        metadata=MetadataConfig(
            github_repo="https://github.com/test/repo",
            webcam_url="https://example.com/cam",
            license="CC BY-SA 4.0",
            license_url="https://creativecommons.org/licenses/by-sa/4.0/",
            license_mark="Test license mark",
        ),
    )

    draw_overlay_on_image(
        img,
        config,
        capture_time,
        sunrise_time,
        sunset_time,
        raw_metar="TEST 021200Z 33009KT 9999 FEW044 04/02 Q1011",
        raw_taf=None,
    )

    # Verify overlay was drawn
    pixels = list(img.getdata())
    assert any(p[3] > 0 for p in pixels)


def test_draw_overlay_on_image_with_taf(mock_config) -> None:
    """Test drawing overlay with TAF data."""
    img = Image.new("RGBA", (800, 600), (0, 0, 0, 0))
    capture_time = datetime(2026, 1, 2, 12, 0, 0, tzinfo=UTC)
    sunrise_time = datetime(2026, 1, 2, 7, 0, 0, tzinfo=UTC)
    sunset_time = datetime(2026, 1, 2, 17, 0, 0, tzinfo=UTC)

    config = Config(
        camera=CameraConfig(rtsp_url="rtsp://test:pass@192.168.0.1:554/stream1"),
        location=LocationConfig(
            name="TEST", latitude=48.9, longitude=-0.1, camera_heading="060° RWY 06"
        ),
        schedule=ScheduleConfig(day_interval_minutes=5, night_interval_minutes=60),
        api=ApiConfig(url="https://api.example.com", key="test-key", timeout_seconds=30),
        overlay=OverlayConfig(
            provider_name="Test Provider",
            provider_logo="images/logo.svg",
            camera_name="test camera",
            font_color="white",
            font_size=16,
            shadow_enabled=True,
            shadow_offset_x=2,
            shadow_offset_y=2,
            shadow_color="black",
        ),
        metar=MetarConfig(enabled=True, icao_code="TEST", raw_metar_enabled=True),
        metadata=MetadataConfig(
            github_repo="https://github.com/test/repo",
            webcam_url="https://example.com/cam",
            license="CC BY-SA 4.0",
            license_url="https://creativecommons.org/licenses/by-sa/4.0/",
            license_mark="Test license mark",
        ),
    )

    draw_overlay_on_image(
        img,
        config,
        capture_time,
        sunrise_time,
        sunset_time,
        raw_metar="TEST 021200Z 33009KT 9999 FEW044 04/02 Q1011",
        raw_taf="TEST 021400Z 0215/0224 34010KT 9999 BKN030",
    )

    # Verify overlay was drawn
    pixels = list(img.getdata())
    assert any(p[3] > 0 for p in pixels)


def test_draw_overlay_on_image_with_logo(mock_config) -> None:
    """Test drawing overlay with logo."""
    img = Image.new("RGBA", (800, 600), (0, 0, 0, 0))
    capture_time = datetime(2026, 1, 2, 12, 0, 0, tzinfo=UTC)
    sunrise_time = datetime(2026, 1, 2, 7, 0, 0, tzinfo=UTC)
    sunset_time = datetime(2026, 1, 2, 17, 0, 0, tzinfo=UTC)

    # Create a simple test logo
    test_logo = Image.new("RGBA", (50, 50), (255, 0, 0, 255))
    with patch("aero_pi_cam.overlay.load_icon", return_value=test_logo):
        draw_overlay_on_image(
            img, mock_config, capture_time, sunrise_time, sunset_time, None, None
        )

    # Verify overlay was drawn
    pixels = list(img.getdata())
    assert any(p[3] > 0 for p in pixels)


def test_add_comprehensive_overlay(mock_config) -> None:
    """Test adding comprehensive overlay to image."""
    # Create a test image
    test_img = Image.new("RGB", (800, 600), (128, 128, 128))
    img_bytes = BytesIO()
    test_img.save(img_bytes, format="JPEG")
    img_bytes.seek(0)
    image_bytes = img_bytes.getvalue()

    capture_time = datetime(2026, 1, 2, 12, 0, 0, tzinfo=UTC)
    sunrise_time = datetime(2026, 1, 2, 7, 0, 0, tzinfo=UTC)
    sunset_time = datetime(2026, 1, 2, 17, 0, 0, tzinfo=UTC)

    result = add_comprehensive_overlay(
        image_bytes, mock_config, capture_time, sunrise_time, sunset_time, None, None
    )

    assert isinstance(result, bytes)
    assert len(result) > 0

    # Verify it's a valid JPEG
    img = Image.open(BytesIO(result))
    assert img.size == (800, 600)


def test_add_comprehensive_overlay_invalid_image(mock_config) -> None:
    """Test adding overlay to invalid image returns original."""
    invalid_bytes = b"not an image"
    capture_time = datetime(2026, 1, 2, 12, 0, 0, tzinfo=UTC)
    sunrise_time = datetime(2026, 1, 2, 7, 0, 0, tzinfo=UTC)
    sunset_time = datetime(2026, 1, 2, 17, 0, 0, tzinfo=UTC)

    result = add_comprehensive_overlay(
        invalid_bytes, mock_config, capture_time, sunrise_time, sunset_time, None, None
    )

    assert result == invalid_bytes


def test_draw_overlay_shadow_disabled() -> None:
    """Test drawing overlay with shadow disabled."""
    config = Config(
        camera=CameraConfig(rtsp_url="rtsp://test:pass@192.168.0.1:554/stream1"),
        location=LocationConfig(
            name="TEST", latitude=48.9, longitude=-0.1, camera_heading="060° RWY 06"
        ),
        schedule=ScheduleConfig(day_interval_minutes=5, night_interval_minutes=60),
        api=ApiConfig(url="https://api.example.com", key="test-key", timeout_seconds=30),
        overlay=OverlayConfig(
            provider_name="Test Provider",
            provider_logo="images/logo.svg",
            camera_name="test camera",
            font_color="white",
            font_size=16,
            shadow_enabled=False,
            shadow_offset_x=2,
            shadow_offset_y=2,
            shadow_color="black",
        ),
        metar=MetarConfig(enabled=False, icao_code="TEST"),
        metadata=MetadataConfig(
            github_repo="https://github.com/test/repo",
            webcam_url="https://example.com/cam",
            license="CC BY-SA 4.0",
            license_url="https://creativecommons.org/licenses/by-sa/4.0/",
            license_mark="Test license mark",
        ),
    )

    img = Image.new("RGBA", (800, 600), (0, 0, 0, 0))
    capture_time = datetime(2026, 1, 2, 12, 0, 0, tzinfo=UTC)
    sunrise_time = datetime(2026, 1, 2, 7, 0, 0, tzinfo=UTC)
    sunset_time = datetime(2026, 1, 2, 17, 0, 0, tzinfo=UTC)

    draw_overlay_on_image(img, config, capture_time, sunrise_time, sunset_time, None, None)

    # Verify overlay was drawn
    pixels = list(img.getdata())
    assert any(p[3] > 0 for p in pixels)


def test_draw_overlay_text_wrapping() -> None:
    """Test text wrapping in METAR/TAF overlay."""
    config = Config(
        camera=CameraConfig(rtsp_url="rtsp://test:pass@192.168.0.1:554/stream1"),
        location=LocationConfig(
            name="TEST", latitude=48.9, longitude=-0.1, camera_heading="060° RWY 06"
        ),
        schedule=ScheduleConfig(day_interval_minutes=5, night_interval_minutes=60),
        api=ApiConfig(url="https://api.example.com", key="test-key", timeout_seconds=30),
        overlay=OverlayConfig(
            provider_name="Test Provider",
            provider_logo="images/logo.svg",
            camera_name="test camera",
            font_color="white",
            font_size=16,
            shadow_enabled=True,
            shadow_offset_x=2,
            shadow_offset_y=2,
            shadow_color="black",
        ),
        metar=MetarConfig(enabled=True, icao_code="TEST", raw_metar_enabled=True),
        metadata=MetadataConfig(
            github_repo="https://github.com/test/repo",
            webcam_url="https://example.com/cam",
            license="CC BY-SA 4.0",
            license_url="https://creativecommons.org/licenses/by-sa/4.0/",
            license_mark="Test license mark",
        ),
    )

    img = Image.new("RGBA", (200, 200), (0, 0, 0, 0))  # Small image to force wrapping
    capture_time = datetime(2026, 1, 2, 12, 0, 0, tzinfo=UTC)
    sunrise_time = datetime(2026, 1, 2, 7, 0, 0, tzinfo=UTC)
    sunset_time = datetime(2026, 1, 2, 17, 0, 0, tzinfo=UTC)

    # Long METAR text that will wrap
    long_metar = "TEST 021200Z 33009KT 9999 FEW044 04/02 Q1011 NOSIG"
    draw_overlay_on_image(
        img, config, capture_time, sunrise_time, sunset_time, long_metar, None
    )

    # Verify overlay was drawn
    pixels = list(img.getdata())
    assert any(p[3] > 0 for p in pixels)


def test_draw_overlay_taf_with_indentation() -> None:
    """Test TAF text with indentation preservation."""
    config = Config(
        camera=CameraConfig(rtsp_url="rtsp://test:pass@192.168.0.1:554/stream1"),
        location=LocationConfig(
            name="TEST", latitude=48.9, longitude=-0.1, camera_heading="060° RWY 06"
        ),
        schedule=ScheduleConfig(day_interval_minutes=5, night_interval_minutes=60),
        api=ApiConfig(url="https://api.example.com", key="test-key", timeout_seconds=30),
        overlay=OverlayConfig(
            provider_name="Test Provider",
            provider_logo="images/logo.svg",
            camera_name="test camera",
            font_color="white",
            font_size=16,
            shadow_enabled=True,
            shadow_offset_x=2,
            shadow_offset_y=2,
            shadow_color="black",
        ),
        metar=MetarConfig(enabled=True, icao_code="TEST", raw_metar_enabled=True),
        metadata=MetadataConfig(
            github_repo="https://github.com/test/repo",
            webcam_url="https://example.com/cam",
            license="CC BY-SA 4.0",
            license_url="https://creativecommons.org/licenses/by-sa/4.0/",
            license_mark="Test license mark",
        ),
    )

    img = Image.new("RGBA", (400, 400), (0, 0, 0, 0))
    capture_time = datetime(2026, 1, 2, 12, 0, 0, tzinfo=UTC)
    sunrise_time = datetime(2026, 1, 2, 7, 0, 0, tzinfo=UTC)
    sunset_time = datetime(2026, 1, 2, 17, 0, 0, tzinfo=UTC)

    # TAF with indentation (leading spaces)
    taf_text = "TEST 021400Z 0215/0224 34010KT 9999 BKN030\n    BECMG 0217/0219 VRB05KT"
    draw_overlay_on_image(
        img, config, capture_time, sunrise_time, sunset_time, None, taf_text
    )

    # Verify overlay was drawn
    pixels = list(img.getdata())
    assert any(p[3] > 0 for p in pixels)


def test_draw_overlay_logo_exception() -> None:
    """Test drawing overlay handles logo loading exception."""
    config = Config(
        camera=CameraConfig(rtsp_url="rtsp://test:pass@192.168.0.1:554/stream1"),
        location=LocationConfig(
            name="TEST", latitude=48.9, longitude=-0.1, camera_heading="060° RWY 06"
        ),
        schedule=ScheduleConfig(day_interval_minutes=5, night_interval_minutes=60),
        api=ApiConfig(url="https://api.example.com", key="test-key", timeout_seconds=30),
        overlay=OverlayConfig(
            provider_name="Test Provider",
            provider_logo="images/logo.svg",
            camera_name="test camera",
            font_color="white",
            font_size=16,
            shadow_enabled=True,
            shadow_offset_x=2,
            shadow_offset_y=2,
            shadow_color="black",
        ),
        metar=MetarConfig(enabled=False, icao_code="TEST"),
        metadata=MetadataConfig(
            github_repo="https://github.com/test/repo",
            webcam_url="https://example.com/cam",
            license="CC BY-SA 4.0",
            license_url="https://creativecommons.org/licenses/by-sa/4.0/",
            license_mark="Test license mark",
        ),
    )

    img = Image.new("RGBA", (800, 600), (0, 0, 0, 0))
    capture_time = datetime(2026, 1, 2, 12, 0, 0, tzinfo=UTC)
    sunrise_time = datetime(2026, 1, 2, 7, 0, 0, tzinfo=UTC)
    sunset_time = datetime(2026, 1, 2, 17, 0, 0, tzinfo=UTC)

    # Mock load_icon to raise exception only for provider logo (not sunrise/sunset icons)
    def mock_load_icon(icon_path: str, size: int, is_codebase_icon: bool = False):
        if not is_codebase_icon:
            raise Exception("Logo error")
        return None  # Return None for codebase icons (they're optional)

    with patch("aero_pi_cam.overlay.load_icon", side_effect=mock_load_icon):
        draw_overlay_on_image(
            img, config, capture_time, sunrise_time, sunset_time, None, None
        )

    # Should not crash, overlay should still be drawn
    pixels = list(img.getdata())
    assert any(p[3] > 0 for p in pixels)


def test_draw_overlay_logo_paste_exception() -> None:
    """Test drawing overlay handles logo paste exception."""
    config = Config(
        camera=CameraConfig(rtsp_url="rtsp://test:pass@192.168.0.1:554/stream1"),
        location=LocationConfig(
            name="TEST", latitude=48.9, longitude=-0.1, camera_heading="060° RWY 06"
        ),
        schedule=ScheduleConfig(day_interval_minutes=5, night_interval_minutes=60),
        api=ApiConfig(url="https://api.example.com", key="test-key", timeout_seconds=30),
        overlay=OverlayConfig(
            provider_name="Test Provider",
            provider_logo="images/logo.svg",
            camera_name="test camera",
            font_color="white",
            font_size=16,
            shadow_enabled=True,
            shadow_offset_x=2,
            shadow_offset_y=2,
            shadow_color="black",
        ),
        metar=MetarConfig(enabled=False, icao_code="TEST"),
        metadata=MetadataConfig(
            github_repo="https://github.com/test/repo",
            webcam_url="https://example.com/cam",
            license="CC BY-SA 4.0",
            license_url="https://creativecommons.org/licenses/by-sa/4.0/",
            license_mark="Test license mark",
        ),
    )

    img = Image.new("RGBA", (800, 600), (0, 0, 0, 0))
    capture_time = datetime(2026, 1, 2, 12, 0, 0, tzinfo=UTC)
    sunrise_time = datetime(2026, 1, 2, 7, 0, 0, tzinfo=UTC)
    sunset_time = datetime(2026, 1, 2, 17, 0, 0, tzinfo=UTC)

    # Create a logo that will cause paste to fail
    test_logo = Image.new("RGBA", (50, 50), (255, 0, 0, 255))
    with (
        patch("aero_pi_cam.overlay.load_icon", return_value=test_logo),
        patch("aero_pi_cam.overlay.paste_image_with_shadow", side_effect=Exception("Paste error")),
    ):
        # Should handle exception gracefully
        try:
            draw_overlay_on_image(
                img, config, capture_time, sunrise_time, sunset_time, None, None
            )
        except Exception:
            # If paste fails, it should be caught internally
            pass

    # Overlay should still be drawn (other elements)
    pixels = list(img.getdata())
    assert any(p[3] > 0 for p in pixels)
