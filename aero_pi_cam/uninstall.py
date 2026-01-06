"""Uninstall helper script for aero-pi-cam."""

import subprocess
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


def find_pip_command() -> str:
    """Find the correct pip command to use for uninstall.

    Returns:
        The pip command path (venv pip if in venv, or 'pip' for system-wide)
    """
    try:
        # Check if we're running from a venv
        import aero_pi_cam

        package_path = Path(aero_pi_cam.__file__).parent

        # Check if package is in a venv (venv typically has 'site-packages' in path)
        if "site-packages" in str(package_path) or "dist-packages" in str(package_path):
            # Extract venv root from package path
            path_parts = package_path.parts
            for i, part in enumerate(path_parts):
                if part in ("site-packages", "dist-packages"):
                    # Go up to find venv root (typically 3 levels up)
                    if i >= 2:
                        venv_root = Path(*path_parts[: i - 2])
                        venv_pip = venv_root / "bin" / "pip"
                        if venv_pip.exists():
                            return str(venv_pip)
                    break

        # Check if we're in a venv via environment variable
        venv_python = Path.cwd() / "venv" / "bin" / "pip"
        if venv_python.exists():
            return str(venv_python)

    except ImportError:
        pass

    # Default to system pip
    return "pip"


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

    # Find the correct pip command
    pip_cmd = find_pip_command()

    if pip_cmd != "pip":
        print(f"\nNow run: {pip_cmd} uninstall aero-pi-cam")
        print("The systemd service file will be removed automatically.")
    else:
        print("\nNow run: pip uninstall aero-pi-cam")
        print("(Or use: sudo pip uninstall aero-pi-cam if installed system-wide)")
        print("The systemd service file will be removed automatically.")


if __name__ == "__main__":
    main()
