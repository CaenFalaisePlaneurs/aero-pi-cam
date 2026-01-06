#!/bin/bash
# Uninstall script for aero-pi-cam
# Usage: sudo bash uninstall.sh

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
INSTALL_DIR="/opt/webcam-cfp"
CONFIG_DIR="/etc/aero-pi-cam"
SERVICE_NAME="aero-pi-cam"

echo -e "${RED}╔════════════════════════════════════════╗${NC}"
echo -e "${RED}║  Webcam Capture Service Uninstaller   ║${NC}"
echo -e "${RED}╚════════════════════════════════════════╝${NC}"
echo ""

# Check if running as root or with sudo
if [ "$EUID" -ne 0 ]; then
    echo -e "${YELLOW}Note: This script requires sudo privileges.${NC}"
    echo "Please run with: sudo bash uninstall.sh"
    exit 1
fi

# Confirm uninstallation
echo -e "${YELLOW}This will completely remove the aero-pi-cam installation.${NC}"
echo ""
echo "The following will be removed:"
echo "  - Systemd service (aero-pi-cam)"
echo "  - Installation directory ($INSTALL_DIR)"
echo "  - All application files"
echo ""
echo -e "${GREEN}The following will be preserved:${NC}"
echo "  - Configuration directory ($CONFIG_DIR) - following Debian best practices"
echo ""
read -p "Are you sure you want to continue? (yes/NO) " -r
echo
if [[ ! $REPLY =~ ^[Yy][Ee][Ss]$ ]]; then
    echo "Uninstallation cancelled."
    exit 0
fi

# Step 1: Stop and disable service
echo -e "${GREEN}[1/4]${NC} Stopping and disabling systemd service..."
if systemctl is-active --quiet "$SERVICE_NAME" 2>/dev/null; then
    systemctl stop "$SERVICE_NAME"
    echo "✓ Service stopped"
else
    echo "Service was not running"
fi

if systemctl is-enabled --quiet "$SERVICE_NAME" 2>/dev/null; then
    systemctl disable "$SERVICE_NAME"
    echo "✓ Service disabled"
else
    echo "Service was not enabled"
fi

# Step 2: Remove systemd service file
echo -e "${GREEN}[2/3]${NC} Removing systemd service file..."
if [ -f "/etc/systemd/system/$SERVICE_NAME.service" ]; then
    rm -f "/etc/systemd/system/$SERVICE_NAME.service"
    systemctl daemon-reload
    systemctl reset-failed 2>/dev/null || true
    echo "✓ Service file removed"
else
    echo "Service file not found (may have been already removed)"
fi

# Step 3: Remove installation directory
echo -e "${GREEN}[3/3]${NC} Removing installation directory..."
if [ -d "$INSTALL_DIR" ]; then
    rm -rf "$INSTALL_DIR"
    echo "✓ Installation directory removed"
else
    echo "Installation directory not found"
fi

echo ""
echo -e "${GREEN}╔════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║  Uninstallation Complete!             ║${NC}"
echo -e "${GREEN}╚════════════════════════════════════════╝${NC}"
echo ""
echo "The aero-pi-cam service has been completely removed."
echo ""
if [ -d "$CONFIG_DIR" ]; then
    echo -e "${GREEN}Your configuration has been preserved at:${NC}"
    echo "  $CONFIG_DIR/config.yaml"
    echo ""
    echo "Following Debian best practices, configuration files are not removed."
    echo "If you reinstall, your existing configuration will be used."
fi
echo ""
echo "To reinstall, run:"
echo "  curl -fsSL https://raw.githubusercontent.com/CaenFalaisePlaneurs/aero-pi-cam/main/install.sh | sudo bash"

