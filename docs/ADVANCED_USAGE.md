---
layout: default
title: Advanced Usage
---

# Advanced Usage

This document covers advanced configuration options and features for aero-pi-cam.

## Installing Custom Fonts

If you want to use a custom font (ex. Poppins) for the overlay text, you can install it system-wide on your Raspberry Pi. The application will automatically use it if configured in `config.yaml`.

### Example: Install Poppins System-Wide on Raspberry Pi (Debian/Raspberry Pi OS)

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

### Alternative: User-Specific Installation

If you prefer to install the font in your home directory (no `sudo` required):

```bash
# Create fonts directory in your home
mkdir -p ~/fonts

# Download and copy font
wget https://github.com/google/fonts/raw/main/ofl/poppins/Poppins-Medium.ttf -O ~/fonts/Poppins-Medium.ttf

# Configure in config.yaml
# font_path: "~/fonts/Poppins-Medium.ttf"
```

## Configuring the Provider Logo

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

## Overriding Configuration Path

You can override the configuration file path using:

1. **Command-line argument** (highest priority):
```bash
python -m aero_pi_cam.core.main --config /path/to/custom-config.yaml
```

Or short form:
```bash
python -m aero_pi_cam.core.main -c /path/to/custom-config.yaml
```

2. **Environment variable** (when running manually):
```bash
export CONFIG_PATH=/path/to/custom-config.yaml
python -m aero_pi_cam.core.main
```

3. **Systemd service override** (when running as systemd service):

Edit the systemd service override:
```bash
sudo systemctl edit aero-pi-cam
```

Add the following:
```ini
[Service]
Environment="CONFIG_PATH=/path/to/custom-config.yaml"
```

Reload systemd and restart the service:
```bash
sudo systemctl daemon-reload
sudo systemctl restart aero-pi-cam
```

4. **Default**: `/etc/aero-pi-cam/config.yaml` (when running as systemd service) or `config.yaml` (when running manually from project directory)

The precedence order is: command-line argument > environment variable > default.

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

## Upload Methods

The service supports two upload methods: **API** and **SFTP**. Configure the method using `upload.method` in `config.yaml`.

### API Upload

**Note**: API upload contract only applies when `upload.method: "API"`.

See the [OpenAPI Specification](openapi.json) for the complete API contract, including request/response formats, headers, and authentication.

### SFTP Upload

**Note**: SFTP upload applies when `upload.method: "SFTP"`.

The service uploads images via SFTP to the configured remote server:
- **Filename format**: `{location}-{camera_name}.jpg` (same as API, e.g., `LFAS-hangar_2.jpg`)
- **Remote path**: Configured via `upload.sftp.remote_path` (e.g., `/public_html/cam/`)
- **Full path**: `{upload.sftp.remote_path}/{filename}` (e.g., `/public_html/cam/LFAS-hangar_2.jpg`)
- **Overwrite behavior**: Each upload overwrites the previous image with the same filename
- **Directory creation**: Remote directory is created automatically if it doesn't exist

## Installation Methods

**Recommended method:**

The recommended installation method is using the install scripts with systemd in a virtual environment, as described in the [main installation guide](README.html#installation). This method:
- Creates a virtual environment (`~/aero-pi-cam-venv`)
- Installs the package via pip
- Sets up systemd service for automatic startup
- Handles all system dependencies

**Installing from a specific release version:**

If you need to install a specific released version (not the latest), you can do so after following the standard installation steps. Replace the install command in Step 2 with:

```bash
~/aero-pi-cam-venv/bin/pip install git+https://github.com/CaenFalaisePlaneurs/aero-pi-cam.git@v1.0.0
```

Replace `v1.0.0` with the version tag you need. This is acceptable for released versions, though we recommend using the latest stable version.

**Not recommended:**

The following installation methods are **not recommended**:

- Installing from a specific branch (e.g., `@develop`) - use released versions only
- System-wide installation (without virtual environment)
- Manual installation without using the provided install scripts

**Help policy:**

We recommend following our installation guides, as no other installation methods are really tested. We provide help on a volunteer basis as maintainers. We cannot guarantee response times or provide commercial help.

