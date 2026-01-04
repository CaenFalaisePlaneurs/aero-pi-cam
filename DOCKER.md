# Docker Development Environment

**⚠️ Development/Testing Only**: This Docker setup is intended for **development and testing purposes only**. For production deployment, use the systemd service on Raspberry Pi as described in [README.md](README.md).

This Docker setup allows you to test the aero-pi-cam service in an isolated environment that mirrors the Raspberry Pi configuration, without affecting your local system.

## Features

- ✅ **Python 3.13.5** - Matches Raspberry Pi OS version
- ✅ **Isolated environment** - No impact on local system
- ✅ **Same dependencies** - ffmpeg, Python packages, etc.
- ✅ **Easy testing** - Run, test, and remove without side effects
- ✅ **Configurable** - Mount config file for easy editing

## Prerequisites

- Docker installed ([Install Docker](https://docs.docker.com/get-docker/))
- Docker Compose (usually included with Docker Desktop)

## Quick Start

### 1. Create configuration file (IMPORTANT - do this first!)

**You must create `config.yaml` locally before running Docker**, otherwise the volume mount will fail:

```bash
cp config.example.yaml config.yaml
# Edit config.yaml with your settings
nano config.yaml
```

### 2. Build the Docker image

```bash
docker build -t aero-pi-cam:latest .
```

### 3. Run the container

**Option A: Using Docker directly**

```bash
docker run -d \
  --name aero-pi-cam \
  --network host \
  --restart unless-stopped \
  -v $(pwd)/config.yaml:/opt/webcam-cfp/config.yaml:ro \
  aero-pi-cam:latest
```

**Option B: Using Docker Compose (Recommended)**

```bash
docker-compose up -d
```

### 4. View logs

```bash
# Docker
docker logs -f aero-pi-cam

# Docker Compose
docker-compose logs -f
```

### 5. Stop and remove

```bash
# Docker
docker stop aero-pi-cam
docker rm aero-pi-cam

# Docker Compose
docker-compose down
```

## Configuration

### Mounting Configuration File

**Yes, the container uses your local `config.yaml` file!**

The `docker-compose.yml` mounts your local config file:
```yaml
volumes:
  - ./config.yaml:/opt/webcam-cfp/config.yaml:rw
```

This means:
- ✅ Your local `./config.yaml` is used inside the container
- ✅ Changes to the local file are immediately available (restart container to reload)
- ✅ The `:ro` flag makes it read-only in the container (container cannot modify it)

**Important**: You must create `config.yaml` locally first, otherwise Docker will create a directory instead of a file and the app will fail.

To test different configurations, just edit your local `config.yaml` and restart:

```bash
# Edit config
nano config.yaml

# Restart container to reload
docker-compose restart
```

Or manually mount with Docker:

```bash
docker run -d \
  --name aero-pi-cam \
  --network host \
  -v $(pwd)/config.yaml:/opt/webcam-cfp/config.yaml:ro \
  aero-pi-cam:latest
```

### Environment Variables

You can override configuration via environment variables:

```bash
docker run -d \
  --name aero-pi-cam \
  --network host \
  -e CONFIG_PATH=/opt/webcam-cfp/config.yaml \
  -e DEBUG_MODE=true \
  aero-pi-cam:latest
```

#### DEBUG_MODE

Enable debug mode to use a local dummy API server for testing:

```bash
# Using Docker Compose
DEBUG_MODE=true docker-compose up -d

# Or set in .env file
echo "DEBUG_MODE=true" >> .env
docker-compose up -d

# Using Docker directly
docker run -d \
  --name aero-pi-cam \
  --network host \
  -e DEBUG_MODE=true \
  -v $(pwd)/.debug:/opt/webcam-cfp/.debug:rw \
  aero-pi-cam:latest
```

When `DEBUG_MODE=true`:
- A dummy API server automatically starts on `localhost:8000`
- All image uploads go to the dummy server (ignores `api.url` if set)
- Images are saved to `.debug/cam/{location}-{camera_name}.jpg` with static filenames
- Example: `.debug/cam/LFAS-hangar_2.jpg`
- Images are accessible from outside the container via the mounted volume
- Useful for testing without an external API, verifying image quality, and debugging capture issues

**Testing without API:**
You can also test without setting `api.url` in `config.yaml`. The dummy server will automatically be used even without `DEBUG_MODE=true`.

## Network Configuration

### Host Network Mode (Default)

The container uses `host` network mode to access:
- RTSP cameras on your local network
- External APIs (Aviation Weather API, your upload API)
- Dummy API server (port 8000) when in debug mode

```yaml
network_mode: host
```

**Note**: With host networking, the dummy API server (when `DEBUG_MODE=true`) is accessible on `localhost:8000` from the host machine.

### Bridge Network Mode

If you need port isolation, use bridge mode:

```yaml
# In docker-compose.yml, comment out network_mode and use:
ports:
  - "8000:8000"  # Dummy API server port (when DEBUG_MODE=true)
  - "8080:8080"  # Example port mapping
```

**Note**: Bridge mode may prevent access to RTSP cameras on your local network unless you configure Docker networking appropriately.

## Testing Workflow

### 1. Build and test locally

```bash
# Build image
docker build -t aero-pi-cam:latest .

# Run interactively to see output
docker run --rm -it \
  --network host \
  -v $(pwd)/config.yaml:/opt/webcam-cfp/config.yaml:ro \
  aero-pi-cam:latest
```

### 2. Test with different configurations

```bash
# Test config 1
cp config.test1.yaml config.yaml
docker-compose restart

# Test config 2
cp config.test2.yaml config.yaml
docker-compose restart
```

### 3. Run tests inside container

```bash
# Build with test dependencies
docker run --rm -it \
  -v $(pwd):/opt/webcam-cfp \
  aero-pi-cam:latest \
  bash -c "venv/bin/pip install -r requirements-dev.txt && venv/bin/pytest"
```

## Development

### Interactive shell

Get a shell inside the container:

```bash
docker run --rm -it \
  --network host \
  -v $(pwd):/opt/webcam-cfp \
  aero-pi-cam:latest \
  bash
```

### Live code editing

Mount the source code for live development:

```bash
docker run --rm -it \
  --network host \
  -v $(pwd)/src:/opt/webcam-cfp/src \
  -v $(pwd)/config.yaml:/opt/webcam-cfp/config.yaml:ro \
  aero-pi-cam:latest
```

## Troubleshooting

### Container won't start

1. Check logs:
   ```bash
   docker logs aero-pi-cam
   ```

2. Check configuration:
   ```bash
   docker run --rm -it aero-pi-cam:latest \
     venv/bin/python -c "from src.config import load_config; load_config()"
   ```

### Can't access RTSP camera

- Ensure `network_mode: host` is set
- Check camera IP is accessible from host
- Verify RTSP URL in config.yaml

### Permission issues

If you encounter permission issues with mounted volumes:

```bash
# Fix ownership (Linux/Mac)
sudo chown -R $USER:$USER config.yaml

# Or run container with user mapping
docker run --rm -it \
  --user $(id -u):$(id -g) \
  aero-pi-cam:latest
```

### Python version mismatch

Verify Python version in container:

```bash
docker run --rm aero-pi-cam:latest venv/bin/python --version
# Should show: Python 3.13.5
```

## Comparison with Raspberry Pi

| Aspect | Raspberry Pi | Docker |
|--------|-------------|--------|
| Python | 3.13.5 (system) | 3.13.5 (container) |
| Service | systemd | Docker restart policy |
| Logs | journalctl | docker logs |
| Config | `/opt/webcam-cfp/config.yaml` | Mounted volume |
| Network | Direct | Host mode (for RTSP) |
| Dependencies | System packages | Container packages |

## Cleanup

Remove everything:

```bash
# Stop and remove container
docker-compose down

# Remove image
docker rmi aero-pi-cam:latest

# Remove volumes (if any)
docker volume prune
```

## CI/CD Integration

Example GitHub Actions workflow:

```yaml
name: Test Docker Build

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Build Docker image
        run: docker build -t aero-pi-cam:test .
      - name: Test configuration
        run: docker run --rm aero-pi-cam:test venv/bin/python -c "from src.config import load_config; load_config()"
```

