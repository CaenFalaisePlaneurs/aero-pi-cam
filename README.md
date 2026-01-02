# Webcam Capture Service

A Node.js/TypeScript background service for Raspberry Pi that captures images from an IP camera via RTSP/ffmpeg on a day/night schedule and uploads them to a remote API.

## Features

- **Scheduled capture**: Different intervals for day and night based on sunrise/sunset
- **RTSP capture**: Reliable frame grabbing via ffmpeg
- **API upload**: PUT requests with retry logic and exponential backoff
- **METAR overlay**: Optional weather information overlay from Aviation Weather API
- **Icon support**: Add SVG icons to overlay (supports URLs, local files, or inline SVG)
- **Systemd service**: Auto-start, auto-restart, journald logging

## Requirements

- Raspberry Pi 4B (or similar)
- Node.js 20+ (via nvm)
- ffmpeg
- IP camera with RTSP support (e.g., VIGI C340)

## Installation

### 1. Install system dependencies

```bash
sudo apt update
sudo apt install ffmpeg
```

### 2. Install nvm and Node.js

```bash
curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.0/install.sh | bash
source ~/.bashrc
nvm install 20
```

### 3. Clone and setup project

```bash
sudo mkdir -p /opt/webcam-cfp
sudo chown pi:pi /opt/webcam-cfp
cd /opt/webcam-cfp
# Copy project files here
nvm use
npm install
npm run build
```

### 4. Configure

```bash
cp config.example.yaml config.yaml
nano config.yaml
```

Edit the configuration:
- `camera.rtsp_url`: Your camera's RTSP URL
- `location`: GPS coordinates for sunrise/sunset calculation
- `api.url`: Your upload API endpoint
- `api.key`: Your API key
- `metar.enabled`: Set to `true` to enable weather overlay

### 5. Test locally

```bash
npm run webcam
```

Press Ctrl+C to stop.

### 6. Install as systemd service

```bash
# Update the service file with your Node.js path
# Run: nvm which node
# Edit webcam-cfp.service and update the paths

sudo cp webcam-cfp.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable webcam-cfp
sudo systemctl start webcam-cfp
```

### 7. Check status and logs

```bash
sudo systemctl status webcam-cfp
sudo journalctl -u webcam-cfp -f
```

## Configuration

See `config.example.yaml` for all options:

| Section | Option | Description |
|---------|--------|-------------|
| camera | rtsp_url | RTSP URL with credentials |
| location | name | Location identifier |
| location | latitude/longitude | GPS coordinates for sun calculation |
| location | timezone | Timezone (e.g., Europe/Paris) |
| schedule | day_interval_minutes | Capture interval during day |
| schedule | night_interval_minutes | Capture interval during night |
| api | url | Upload API endpoint |
| api | key | Bearer token for authentication |
| api | timeout_seconds | Request timeout |
| metar | enabled | Enable/disable weather overlay |
| metar | icao_code | Airport code for METAR data |
| metar | icon | Optional icon configuration (url/path/svg, size, position) |

### Icon Support

The overlay supports adding SVG icons from [SVGRepo Dazzle Line Icons](https://www.svgrepo.com/collection/dazzle-line-icons/) or any other SVG source:

- **url**: Direct URL to SVG file (e.g., from SVGRepo)
- **path**: Local file path to SVG
- **svg**: Inline SVG string
- **size**: Icon size in pixels (8-128, default: 24)
- **position**: "left" or "right" of text (default: "left")

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

Expected response:

```json
{
  "id": "uuid",
  "received_at": "2026-01-02T15:30:05Z",
  "size_bytes": 245000
}
```

## Development

```bash
# Install dependencies
npm install

# Build
npm run build

# Run tests
npm test

# Lint
npm run lint

# Format
npm run format
```

## License

GPL-3.0 - See [LICENSE](LICENSE) file for details.

This project is open source and available under the GNU General Public License v3.0.

