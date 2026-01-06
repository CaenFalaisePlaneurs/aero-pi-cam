"""External dependency checking."""

import shutil
import sys


def check_external_dependencies() -> None:
    """Check for required external dependencies and exit if missing."""
    missing_deps: list[str] = []

    # Check for ffmpeg (required for RTSP capture)
    if not shutil.which("ffmpeg"):
        missing_deps.append("ffmpeg")

    # Check for cairo library (required for cairosvg/SVG icon support)
    # This is a system library, so we check if cairosvg can import properly
    try:
        import cairosvg  # noqa: F401
    except OSError as e:
        error_msg = str(e).lower()
        if "cairo" in error_msg or "libcairo" in error_msg or "no library called" in error_msg:
            missing_deps.append("cairo (system library)")
    except ImportError:
        # cairosvg not installed, but that's a Python dependency issue
        pass

    if missing_deps:
        print("ERROR: Required external dependencies are missing:")
        for dep in missing_deps:
            print(f"  - {dep}")
        print("\nInstallation instructions:")
        if "ffmpeg" in missing_deps:
            print("  macOS: brew install ffmpeg")
            print("  Linux/Debian: sudo apt install ffmpeg")
            print("  Raspberry Pi: sudo apt install ffmpeg")
        if "cairo (system library)" in missing_deps:
            print("  macOS: brew install cairo")
            print("  Linux/Debian: sudo apt install libcairo2-dev")
            print("  Raspberry Pi: sudo apt install libcairo2-dev")
        sys.exit(1)
