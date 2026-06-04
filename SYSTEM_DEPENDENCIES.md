# System Dependencies & Setup Guide

## System Requirements Fixed

### Issue Encountered
The GUI was flashing and immediately crashing with no visible error messages. 

**Root Cause:** Missing system library `libxcb-cursor0` required by Qt 6.5+ for the XCB platform plugin.

### Solution Applied
Installed the missing system dependency:
```bash
sudo apt-get install libxcb-cursor0
```

### All Required System Libraries

For the EAMS face recognition and attendance GUI system to work properly on Raspberry Pi (Debian Bookworm), install:

```bash
sudo apt-get update
sudo apt-get install -y \
  libxcb-cursor0          # Qt XCB platform plugin support \
  libgl1-mesa-glx         # OpenGL support \
  libxkbcommon0           # Keyboard handling \
  libdbus-1-3             # D-Bus communication \
  libcap-dev              # For python-prctl (picamera2 dependency)
```

Or run the automated setup script:
```bash
chmod +x install_system_deps.sh
./install_system_deps.sh
```

### Display Configuration

The GUI requires a valid X11 display. Ensure:

1. **DISPLAY environment variable is set:**
   ```bash
   export DISPLAY=:0
   ```

2. **Qt platform plugin configuration:**
   ```bash
   export QT_QPA_PLATFORM=xcb
   ```

These are automatically set in `start_attendance.sh`, so you can simply run:
```bash
./start_attendance.sh
```

### Python Environment

Python dependencies are specified in `requirements.txt`:

```bash
source env/bin/activate
pip install -r requirements.txt
```

### Camera & Hardware

The system uses:
- **Camera:** libcamera (for Raspberry Pi camera on Pi 4+)
- **Face Recognition:** InsightFace + ONNX Runtime (CPU inference on ARM64)
- **GUI Framework:** PySide6

All Python packages are compatible with Python 3.11 on ARM64 architecture.

### Testing

To verify everything is working:

```bash
# Test minimal GUI
python test_minimal_gui.py

# Test full attendance system  
python attendance_gui.py
```

### Known Issues & Solutions

| Issue | Solution |
|-------|----------|
| GUI flickers and disappears | Install `libxcb-cursor0` ✅ (FIXED) |
| "Could not load Qt platform plugin" | Set `DISPLAY=:0` and `QT_QPA_PLATFORM=xcb` |
| No camera feed | Ensure camera is enabled in `raspi-config` |
| CPU-only inference is slow | Normal for ARM64 - uses CPU fallback (no GPU) |

---

**Last Updated:** June 4, 2026  
**System:** Raspberry Pi 4 with 7" touchscreen, Debian Bookworm, Python 3.11
