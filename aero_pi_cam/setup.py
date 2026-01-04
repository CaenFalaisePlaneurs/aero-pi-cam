"""Setup module for aero-pi-cam system configuration."""

import os
import shutil
import subprocess
import sys
from pathlib import Path


def check_system_dependencies() -> tuple[bool, list[str]]:
    """Check if system dependencies are installed.

    Returns:
        Tuple of (all_installed, missing_deps)
    """
    missing: list[str] = []
    deps = {
        "ffmpeg": "ffmpeg",
        "cairo": "libcairo2-dev",
    }

    # Check ffmpeg
    if not shutil.which("ffmpeg"):
        missing.append(deps["ffmpeg"])

    # Check cairo (try importing cairosvg to see if cairo library is available)
    try:
        import cairosvg  # noqa: F401
    except OSError as e:
        error_msg = str(e).lower()
        if "cairo" in error_msg or "libcairo" in error_msg or "no library called" in error_msg:
            missing.append(deps["cairo"])
    except ImportError:
        # cairosvg not installed, but that's a Python dependency issue
        pass

    return len(missing) == 0, missing


def install_system_dependencies(missing: list[str]) -> bool:
    """Install missing system dependencies.

    Args:
        missing: List of missing package names

    Returns:
        True if installation succeeded, False otherwise
    """
    if not missing:
        return True

    print(f"Installing system dependencies: {', '.join(missing)}")
    print("This requires sudo privileges...")

    try:
        # Check if running with sudo
        if os.geteuid() != 0:
            print("Error: This command requires sudo privileges.")
            print("Please run: sudo aero-pi-cam-setup")
            return False

        # Update package list
        subprocess.run(["apt-get", "update", "-qq"], check=True)

        # Install packages
        subprocess.run(
            ["apt-get", "install", "-y", "-qq"] + missing,
            check=True,
        )
        print(f"✓ Installed: {', '.join(missing)}")
        return True
    except subprocess.CalledProcessError as e:
        print(f"Error installing system dependencies: {e}")
        return False
    except FileNotFoundError:
        print("Error: apt-get not found. This script is designed for Debian/Ubuntu systems.")
        return False


def find_webcam_executable() -> str:
    """Find the webcam executable path.

    Checks if installed in a virtual environment or system-wide by finding
    where the aero_pi_cam package is installed.

    Returns:
        Path to webcam executable
    """
    import shutil

    try:
        # Try to import the package and find its location
        import aero_pi_cam

        package_path = Path(aero_pi_cam.__file__).parent
        # Check if package is in a venv (venv typically has 'site-packages' in path)
        if "site-packages" in str(package_path) or "dist-packages" in str(package_path):
            # Extract venv root from package path
            # e.g., /opt/aero-pi-cam-venv/lib/python3.13/site-packages/aero_pi_cam
            path_parts = package_path.parts
            for i, part in enumerate(path_parts):
                if part in ("site-packages", "dist-packages"):
                    # Go up to find venv root (typically 3 levels up: site-packages -> lib -> python3.x -> venv)
                    if i >= 2:
                        venv_root = Path(*path_parts[: i - 2])
                        venv_webcam = venv_root / "bin" / "webcam"
                        if venv_webcam.exists():
                            return str(venv_webcam)
                    break
    except ImportError:
        pass

    # Check if we're running from a venv (environment variable)
    venv_python = os.environ.get("VIRTUAL_ENV")
    if venv_python:
        venv_bin = Path(venv_python) / "bin" / "webcam"
        if venv_bin.exists():
            return str(venv_bin)

    # Check common venv locations
    common_venv_paths = [
        "/opt/aero-pi-cam-venv/bin/webcam",
        "/opt/webcam-cfp/venv/bin/webcam",
        "/usr/local/aero-pi-cam-venv/bin/webcam",
    ]
    for venv_path in common_venv_paths:
        if Path(venv_path).exists():
            return venv_path

    # Check if webcam is in system PATH
    webcam_path = shutil.which("webcam")
    if webcam_path:
        return webcam_path

    # Default to system installation
    return "/usr/bin/webcam"


def create_systemd_service() -> bool:
    """Create systemd service file.

    Returns:
        True if service file was created/updated, False otherwise
    """
    service_name = "aero-pi-cam"
    service_file_source = Path(__file__).parent.parent / "aero-pi-cam.service"
    service_file_dest = Path(f"/etc/systemd/system/{service_name}.service")

    if not service_file_source.exists():
        print(f"Error: Service file not found at {service_file_source}")
        return False

    try:
        # Check if running with sudo
        if os.geteuid() != 0:
            print("Error: This command requires sudo privileges.")
            print("Please run: sudo aero-pi-cam-setup")
            return False

        # Find webcam executable (detects venv or system installation)
        webcam_executable = find_webcam_executable()
        print(f"Detected webcam executable: {webcam_executable}")

        # Read and update service file
        service_content = service_file_source.read_text()

        # Replace the ExecStart line to use the webcam command
        # Find the ExecStart line and replace it
        lines = service_content.split("\n")
        updated_lines = []
        exec_start_found = False

        for line in lines:
            if line.strip().startswith("ExecStart="):
                # Use the detected webcam executable path
                updated_lines.append(f"ExecStart={webcam_executable}")
                exec_start_found = True
            elif line.strip().startswith("WorkingDirectory="):
                # Remove or comment out WorkingDirectory for pip-installed package
                # updated_lines.append("# WorkingDirectory removed for pip-installed package")
                pass
            elif line.strip().startswith("Environment=") and "PATH=" in line:
                # Remove PATH override for pip-installed package
                # updated_lines.append("# PATH override removed for pip-installed package")
                pass
            else:
                updated_lines.append(line)

        if not exec_start_found:
            # Add ExecStart if not found
            updated_lines.insert(
                len([line for line in updated_lines if line.strip().startswith("[Service]")]) + 1,
                f"ExecStart={webcam_executable}",
            )

        # Write updated service file
        service_file_dest.parent.mkdir(parents=True, exist_ok=True)
        service_file_dest.write_text("\n".join(updated_lines))
        print(f"✓ Created systemd service file: {service_file_dest}")

        # Reload systemd
        subprocess.run(["systemctl", "daemon-reload"], check=True)
        print("✓ Reloaded systemd daemon")

        return True
    except PermissionError:
        print("Error: Permission denied. This command requires sudo privileges.")
        print("Please run: sudo aero-pi-cam-setup")
        return False
    except Exception as e:
        print(f"Error creating systemd service: {e}")
        return False


def create_config_template() -> bool:
    """Create configuration file template if it doesn't exist.

    Returns:
        True if config was created or already exists, False on error
    """
    config_dir = Path("/etc/aero-pi-cam")
    config_file = config_dir / "config.yaml"
    example_config = Path(__file__).parent.parent / "config.example.yaml"

    if config_file.exists():
        print(f"✓ Configuration file already exists: {config_file}")
        return True

    if not example_config.exists():
        print(f"Warning: Example config not found at {example_config}")
        return False

    try:
        # Check if running with sudo
        if os.geteuid() != 0:
            print("Error: This command requires sudo privileges.")
            print("Please run: sudo aero-pi-cam-setup")
            return False

        # Create config directory
        config_dir.mkdir(parents=True, exist_ok=True)

        # Copy example config
        shutil.copy(example_config, config_file)
        print(f"✓ Created configuration template: {config_file}")
        print(f"⚠ Please edit {config_file} before starting the service")
        return True
    except PermissionError:
        print("Error: Permission denied. This command requires sudo privileges.")
        print("Please run: sudo aero-pi-cam-setup")
        return False
    except Exception as e:
        print(f"Error creating config file: {e}")
        return False


def enable_and_start_service() -> bool:
    """Enable and optionally start the systemd service.

    Returns:
        True if service was enabled, False otherwise
    """
    service_name = "aero-pi-cam"

    try:
        # Check if running with sudo
        if os.geteuid() != 0:
            print("Error: This command requires sudo privileges.")
            print("Please run: sudo aero-pi-cam-setup")
            return False

        # Enable service
        subprocess.run(["systemctl", "enable", service_name], check=True)
        print(f"✓ Enabled {service_name} service (will start on boot)")

        # Ask if user wants to start it now
        config_file = Path("/etc/aero-pi-cam/config.yaml")
        if config_file.exists():
            # Check if config has been edited (not just example values)
            config_content = config_file.read_text()
            if "secret-api-key" in config_content or "api.example.com" in config_content:
                print("⚠ Configuration file still contains example values.")
                print(f"⚠ Please edit {config_file} before starting the service.")
                response = input("Start the service anyway? (y/N): ").strip().lower()
                if response != "y":
                    print(
                        "Service enabled but not started. Start it with: sudo systemctl start aero-pi-cam"
                    )
                    return True

        # Start service
        subprocess.run(["systemctl", "start", service_name], check=True)
        print(f"✓ Started {service_name} service")
        return True
    except subprocess.CalledProcessError as e:
        print(f"Error managing service: {e}")
        return False
    except PermissionError:
        print("Error: Permission denied. This command requires sudo privileges.")
        print("Please run: sudo aero-pi-cam-setup")
        return False


def main() -> None:
    """Main setup function."""
    print("╔════════════════════════════════════════╗")
    print("║  aero-pi-cam Setup                     ║")
    print("╚════════════════════════════════════════╝")
    print()

    # Check system dependencies
    print("[1/4] Checking system dependencies...")
    all_installed, missing = check_system_dependencies()
    if all_installed:
        print("✓ All system dependencies installed")
    else:
        if not install_system_dependencies(missing):
            print("Failed to install system dependencies")
            sys.exit(1)

    # Create systemd service
    print("\n[2/4] Setting up systemd service...")
    if not create_systemd_service():
        print("Failed to create systemd service")
        sys.exit(1)

    # Create config template
    print("\n[3/4] Setting up configuration...")
    if not create_config_template():
        print("Failed to create configuration template")
        sys.exit(1)

    # Enable and start service
    print("\n[4/4] Enabling service...")
    if not enable_and_start_service():
        print("Failed to enable service")
        sys.exit(1)

    print()
    print("╔════════════════════════════════════════╗")
    print("║  Setup Complete!                     ║")
    print("╚════════════════════════════════════════╝")
    print()
    print("Next steps:")
    print("1. Edit configuration: sudo nano /etc/aero-pi-cam/config.yaml")
    print("2. Check service status: sudo systemctl status aero-pi-cam")
    print("3. View logs: sudo journalctl -u aero-pi-cam -f")


if __name__ == "__main__":
    main()
