"""Setup module for aero-pi-cam system configuration."""

import os
import pwd
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


def is_docker_environment() -> bool:
    """Check if running in Docker container.

    Returns:
        True if running in Docker, False otherwise
    """
    # Check for Docker-specific files
    if Path("/.dockerenv").exists():
        return True
    # Check if systemd is not available (Docker typically doesn't run systemd)
    try:
        result = subprocess.run(
            ["systemctl", "--version"],
            capture_output=True,
            timeout=1,
            check=False,
        )
        return result.returncode != 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return True
    return False


def get_current_user() -> str:
    """Get the current username.

    Returns:
        Username as string, defaults to 'pi' if cannot be determined
    """
    try:
        # Try to get from environment
        user = os.environ.get("USER") or os.environ.get("USERNAME")
        if user:
            return user
        # Try to get from system
        return pwd.getpwuid(os.getuid()).pw_name
    except (KeyError, AttributeError):
        # Default to 'pi' for Raspberry Pi compatibility
        return "pi"


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
    # Skip systemd service creation in Docker (systemd not available)
    if is_docker_environment():
        print("Skipping systemd service setup (Docker environment detected)")
        print("Note: In Docker, the application runs directly, not via systemd")
        return True

    service_name = "aero-pi-cam"
    service_file_dest = Path(f"/etc/systemd/system/{service_name}.service")

    # Get current user (or default to 'pi' for Raspberry Pi)
    service_user = get_current_user()

    # Try to find existing service file from various locations
    # Note: When installed via pip from git, the file is installed to /etc/systemd/system/
    # via data_files, but the source file may not be accessible. We can use the installed
    # file as a source if it exists.
    possible_locations = [
        # If running from source, check repository root
        Path(__file__).parent.parent / "aero-pi-cam.service",
        # If installed as package, check parent directories
        Path(__file__).parent.parent.parent / "aero-pi-cam.service",
        # Check if already installed at destination (use it as source if it exists)
        # This is important when installing via pip from git
        service_file_dest,
    ]

    service_file_source = None
    for location in possible_locations:
        if location.exists():
            service_file_source = location
            break

    if service_file_source is None:
        # Try to find it using the package location (when installed via pip from git)
        try:
            import aero_pi_cam

            package_path = Path(aero_pi_cam.__file__).parent
            # When installed via pip, the file might be in various parent directories
            search_paths = [
                package_path.parent,  # site-packages or dist-packages
                package_path.parent.parent,  # lib/python3.x
                package_path.parent.parent.parent,  # venv root or /usr
            ]
            # Also check if we can find it relative to the current working directory
            cwd = Path.cwd()
            if (cwd / "aero-pi-cam.service").exists():
                service_file_source = cwd / "aero-pi-cam.service"
            else:
                for parent in search_paths:
                    candidate = parent / "aero-pi-cam.service"
                    if candidate.exists():
                        service_file_source = candidate
                        break
        except ImportError:
            pass

    if service_file_source is None:
        # When installing from git via pip, the file is in the source distribution
        # but not accessible after installation. However, pip does install it to
        # /etc/systemd/system/ during installation. If this is a fresh install
        # and the file doesn't exist yet, we need to download it from the repo.
        # For now, let's provide a helpful error message.
        print("Error: Could not find aero-pi-cam.service file.")
        print("\nThis may happen when installing from git. The file is included in")
        print("the source distribution but may not be accessible after installation.")
        print("\nTroubleshooting:")
        print("1. Check if the file is already installed:")
        print(f"   sudo ls -la {service_file_dest}")
        print("2. If not, the file should be installed during pip install.")
        print(
            "   Try reinstalling: pip install --force-reinstall git+https://github.com/CaenFalaisePlaneurs/aero-pi-cam.git@develop"
        )
        print("3. Then run setup again: sudo aero-pi-cam-setup")
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

        # Read service file content from the actual file
        service_content = service_file_source.read_text()

        # Update the service file content with detected values
        lines = service_content.split("\n")
        updated_lines = []
        exec_start_found = False
        user_found = False
        config_path_found = False

        for line in lines:
            if line.strip().startswith("ExecStart="):
                # Use the detected webcam executable path
                updated_lines.append(f"ExecStart={webcam_executable}")
                exec_start_found = True
            elif line.strip().startswith("User="):
                # Use the detected user
                updated_lines.append(f"User={service_user}")
                user_found = True
            elif line.strip().startswith("WorkingDirectory="):
                # Remove or comment out WorkingDirectory for pip-installed package
                pass
            elif line.strip().startswith("Environment=") and "PATH=" in line:
                # Remove PATH override for pip-installed package
                pass
            elif line.strip().startswith("Environment=") and "CONFIG_PATH=" in line:
                # Update CONFIG_PATH to ensure it's set correctly
                updated_lines.append('Environment="CONFIG_PATH=/etc/aero-pi-cam/config.yaml"')
                config_path_found = True
            else:
                updated_lines.append(line)

        if not exec_start_found:
            # Add ExecStart if not found (insert after [Service] line)
            service_idx = -1
            for i, line in enumerate(updated_lines):
                if line.strip().startswith("[Service]"):
                    service_idx = i
                    break
            if service_idx >= 0:
                updated_lines.insert(service_idx + 1, f"ExecStart={webcam_executable}")
            else:
                updated_lines.append(f"ExecStart={webcam_executable}")

        if not user_found:
            # Add User if not found (insert after [Service] line)
            service_idx = -1
            for i, line in enumerate(updated_lines):
                if line.strip().startswith("[Service]"):
                    service_idx = i
                    break
            if service_idx >= 0:
                updated_lines.insert(service_idx + 1, f"User={service_user}")
            else:
                updated_lines.append(f"User={service_user}")

        if not config_path_found:
            # Add CONFIG_PATH if not found (insert after [Service] line, before ExecStart)
            service_idx = -1
            for i, line in enumerate(updated_lines):
                if line.strip().startswith("[Service]"):
                    service_idx = i
                    break
            if service_idx >= 0:
                # Insert after [Service] but before ExecStart if it exists
                insert_idx = service_idx + 1
                # Find ExecStart position to insert before it
                for i, line in enumerate(updated_lines[insert_idx:], start=insert_idx):
                    if line.strip().startswith("ExecStart="):
                        insert_idx = i
                        break
                updated_lines.insert(
                    insert_idx, 'Environment="CONFIG_PATH=/etc/aero-pi-cam/config.yaml"'
                )
            else:
                updated_lines.append('Environment="CONFIG_PATH=/etc/aero-pi-cam/config.yaml"')

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


def get_config_example_content() -> str | None:
    """Get the content of config.example.yaml from the package or repository.

    Returns:
        Config file content as string, or None if not found
    """
    # Try to find example config from various locations
    # Note: When installed via pip from git, the file is installed to
    # /usr/share/aero-pi-cam/ (system) or <venv>/usr/share/aero-pi-cam/ (venv)
    # via data_files, but we also need to check repository root when running from source.
    possible_locations = [
        # If running from source, check repository root
        Path(__file__).parent.parent / "config.example.yaml",
        # If installed as package, check parent directories
        Path(__file__).parent.parent.parent / "config.example.yaml",
    ]

    # Check file system locations
    for location in possible_locations:
        if location.exists():
            return location.read_text()

    # Try to find it using the package location (when installed via pip from git)
    try:
        import aero_pi_cam

        package_path = Path(aero_pi_cam.__file__).parent
        # When installed via pip, the file might be in various parent directories
        search_paths = [
            package_path.parent,  # site-packages or dist-packages
            package_path.parent.parent,  # lib/python3.x
            package_path.parent.parent.parent,  # venv root or /usr
        ]

        # Check installed location (data_files installs to usr/share/aero-pi-cam/)
        # For system installs: /usr/share/aero-pi-cam/
        # For venv installs: <venv>/usr/share/aero-pi-cam/
        if "site-packages" in str(package_path) or "dist-packages" in str(package_path):
            # Find venv root or system root
            for i, part in enumerate(package_path.parts):
                if part in ("site-packages", "dist-packages"):
                    if i >= 2:
                        # Go up to find potential root (venv or /usr)
                        potential_root = Path(*package_path.parts[: i - 2])
                        # Check venv location
                        venv_location = (
                            potential_root / "usr" / "share" / "aero-pi-cam" / "config.example.yaml"
                        )
                        if venv_location.exists():
                            return venv_location.read_text()
                    break

        # Check system-wide location
        system_location = Path("/usr/share/aero-pi-cam/config.example.yaml")
        if system_location.exists():
            return system_location.read_text()

        # Also check if we can find it relative to the current working directory
        cwd = Path.cwd()
        if (cwd / "config.example.yaml").exists():
            return (cwd / "config.example.yaml").read_text()
        else:
            for parent in search_paths:
                candidate = parent / "config.example.yaml"
                if candidate.exists():
                    return candidate.read_text()
    except ImportError:
        pass

    # Final check: system-wide installation location
    system_location = Path("/usr/share/aero-pi-cam/config.example.yaml")
    if system_location.exists():
        return system_location.read_text()

    return None


def create_config_template() -> bool:
    """Create configuration file template if it doesn't exist.

    Returns:
        True if config was created or already exists, False on error
    """
    config_dir = Path("/etc/aero-pi-cam")
    config_file = config_dir / "config.yaml"

    if config_file.exists():
        print(f"✓ Configuration file already exists: {config_file}")
        return True

    # Get config example content from the actual file
    config_content = get_config_example_content()

    if config_content is None:
        print("Error: Could not find config.example.yaml file.")
        print("Please ensure the package is properly installed.")
        return False

    try:
        # Check if running with sudo
        if os.geteuid() != 0:
            print("Error: This command requires sudo privileges.")
            print("Please run: sudo aero-pi-cam-setup")
            return False

        # Create config directory
        config_dir.mkdir(parents=True, exist_ok=True)

        # Write config content from the actual config.example.yaml file
        config_file.write_text(config_content)

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
    # Skip systemd service management in Docker
    if is_docker_environment():
        print("Skipping systemd service management (Docker environment detected)")
        return True

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
