#!/bin/bash

# Set display (important for GUI)
export DISPLAY=:0

# Optional: force Qt to use X11
# export QT_QPA_PLATFORM=xcb

# Rotate screen (Wayland)
# wlr-randr --output DSI-1 --transform 90

# Go to project directory
cd /home/parko-thrissur/EAMS_PARKO_PYTHON

# Activate virtual environment
source env/bin/activate

# Kill any previous instance (avoid camera busy issue)
pkill -f attendance_gui.py

# Run your app (logs go to systemd journal visible with journalctl)
python -u attendance_gui.py
