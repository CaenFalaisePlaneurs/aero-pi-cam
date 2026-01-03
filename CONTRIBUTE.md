# Contributing

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
# Activate virtual environment
source venv/bin/activate

# Install dev dependencies
pip install -r requirements-dev.txt

# Run tests
pytest

# Lint
ruff check src tests

# Format
black src tests

# Type check
mypy src
```

### Running the App Manually

To run the app manually in the terminal for development (without systemd service or Docker):

```bash
# Activate virtual environment
source venv/bin/activate

# Optional: specify config path (defaults to config.yaml)
export CONFIG_PATH=config.yaml

# Optional: enable debug mode to save captured images locally
export DEBUG_MODE=true

# Run the app
python src/main.py
```

The app will:
- Load configuration from `config.yaml` (or the path specified in `CONFIG_PATH`)
- Perform an initial capture
- Start scheduled captures based on day/night intervals
- Run until interrupted with `Ctrl+C`

**Note**: With `DEBUG_MODE=true`, captured images are saved to `.debug/capture_YYYYMMDD_HHMMSS.jpg` in the project directory for inspection.

To stop the app, press `Ctrl+C` (handles SIGINT gracefully).

### Docker Development Environment

Docker is available for **development and testing only** - it is not intended for production use. For production deployment, use the systemd service on Raspberry Pi.

The Docker setup allows you to test the service in an isolated environment that mirrors the Raspberry Pi configuration. See [DOCKER.md](../DOCKER.md) for complete documentation.

**Quick start:**

```bash
# Create config file first
cp config.example.yaml config.yaml
# Edit config.yaml with your settings

# Build and run with Docker Compose
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
- Debug mode support for image inspection

For detailed Docker usage, troubleshooting, and advanced options, see [DOCKER.md](../DOCKER.md).

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

