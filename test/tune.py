#!/usr/bin/env python3
"""
Interactive tuning - adjust thresholds in real-time
"""

import os
os.environ['GLOG_minloglevel'] = '2'
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'

import cv2
from picamera2 import Picamera2
from face_recognizer import FaceRecognizer
import numpy as np
from sklearn.metrics.pairwise import cosine_similarity

print("\n" + "="*60)
print("INTERACTIVE THRESHOLD TUNING")
print("="*60)

# Start with your current settings
current_threshold = 0.58
current_margin = 0.06

recognizer = FaceRecognizer(
    model_path="models/mobilefacenet.tflite",
    detection_confidence=0.5,
    recognition_threshold=current_threshold,
    margin_threshold=current_margin,
    preprocessing_method='clahe',
    enable_liveness=False,
    strict_quality=False,
    use_face_alignment=False
)

print(f"\n✓ Database: {len(recognizer.known_faces)} persons")
print(f"\n🎮 CONTROLS:")
print("  ↑/↓ : Adjust recognition threshold (±0.02)")
print("  ←/→ : Adjust margin threshold (±0.01)")
print("  'r' : Reset to defaults")
print("  'q' : Quit")
print("\nStarting...\n")

# Camera
picam2 = Picamera2()
config = picam2.create_preview_configuration(
    main={"size": (1280, 960), "format": "RGB888"}
)
picam2.configure(config)
picam2.start()

import time
time.sleep(0.5)

while True:
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
                # Compute similarities to all
                all_sims = []
                
                for db_name, db_data in recognizer.known_faces.items():
                    if isinstance(db_data, dict):
                        db_embeddings = db_data['individual']
                    else:
                        db_embeddings = db_data
                    
                    person_sims = []
                    for db_emb in db_embeddings:
                        s = cosine_similarity([embedding], [db_emb])[0][0]
                        person_sims.append(s)
                    
                    max_sim = max(person_sims)
                    avg_sim = np.mean(sorted(person_sims, reverse=True)[:3])
                    
                    all_sims.append({
                        'name': db_name,
                        'max': max_sim,
                        'avg': avg_sim,
                        'score': avg_sim  # Using average for matching
                    })
                
                # Sort by score
                all_sims.sort(key=lambda x: x['score'], reverse=True)
                
                if len(all_sims) > 0:
                    best = all_sims[0]
                    
                    # Apply current thresholds
                    passes_threshold = best['score'] >= current_threshold
                    
                    if len(all_sims) > 1:
                        margin = best['score'] - all_sims[1]['score']
                        passes_margin = margin >= current_margin
                    else:
                        margin = 1.0
                        passes_margin = True
                    
                    is_recognized = passes_threshold and passes_margin
                    
                    # Draw box
                    if is_recognized:
                        color = (0, 255, 0)
                        name = best['name']
                        status = "✓ RECOGNIZED"
                    else:
                        color = (0, 165, 255)
                        name = best['name']
                        if not passes_threshold:
                            status = f"✗ Below threshold ({best['score']:.2f} < {current_threshold:.2f})"
                        else:
                            status = f"✗ Low margin ({margin:.2f} < {current_margin:.2f})"
                    
                    cv2.rectangle(frame_bgr, (x, y), (x + w, y + h), color, 3)
                    cv2.rectangle(frame_bgr, (x, y - 40), (x + w, y), color, -1)
                    cv2.putText(frame_bgr, f"{name} {best['score']:.2f}", (x + 5, y - 10), 
                               cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 0), 2)
                    
                    # Show status
                    cv2.putText(frame_bgr, status, (10, 40), 
                               cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)
                    
                    # Show top 3 matches
                    y_offset = 80
                    for i, match in enumerate(all_sims[:3]):
                        text = f"{i+1}. {match['name']}: {match['score']:.3f}"
                        match_color = (0, 255, 0) if match['score'] >= current_threshold else (128, 128, 128)
                        cv2.putText(frame_bgr, text, (10, y_offset), 
                                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, match_color, 1)
                        y_offset += 25
    
    # Show current settings
    h = frame_bgr.shape[0]
    cv2.putText(frame_bgr, f"Recognition Threshold: {current_threshold:.2f} (Up/Down)", 
               (10, h - 60), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 0), 2)
    cv2.putText(frame_bgr, f"Margin Threshold: {current_margin:.2f} (Left/Right)", 
               (10, h - 30), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 0), 2)
    
    # Display
    cv2.imshow("Threshold Tuning (q=quit, r=reset)", frame_bgr)
    
    # Handle keys
    key = cv2.waitKey(1) & 0xFF
    
    if key == ord('q'):
        break
    elif key == ord('r'):
        current_threshold = 0.58
        current_margin = 0.06
        recognizer.matcher.threshold = current_threshold
        recognizer.matcher.margin_threshold = current_margin
        print(f"\n✓ Reset: threshold={current_threshold:.2f}, margin={current_margin:.2f}")
    elif key == 82:  # Up arrow
        current_threshold = min(0.90, current_threshold + 0.02)
        recognizer.matcher.threshold = current_threshold
        print(f"↑ Threshold: {current_threshold:.2f}")
    elif key == 84:  # Down arrow
        current_threshold = max(0.30, current_threshold - 0.02)
        recognizer.matcher.threshold = current_threshold
        print(f"↓ Threshold: {current_threshold:.2f}")
    elif key == 81:  # Left arrow
        current_margin = max(0.01, current_margin - 0.01)
        recognizer.matcher.margin_threshold = current_margin
        print(f"← Margin: {current_margin:.2f}")
    elif key == 83:  # Right arrow
        current_margin = min(0.20, current_margin + 0.01)
        recognizer.matcher.margin_threshold = current_margin
        print(f"→ Margin: {current_margin:.2f}")

picam2.stop()
cv2.destroyAllWindows()

print(f"\n" + "="*60)
print(f"FINAL SETTINGS:")
print(f"="*60)
print(f"recognition_threshold={current_threshold:.2f}")
print(f"margin_threshold={current_margin:.2f}")
print(f"\nUpdate attendance_gui.py with these values!")
