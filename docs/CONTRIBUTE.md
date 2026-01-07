---
layout: default
title: Contributing Guide
---

# Contributing

> **Note**: Contributing is volunteer-based and does not provide any right for help. We all do our best, but we need time to fly too...

## Development Setup

### Python Version Management

This project targets **Python 3.13.5** (as included on Raspberry Pi). To ensure compatibility:

#### On Development Machine

If you use **pyenv** for Python version management:
```bash
# Install Python 3.13.5 (if not already installed)
pyenv install 3.13.5

# Set local version for this project
pyenv local 3.13.5

# Verify
python --version  # Should show 3.13.5
```

The `.python-version` file is included in the repository and will be automatically used by pyenv.

#### On Raspberry Pi

The Raspberry Pi comes with Python 3.13.5 pre-installed. Simply use:
```bash
python3 --version  # Should show Python 3.13.5
```

The virtual environment will use the system Python 3.13.5 automatically.

### System Dependencies

The project requires some system libraries that must be installed via your system package manager:

#### macOS (Homebrew)

```bash
# Install cairo (required for cairosvg - SVG icon support)
brew install cairo

# Install ffmpeg (required for RTSP camera capture)
brew install ffmpeg
```

#### Linux (Debian/Ubuntu/Raspberry Pi OS)

```bash
# Install cairo and ffmpeg
sudo apt update
sudo apt install libcairo2-dev ffmpeg
```

**Note**: On Raspberry Pi, these dependencies are automatically installed by the installation script. For local development on macOS or Linux, you need to install them manually.

### Development Workflow

```bash
# Activate virtual environment (REQUIRED - all commands must run in venv)
source venv/bin/activate

# Install dev dependencies
pip install -r requirements-dev.txt

# Run tests
pytest tests/

# Lint
ruff check aero_pi_cam tests

# Format
black aero_pi_cam tests

# Type check
mypy aero_pi_cam
```

**Note**: Warning filters are configured in `pyproject.toml` under `[tool.pytest.ini_options]` → `filterwarnings`. This suppresses known deprecation warnings from third-party libraries (e.g., Pillow, suncalc) that don't affect functionality. See [pytest warning documentation](https://docs.pytest.org/en/stable/how-to/capture-warnings.html) for details.

### Running the App Manually

To run the app manually in the terminal for development (without systemd service or Docker):

```bash
# Activate virtual environment
source venv/bin/activate

# Optional: specify config path (defaults to config.yaml)
export CONFIG_PATH=config.yaml

# Optional: enable debug mode to use dummy API server
export DEBUG_MODE=true

# Optional: force day or night mode (for testing)
export DEBUG_DAY_NIGHT_MODE=day  # or "night"

# Run the app
python -m aero_pi_cam.core.main
```

The app will:
- Load configuration from `config.yaml` (or the path specified in `CONFIG_PATH`)
- Start dummy API server on `localhost:8000` if `DEBUG_MODE=true` or `api.url` is not set
- Perform an initial capture
- Start scheduled captures based on day/night intervals
- Run until interrupted with `Ctrl+C`

**Note**: With `DEBUG_MODE=true`, a dummy API server runs on `localhost:8000` and saves images to `.debug/cam/{location}-{camera_name}.jpg` (e.g., `.debug/cam/LFAS-hangar_2.jpg`). You can also test without an API by leaving `api.url` unset in the config.

### Enabling Debug Mode in Systemd Service

To enable debug mode when running as a systemd service:

1. **Edit the systemd service file:**
   ```bash
   sudo systemctl edit aero-pi-cam
   ```

2. **Add the following:**
   ```ini
   [Service]
   Environment="DEBUG_MODE=true"
   ```

3. **Reload systemd:**
   ```bash
   sudo systemctl daemon-reload
   ```

4. **Restart the service:**
   ```bash
   sudo systemctl restart aero-pi-cam
   ```

**How it works:**
- When `DEBUG_MODE=true` and `upload.method: "API"`, the service automatically starts a dummy API server on `localhost:8000`
- All image uploads go to the dummy server instead of the configured API
- The dummy server saves images to `.debug/cam/{location}-{camera_name}.jpg` with static filenames
- No direct file writes - all images go through the upload process (same as production)
- **Note**: Debug mode only applies when using API upload method. SFTP uploads will use the configured SFTP server even in debug mode.

**Image location:**
- Images are saved to `.debug/cam/{location}-{camera_name}.jpg` in the current working directory
- Example: `.debug/cam/LFAS-hangar_2.jpg`
- Filenames are sanitized (spaces → underscores, non-ASCII removed)

To stop the app, press `Ctrl+C` (handles SIGINT gracefully).

### Docker Development Environment

Docker is available for **development and testing only** - it is not intended for production use. For production deployment, use the systemd service on Raspberry Pi.

The Docker setup allows you to test the service in an isolated environment that mirrors the Raspberry Pi configuration. See [DOCKER.md](DOCKER.md) for complete documentation.

**Quick start:**

```bash
# Create config file first (from project root)
cp config.example.yaml config.yaml
# Edit config.yaml with your settings

# Build and run with Docker Compose (from project root)
cd docker
docker-compose up -d

# View logs
docker-compose logs -f

# Stop
docker-compose down
```

**Key features:**
- Python 3.13.5 environment matching Raspberry Pi
- Isolated testing without affecting local system
- Easy configuration via mounted `config.yaml`
- Dummy API server for debug mode and testing (no external API needed)

For detailed Docker usage, troubleshooting, and advanced options, see [DOCKER.md](DOCKER.md).

## Aeronautical Requirements

### UTC Time Standard

**All timestamps and time calculations MUST use UTC (Coordinated Universal Time) exclusively.**

- ✅ Use `datetime.now(timezone.utc)` or `datetime.utcnow()` for current time
- ✅ All datetime objects should be timezone-aware with UTC timezone
- ✅ Timestamps in API requests/responses use ISO 8601 format with 'Z' suffix (e.g., `2026-01-02T15:30:00Z`)
- ✅ Log messages display times with "UTC" suffix for clarity
- ❌ **NEVER** use local timezone or `datetime.now()` without timezone
- ❌ **NEVER** apply timezone conversions or daylight saving time adjustments
- ❌ **NEVER** use timezone fields in configuration - they are not needed and not used

This ensures compliance with aeronautical standards where UTC is the universal time reference.

