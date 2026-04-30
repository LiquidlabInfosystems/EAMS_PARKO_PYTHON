#!/usr/bin/env python3
"""
Test FPS with different settings
"""

import os
os.environ['GLOG_minloglevel'] = '2'
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'

import cv2
from picamera2 import Picamera2
from face_recognizer import FaceRecognizer
import time

recognizer = FaceRecognizer(
    detection_confidence=0.5,
    recognition_threshold=0.55,
    preprocessing_method='histogram',
    enable_liveness=False,
    use_face_alignment=False
)

picam2 = Picamera2()
config = picam2.create_preview_configuration(
    main={"size": (960, 720), "format": "RGB888"}
)
picam2.configure(config)
picam2.start()

print("\n✓ Testing FPS...")
print("Press 'q' to quit\n")

frame_count = 0
start_time = time.time()
process_every = 2  # Process every 2nd frame

while True:
    frame_rgb = picam2.capture_array()
    frame_bgr = cv2.cvtColor(frame_rgb, cv2.COLOR_RGB2BGR)
    
    frame_count += 1
    
    # Only process every Nth frame
    if frame_count % process_every == 0:
        detected, recognized = recognizer.process_frame(frame_rgb, preprocess=True)
        
        for person in recognized:
            if person['is_confident']:
                x, y, w, h = person['bbox']
                cv2.rectangle(frame_bgr, (x, y), (x+w, y+h), (0, 255, 0), 2)
                cv2.putText(frame_bgr, person['name'], (x, y-10), 
                           cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
    
    # Calculate FPS
    elapsed = time.time() - start_time
    if elapsed > 0:
        fps = frame_count / elapsed
        cv2.putText(frame_bgr, f"FPS: {fps:.1f}", (10, 30), 
                   cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 255, 255), 2)
    
    cv2.imshow("FPS Test", frame_bgr)
    
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

picam2.stop()
cv2.destroyAllWindows()

elapsed = time.time() - start_time
print(f"\n✓ Average FPS: {frame_count / elapsed:.1f}")
