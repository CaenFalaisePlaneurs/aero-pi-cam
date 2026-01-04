# Webcam Capture Service

A Python 3.13 background service for Raspberry Pi that captures images from an IP camera via RTSP/ffmpeg on a day/night schedule and uploads them to a remote API.

**Aeronautical Compliance**: All timestamps and time calculations use UTC (Coordinated Universal Time) exclusively. No timezone conversions or daylight saving time adjustments are applied, ensuring compliance with aeronautical standards.

## Features

- **Scheduled capture**: Different intervals for day and night based on sunrise/sunset
- **RTSP capture**: Reliable frame grabbing via ffmpeg with VIGI camera authentication support
- **API upload**: PUT requests with retry logic and exponential backoff
- **METAR overlay**: Optional weather information overlay from Aviation Weather API
- **Icon support**: Add SVG icons to overlay (URL, local file, or inline)
- **Debug mode**: Uses dummy API server for testing (saves images locally, no external API needed)
- **Systemd service**: Auto-start, auto-restart, journald logging

## Requirements

- Raspberry Pi 4B (or similar)
- Python 3.13.5 (already included on Raspberry Pi)
- ffmpeg
- IP camera with RTSP support (e.g., VIGI C340)

## Installation

### Pip Installation (Recommended for Python Package)

**New**: Install as a Python package from GitHub:

```bash
# Install from main branch (stable)
pip install git+https://github.com/CaenFalaisePlaneurs/aero-pi-cam.git

# Install from specific branch (e.g., develop)
pip install git+https://github.com/CaenFalaisePlaneurs/aero-pi-cam.git@develop

# Install from GitHub release (uses the release tag, e.g., v1.0.0)
pip install git+https://github.com/CaenFalaisePlaneurs/aero-pi-cam.git@v1.0.0

# Install from specific commit
pip install git+https://github.com/CaenFalaisePlaneurs/aero-pi-cam.git@abc123def

# Run setup (installs system deps, creates service, config)
sudo aero-pi-cam-setup
```

Or in one command:

```bash
# From main branch
sudo pip install git+https://github.com/CaenFalaisePlaneurs/aero-pi-cam.git && sudo aero-pi-cam-setup

# From develop branch
sudo pip install git+https://github.com/CaenFalaisePlaneurs/aero-pi-cam.git@develop && sudo aero-pi-cam-setup

# From specific release (e.g., v1.0.0)
sudo pip install git+https://github.com/CaenFalaisePlaneurs/aero-pi-cam.git@v1.0.0 && sudo aero-pi-cam-setup
```

**Note**: GitHub releases are created from tags, so installing from a release uses the same syntax as installing from a tag. Find available releases and their tags on the [GitHub Releases page](https://github.com/CaenFalaisePlaneurs/aero-pi-cam/releases).

The setup command will:
- ✅ Check and install system dependencies (ffmpeg, libcairo2-dev)
- ✅ Create systemd service file
- ✅ Create configuration template at `/etc/aero-pi-cam/config.yaml`
- ✅ Enable and optionally start the service

**After installation**, edit the configuration:
```bash
sudo nano /etc/aero-pi-cam/config.yaml
```

Then start the service (if not already started):
```bash
sudo systemctl start aero-pi-cam
sudo systemctl status aero-pi-cam
```

### Uninstallation (Pip Install)

To uninstall the package:

```bash
# Step 1: Stop and disable the service (recommended)
sudo aero-pi-cam-uninstall

# Step 2: Remove the Python package (this will also remove the systemd service file)
sudo pip uninstall aero-pi-cam
```

Or in one command:

```bash
sudo aero-pi-cam-uninstall && sudo pip uninstall aero-pi-cam
```

The uninstall process will:
- ✅ Stop and disable the systemd service (via `aero-pi-cam-uninstall`)
- ✅ Remove the systemd service file (automatically via `pip uninstall`)
- ✅ Remove Python package files
- ✅ **Preserve** configuration file at `/etc/aero-pi-cam/config.yaml` (following Debian FHS best practices)

**Note**: The `aero-pi-cam-uninstall` command prepares the system for uninstallation by stopping the service. The actual file removal is handled by `pip uninstall`, which automatically removes files installed via `data_files` (including the systemd service file).

### Quick Install (One Command - Legacy Method)

**Alternative**: Use the automated installation script:

```bash
curl -fsSL https://raw.githubusercontent.com/CaenFalaisePlaneurs/aero-pi-cam/main/install.sh | sudo bash
```

Or if you prefer to review the script first:

```bash
# Download and review
wget https://raw.githubusercontent.com/CaenFalaisePlaneurs/aero-pi-cam/main/install.sh
cat install.sh
sudo bash install.sh
```

The installer will:
- ✅ Install system dependencies (ffmpeg, python3-pip, python3-venv)
- ✅ Clone/download the repository to `/opt/webcam-cfp`
- ✅ Create Python virtual environment
- ✅ Install all Python dependencies
- ✅ Create configuration file from example
- ✅ Install and enable systemd service
- ✅ Optionally start the service

**After installation**, edit the configuration:
```bash
sudo nano /etc/aero-pi-cam/config.yaml
```

Then start the service:
```bash
sudo systemctl start aero-pi-cam
sudo systemctl status aero-pi-cam
```

### Uninstallation (Legacy Method)

If you installed using the install script, use the uninstall script:

```bash
sudo bash uninstall.sh
```

Or if installed from GitHub:

```bash
curl -fsSL https://raw.githubusercontent.com/CaenFalaisePlaneurs/aero-pi-cam/main/uninstall.sh | sudo bash
```

The uninstaller will:
- ✅ Stop and disable the systemd service
- ✅ Remove the service file
- ✅ Remove the installation directory
- ✅ Preserve your configuration at `/etc/aero-pi-cam/config.yaml` (following Debian best practices)

### Manual Installation

If you prefer to install manually:

#### 1. Install system dependencies

```bash
sudo apt update
sudo apt install ffmpeg python3-pip python3-venv git
```

#### 2. Clone and setup project

```bash
sudo mkdir -p /opt/webcam-cfp
sudo chown pi:pi /opt/webcam-cfp
cd /opt/webcam-cfp
git clone https://github.com/CaenFalaisePlaneurs/aero-pi-cam.git .
```

#### 3. Setup Python virtual environment

**Recommended**: Use a virtual environment to isolate dependencies and ensure Python 3.13.5 compatibility.

**Option A: Using the setup script (recommended)**

```bash
# Make script executable (if not already)
chmod +x setup-venv.sh

# Create venv with Python 3.13.5
./setup-venv.sh 3.13.5

# Activate the virtual environment
source venv/bin/activate
```

**Option B: Manual setup**

```bash
# Verify Python version (should be 3.13.5 on Raspberry Pi)
python3 --version

# Create virtual environment
python3 -m venv venv

# Activate the virtual environment
source venv/bin/activate

# Upgrade pip
pip install --upgrade pip setuptools wheel

# Install dependencies
pip install -r requirements.txt
```

**Note**: The virtual environment ensures you're using the correct Python version and isolates project dependencies. The systemd service is configured to use the virtual environment automatically.

#### 4. Configure

```bash
sudo mkdir -p /etc/aero-pi-cam
sudo cp config.example.yaml /etc/aero-pi-cam/config.yaml
sudo nano /etc/aero-pi-cam/config.yaml
sudo chown pi:pi /etc/aero-pi-cam/config.yaml
sudo chmod 600 /etc/aero-pi-cam/config.yaml
```

Edit the configuration:
- `camera.rtsp_url`: Your camera's RTSP URL
- `location`: GPS coordinates for sunrise/sunset calculation
- `api.url`: Your upload API endpoint (optional - uses dummy server if not set)
- `api.key`: Your API key
- `metar.enabled`: Set to `true` to enable weather overlay

#### 5. Install as systemd service

```bash
sudo cp aero-pi-cam.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable aero-pi-cam
sudo systemctl start aero-pi-cam
```

#### 6. Check status and logs

```bash
sudo systemctl status aero-pi-cam
sudo journalctl -u aero-pi-cam -f
```

## Service Management

```bash
# Start service
sudo systemctl start aero-pi-cam

# Stop service
sudo systemctl stop aero-pi-cam

# Restart service
sudo systemctl restart aero-pi-cam

# Check status
sudo systemctl status aero-pi-cam

# View logs
sudo journalctl -u aero-pi-cam -f

# Disable auto-start
sudo systemctl disable aero-pi-cam

# Enable auto-start
sudo systemctl enable aero-pi-cam
```

## Updating

To update an existing installation:

```bash
cd /opt/webcam-cfp
sudo -u pi git pull
sudo -u pi /opt/webcam-cfp/venv/bin/pip install -r requirements.txt
sudo systemctl restart aero-pi-cam
```

Or re-run the installer (it will detect existing installation and update it).

## Configuration

See `config.example.yaml` for all options:

| Section | Option | Description |
|---------|--------|-------------|
| camera | rtsp_url | RTSP URL (without credentials if using separate fields) |
| camera | rtsp_user | RTSP username (optional, if not in URL) |
| camera | rtsp_password | RTSP password (optional, if not in URL - **VIGI cameras**: use unencoded, even with special characters like `$` or `&`) |
| location | name | Location identifier |
| location | latitude/longitude | GPS coordinates for sun calculation |
| schedule | day_interval_minutes | Capture interval during day |
| schedule | night_interval_minutes | Capture interval during night |
| api | url | Upload API endpoint |
| api | key | Bearer token for authentication |
| api | timeout_seconds | Request timeout |
| metar | enabled | Enable/disable weather overlay |
| metar | icao_code | Airport code for METAR data |
| metar | icon | Optional icon configuration (url/path/svg, size, position) |

## API Contract

The service uploads images using this format:

```
PUT /api/webcam/image
Authorization: Bearer {api_key}
Content-Type: image/jpeg
X-Capture-Timestamp: 2026-01-02T15:30:00Z
X-Location: LFAS
X-Is-Day: true

[binary JPEG data]
```

**Note**: All timestamps are in UTC (ISO 8601 format with 'Z' suffix) for aeronautical compliance.

Expected response:

```json
{
  "id": "uuid",
  "received_at": "2026-01-02T15:30:05Z",
  "size_bytes": 245000
}
```

## Troubleshooting

### RTSP Authentication Issues (401 Unauthorized)

**Problem**: Getting 401 Unauthorized errors even with correct credentials.

**Solution for VIGI cameras**:
- VIGI cameras require passwords with special characters (e.g., `$`, `&`) but reject URL-encoded passwords
- Use separate `rtsp_user` and `rtsp_password` fields instead of embedding in URL
- The password will be passed unencoded (as-is) to match VLC and direct ffmpeg behavior

**Example**:
```yaml
camera:
  rtsp_url: "rtsp://192.168.0.60:554/stream1"
  rtsp_user: "pi"
  rtsp_password: "password"  # Special characters OK, no encoding needed
```

**Testing**: Verify your RTSP URL works in VLC or with direct ffmpeg command:
```bash
ffmpeg -rtsp_transport tcp -i 'rtsp://pi:password$@192.168.0.60:554/stream1' -frames:v 1 -f image2 test.jpg
```

### Debug Mode

Debug mode uses a local dummy API server for testing, eliminating the need for an external API during development.

**How it works:**
- When `DEBUG_MODE=true`, the service automatically starts a dummy API server on `localhost:8000`
- All image uploads go to the dummy server instead of the configured API
- The dummy server saves images to `.debug/cam/{location}-{camera_name}.jpg` with static filenames
- No direct file writes - all images go through the upload process (same as production)

**Enable debug mode:**

Edit the systemd service file:

```bash
sudo systemctl edit aero-pi-cam
```

Add the following:

```ini
[Service]
Environment="DEBUG_MODE=true"
```

Then restart the service:

```bash
sudo systemctl daemon-reload
sudo systemctl restart aero-pi-cam
```

**Image location:**
- Images are saved to `/opt/webcam-cfp/.debug/cam/{location}-{camera_name}.jpg`
- Example: `/opt/webcam-cfp/.debug/cam/LFAS-hangar_2.jpg`
- Filenames are sanitized (spaces → underscores, non-ASCII removed)

**Testing without API:**
You can also test without an API by leaving `api.url` unset in `config.yaml`. The dummy server will automatically be used.

### Service won't start

1. Check service status:
   ```bash
   sudo systemctl status aero-pi-cam
   ```

2. Check logs:
   ```bash
   sudo journalctl -u aero-pi-cam -n 50
   ```

3. Verify configuration:
   ```bash
   sudo -u pi /opt/webcam-cfp/venv/bin/python -m src.main
   ```

### Configuration errors

- Ensure `config.yaml` exists and is valid YAML at `/etc/aero-pi-cam/config.yaml`
- Check file permissions: `sudo chown pi:pi /etc/aero-pi-cam/config.yaml`
- Validate with: `python3 -c "from aero_pi_cam.config import load_config; load_config('/etc/aero-pi-cam/config.yaml')"`

### Python/dependency issues

- Recreate virtual environment:
  ```bash
  cd /opt/webcam-cfp
  sudo -u pi rm -rf venv
  sudo -u pi python3 -m venv venv
  sudo -u pi venv/bin/pip install -r requirements.txt
  sudo systemctl restart aero-pi-cam
  ```

### Camera connection issues

- Test RTSP URL manually:
  ```bash
  ffmpeg -rtsp_transport tcp -i "rtsp://..." -frames:v 1 test.jpg
  ```
- Check camera network connectivity
- Verify RTSP credentials

### Configuration Location

The configuration file is located at `/etc/aero-pi-cam/config.yaml` following Debian Filesystem Hierarchy Standard (FHS) best practices. This means:

- ✅ Configuration persists across uninstalls (standard Debian behavior)
- ✅ Configuration is in the standard system location (`/etc/`)

To edit your configuration:
```bash
sudo nano /etc/aero-pi-cam/config.yaml
```

### Overriding Configuration Path

You can override the configuration file path using:

1. **Command-line argument** (highest priority):
   ```bash
   python -m src.main --config /path/to/custom-config.yaml
   # or short form:
   python -m src.main -c /path/to/custom-config.yaml
   ```

2. **Environment variable**:
   ```bash
   export CONFIG_PATH=/path/to/custom-config.yaml
   python -m src.main
   ```

3. **Default**: `/etc/aero-pi-cam/config.yaml` (when running as systemd service) or `config.yaml` (when running manually from project directory)

The precedence order is: command-line argument > environment variable > default.

## License

GPL-3.0 - See [LICENSE](LICENSE) file for details.

This project is open source and available under the GNU General Public License v3.0.

Copyright (C) 2026 Caen Falaise Planeurs
