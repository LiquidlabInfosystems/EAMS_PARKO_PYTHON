#!/bin/bash

# Set display (important for GUI)
export DISPLAY=:0

# Qt configuration for proper platform support
export QT_QPA_PLATFORM=xcb
export QT_DEBUG_PLUGINS=0
# Virtual keyboard is built-in (modules/virtual_keyboard.py) — no system OSK needed

# Rotate screen (Wayland)
# wlr-randr --output DSI-1 --transform 90

# Go to project directory
cd /home/admin/EAMS_PARKO_PYTHON

# Activate virtual environment
source env/bin/activate

# Kill any previous instance (avoid camera busy issue)
pkill -f attendance_gui.py

# Run your app (logs go to systemd journal visible with journalctl)
python -u attendance_gui.py
