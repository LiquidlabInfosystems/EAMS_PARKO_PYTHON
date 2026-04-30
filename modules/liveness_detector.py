"""
Simplified Liveness Detection - Blink Only
Resets only when person leaves frame for 30+ seconds
"""

import cv2
import numpy as np
from collections import deque
import mediapipe as mp


class LivenessDetector:
    """
    Simple blink-only liveness detection
    Once a blink is detected, person is marked as live until they leave
    """
    
    def __init__(self, method='blink', fast_mode=True):
        """
        Args:
            method: Only 'blink' is used
            fast_mode: Enables caching
        """
        self.method = 'blink'
        self.fast_mode = fast_mode
        
        # MediaPipe Face Mesh for eye tracking
        self.mp_face_mesh = mp.solutions.face_mesh
        self.face_mesh = self.mp_face_mesh.FaceMesh(
            static_image_mode=False,
            max_num_faces=1,
            refine_landmarks=True,
            min_detection_confidence=0.5
        )
        
        # Blink detection parameters
        self.EAR_THRESHOLD = 0.23  # Slightly higher for easier detection
        self.EAR_CONSECUTIVE_FRAMES = 2
        self.blink_counter = 0
        self.total_blinks = 0
        self.frame_counter = 0
        self.ear_history = deque(maxlen=10)
        
        # Minimum frames before we can detect blink reliably
        self.min_frames_for_detection = 10  # Reduced from 15
        
        # Once blink detected, person is "verified live"
        self.is_verified_live = False
    
    def reset(self):
        """Reset detection state (only called when person leaves for 30s)"""
        self.blink_counter = 0
        self.total_blinks = 0
        self.frame_counter = 0
        self.ear_history.clear()
        self.is_verified_live = False
        print("  ↻ Liveness state fully reset")
    
    def check_liveness(self, face_rgb):
        """
        Simple blink-only check
        Once 1 blink detected = permanently live until reset
        
        Returns:
            (is_live: bool, confidence: float, details: dict)
        """
        self.frame_counter += 1
        
        # If already verified live, just return True
        if self.is_verified_live:
            details = {
                'method': 'blink',
                'blinks_detected': self.total_blinks,
                'verified': True,
                'frames_analyzed': self.frame_counter
            }
            return True, 0.95, details
        
        # Check for blink
        blink_detected, confidence = self._detect_blink(face_rgb)
        
        # If blink detected, mark as verified
        if blink_detected and self.total_blinks > 0:
            self.is_verified_live = True
            confidence = 0.95
        
        details = {
            'method': 'blink',
            'blinks_detected': self.total_blinks,
            'verified': self.is_verified_live,
            'frames_analyzed': self.frame_counter
        }
        
        return self.is_verified_live or blink_detected, confidence, details
    
    def _detect_blink(self, face_rgb):
        """
        Detect eye blinks using Eye Aspect Ratio (EAR)
        """
        try:
            results = self.face_mesh.process(face_rgb)
            
            if not results.multi_face_landmarks:
                return False, 0.0
            
            landmarks = results.multi_face_landmarks[0]
            h, w = face_rgb.shape[:2]
            
            # Eye landmarks
            left_eye = [362, 385, 387, 263, 373, 380]
            right_eye = [33, 160, 158, 133, 153, 144]
            
            def get_ear(eye_points):
                """Calculate Eye Aspect Ratio"""
                coords = []
                for idx in eye_points:
                    lm = landmarks.landmark[idx]
                    coords.append([lm.x * w, lm.y * h])
                coords = np.array(coords)
                
                # Vertical distances
                A = np.linalg.norm(coords[1] - coords[5])
                B = np.linalg.norm(coords[2] - coords[4])
                
                # Horizontal distance
                C = np.linalg.norm(coords[0] - coords[3])
                
                # EAR formula
                ear = (A + B) / (2.0 * C + 1e-6)
                return ear
            
            # Calculate EAR for both eyes
            left_ear = get_ear(left_eye)
            right_ear = get_ear(right_eye)
            
            # Average EAR
            ear = (left_ear + right_ear) / 2.0
            self.ear_history.append(ear)
            
            # Check for blink (eye closed)
            if ear < self.EAR_THRESHOLD:
                self.blink_counter += 1
            else:
                # Eye opened - check if it was a blink
                if self.blink_counter >= self.EAR_CONSECUTIVE_FRAMES:
                    self.total_blinks += 1
                    print(f"  ✓ Blink #{self.total_blinks} detected!")
                self.blink_counter = 0
            
            # Return status
            if self.frame_counter >= self.min_frames_for_detection:
                if self.total_blinks > 0:
                    return True, 0.95  # Blink detected = live
                else:
                    # Check EAR variance (real eyes move)
                    if len(self.ear_history) >= 5:
                        ear_std = np.std(self.ear_history)
                        confidence = min(0.3 + ear_std * 3, 0.60)
                    else:
                        confidence = 0.3
                    return False, confidence
            else:
                # Still warming up
                return False, 0.4
                
        except Exception as e:
            print(f"Blink detection error: {e}")
            return False, 0.0
