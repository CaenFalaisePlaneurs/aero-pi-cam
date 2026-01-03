#!/bin/bash
# One-command installation script for aero-pi-cam on Raspberry Pi
# Usage: curl -fsSL https://raw.githubusercontent.com/CaenFalaisePlaneurs/aero-pi-cam/main/install.sh | bash
# Or: bash <(curl -fsSL https://raw.githubusercontent.com/CaenFalaisePlaneurs/aero-pi-cam/main/install.sh)

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
INSTALL_DIR="/opt/webcam-cfp"
SERVICE_USER="${SUDO_USER:-$USER}"
REPO_URL="${REPO_URL:-https://github.com/CaenFalaisePlaneurs/aero-pi-cam.git}"
BRANCH="${BRANCH:-main}"

echo -e "${GREEN}╔════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║  Webcam Capture Service Installer     ║${NC}"
echo -e "${GREEN}╚════════════════════════════════════════╝${NC}"
echo ""

# Check if running as root or with sudo
if [ "$EUID" -ne 0 ]; then
    echo -e "${YELLOW}Note: This script requires sudo privileges.${NC}"
    echo "Please run with: sudo bash install.sh"
    echo "Or use: curl -fsSL URL | sudo bash"
    exit 1
fi

# Check Python version
echo -e "${GREEN}[1/7]${NC} Checking Python version..."
PYTHON_VERSION=$(python3 --version 2>&1 | awk '{print $2}')
echo "Found Python ${PYTHON_VERSION}"

if ! python3 -c "import sys; exit(0 if sys.version_info >= (3, 11) else 1)"; then
    echo -e "${RED}Error: Python 3.11 or higher is required. Found ${PYTHON_VERSION}${NC}"
    exit 1
fi

# Install system dependencies
echo -e "${GREEN}[2/7]${NC} Installing system dependencies..."
apt-get update -qq
apt-get install -y -qq ffmpeg python3-pip python3-venv git > /dev/null 2>&1 || {
    echo -e "${RED}Error: Failed to install system dependencies${NC}"
    exit 1
}
echo "✓ System dependencies installed"

# Create installation directory
echo -e "${GREEN}[3/7]${NC} Setting up installation directory..."
if [ -d "$INSTALL_DIR" ]; then
    echo -e "${YELLOW}Directory $INSTALL_DIR already exists.${NC}"
    read -p "Do you want to update the existing installation? (y/N) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "Installation cancelled."
        exit 0
    fi
    echo "Updating existing installation..."
    cd "$INSTALL_DIR"
    if [ -d ".git" ]; then
        git pull origin "$BRANCH" || echo "Warning: Could not pull latest changes"
    fi
else
    mkdir -p "$INSTALL_DIR"
    cd "$INSTALL_DIR"
    
    # Clone repository
    if [ -n "$REPO_URL" ] && [ "$REPO_URL" != "https://github.com/CaenFalaisePlaneurs/aero-pi-cam.git" ]; then
        echo "Cloning repository from $REPO_URL..."
        git clone -b "$BRANCH" "$REPO_URL" . || {
            echo -e "${RED}Error: Failed to clone repository${NC}"
            echo "Please ensure the repository URL is correct and accessible."
            exit 1
        }
    else
        echo -e "${YELLOW}Warning: REPO_URL not set. Please copy project files manually to $INSTALL_DIR${NC}"
        echo "Or set REPO_URL environment variable before running this script."
        exit 1
    fi
fi

# Set ownership
chown -R "$SERVICE_USER:$SERVICE_USER" "$INSTALL_DIR"
echo "✓ Installation directory ready"

# Create virtual environment
echo -e "${GREEN}[4/7]${NC} Creating Python virtual environment..."
if [ -d "$INSTALL_DIR/venv" ]; then
    echo "Virtual environment already exists, skipping..."
else
    sudo -u "$SERVICE_USER" python3 -m venv "$INSTALL_DIR/venv"
    echo "✓ Virtual environment created"
fi

# Install Python dependencies
echo -e "${GREEN}[5/7]${NC} Installing Python dependencies..."
sudo -u "$SERVICE_USER" "$INSTALL_DIR/venv/bin/pip" install --upgrade pip setuptools wheel -q
sudo -u "$SERVICE_USER" "$INSTALL_DIR/venv/bin/pip" install -r "$INSTALL_DIR/requirements.txt" -q
echo "✓ Python dependencies installed"

# Setup configuration
echo -e "${GREEN}[6/7]${NC} Setting up configuration..."
if [ ! -f "$INSTALL_DIR/config.yaml" ]; then
    if [ -f "$INSTALL_DIR/config.example.yaml" ]; then
        cp "$INSTALL_DIR/config.example.yaml" "$INSTALL_DIR/config.yaml"
        chown "$SERVICE_USER:$SERVICE_USER" "$INSTALL_DIR/config.yaml"
        echo -e "${YELLOW}⚠ Configuration file created from example.${NC}"
        echo -e "${YELLOW}⚠ Please edit $INSTALL_DIR/config.yaml before starting the service.${NC}"
    else
        echo -e "${YELLOW}Warning: config.example.yaml not found${NC}"
    fi
else
    echo "Configuration file already exists, skipping..."
fi

# Install systemd service
echo -e "${GREEN}[7/7]${NC} Installing systemd service..."
if [ -f "$INSTALL_DIR/aero-pi-cam.service" ]; then
    cp "$INSTALL_DIR/aero-pi-cam.service" /etc/systemd/system/
    systemctl daemon-reload
    systemctl enable aero-pi-cam.service
    echo "✓ Systemd service installed and enabled"
    
    # Check if config exists and is configured
    if [ -f "$INSTALL_DIR/config.yaml" ]; then
        # Check if config has been edited (not just example values)
        if grep -q "secret-api-key" "$INSTALL_DIR/config.yaml" || grep -q "api.example.com" "$INSTALL_DIR/config.yaml"; then
            echo -e "${YELLOW}⚠ Configuration file still contains example values.${NC}"
            echo -e "${YELLOW}⚠ Please edit $INSTALL_DIR/config.yaml before starting the service.${NC}"
            echo ""
            read -p "Do you want to start the service anyway? (y/N) " -n 1 -r
            echo
            if [[ $REPLY =~ ^[Yy]$ ]]; then
                systemctl start aero-pi-cam.service
                echo "✓ Service started (but may fail without proper configuration)"
            else
                echo "Service installed but not started. Edit config and start with: sudo systemctl start aero-pi-cam"
            fi
        else
            # Config looks configured, ask to start
            echo ""
            read -p "Do you want to start the service now? (y/N) " -n 1 -r
            echo
            if [[ $REPLY =~ ^[Yy]$ ]]; then
                systemctl start aero-pi-cam.service
                echo "✓ Service started"
                echo ""
                echo "Check status with: sudo systemctl status aero-pi-cam"
                echo "View logs with: sudo journalctl -u aero-pi-cam -f"
            else
                echo "Service installed but not started. Start it with: sudo systemctl start aero-pi-cam"
            fi
        fi
    else
        echo -e "${YELLOW}⚠ Configuration file not found.${NC}"
        echo "Service installed but not started. Create config and start with: sudo systemctl start aero-pi-cam"
    fi
else
    echo -e "${RED}Error: aero-pi-cam.service file not found${NC}"
    exit 1
fi

echo ""
echo -e "${GREEN}╔════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║  Installation Complete!               ║${NC}"
echo -e "${GREEN}╚════════════════════════════════════════╝${NC}"
echo ""
echo "Next steps:"
echo "1. Edit configuration: sudo nano $INSTALL_DIR/config.yaml"
echo "2. Start service: sudo systemctl start aero-pi-cam"
echo "3. Check status: sudo systemctl status aero-pi-cam"
echo "4. View logs: sudo journalctl -u aero-pi-cam -f"
echo ""
echo "Service will start automatically on boot."

