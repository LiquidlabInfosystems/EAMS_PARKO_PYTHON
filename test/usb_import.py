#!/usr/bin/env python3
"""
Import faces from USB drive
Put images in: /media/usb/faces/PersonName/*.jpg
"""

import os
from pathlib import Path
from face_recognizer import FaceRecognizer
import cv2

def import_from_usb():
    """Import faces from USB folders"""
    
    # USB mount points
    usb_paths = [
        "/media/usb/faces",
        "/media/pi/USB/faces",
        "/mnt/usb/faces"
    ]
    
    faces_root = None
    for path in usb_paths:
        if os.path.exists(path):
            faces_root = Path(path)
            break
    
    if not faces_root:
        print("❌ USB not found! Expected folder structure:")
        print("   /media/usb/faces/PersonName/image1.jpg")
        return
    
    print(f"✓ Found USB at: {faces_root}")
    
    # Initialize recognizer
    recognizer = FaceRecognizer(
        model_path="models/mobilefacenet.tflite",
        strict_quality_check=False
    )
    
    # Get all person folders
    person_folders = [d for d in faces_root.iterdir() if d.is_dir()]
    
    if not person_folders:
        print("❌ No person folders found!")
        return
    
    print(f"\nFound {len(person_folders)} person(s) to import:\n")
    
    for person_folder in person_folders:
        person_name = person_folder.name
        
        # Get all images
        images = []
        for ext in ['*.jpg', '*.jpeg', '*.png', '*.JPG', '*.JPEG', '*.PNG']:
            images.extend(person_folder.glob(ext))
        
        if not images:
            print(f"⚠ {person_name}: No images found - skipping")
            continue
        
        print(f"📁 {person_name}: Found {len(images)} images")
        
        # Process images
        captured_faces = []
        
        for img_path in images:
            frame = cv2.imread(str(img_path))
            if frame is None:
                continue
            
            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            faces = recognizer.detect_faces(frame_rgb)
            
            if faces:
                face = max(faces, key=lambda f: f['bbox'][2] * f['bbox'][3])
                face_img = recognizer.extract_face_region(frame_rgb, face['bbox'])
                
                is_valid, msg, quality = recognizer.validate_face_sample(face_img)
                
                if is_valid:
                    captured_faces.append(face_img)
        
        # Save to database
        if len(captured_faces) >= 3:
            success = recognizer.add_faces(captured_faces, person_name)
            if success:
                print(f"   ✅ Registered {person_name} ({len(captured_faces)} samples)\n")
            else:
                print(f"   ❌ Failed to save {person_name}\n")
        else:
            print(f"   ⚠ Only {len(captured_faces)} good samples - need 3+\n")
    
    print("=" * 60)
    print("Import complete! Unplug USB safely.")

if __name__ == "__main__":
    import_from_usb()
