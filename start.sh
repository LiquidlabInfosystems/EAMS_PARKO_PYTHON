#!/bin/bash
# /home/pi/myapp/start.sh

# Activate virtual environment
source /home/admin/dev/EAMS/env/bin/activate

# Set environment variables if needed
export PYTHONPATH="/home/admin/dev/EAMS:$PYTHONPATH"
export APP_ENV="production"

# Change to your app directory
cd /home/admin/dev/EAMS

# Start your application
python attendance_gui.py