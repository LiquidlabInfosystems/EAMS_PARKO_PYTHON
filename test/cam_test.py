#!/usr/bin/env python3
"""
Simple Picamera2 Camera Feed
Displays live camera preview with 180-degree rotation
"""


from picamera2 import Picamera2
import cv2
import numpy as np


def main():
    # Initialize camera
    picam2 = Picamera2()
    
    # Configure camera for preview
    config = picam2.create_preview_configuration(
        main={"size": (1280, 960), "format": "RGB888"}
    )
    
    picam2.configure(config)
    picam2.start()
    
    print("Camera started. Press 'q' to quit.")
    
    try:
        while True:
            # Capture frame
            frame = picam2.capture_array()
            
            # Rotate frame 180 degrees
            # frame = cv2.rotate(frame, cv2.ROTATE_180)
            
            # Display frame
            cv2.imshow("Picamera2 Feed", frame)
            
            # Press 'q' to quit
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break
                
    except KeyboardInterrupt:
        print("\nStopping camera...")
    
    finally:
        # Cleanup
        cv2.destroyAllWindows()
        picam2.stop()
        print("Camera stopped.")


if __name__ == "__main__":
    main()
