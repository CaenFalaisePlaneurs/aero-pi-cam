"""Image overlay and metadata."""

from .exif import embed_exif_in_jpeg
from .overlay import (
    add_comprehensive_overlay,
    draw_overlay_on_image,
    draw_text_with_shadow,
    load_font,
    load_icon,
    parse_color,
    paste_image_with_shadow,
)

__all__ = [
    "add_comprehensive_overlay",
    "draw_overlay_on_image",
    "draw_text_with_shadow",
    "embed_exif_in_jpeg",
    "load_font",
    "load_icon",
    "parse_color",
    "paste_image_with_shadow",
]
