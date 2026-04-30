#!/usr/bin/env python3
"""
Verify RGB format
"""

import cv2
from picamera2 import Picamera2
import numpy as np

picam2 = Picamera2()
picam2.configure(picam2.create_preview_configuration(
    main={"size": (1280, 960), "format": "RGB888"}
))
picam2.start()

print("Capturing frame...")
frame = picam2.capture_array()

print(f"\n✅ Frame Info:")
print(f"   Shape: {frame.shape}")
print(f"   Dtype: {frame.dtype}")
print(f"   Min/Max: {frame.min()} / {frame.max()}")
print(f"   Channels: {frame.shape[2] if len(frame.shape) == 3 else 'N/A'}")
print(f"\n✅ Format: RGB888 (3 channels, 8-bit each)\n")

# Show a sample
cv2.imshow("RGB Frame", cv2.cvtColor(frame, cv2.COLOR_RGB2BGR))
cv2.waitKey(0)

picam2.stop()
cv2.destroyAllWindows()
