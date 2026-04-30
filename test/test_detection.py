#!/usr/bin/env python3
"""
Test face detection only
"""

import os
os.environ['GLOG_minloglevel'] = '2'
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'

import cv2
from picamera2 import Picamera2
import mediapipe as mp
import time

print("\n" + "="*60)
print("FACE DETECTION TEST")
print("="*60)

# Initialize MediaPipe directly
mp_face_detection = mp.solutions.face_detection
face_detection = mp_face_detection.FaceDetection(
    model_selection=0,
    min_detection_confidence=0.3  # VERY LOW
)

# Start camera
picam2 = Picamera2()
config = picam2.create_preview_configuration(
    main={"size": (1280, 960), "format": "RGB888"}
)
picam2.configure(config)
picam2.start()
time.sleep(0.5)

print("\n✓ Camera started")
print("✓ Detection confidence: 0.3 (very low)")
print("\nPosition your face in front of camera...")
print("Press 'q' to quit\n")

frame_count = 0

while True:
    # Capture
    frame_rgb = picam2.capture_array()
    frame_bgr = cv2.cvtColor(frame_rgb, cv2.COLOR_RGB2BGR)
    
    # Detect with MediaPipe
    results = face_detection.process(frame_rgb)
    
    # Draw results
    if results.detections:
        print(f"Frame {frame_count}: ✓ {len(results.detections)} face(s) detected!", end="\r", flush=True)
        
        h, w = frame_rgb.shape[:2]
        
        for detection in results.detections:
            bbox = detection.location_data.relative_bounding_box
            
            x = int(bbox.xmin * w)
            y = int(bbox.ymin * h)
            width = int(bbox.width * w)
            height = int(bbox.height * h)
            
            confidence = detection.score[0] if detection.score else 0.0
            
            # Draw green box
            cv2.rectangle(frame_bgr, (x, y), (x + width, y + height), (0, 255, 0), 3)
            
            # Draw confidence
            cv2.putText(frame_bgr, f"Conf: {confidence:.2f}", (x, y - 10), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
    else:
        print(f"Frame {frame_count}: ✗ No face detected", end="\r", flush=True)
    
    # Show instructions
    cv2.putText(frame_bgr, "Detection Test (Press 'q' to quit)", (10, 30), 
               cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 255), 2)
    
    cv2.putText(frame_bgr, f"Frames: {frame_count}", (10, 60), 
               cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1)
    
    # Display
    cv2.imshow("Face Detection Test", frame_bgr)
    
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break
    
    frame_count += 1

picam2.stop()
cv2.destroyAllWindows()

print(f"\n\n✓ Test complete. Processed {frame_count} frames")
