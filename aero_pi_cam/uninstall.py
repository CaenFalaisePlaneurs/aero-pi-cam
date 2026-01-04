"""Uninstall helper script for aero-pi-cam."""

import subprocess
import sys
from pathlib import Path


def stop_and_disable_service() -> None:
    """Stop and disable the systemd service."""
    service_name = "aero-pi-cam"
    try:
        # Check if service is active and stop it
        result = subprocess.run(
            ["systemctl", "is-active", "--quiet", service_name],
            capture_output=True,
            check=False,
        )
        if result.returncode == 0:
            subprocess.run(["systemctl", "stop", service_name], check=False)
            print(f"✓ Stopped {service_name} service")

        # Check if service is enabled and disable it
        result = subprocess.run(
            ["systemctl", "is-enabled", "--quiet", service_name],
            capture_output=True,
            check=False,
        )
        if result.returncode == 0:
            subprocess.run(["systemctl", "disable", service_name], check=False)
            print(f"✓ Disabled {service_name} service")
    except Exception as e:
        print(f"Warning: Could not stop/disable service: {e}")


def reload_systemd() -> None:
    """Reload systemd daemon."""
    try:
        subprocess.run(["systemctl", "daemon-reload"], check=False)
        subprocess.run(["systemctl", "reset-failed"], check=False)
    except Exception as e:
        print(f"Warning: Could not reload systemd: {e}")


def main() -> None:
    """Main uninstall helper function."""
    print("Preparing to uninstall aero-pi-cam...")
    print("Stopping and disabling systemd service...")

    # Stop and disable service before pip uninstall removes files
    stop_and_disable_service()

    # Note about config preservation
    config_path = Path("/etc/aero-pi-cam/config.yaml")
    if config_path.exists():
        print(f"\n✓ Configuration will be preserved at {config_path}")
        print("  (Following Debian FHS best practices)")
    else:
        print("\n✓ Ready for uninstall")

    print("\nNow run: pip uninstall aero-pi-cam")
    print("The systemd service file will be removed automatically.")


if __name__ == "__main__":
    main()

