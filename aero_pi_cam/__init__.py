"""Webcam Capture Service for Aeronautical Webcams."""

__version__ = "1.1.1"

# Backward compatibility re-exports
from .capture.capture import capture_frame
from .core.config import Config, load_config
from .core.debug import _is_debug_mode, debug_print
from .core.dependencies import check_external_dependencies
from .core.main import main
from .core.scheduler import schedule_next_capture
from .core.workflow import capture_and_upload
from .overlay.exif import embed_exif_in_jpeg
from .overlay.overlay import add_comprehensive_overlay
from .upload.api import ApiUploader
from .upload.sftp import SftpUploader
from .upload.upload import UploadResult, create_uploader, upload_image
from .weather.day_night import get_day_night_mode
from .weather.metar import fetch_metar, get_raw_metar, get_raw_taf
from .weather.sun import get_sun_times, is_day

__all__ = [
    "__version__",
    "Config",
    "load_config",
    "main",
    "schedule_next_capture",
    "capture_and_upload",
    "debug_print",
    "_is_debug_mode",
    "check_external_dependencies",
    "capture_frame",
    "upload_image",
    "UploadResult",
    "create_uploader",
    "ApiUploader",
    "SftpUploader",
    "add_comprehensive_overlay",
    "embed_exif_in_jpeg",
    "fetch_metar",
    "get_raw_metar",
    "get_raw_taf",
    "get_sun_times",
    "is_day",
    "get_day_night_mode",
]
