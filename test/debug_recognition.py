#!/usr/bin/env python3
"""
Debug Recognition Issues
Check database, thresholds, and recognition pipeline
"""

import os
os.environ['GLOG_minloglevel'] = '2'
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'

import cv2
import numpy as np
from picamera2 import Picamera2
import pickle
import time

from face_recognizer import FaceRecognizer

print("\n" + "="*60)
print("RECOGNITION DIAGNOSTICS")
print("="*60)

# Initialize recognizer
recognizer = FaceRecognizer(
    model_path="models/mobilefacenet.tflite",
    detection_confidence=0.5,  # Lower for testing
    recognition_threshold=0.6,  # Lower for testing
    margin_threshold=0.05,
    preprocessing_method='clahe',
    enable_liveness=False,  # Disable for testing
    use_face_alignment=False  # Disable for testing
)

# Check database
print("\n1. DATABASE CHECK")
print("-" * 60)
if os.path.exists("simple_faces.pkl"):
    with open("simple_faces.pkl", 'rb') as f:
        db = pickle.load(f)
    
    print(f"✓ Database found: {len(db)} persons")
    
    for name, data in db.items():
        if isinstance(data, dict):
            count = len(data.get('individual', []))
            avg_emb = data.get('averaged')
            print(f"  • {name}: {count} samples")
            if avg_emb is not None:
                print(f"    - Averaged embedding: {avg_emb.shape} (norm: {np.linalg.norm(avg_emb):.4f})")
            else:
                print(f"    - No averaged embedding!")
        else:
            print(f"  • {name}: {len(data)} samples (old format)")
else:
    print("✗ No database file found!")
    exit(1)

# Test with camera
print("\n2. LIVE RECOGNITION TEST")
print("-" * 60)
print("Starting camera... Position a registered face")

picam2 = Picamera2()
config = picam2.create_preview_configuration(
    main={"size": (1280, 960), "format": "RGB888"}
)
picam2.configure(config)
picam2.start()
time.sleep(0.5)

test_count = 0
max_tests = 30

print("\nTesting for 10 seconds (press 'q' to quit early)...")

while test_count < max_tests:
    # Capture
    frame_rgb = picam2.capture_array()
    frame_bgr = cv2.cvtColor(frame_rgb, cv2.COLOR_RGB2BGR)
    
    # Detect
    faces = recognizer.detect_faces(frame_rgb)
    
    if faces:
        face = max(faces, key=lambda f: f['bbox'][2] * f['bbox'][3])
        x, y, w, h = face['bbox']
        
        # Extract
        face_img = recognizer.extract_face_region(frame_rgb, face, align=False)
        
        if face_img is not None:
            # Get embedding
            embedding = recognizer.extract_embedding(face_img)
            
            if embedding is not None:
                # Recognize
                name, similarity, confident = recognizer.recognize_face(embedding)
                
                # Show detailed info
                color = (0, 255, 0) if confident else (0, 0, 255)
                cv2.rectangle(frame_bgr, (x, y), (x + w, y + h), color, 2)
                
                text = f"{name} {similarity:.2f}"
                cv2.putText(frame_bgr, text, (x, y - 10), 
                           cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)
                
                # Print to console
                print(f"\rFrame {test_count}: {name} (sim: {similarity:.3f}, conf: {confident})", end="", flush=True)
                
                # Compare against all in database
                if test_count % 10 == 0:
                    print(f"\n\nDetailed comparison:")
                    for db_name, db_data in recognizer.known_faces.items():
                        if isinstance(db_data, dict):
                            db_embeddings = db_data['individual']
                        else:
                            db_embeddings = db_data
                        
                        sims = []
                        for db_emb in db_embeddings:
                            from sklearn.metrics.pairwise import cosine_similarity
                            sim = cosine_similarity([embedding], [db_emb])[0][0]
                            sims.append(sim)
                        
                        avg_sim = np.mean(sims)
                        max_sim = max(sims)
                        print(f"  {db_name}: avg={avg_sim:.3f}, max={max_sim:.3f}")
    
    cv2.imshow("Recognition Test (Press 'q' to quit)", frame_bgr)
    
    if cv2.waitKey(100) & 0xFF == ord('q'):
        break
    
    test_count += 1

picam2.stop()
cv2.destroyAllWindows()

print("\n\n" + "="*60)
print("DIAGNOSTICS COMPLETE")
print("="*60)
