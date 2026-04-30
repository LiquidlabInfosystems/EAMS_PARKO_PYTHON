#!/usr/bin/env python3
"""
Minimal Face Recognition Script
Picamera2 + OpenCV only - No Face Alignment
"""

import cv2
from picamera2 import Picamera2
from face_recognizer import FaceRecognizer

# Initialize WITHOUT face alignment
recognizer = FaceRecognizer(
    model_path="models/mobilefacenet.tflite",
    preprocessing_method='clahe',
    use_face_alignment=False  # DISABLED to avoid landmark issues
)

picam2 = Picamera2()
picam2.configure(picam2.create_preview_configuration(
    main={"size": (1280, 960), "format": "RGB888"}
))
picam2.start()

print("✅ Started! Press 'q' to quit\n")

# Main loop
while True:
    # Capture
    frame_rgb = picam2.capture_array()
    frame_bgr = cv2.cvtColor(frame_rgb, cv2.COLOR_RGB2BGR)
    
    # Detect and recognize
    faces = recognizer.detect_faces(frame_rgb)
    
    for face in faces:
        x, y, w, h = face['bbox']
        
        # Extract WITHOUT alignment
        face_img = recognizer.extract_face_region(frame_rgb, face, align=False)
        
        if face_img is not None:
            embedding = recognizer.extract_embedding(face_img)
            
            if embedding is not None:
                name, similarity, confident = recognizer.recognize_face(embedding)
                
                # Draw box
                color = (0, 255, 0) if confident else (0, 0, 255)
                cv2.rectangle(frame_bgr, (x, y), (x + w, y + h), color, 2)
                
                # Draw name
                text = f"{name} {similarity:.0%}"
                cv2.putText(frame_bgr, text, (x, y - 10), 
                           cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)
    
    # Display
    cv2.imshow("Face Recognition", frame_bgr)
    
    # Quit on 'q'
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

# Cleanup
picam2.stop()
cv2.destroyAllWindows()
