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
SERVICE_NAME="aero-pi-cam"
CONFIG_BACKUP_DIR="$HOME/aero-pi-cam-config-backup"

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
echo "  - Configuration file (config.yaml) - will be backed up to $CONFIG_BACKUP_DIR"
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
echo -e "${GREEN}[2/4]${NC} Removing systemd service file..."
if [ -f "/etc/systemd/system/$SERVICE_NAME.service" ]; then
    rm -f "/etc/systemd/system/$SERVICE_NAME.service"
    systemctl daemon-reload
    systemctl reset-failed 2>/dev/null || true
    echo "✓ Service file removed"
else
    echo "Service file not found (may have been already removed)"
fi

# Step 3: Backup configuration files
echo -e "${GREEN}[3/4]${NC} Backing up configuration files..."
if [ -d "$INSTALL_DIR" ]; then
    # Create backup directory
    mkdir -p "$CONFIG_BACKUP_DIR"
    
    # Backup config.yaml if it exists
    if [ -f "$INSTALL_DIR/config.yaml" ]; then
        cp "$INSTALL_DIR/config.yaml" "$CONFIG_BACKUP_DIR/config.yaml"
        echo "✓ Configuration backed up to $CONFIG_BACKUP_DIR/config.yaml"
    else
        echo "No config.yaml found to backup"
    fi
    
    # Also backup config.example.yaml for reference
    if [ -f "$INSTALL_DIR/config.example.yaml" ]; then
        cp "$INSTALL_DIR/config.example.yaml" "$CONFIG_BACKUP_DIR/config.example.yaml"
    fi
    
    # Set ownership of backup directory
    if [ -n "$SUDO_USER" ]; then
        chown -R "$SUDO_USER:$SUDO_USER" "$CONFIG_BACKUP_DIR"
    fi
else
    echo "Installation directory not found, skipping backup"
fi

# Step 4: Remove installation directory
echo -e "${GREEN}[4/4]${NC} Removing installation directory..."
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
if [ -d "$CONFIG_BACKUP_DIR" ] && [ -f "$CONFIG_BACKUP_DIR/config.yaml" ]; then
    echo -e "${GREEN}Your configuration has been backed up to:${NC}"
    echo "  $CONFIG_BACKUP_DIR/config.yaml"
    echo ""
    echo "To restore it after reinstalling, copy it back:"
    echo "  cp $CONFIG_BACKUP_DIR/config.yaml /opt/webcam-cfp/config.yaml"
fi
echo ""
echo "To reinstall, run:"
    echo "  curl -fsSL https://raw.githubusercontent.com/CaenFalaisePlaneurs/aero-pi-cam/main/install.sh | sudo bash"

