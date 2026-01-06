#!/bin/bash
# Setup script for creating a Python virtual environment

set -e

PYTHON_VERSION="${1:-3.13.5}"

echo "Setting up Python virtual environment for aero-pi-cam..."
echo "Target Python version: ${PYTHON_VERSION}"

# Check if Python version is available
if ! command -v "python${PYTHON_VERSION}" &> /dev/null && ! python3 --version | grep -q "${PYTHON_VERSION}"; then
    echo "Warning: Python ${PYTHON_VERSION} not found. Using system python3."
    PYTHON_CMD="python3"
else
    # Try to find the right Python command
    if command -v "python${PYTHON_VERSION}" &> /dev/null; then
        PYTHON_CMD="python${PYTHON_VERSION}"
    else
        PYTHON_CMD="python3"
    fi
fi

echo "Using: $(${PYTHON_CMD} --version)"

# Create virtual environment
echo "Creating virtual environment..."
${PYTHON_CMD} -m venv venv

# Activate and upgrade pip
echo "Activating virtual environment and upgrading pip..."
source venv/bin/activate
pip install --upgrade pip setuptools wheel

# Install dependencies
echo "Installing dependencies..."
pip install -r requirements.txt

echo ""
echo "✓ Virtual environment created successfully!"
echo ""
echo "To activate the virtual environment, run:"
echo "  source venv/bin/activate"
echo ""
echo "To deactivate, run:"
echo "  deactivate"
echo ""
echo "To install dev dependencies, run:"
echo "  pip install -r requirements-dev.txt"

