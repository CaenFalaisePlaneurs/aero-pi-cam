# Dockerfile for aero-pi-cam - Testing environment matching Raspberry Pi
# Uses Python 3.13.5 to match Raspberry Pi OS

FROM python:3.13.5-slim

# Set metadata
LABEL maintainer="Nicolas Massart <contact@caenfalaiseplaneurs.fr>"
LABEL description="Webcam Capture Service - Test Environment"

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    DEBIAN_FRONTEND=noninteractive \
    INSTALL_DIR=/opt/webcam-cfp \
    CONFIG_PATH=/opt/webcam-cfp/config.yaml

# Install system dependencies (matching Raspberry Pi setup)
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        ffmpeg \
        git \
        ca-certificates \
        && \
    rm -rf /var/lib/apt/lists/*

# Create application directory
WORKDIR ${INSTALL_DIR}

# Copy project files
COPY . .

# Create virtual environment and install dependencies
RUN python3 -m venv venv && \
    venv/bin/pip install --upgrade pip setuptools wheel && \
    venv/bin/pip install -r requirements.txt

# Create config from example if it doesn't exist
RUN if [ ! -f config.yaml ]; then \
        cp config.example.yaml config.yaml; \
    fi

# Set permissions
RUN chmod +x install.sh uninstall.sh setup-venv.sh || true

# Expose any ports if needed (none for this service, but kept for future)
# EXPOSE 8080

# Health check (optional - checks if Python can import the modules)
# Disabled by default - uncomment if needed
# HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
#     CMD venv/bin/python -c "from src.config import load_config; load_config()" || exit 1

# Default command - run the application directly (not via systemd)
CMD ["venv/bin/python", "-m", "src.main"]

