# Testing Pip Package Installation

This document describes how to test the pip package installation process using Docker.

## Overview

The test verifies that:
1. The package can be installed via `pip install .`
2. Entry points (`webcam` and `aero-pi-cam-setup`) are correctly installed
3. Package data (fonts, images) are included in the installation
4. The setup command is callable
5. The package can be uninstalled cleanly

## Running the Test

### Option 1: Using Docker Compose (Recommended)

```bash
docker-compose -f docker-compose.test.yml build
docker-compose -f docker-compose.test.yml run --rm test-pip-install
```

### Option 2: Using Docker Directly

```bash
docker build -f Dockerfile.test -t aero-pi-cam-test .
docker run --rm aero-pi-cam-test
```

## What the Test Does

1. **Installs the package** from the local directory (simulating `pip install git+...`)
2. **Verifies entry points** - Checks that `webcam` and `aero-pi-cam-setup` commands are available
3. **Verifies package data** - Ensures fonts and images are included in the installed package
4. **Tests setup command** - Verifies the setup command exists (full systemd setup won't work in Docker)
5. **Tests uninstall** - Verifies `pip uninstall` works correctly and removes entry points

## Test Results

All tests pass successfully! ✅

## Expected Output

You should see:
```
╔════════════════════════════════════════╗
║  Testing pip Package Installation     ║
╚════════════════════════════════════════╝

[Test 1/5] Installing package from local directory...
✓ Package installed successfully

[Test 2/5] Verifying entry points...
✓ 'webcam' command found
✓ 'aero-pi-cam-setup' command found

[Test 3/5] Verifying package data...
✓ Font file found
✓ Images directory found
✓ Icon files found
✓ Package data verified

[Test 4/5] Testing setup command...
✓ Setup command is callable
  (Note: Full setup test requires systemd, skipping in Docker)

[Test 5/5] Testing package uninstall...
✓ Package uninstalled successfully
✓ Entry points removed

╔════════════════════════════════════════╗
║  All Tests Passed!                    ║
╚════════════════════════════════════════╝
```

## Limitations

- **Systemd service installation** cannot be fully tested in Docker (systemd doesn't run in containers)
- The setup command will show an error about missing systemd, which is expected
- For full systemd testing, use a Raspberry Pi or VM with systemd

## Troubleshooting

If tests fail:
1. Check that all files are present (especially `setup.py`, `pyproject.toml`, `MANIFEST.in`)
2. Verify package structure is correct (`aero_pi_cam/` directory exists)
3. Check that fonts and images are in the correct location (`aero_pi_cam/fonts/`, `aero_pi_cam/images/`)

