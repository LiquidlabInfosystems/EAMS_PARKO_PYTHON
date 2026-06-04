#!/bin/bash
# System Dependencies Setup for EAMS_PARKO_PYTHON
# This script installs all required system-level packages

echo "=================================================="
echo "Installing System Dependencies for EAMS"
echo "=================================================="

# Update package list
echo "[1/2] Updating package lists..."
sudo apt-get update

# Install required system libraries
echo "[2/2] Installing required libraries..."
sudo apt-get install -y \
  libxcb-cursor0 \
  libgl1-mesa-glx \
  libxkbcommon0 \
  libdbus-1-3 \
  libcap-dev

echo ""
echo "=================================================="
echo "✅ System dependencies installed successfully!"
echo "=================================================="
echo ""
echo "Next step: Activate the virtual environment and install Python packages:"
echo "  cd /home/admin/EAMS_PARKO_PYTHON"
echo "  source env/bin/activate"
echo "  pip install -r requirements.txt"
echo ""
