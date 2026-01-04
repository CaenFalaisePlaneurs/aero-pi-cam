"""Setup script for aero-pi-cam package with data_files for systemd service."""

from pathlib import Path

from setuptools import setup


def get_service_file_path() -> Path:
    """Get the path to the systemd service file."""
    return Path(__file__).parent / "aero-pi-cam.service"


# This setup.py is used only for data_files (systemd service)
# Package metadata comes from pyproject.toml
# Note: pip uninstall will automatically remove files listed in data_files
# We cannot hook into pip uninstall to stop/disable the service automatically,
# but the service file will be removed, and config will be preserved (not in data_files)

# Read package files for data_files
# Note: Path must be relative to setup.py directory
service_file = get_service_file_path()
config_example = Path(__file__).parent / "config.example.yaml"
data_files = []
if service_file.exists():
    # Use relative path from setup.py directory
    service_file_rel = service_file.relative_to(Path(__file__).parent)
    data_files = [("etc/systemd/system", [str(service_file_rel)])]
# Install config.example.yaml to /usr/share/aero-pi-cam/ for access during setup
if config_example.exists():
    config_example_rel = config_example.relative_to(Path(__file__).parent)
    data_files.append(("usr/share/aero-pi-cam", [str(config_example_rel)]))

# Minimal setup() call - metadata comes from pyproject.toml
setup(
    name="aero-pi-cam",  # Must match pyproject.toml
    data_files=data_files,
)
