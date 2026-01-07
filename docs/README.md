---
layout: page
title: aero-pi-cam
---

<img src="https://raw.githubusercontent.com/CaenFalaisePlaneurs/aero-pi-cam/main/docs/aero-pi-cam_logo.png" alt="aero-pi-cam logo" style="max-width: 20vw;">

# aero-pi-cam

A Python 3.13 background service for Raspberry Pi that captures images from an IP camera via RTSP/ffmpeg on a day/night schedule and uploads them via API or SFTP.

[![Quality Check](https://github.com/CaenFalaisePlaneurs/aero-pi-cam/actions/workflows/quality.yml/badge.svg)](https://github.com/CaenFalaisePlaneurs/aero-pi-cam/actions/workflows/quality.yml)
[![pages-build-deployment](https://github.com/CaenFalaisePlaneurs/aero-pi-cam/actions/workflows/pages/pages-build-deployment/badge.svg)](https://github.com/CaenFalaisePlaneurs/aero-pi-cam/actions/workflows/pages/pages-build-deployment)

## Features

- **Scheduled capture**: Different intervals for day and night based on sunrise/sunset
- **RTSP capture**: Reliable frame grabbing via ffmpeg with authentication support (works with any RTSP camera, including VIGI)
- **Multiple upload methods**: API (PUT requests with retry logic) or SFTP upload
- **METAR/TAF overlay**: Optional weather information overlay from Aviation Weather API (METAR and TAF data)
- **Provider logo**: Add provider logo to overlay (PNG or SVG format, supports absolute paths and ~ expansion)
- **Custom fonts**: Use custom fonts for overlay text (e.g., Poppins) with fallback to system fonts
- **Built-in icons**: Sunrise, sunset, and compass icons included in overlay
- **EXIF metadata**: Automatic embedding of camera info, GPS coordinates, METAR/TAF data, and license information in JPEG images
- **XMP metadata**: Custom XMP schema with all metadata duplicated for maximum compatibility
- **SFTP metadata JSON**: Automatic generation of JSON metadata files alongside images for SFTP uploads (includes TTL, timestamps, METAR/TAF data)
- **Dual image upload**: SFTP can upload both images with and without METAR overlay
- **Debug mode**: Uses dummy API server for testing (saves images locally, no external API needed)
- **Systemd service**: Auto-start, auto-restart, journald logging

> **Note**: All timestamps and time calculations use UTC (Coordinated Universal Time) exclusively, ensuring compliance with aeronautical standards.

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
sudo /home/$(whoami)/aero-pi-cam-venv/bin/python -m aero_pi_cam.setup.setup
```

You'll be asked for your password (for `sudo`). Type it and press Enter.

**Verify Step 3 completed successfully:**

```bash
ls /etc/aero-pi-cam/config.yaml && echo "✅ Setup completed successfully!" || echo "❌ Setup failed. Try running: sudo /home/$(whoami)/aero-pi-cam-venv/bin/python -m aero_pi_cam.setup.setup"
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
- `upload.method`: Choose `"API"` or `"SFTP"` for upload method
- **For API upload** (`upload.method: "API"`):
  - `upload.api.url`: Your upload API address (leave empty to use test mode)
  - `upload.api.key`: Your API key
  - `upload.api.timeout_seconds`: Request timeout
- **For SFTP upload** (`upload.method: "SFTP"`):
  - `upload.sftp.host`: SFTP server hostname
  - `upload.sftp.port`: SFTP server port (usually 22)
  - `upload.sftp.user`: SFTP username
  - `upload.sftp.password`: SFTP password
  - `upload.sftp.remote_path`: Remote directory path for uploads
  - `upload.sftp.timeout_seconds`: Connection timeout

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

### Python/dependency issues

Reinstall the package:
```bash
sudo systemctl stop aero-pi-cam
~/aero-pi-cam-venv/bin/pip install --force-reinstall git+https://github.com/CaenFalaisePlaneurs/aero-pi-cam.git
sudo systemctl start aero-pi-cam
```

### Camera connection issues

Test RTSP URL manually:
```bash
ffmpeg -rtsp_transport tcp -i "rtsp://..." -frames:v 1 test.jpg
```

Check camera network connectivity and verify RTSP credentials.

### API/SFTP upload issues

Check the service logs for upload errors:
```bash
sudo journalctl -u aero-pi-cam -n 50
```

Verify your API endpoint or SFTP server is accessible and credentials are correct.

---

## Configuration

See `config.example.yaml` for all configuration options.

To edit your configuration:
```bash
sudo nano /etc/aero-pi-cam/config.yaml
```

---

## EXIF and XMP Metadata

All captured JPEG images automatically include embedded metadata in both EXIF and XMP formats. See [Advanced Usage](ADVANCED_USAGE.html) for details.

---

## Upload Methods

The service supports two upload methods: **API** and **SFTP**. Configure the method using `upload.method` in `config.yaml`. See [Advanced Usage](ADVANCED_USAGE.html) for API contract details.

---

## Uninstallation

**What gets removed:**
- ✅ Python package files
- ✅ Systemd service file (`/etc/systemd/system/aero-pi-cam.service`)
- ✅ Service is stopped and disabled

**What is preserved (intentionally):**
- 📁 Configuration file (`/etc/aero-pi-cam/config.yaml`) - following Debian best practices

**Steps:**

1. Stop and disable the service:
```bash
sudo /home/$(whoami)/aero-pi-cam-venv/bin/python -m aero_pi_cam.setup.uninstall
```

2. Remove the Python package:
```bash
~/aero-pi-cam-venv/bin/pip uninstall aero-pi-cam
```

3. (Optional) Remove the virtual environment:
```bash
rm -rf ~/aero-pi-cam-venv
```

---

## Help

We recommend following our installation guides, as no other installation methods are really tested. Help is provided on a volunteer basis by the maintainers. We cannot guarantee response times or provide commercial help.

---

## License

GPL-3.0 - See [LICENSE](LICENSE) file for details.

This project is open source and available under the GNU General Public License v3.0.

Copyright (C) 2026 Caen Falaise Planeurs
