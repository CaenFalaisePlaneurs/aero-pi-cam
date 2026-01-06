# Webcam Capture Service

A Python 3.13 background service for Raspberry Pi that captures images from an IP camera via RTSP/ffmpeg on a day/night schedule and uploads them via API or SFTP.

**Aeronautical Compliance**: All timestamps and time calculations use UTC (Coordinated Universal Time) exclusively. No timezone conversions or daylight saving time adjustments are applied, ensuring compliance with aeronautical standards.

## Features

- **Scheduled capture**: Different intervals for day and night based on sunrise/sunset
- **RTSP capture**: Reliable frame grabbing via ffmpeg with VIGI camera authentication support
- **Multiple upload methods**: API (PUT requests with retry logic) or SFTP upload
- **METAR overlay**: Optional weather information overlay from Aviation Weather API
- **Icon support**: Add SVG icons to overlay (URL, local file, or inline)
- **EXIF metadata**: Automatic embedding of camera info, GPS coordinates, METAR/TAF data, and license information in JPEG images
- **XMP metadata**: Custom XMP schema with all metadata duplicated for maximum compatibility
- **Debug mode**: Uses dummy API server for testing (saves images locally, no external API needed)
- **Systemd service**: Auto-start, auto-restart, journald logging

## Requirements

- Raspberry Pi 4B (or similar)
- Python 3.13.5 (already included on Raspberry Pi)
- ffmpeg
- IP camera with RTSP support (e.g., VIGI C340)

## Installation

Follow these steps one by one. Copy and paste each command into your terminal.

### Step 1: Create a virtual environment

This creates an isolated space for the software so it doesn't interfere with other programs:

```bash
python3 -m venv ~/aero-pi-cam-venv
```

**Verify Step 1 completed successfully:**

```bash
ls -d ~/aero-pi-cam-venv && echo "✅ Virtual environment created successfully!" || echo "❌ Virtual environment creation failed. Try running: python3 -m venv ~/aero-pi-cam-venv"
```

**🎉 Congratulations! Step 1 complete. You've created the virtual environment.**

---

### Step 2: Install the software

Copy and paste this command to install the latest stable version:

```bash
~/aero-pi-cam-venv/bin/pip install git+https://github.com/CaenFalaisePlaneurs/aero-pi-cam.git
```

**Note**: This will take a few minutes. Wait for it to finish.

**Verify Step 2 completed successfully:**

```bash
~/aero-pi-cam-venv/bin/pip list | grep aero-pi-cam && echo "✅ Package installed successfully!" || echo "❌ Package installation failed. Try running: ~/aero-pi-cam-venv/bin/pip install git+https://github.com/CaenFalaisePlaneurs/aero-pi-cam.git"
```

**🎉 Congratulations! Step 2 complete. The software is now installed.**

---

### Step 3: Run the setup

This command will:
- Install required system tools (ffmpeg, etc.)
- Create the configuration file
- Set up the service to run automatically

**Important**: This command needs root privileges to write system files. Use `sudo` without `-u`:

```bash
sudo /home/$(whoami)/aero-pi-cam-venv/bin/python -m aero_pi_cam.setup
```

You'll be asked for your password (for `sudo`). Type it and press Enter.

**Verify Step 3 completed successfully:**

```bash
ls /etc/aero-pi-cam/config.yaml && echo "✅ Setup completed successfully!" || echo "❌ Setup failed. Try running: sudo /home/$(whoami)/aero-pi-cam-venv/bin/python -m aero_pi_cam.setup"
```

**🎉 Congratulations! Step 3 complete. The system is configured and ready.**

---

### Step 4: Configure the software

Edit the configuration file with your camera and upload settings:

```bash
sudo nano /etc/aero-pi-cam/config.yaml
```

**What to change:**
- `camera.rtsp_url`: Your camera's RTSP address (e.g., `rtsp://192.168.1.100:554/stream1`)
- `camera.rtsp_user`: Your camera's username
- `camera.rtsp_password`: Your camera's password
- `location.name`: Your location name (e.g., `LFAS`)
- `location.latitude` and `location.longitude`: Your GPS coordinates
- `upload_method`: Choose `"API"` or `"SFTP"` for upload method
- **For API upload** (`upload_method: "API"`):
  - `api.url`: Your upload API address (leave empty to use test mode)
  - `api.key`: Your API key
- **For SFTP upload** (`upload_method: "SFTP"`):
  - `sftp.host`: SFTP server hostname
  - `sftp.port`: SFTP server port (usually 22)
  - `sftp.user`: SFTP username
  - `sftp.password`: SFTP password
  - `sftp.remote_path`: Remote directory path for uploads
  - `sftp.timeout_seconds`: Connection timeout

Press `Ctrl+X`, then `Y`, then `Enter` to save and exit.

**Verify Step 4 completed successfully:**

```bash
grep -q "rtsp_url" /etc/aero-pi-cam/config.yaml && echo "✅ Configuration file looks good!" || echo "❌ Configuration file not found or incomplete. Try running: sudo nano /etc/aero-pi-cam/config.yaml"
```

**🎉 Congratulations! Step 4 complete. Your configuration is saved.**

---

### Step 5: Start the service

Start the webcam service:

```bash
sudo systemctl start aero-pi-cam
```

**Verify Step 5 completed successfully:**

```bash
sudo systemctl is-active aero-pi-cam && echo "✅ Service started successfully!" || echo "❌ Service failed to start. Check logs with: sudo journalctl -u aero-pi-cam -n 50"
```

**🎉 Congratulations! Step 5 complete. The service is now running.**

---

### Step 6: Check if it's working

Verify the service is running properly:

```bash
sudo systemctl status aero-pi-cam
```

You should see "active (running)" in green. Press `Q` to exit.

**Verify Step 6 completed successfully:**

```bash
sudo systemctl is-active aero-pi-cam && echo "✅ Service is running perfectly!" || echo "❌ Service is not running. Try restarting with: sudo systemctl restart aero-pi-cam"
```

If you see "✅ Service is running perfectly!", everything is working! ✅

**🎉🎉🎉 Congratulations! Installation complete! 🎉🎉🎉**

The webcam will now capture images automatically according to your schedule. You're all set!

---

## Viewing Logs

To see what the service is doing:

```bash
sudo journalctl -u aero-pi-cam -f
```

Press `Ctrl+C` to stop viewing logs.

---

## Service Management

### Start the service

```bash
sudo systemctl start aero-pi-cam
```

### Stop the service

```bash
sudo systemctl stop aero-pi-cam
```

### Restart the service

```bash
sudo systemctl restart aero-pi-cam
```

### Check service status

```bash
sudo systemctl status aero-pi-cam
```

### View logs

```bash
sudo journalctl -u aero-pi-cam -f
```

### Disable auto-start

```bash
sudo systemctl disable aero-pi-cam
```

### Enable auto-start

```bash
sudo systemctl enable aero-pi-cam
```

---

## Troubleshooting

### Service won't start

Check what went wrong:

```bash
sudo journalctl -u aero-pi-cam -n 50
```

### Restart the service

If something isn't working, try restarting:

```bash
sudo systemctl restart aero-pi-cam
```

### Check service status

```bash
sudo systemctl status aero-pi-cam
```

### Configuration errors

Ensure `config.yaml` exists and is valid YAML at `/etc/aero-pi-cam/config.yaml`

Check file permissions:
```bash
sudo chown pi:pi /etc/aero-pi-cam/config.yaml
```

Validate with:
```bash
python3 -c "from aero_pi_cam.config import load_config; load_config('/etc/aero-pi-cam/config.yaml')"
```

### Python/dependency issues

Recreate virtual environment:
```bash
cd /opt/webcam-cfp
sudo -u pi rm -rf venv
sudo -u pi python3 -m venv venv
sudo -u pi venv/bin/pip install -r requirements.txt
sudo systemctl restart aero-pi-cam
```

### Camera connection issues

Test RTSP URL manually:
```bash
ffmpeg -rtsp_transport tcp -i "rtsp://..." -frames:v 1 test.jpg
```

Check camera network connectivity and verify RTSP credentials.

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
- When `DEBUG_MODE=true` and `upload_method: "API"`, the service automatically starts a dummy API server on `localhost:8000`
- All image uploads go to the dummy server instead of the configured API
- The dummy server saves images to `.debug/cam/{location}-{camera_name}.jpg` with static filenames
- No direct file writes - all images go through the upload process (same as production)
- **Note**: Debug mode only applies when using API upload method. SFTP uploads will use the configured SFTP server even in debug mode.

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

Reload systemd:
```bash
sudo systemctl daemon-reload
```

Restart the service:
```bash
sudo systemctl restart aero-pi-cam
```

**Image location:**
- Images are saved to `/opt/webcam-cfp/.debug/cam/{location}-{camera_name}.jpg`
- Example: `/opt/webcam-cfp/.debug/cam/LFAS-hangar_2.jpg`
- Filenames are sanitized (spaces → underscores, non-ASCII removed)

**Testing without API:**
You can also test without an API by setting `upload_method: "API"` and leaving `api.url` unset in `config.yaml`. The dummy server will automatically be used.

---

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
| upload_method | | Upload method: "API" or "SFTP" |
| api | url | Upload API endpoint (required when upload_method is "API") |
| api | key | Bearer token for authentication (required when upload_method is "API") |
| api | timeout_seconds | Request timeout (required when upload_method is "API") |
| sftp | host | SFTP server hostname (required when upload_method is "SFTP") |
| sftp | port | SFTP server port (required when upload_method is "SFTP") |
| sftp | user | SFTP username (required when upload_method is "SFTP") |
| sftp | password | SFTP password (required when upload_method is "SFTP") |
| sftp | remote_path | Remote directory path for uploads (required when upload_method is "SFTP") |
| sftp | timeout_seconds | Connection timeout in seconds (required when upload_method is "SFTP") |
| overlay | provider_logo | Path to logo file (PNG or SVG). Supports absolute paths, ~ expansion (e.g., `~/images/logo.png`), or relative paths. |
| overlay | logo_size | Logo size in pixels |
| overlay | font_path | Optional path to custom font file (e.g., `~/fonts/Poppins-Medium.ttf`). If not set, uses system font. |
| overlay | font_size | Font size in pixels |
| overlay | font_color | Text color (e.g., "white", "black") |
| metar | enabled | Enable/disable weather overlay |
| metar | icao_code | Airport code for METAR data |
| metar | icon | Optional icon configuration (url/path/svg, size, position) |
| metadata | github_repo | GitHub repository URL for the project |
| metadata | webcam_url | URL where webcam images are published |
| metadata | license | License identifier (e.g., "CC BY-SA 4.0") |
| metadata | license_url | URL to the license text |
| metadata | license_mark | Short license attribution mark |

### Installing Custom Fonts

If you want to use a custom font (ex. Poppins) for the overlay text, you can install it system-wide on your Raspberry Pi. The application will automatically use it if configured in `config.yaml`.

#### Example: Install Poppins System-Wide on Raspberry Pi (Debian/Raspberry Pi OS)

**Steps:**

1. **Create the font directory:**
   ```bash
   sudo mkdir -p /usr/share/fonts/truetype/poppins
   ```

2. **Download fonts directly into the directory:**
   ```bash
   sudo wget -O /usr/share/fonts/truetype/poppins/Poppins-Regular.ttf https://github.com/google/fonts/raw/main/ofl/poppins/Poppins-Regular.ttf
   ```

3. **(Optional) Download other weights you need (Bold, Medium, etc.):**
   ```bash
   sudo wget -O /usr/share/fonts/truetype/poppins/Poppins-Medium.ttf https://github.com/google/fonts/raw/main/ofl/poppins/Poppins-Medium.ttf
   sudo wget -O /usr/share/fonts/truetype/poppins/Poppins-Bold.ttf https://github.com/google/fonts/raw/main/ofl/poppins/Poppins-Bold.ttf
   ```

4. **Set proper permissions:**
   ```bash
   sudo chmod 644 /usr/share/fonts/truetype/poppins/*.ttf
   ```

5. **Rebuild font cache:**
   ```bash
   sudo fc-cache -f -v
   ```

6. **Verify installation:**
   ```bash
   fc-list | grep -i poppins
   ```

7. **Configure in `config.yaml`:**
   ```yaml
   overlay:
     font_path: "/usr/share/fonts/truetype/poppins/Poppins-Medium.ttf"
     # Or use ~ expansion for user-specific installation:
     # font_path: "~/fonts/Poppins-Medium.ttf"
   ```

**Alternative: User-Specific Installation**

If you prefer to install the font in your home directory (no `sudo` required):

```bash
# Create fonts directory in your home
mkdir -p ~/fonts

# Download and copy font
wget https://github.com/google/fonts/raw/main/ofl/poppins/Poppins-Medium.ttf -O ~/fonts/Poppins-Medium.ttf

# Configure in config.yaml
# font_path: "~/fonts/Poppins-Medium.ttf"
```

### Configuring the Provider Logo

The provider logo is displayed in the overlay. You can use either a PNG or SVG file. The logo path supports:
- Absolute paths (e.g., `/home/user/images/logo.png`)
- Home directory expansion with `~` (e.g., `~/images/logo.png`)
- Relative paths (relative to project root, for development)

**Steps to upload and configure your logo:**

1. **Create a directory for your logo (optional, but recommended):**
   ```bash
   mkdir -p ~/images
   ```

2. **Upload your logo file to the Raspberry Pi:**
   - You can use `scp` from your computer:
     ```bash
     scp logo.png user@raspberry-pi-ip:~/images/logo.png
     ```
   - Or download it directly on the Pi:
     ```bash
     wget https://example.com/logo.png -O ~/images/logo.png
     ```

3. **Configure in `config.yaml`:**
   ```yaml
   overlay:
     provider_logo: "~/images/logo.png"  # Supports ~ expansion
     # Or use absolute path:
     # provider_logo: "/home/user/images/logo.png"
     # Or relative path (for development):
     # provider_logo: "images/logo.png"
     logo_size: 72  # Logo size in pixels
   ```

**Supported formats:**
- PNG (with transparency support)
- SVG (automatically converted to PNG)

**Note:** If the logo file is not found at the specified path, the overlay will continue without the logo (no error, graceful degradation).

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
```

Or short form:
```bash
python -m src.main -c /path/to/custom-config.yaml
```

2. **Environment variable**:
```bash
export CONFIG_PATH=/path/to/custom-config.yaml
python -m src.main
```

3. **Default**: `/etc/aero-pi-cam/config.yaml` (when running as systemd service) or `config.yaml` (when running manually from project directory)

The precedence order is: command-line argument > environment variable > default.

---

## EXIF and XMP Metadata

All captured JPEG images automatically include embedded metadata in both EXIF and XMP formats:

### Standard EXIF Tags

- **ImageDescription**: Camera name
- **Copyright**: Provider name and license attribution
- **GPS coordinates**: Camera location (latitude/longitude in degrees/minutes/seconds format)

### Custom Metadata (EXIF UserComment and XMP)

The following metadata is embedded in structured JSON format (EXIF UserComment) and custom XMP schema:

- **camera_name**: Camera identifier
- **provider_name**: Image provider name
- **latitude/longitude**: GPS coordinates (decimal degrees)
- **github_repo**: GitHub repository URL
- **webcam_url**: URL where webcam images are published
- **license**: License identifier (e.g., "CC BY-SA 4.0")
- **license_url**: URL to the license text
- **license_mark**: Short license attribution mark
- **airfield_icao**: Airfield ICAO code (if METAR enabled)
- **metar**: Raw METAR text (if METAR enabled)
- **taf**: Raw TAF text (if METAR enabled)
- **sunrise/sunset**: Sunrise and sunset times in ISO 8601 UTC format

### XMP Custom Schema

All metadata is also embedded in XMP format using a custom schema (`http://aero-pi-cam.org/xmp/1.0/`) for maximum compatibility with image management software.

### Viewing Metadata

You can view the embedded metadata using standard tools:

```bash
# Using exiftool (if installed)
exiftool image.jpg

# Using Python
python3 -c "import piexif; print(piexif.load(open('image.jpg', 'rb')))"
```

---

## Upload Methods

The service supports two upload methods: **API** and **SFTP**. Configure the method using `upload_method` in `config.yaml`.

### API Upload

**Note**: API upload contract only applies when `upload_method: "API"`.

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

### SFTP Upload

**Note**: SFTP upload applies when `upload_method: "SFTP"`.

The service uploads images via SFTP to the configured remote server:
- **Filename format**: `{location}-{camera_name}.jpg` (same as API, e.g., `LFAS-hangar_2.jpg`)
- **Remote path**: Configured via `sftp.remote_path` (e.g., `/public_html/cam/`)
- **Full path**: `{sftp.remote_path}/{filename}` (e.g., `/public_html/cam/LFAS-hangar_2.jpg`)
- **Overwrite behavior**: Each upload overwrites the previous image with the same filename
- **Directory creation**: Remote directory is created automatically if it doesn't exist

---

## Advanced Options

### Install from a specific branch (e.g., develop)

```bash
~/aero-pi-cam-venv/bin/pip install git+https://github.com/CaenFalaisePlaneurs/aero-pi-cam.git@develop
```

### Install from a specific release

```bash
~/aero-pi-cam-venv/bin/pip install git+https://github.com/CaenFalaisePlaneurs/aero-pi-cam.git@v1.0.0
```

### System-wide installation (alternative method)

```bash
sudo pip install --break-system-packages git+https://github.com/CaenFalaisePlaneurs/aero-pi-cam.git@develop
sudo aero-pi-cam-setup
```

### Uninstallation

**What gets removed:**
- ✅ Python package files
- ✅ Systemd service file (`/etc/systemd/system/aero-pi-cam.service`)
- ✅ Service is stopped and disabled

**What is preserved (intentionally):**
- 📁 Configuration file (`/etc/aero-pi-cam/config.yaml`) - following Debian best practices
- 📁 Virtual environment directory (`~/aero-pi-cam-venv`) - you can remove it manually if desired
- 📁 Any log files or debug images created during runtime

**If installed in virtual environment:**

Step 1: Stop and disable the service (recommended)

**Important**: This command needs root privileges. Use `sudo` without `-u`:

```bash
sudo /home/$(whoami)/aero-pi-cam-venv/bin/python -m aero_pi_cam.uninstall
```

Or if you know your username (replace 'lfas' with your username):
```bash
sudo /home/lfas/aero-pi-cam-venv/bin/python -m aero_pi_cam.uninstall
```

**Verify Step 1 completed successfully:**
```bash
sudo systemctl is-active aero-pi-cam 2>&1 | grep -q "inactive" && echo "✅ Service stopped successfully!" || echo "❌ Service stop failed. Try running: sudo systemctl stop aero-pi-cam"
```

**🎉 Step 1 complete. Service stopped and disabled.**

---

Step 2: Remove the Python package (this will also remove the systemd service file)

**Important**: Use the full path to the venv's pip, not just `pip`:
```bash
~/aero-pi-cam-venv/bin/pip uninstall aero-pi-cam
```

**Verify Step 2 completed successfully:**
```bash
~/aero-pi-cam-venv/bin/pip list | grep aero-pi-cam && echo "❌ Package removal failed. Try running: ~/aero-pi-cam-venv/bin/pip uninstall aero-pi-cam" || echo "✅ Package removed successfully!"
```

**🎉 Step 2 complete. Package and service file removed.**

---

Step 3: Remove the virtual environment (optional, for complete cleanup)

If you want to completely remove everything including the virtual environment:
```bash
rm -rf ~/aero-pi-cam-venv
```

**Verify Step 3 completed successfully:**
```bash
ls ~/aero-pi-cam-venv 2>&1 | grep -q "No such file" && echo "✅ Virtual environment removed successfully!" || echo "❌ Virtual environment removal failed. Try running: rm -rf ~/aero-pi-cam-venv"
```

**🎉 Step 3 complete. Virtual environment removed.**

---

**If installed system-wide:**

Step 1: Stop and disable the service (recommended)
```bash
sudo aero-pi-cam-uninstall
```

Step 2: Remove the Python package (this will also remove the systemd service file)
```bash
sudo pip uninstall aero-pi-cam
```

**Note**: For complete cleanup, you may also want to manually remove:
- Configuration file: `sudo rm /etc/aero-pi-cam/config.yaml` (if you don't want to keep it)
- Configuration directory: `sudo rmdir /etc/aero-pi-cam` (if empty)

---

## License

GPL-3.0 - See [LICENSE](LICENSE) file for details.

This project is open source and available under the GNU General Public License v3.0.

Copyright (C) 2026 Caen Falaise Planeurs
