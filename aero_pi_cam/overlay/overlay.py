"""Image overlay with text and SVG icons using Poppins font."""

import os
import platform
from datetime import datetime
from io import BytesIO
from pathlib import Path

import cairosvg  # type: ignore[import-untyped]
from PIL import Image, ImageDraw, ImageFont

from ..core.config import Config


def _is_debug_mode() -> bool:
    """Check if debug mode is enabled."""
    return os.getenv("DEBUG_MODE", "false").lower() == "true"


# Hardcoded icon paths (relative to src/ directory - part of codebase)
SUNRISE_ICON_PATH = "assets/icons/sunrise.svg"
SUNSET_ICON_PATH = "assets/icons/sunset.svg"
COMPASS_ICON_PATH = "assets/icons/compass.svg"


def load_icon(icon_path: str, size: int, is_codebase_icon: bool = False) -> Image.Image | None:
    """Load icon from local file path.

    Supports both PNG (with transparency) and SVG formats.

    Args:
        icon_path: Path to PNG or SVG file. Supports absolute paths, ~ expansion, and relative paths.
        size: Icon size in pixels
        is_codebase_icon: If True, path is relative to src/ directory (hardcoded icons).
                         If False, path can be absolute, use ~ expansion, or be relative to project root.
    """
    try:
        # Expand ~ to home directory if present
        icon_file = Path(icon_path).expanduser()

        if icon_file.is_absolute():
            # Absolute path (or expanded from ~) - use as-is
            pass
        else:
            # Relative path - resolve relative to package or project root
            current_file = Path(__file__)
            if is_codebase_icon:
                # Codebase icons are in aero_pi_cam/assets/icons/ (package directory)
                package_dir = current_file.parent
                icon_file = package_dir / icon_path
            else:
                # User-configured logos: try package directory first, then project root
                package_dir = current_file.parent
                icon_file = package_dir / icon_path
                if not icon_file.exists():
                    # Fallback to project root (for development)
                    project_root = current_file.parent.parent
                    icon_file = project_root / icon_path

        # Check file extension to determine format
        file_ext = icon_file.suffix.lower()

        if file_ext == ".png":
            # Load PNG directly with PIL, preserving transparency
            icon_img = Image.open(icon_file)
            # Ensure RGBA mode to preserve transparency
            if icon_img.mode != "RGBA":
                icon_img = icon_img.convert("RGBA")
            # Resize while preserving aspect ratio (logo_size is max dimension)
            icon_img.thumbnail((size, size), Image.Resampling.LANCZOS)
            return icon_img
        elif file_ext == ".svg":
            # Convert SVG to PNG using cairosvg
            with open(icon_file, encoding="utf-8") as f:
                svg_content = f.read()
            png_bytes = cairosvg.svg2png(
                bytestring=svg_content.encode("utf-8"), output_width=size, output_height=size
            )
            icon_img = Image.open(BytesIO(png_bytes))
            return icon_img.convert("RGBA")
        else:
            # Unknown format, return None
            return None
    except Exception:
        return None


def load_font(
    size: int, font_path: str | None = None, is_codebase_font: bool = False
) -> ImageFont.ImageFont:
    """Load font with fallback to system fonts.

    PIL's ImageFont.truetype() uses font size in points (1/72 inch).
    To ensure consistent pixel rendering across platforms (macOS vs Raspberry Pi),
    we normalize the font size to account for DPI differences.
    Standard DPI is 72, but some systems may use 96 DPI or other values.
    We scale the point size to achieve consistent pixel rendering.

    Args:
        size: Font size in pixels
        font_path: Optional path to custom font file (supports ~ expansion). If None, uses system font.
    """
    # Normalize font size for consistent rendering across platforms
    # PIL uses points (1/72 inch), but actual pixel size depends on DPI
    # On Linux/Raspberry Pi, fonts may render smaller due to different DPI handling
    # Scale up font size on Linux to match macOS rendering
    system = platform.system()
    if system == "Linux":
        # Scale up font size on Linux to compensate for DPI differences
        # Typical ratio: 96 DPI (Linux) vs 72 DPI (macOS) = 1.33x
        normalized_size = int(size * 96 / 72)
    else:
        normalized_size = size

    if _is_debug_mode():
        print(
            f"Font loading: requested size={size}, normalized size={normalized_size}, system={system}"
        )

    # If custom font path is configured, try to load it first
    if font_path:
        # Expand ~ to home directory
        expanded_path = Path(font_path).expanduser()
        if _is_debug_mode():
            print(
                f"Font loading: checking configured font path {expanded_path} (exists: {expanded_path.exists()})"
            )
        if expanded_path.exists():
            try:
                font = ImageFont.truetype(str(expanded_path), normalized_size)  # type: ignore[return-value]
                if _is_debug_mode():
                    print(f"Font loading: successfully loaded font from {expanded_path}")
                return font  # type: ignore[return-value]
            except Exception as e:
                if _is_debug_mode():
                    print(f"WARNING: Failed to load font from {expanded_path}: {e}")
        else:
            if _is_debug_mode():
                print(f"WARNING: Configured font path does not exist: {expanded_path}")

    # Fallback to system fonts that respect size parameter
    # Try common system fonts available on Linux/macOS
    if _is_debug_mode():
        print("Font loading: custom font not configured or not found, trying system fonts...")
    system_fonts = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",  # DejaVu Sans (common on Linux)
        "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",  # Liberation Sans (common on Linux)
        "/System/Library/Fonts/Helvetica.ttc",  # macOS
        "/Library/Fonts/Arial.ttf",  # macOS
    ]

    for font_file in system_fonts:
        if Path(font_file).exists():
            if _is_debug_mode():
                print(f"Font loading: trying system font {font_file}")
            try:
                font = ImageFont.truetype(font_file, normalized_size)  # type: ignore[return-value]
                if _is_debug_mode():
                    print(
                        f"Font loading: successfully loaded {font_file} at size {normalized_size}"
                    )
                return font  # type: ignore[return-value]
            except Exception as e:
                if _is_debug_mode():
                    print(f"WARNING: Failed to load system font {font_file}: {e}")
                continue

    # Last resort: try to find any TTF font in common system font directories
    if system == "Linux":
        common_font_dirs = [
            "/usr/share/fonts/truetype",
            "/usr/share/fonts/TTF",
        ]
        for font_dir in common_font_dirs:
            font_dir_path = Path(font_dir)
            if font_dir_path.exists():
                # Try to find any sans-serif font
                for found_font_path in font_dir_path.rglob("*.ttf"):
                    try:
                        return ImageFont.truetype(str(found_font_path), normalized_size)  # type: ignore[return-value]
                    except Exception:
                        continue

    # Final fallback: default font (doesn't respect size, but better than crashing)
    if _is_debug_mode():
        print(
            "WARNING: Could not load any TrueType font, using default font (size may be incorrect)"
        )
    return ImageFont.load_default()


def parse_color(color_str: str) -> tuple[int, int, int]:
    """Parse color string to RGB tuple."""
    color_map = {
        "white": (255, 255, 255),
        "black": (0, 0, 0),
        "red": (255, 0, 0),
        "green": (0, 255, 0),
        "blue": (0, 0, 255),
    }
    return color_map.get(color_str.lower(), (255, 255, 255))


def draw_text_with_shadow(
    draw: ImageDraw.ImageDraw,
    position: tuple[int, int],
    text: str,
    fill: tuple[int, int, int],
    font: ImageFont.ImageFont,
    shadow_enabled: bool,
    shadow_offset_x: int,
    shadow_offset_y: int,
    shadow_color: tuple[int, int, int],
) -> None:
    """Draw text with optional drop shadow.

    Args:
        draw: ImageDraw instance
        position: (x, y) position for text
        text: Text to draw
        fill: Text color (RGB tuple)
        font: Font to use
        shadow_enabled: Whether to draw shadow
        shadow_offset_x: Horizontal shadow offset
        shadow_offset_y: Vertical shadow offset
        shadow_color: Shadow color (RGB tuple)
    """
    if shadow_enabled:
        # Draw shadow first (offset position)
        shadow_pos = (position[0] + shadow_offset_x, position[1] + shadow_offset_y)
        draw.text(shadow_pos, text, fill=shadow_color, font=font)

    # Draw text on top
    draw.text(position, text, fill=fill, font=font)


def paste_image_with_shadow(
    img: Image.Image,
    icon: Image.Image,
    position: tuple[int, int],
    shadow_enabled: bool,
    shadow_offset_x: int,
    shadow_offset_y: int,
    shadow_color: tuple[int, int, int],
) -> None:
    """Paste an image with optional drop shadow.

    Args:
        img: Target image to paste onto
        icon: Image to paste (should have alpha channel)
        position: (x, y) position for image
        shadow_enabled: Whether to draw shadow
        shadow_offset_x: Horizontal shadow offset
        shadow_offset_y: Vertical shadow offset
        shadow_color: Shadow color (RGB tuple)
    """
    if shadow_enabled and icon.mode == "RGBA":
        # Create shadow version: convert icon to shadow color while preserving alpha
        shadow_icon = icon.copy()
        shadow_pixels = shadow_icon.load()
        shadow_r, shadow_g, shadow_b = shadow_color

        # Replace RGB channels with shadow color, keep alpha
        for y in range(shadow_icon.height):
            for x in range(shadow_icon.width):
                r, g, b, a = shadow_pixels[x, y]
                if a > 0:  # Only modify non-transparent pixels
                    shadow_pixels[x, y] = (shadow_r, shadow_g, shadow_b, a)

        # Paste shadow first at offset position
        shadow_pos = (position[0] + shadow_offset_x, position[1] + shadow_offset_y)
        img.paste(shadow_icon, shadow_pos, shadow_icon)

    # Paste original image on top
    img.paste(icon, position, icon)


def draw_overlay_on_image(
    img: Image.Image,
    config: Config,
    capture_time: datetime,
    sunrise_time: datetime,
    sunset_time: datetime,
    raw_metar: str | None = None,
    raw_taf: str | None = None,
    include_metar_overlay: bool = True,
    include_sun_info: bool = True,
) -> None:
    """Draw overlay elements on a PIL Image.

    This is the shared overlay drawing logic used by both debug and production modes.
    The image should be in RGBA mode to support transparency.

    Args:
        img: PIL Image to draw on
        config: Configuration object
        capture_time: Capture timestamp in UTC
        sunrise_time: Sunrise time in UTC
        sunset_time: Sunset time in UTC
        raw_metar: Optional raw METAR text
        raw_taf: Optional raw TAF text
        include_metar_overlay: If False, skip drawing METAR/TAF text overlay (metadata still embedded)
        include_sun_info: If False, skip drawing sunrise/sunset times and camera heading overlay
    """
    draw = ImageDraw.Draw(img)
    img_width, img_height = img.size

    # Load font using configured size and path
    font_size = config.overlay.font_size
    font = load_font(font_size, config.overlay.font_path)
    font_small = load_font(
        max(8, font_size - 2), config.overlay.font_path
    )  # Smaller font for METAR

    # Parse text color and shadow settings
    text_color = parse_color(config.overlay.font_color)
    shadow_color = parse_color(config.overlay.shadow_color)

    # Padding and spacing
    padding = config.overlay.padding
    line_spacing = config.overlay.line_spacing
    icon_spacing = 6

    # Load logo (gracefully handle missing logo)
    logo_size = config.overlay.logo_size
    logo = None
    try:
        logo = load_icon(config.overlay.provider_logo, logo_size, is_codebase_icon=False)
    except Exception:
        pass

    # Calculate positions
    y_pos = padding

    # Top-left: Provider name only (no location name, no logo)
    provider_text = config.overlay.provider_name
    temp_draw = ImageDraw.Draw(Image.new("RGBA", (1, 1)))
    provider_bbox = temp_draw.textbbox((0, 0), provider_text, font=font)

    # Camera name + UTC date/time on top-right, right aligned
    capture_str = capture_time.strftime("%Y-%m-%dT%H:%M:%SZ")
    camera_text = f"{config.overlay.camera_name} - {capture_str}"
    camera_bbox = temp_draw.textbbox((0, 0), camera_text, font=font)

    # Calculate common baseline Y position for vertical alignment
    # Use the maximum (most negative) top value to ensure both texts align
    common_top = min(provider_bbox[1], camera_bbox[1])
    common_y = padding - common_top

    # Draw provider name (left aligned)
    provider_x = padding
    draw_text_with_shadow(
        draw,
        (provider_x, common_y),
        provider_text,
        text_color,
        font,
        config.overlay.shadow_enabled,
        config.overlay.shadow_offset_x,
        config.overlay.shadow_offset_y,
        shadow_color,
    )

    # Draw camera name + date/time (right aligned)
    camera_text_width = camera_bbox[2] - camera_bbox[0]
    camera_text_height = camera_bbox[3] - camera_bbox[1]
    camera_x = img_width - padding - camera_text_width
    draw_text_with_shadow(
        draw,
        (camera_x, common_y),
        camera_text,
        text_color,
        font,
        config.overlay.shadow_enabled,
        config.overlay.shadow_offset_x,
        config.overlay.shadow_offset_y,
        shadow_color,
    )

    # Sunrise and sunset times with icons (below camera name, right aligned)
    # Only draw if include_sun_info is True
    if include_sun_info:
        # Use maximum height of both texts for consistent spacing
        provider_text_height = provider_bbox[3] - provider_bbox[1]
        max_text_height = max(provider_text_height, camera_text_height)
        y_pos = padding + max_text_height + line_spacing
        sunrise_str = sunrise_time.strftime("%H:%MZ")
        sunset_str = sunset_time.strftime("%H:%MZ")

        # Load sunrise and sunset icons
        sun_icon_size = config.overlay.sun_icon_size
        sunrise_icon = load_icon(SUNRISE_ICON_PATH, sun_icon_size, is_codebase_icon=True)
        sunset_icon = load_icon(SUNSET_ICON_PATH, sun_icon_size, is_codebase_icon=True)

        # Calculate total width for sunrise + sunset to right-align them
        sunrise_bbox = temp_draw.textbbox((0, 0), sunrise_str, font=font)
        sunset_bbox = temp_draw.textbbox((0, 0), sunset_str, font=font)
        sunrise_text_width = sunrise_bbox[2] - sunrise_bbox[0]
        sunset_text_width = sunset_bbox[2] - sunset_bbox[0]

        # Start from right edge
        sunset_text_x = img_width - padding - sunset_text_width
        sunset_icon_x = sunset_text_x - icon_spacing - sun_icon_size
        sunrise_text_x = sunset_icon_x - 16 - sunrise_text_width
        sunrise_icon_x = sunrise_text_x - icon_spacing - sun_icon_size

        # Paste icons and draw text
        sunrise_y = y_pos
        if sunrise_icon:
            paste_image_with_shadow(
                img,
                sunrise_icon,
                (sunrise_icon_x, sunrise_y),
                config.overlay.shadow_enabled,
                config.overlay.shadow_offset_x,
                config.overlay.shadow_offset_y,
                shadow_color,
            )

        sunrise_text_height = sunrise_bbox[3] - sunrise_bbox[1]
        sunrise_text_y = sunrise_y + (sun_icon_size - sunrise_text_height) // 2 - sunrise_bbox[1]
        draw_text_with_shadow(
            draw,
            (sunrise_text_x, sunrise_text_y),
            sunrise_str,
            text_color,
            font,
            config.overlay.shadow_enabled,
            config.overlay.shadow_offset_x,
            config.overlay.shadow_offset_y,
            shadow_color,
        )

        if sunset_icon:
            paste_image_with_shadow(
                img,
                sunset_icon,
                (sunset_icon_x, sunrise_y),
                config.overlay.shadow_enabled,
                config.overlay.shadow_offset_x,
                config.overlay.shadow_offset_y,
                shadow_color,
            )

        sunset_text_height = sunset_bbox[3] - sunset_bbox[1]
        sunset_text_y = sunrise_y + (sun_icon_size - sunset_text_height) // 2 - sunset_bbox[1]
        draw_text_with_shadow(
            draw,
            (sunset_text_x, sunset_text_y),
            sunset_str,
            text_color,
            font,
            config.overlay.shadow_enabled,
            config.overlay.shadow_offset_x,
            config.overlay.shadow_offset_y,
            shadow_color,
        )

        # Camera heading with compass icon (below sun info, right aligned)
        y_pos = (
            sunrise_y + max(sun_icon_size, sunrise_text_height, sunset_text_height) + line_spacing
        )
        heading_text = config.location.camera_heading

        # Load compass icon
        compass_icon = load_icon(COMPASS_ICON_PATH, sun_icon_size, is_codebase_icon=True)

        # Calculate width for camera heading to right-align it
        heading_bbox = temp_draw.textbbox((0, 0), heading_text, font=font)
        heading_text_width = heading_bbox[2] - heading_bbox[0]

        # Start from right edge
        heading_text_x = img_width - padding - heading_text_width
        heading_icon_x = heading_text_x - icon_spacing - sun_icon_size

        # Paste compass icon and draw text
        heading_y = y_pos
        if compass_icon:
            paste_image_with_shadow(
                img,
                compass_icon,
                (heading_icon_x, heading_y),
                config.overlay.shadow_enabled,
                config.overlay.shadow_offset_x,
                config.overlay.shadow_offset_y,
                shadow_color,
            )

        heading_text_height = heading_bbox[3] - heading_bbox[1]
        heading_text_y = heading_y + (sun_icon_size - heading_text_height) // 2 - heading_bbox[1]
        draw_text_with_shadow(
            draw,
            (heading_text_x, heading_text_y),
            heading_text,
            text_color,
            font,
            config.overlay.shadow_enabled,
            config.overlay.shadow_offset_x,
            config.overlay.shadow_offset_y,
            shadow_color,
        )

    # Raw METAR and TAF at bottom-left (if enabled and available and include_metar_overlay is True)
    all_text_lines = []

    if include_metar_overlay and config.metar.raw_metar_enabled and raw_metar:
        all_text_lines.append(raw_metar)

    if include_metar_overlay and config.metar.raw_metar_enabled and raw_taf:
        # TAF can have multiple lines - preserve them (keep leading spaces)
        taf_lines = raw_taf.split("\n")
        for i, taf_line in enumerate(taf_lines):
            # Only strip trailing whitespace to preserve leading spaces
            taf_line = taf_line.rstrip()
            if taf_line:
                all_text_lines.append(taf_line)

    if all_text_lines:
        # Calculate text dimensions for wrapping
        max_width = img_width - padding * 2
        wrapped_lines = []

        for text_line in all_text_lines:
            # Extract leading spaces to preserve indentation
            leading_spaces = len(text_line) - len(text_line.lstrip())
            indent = text_line[:leading_spaces] if leading_spaces > 0 else ""

            words = text_line.split()
            current_line = indent  # Start with leading spaces

            for word in words:
                # Only add space if current_line has content beyond just the indent
                if current_line.strip():
                    test_line = f"{current_line} {word}".rstrip()
                else:
                    # current_line is just indent, don't add extra space
                    test_line = current_line + word
                test_bbox = temp_draw.textbbox((0, 0), test_line, font=font_small)
                test_width = test_bbox[2] - test_bbox[0]

                if test_width <= max_width:
                    current_line = test_line
                else:
                    if current_line.strip():  # Only add non-empty lines
                        wrapped_lines.append(current_line)
                    current_line = indent + word  # Start new line with indent

            if current_line.strip():  # Only add non-empty lines
                wrapped_lines.append(current_line)

        # Draw lines from bottom
        # Calculate total height: sum of all line heights plus line_spacing gaps between them
        line_heights = []
        for line in wrapped_lines:
            line_bbox = temp_draw.textbbox((0, 0), line, font=font_small)
            line_heights.append(line_bbox[3] - line_bbox[1])
        total_height = sum(line_heights) + (len(wrapped_lines) - 1) * line_spacing
        y_pos = img.height - total_height - padding

        current_y = y_pos
        for i, line in enumerate(wrapped_lines):
            # Calculate width of leading spaces to preserve indentation
            leading_spaces = len(line) - len(line.lstrip())
            leading_space_width = 0
            if leading_spaces > 0:
                leading_space_text = line[:leading_spaces]
                leading_space_width = int(temp_draw.textlength(leading_space_text, font=font_small))

            # Draw line without leading spaces at offset position to preserve indentation
            line_without_spaces = line.lstrip()
            line_bbox = temp_draw.textbbox((0, 0), line_without_spaces, font=font_small)
            draw_text_with_shadow(
                draw,
                (padding + leading_space_width, current_y - line_bbox[1]),
                line_without_spaces,
                text_color,
                font_small,
                config.overlay.shadow_enabled,
                config.overlay.shadow_offset_x,
                config.overlay.shadow_offset_y,
                shadow_color,
            )
            current_y += line_heights[i] + line_spacing

    # Bottom-right: Logo
    if logo:
        try:
            # Use actual logo dimensions (may not be square)
            logo_width, logo_height = logo.size
            logo_x = img_width - padding - logo_width
            logo_y = img_height - padding - logo_height
            paste_image_with_shadow(
                img,
                logo,
                (logo_x, logo_y),
                config.overlay.shadow_enabled,
                config.overlay.shadow_offset_x,
                config.overlay.shadow_offset_y,
                shadow_color,
            )
        except Exception:
            pass


def add_comprehensive_overlay(
    image_bytes: bytes,
    config: Config,
    capture_time: datetime,
    sunrise_time: datetime,
    sunset_time: datetime,
    raw_metar: str | None = None,
    raw_taf: str | None = None,
    include_metar_overlay: bool = True,
    include_sun_info: bool = True,
) -> bytes:
    """Add comprehensive overlay by compositing overlay image on top of camera image.

    Uses the same overlay generation logic as debug mode, but composites it on the camera image.

    Args:
        image_bytes: Original image bytes
        config: Configuration object
        capture_time: Capture timestamp in UTC
        sunrise_time: Sunrise time in UTC
        sunset_time: Sunset time in UTC
        raw_metar: Optional raw METAR text
        raw_taf: Optional raw TAF text
        include_metar_overlay: If False, skip drawing METAR/TAF text overlay (metadata still embedded)
        include_sun_info: If False, skip drawing sunrise/sunset times and camera heading overlay

    Returns:
        JPEG bytes with overlay and metadata embedded
    """
    try:
        # Load camera image
        camera_img = Image.open(BytesIO(image_bytes)).convert("RGBA")
        img_width, img_height = camera_img.size
    except Exception as e:
        if _is_debug_mode():
            print(f"ERROR: Failed to open image for overlay: {e}")
        return image_bytes

    # Log actual image dimensions for debugging
    if _is_debug_mode():
        print(f"Overlay: Image size is {img_width}x{img_height}")

    # Generate overlay on transparent image using shared function
    overlay_img = Image.new("RGBA", (img_width, img_height), (0, 0, 0, 0))
    draw_overlay_on_image(
        overlay_img,
        config,
        capture_time,
        sunrise_time,
        sunset_time,
        raw_metar=raw_metar,
        raw_taf=raw_taf,
        include_metar_overlay=include_metar_overlay,
        include_sun_info=include_sun_info,
    )

    # Check if overlay has any non-transparent pixels (for debugging)
    overlay_has_content = any(
        overlay_img.getpixel((x, y))[3] > 0
        for x in range(0, min(100, img_width), 10)
        for y in range(0, min(100, img_height), 10)
    )
    if _is_debug_mode():
        print(
            f"Overlay: Has content: {overlay_has_content}, Size: {overlay_img.size}, Mode: {overlay_img.mode}"
        )
        print(f"Camera: Size: {camera_img.size}, Mode: {camera_img.mode}")

    # Composite overlay on top of camera image using alpha compositing
    # Both images must be RGBA and same size
    result_img = Image.alpha_composite(camera_img, overlay_img)

    # Convert back to RGB and save as JPEG
    result_rgb = result_img.convert("RGB")
    output = BytesIO()
    result_rgb.save(output, format="JPEG", quality=90)
    jpeg_bytes = output.getvalue()

    # Embed EXIF and XMP metadata
    try:
        from .exif import build_exif_dict, build_xmp_xml, embed_exif_in_jpeg

        exif_dict = build_exif_dict(
            config,
            sunrise_time,
            sunset_time,
            raw_metar=raw_metar,
            raw_taf=raw_taf,
        )
        xmp_xml = build_xmp_xml(
            config,
            sunrise_time,
            sunset_time,
            raw_metar=raw_metar,
            raw_taf=raw_taf,
        )
        jpeg_bytes = embed_exif_in_jpeg(jpeg_bytes, exif_dict, xmp_xml=xmp_xml)
    except Exception as e:
        # Log warning but continue without EXIF/XMP metadata
        if _is_debug_mode():
            print(f"WARNING: Failed to embed EXIF/XMP metadata: {e}")

    return jpeg_bytes
