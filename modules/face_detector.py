"""
Enhanced Face Detection with Alignment
Uses MediaPipe with landmark-based alignment
"""

import cv2
import numpy as np
import mediapipe as mp


class FaceDetector:
    """
    Face detection with alignment using facial landmarks
    """
    
    def __init__(self, detection_confidence=0.7):
        """
        Args:
            detection_confidence: Minimum confidence for detection
        """
        self.detection_confidence = detection_confidence
        
        # MediaPipe Face Detection
        self.mp_face_detection = mp.solutions.face_detection
        self.face_detection = self.mp_face_detection.FaceDetection(
            model_selection=0,
            min_detection_confidence=detection_confidence
        )
        
        # MediaPipe Face Mesh for landmarks
        self.mp_face_mesh = mp.solutions.face_mesh
        self.face_mesh = self.mp_face_mesh.FaceMesh(
            static_image_mode=True,
            max_num_faces=1,
            refine_landmarks=True,
            min_detection_confidence=detection_confidence
        )
    
    def detect_faces(self, image_rgb):
        """
        Detect faces in RGB image
        
        Args:
            image_rgb: RGB image array
            
        Returns:
            List of face dictionaries with bbox and landmarks
        """
        results = self.face_detection.process(image_rgb)
        
        faces = []
        if results.detections:
            h, w = image_rgb.shape[:2]
            
            for detection in results.detections:
                bbox = detection.location_data.relative_bounding_box
                
                x = int(bbox.xmin * w)
                y = int(bbox.ymin * h)
                width = int(bbox.width * w)
                height = int(bbox.height * h)
                
                # Bounds checking
                x = max(0, x)
                y = max(0, y)
                width = min(width, w - x)
                height = min(height, h - y)
                
                confidence = detection.score[0] if detection.score else 0.0
                
                # Get landmarks
                landmarks = self._get_landmarks(image_rgb, (x, y, width, height))
                
                faces.append({
                    'bbox': (x, y, width, height),
                    'confidence': confidence,
                    'landmarks': landmarks
                })
        
        return faces
    
    def _get_landmarks(self, image_rgb, bbox):
        """
        Get facial landmarks for a detected face
        
        Args:
            image_rgb: RGB image
            bbox: Face bounding box (x, y, w, h)
            
        Returns:
            Dictionary of landmark positions
        """
        try:
            results = self.face_mesh.process(image_rgb)
            
            if not results.multi_face_landmarks:
                return None
            
            h, w = image_rgb.shape[:2]
            landmarks = results.multi_face_landmarks[0]
            
            # Key landmarks indices (MediaPipe 468-point model)
            LEFT_EYE = 33
            RIGHT_EYE = 263
            NOSE_TIP = 1
            MOUTH_LEFT = 61
            MOUTH_RIGHT = 291
            
            def get_point(idx):
                lm = landmarks.landmark[idx]
                return (int(lm.x * w), int(lm.y * h))
            
            return {
                'left_eye': get_point(LEFT_EYE),
                'right_eye': get_point(RIGHT_EYE),
                'nose': get_point(NOSE_TIP),
                'mouth_left': get_point(MOUTH_LEFT),
                'mouth_right': get_point(MOUTH_RIGHT)
            }
        except Exception as e:
            print(f"Landmark extraction error: {e}")
            return None
    
    def align_face(self, image_rgb, landmarks, output_size=(160, 160)):
        """
        Align face using eye landmarks
        
        Args:
            image_rgb: RGB image
            landmarks: Dictionary of facial landmarks
            output_size: Desired output size
            
        Returns:
            Aligned face image
        """
        if landmarks is None or 'left_eye' not in landmarks or 'right_eye' not in landmarks:
            # Fallback: just resize
            return cv2.resize(image_rgb, output_size)
        
        try:
            # Convert to numpy arrays with explicit dtype
            left_eye = np.array(landmarks['left_eye'], dtype=np.float32)
            right_eye = np.array(landmarks['right_eye'], dtype=np.float32)
            
            # Compute angle to rotate face upright
            dY = float(right_eye[1] - left_eye[1])
            dX = float(right_eye[0] - left_eye[0])
            angle = float(np.degrees(np.arctan2(dY, dX)))
            
            # Compute center point between eyes (as Python floats)
            eyes_center = (
                float((left_eye[0] + right_eye[0]) / 2.0),
                float((left_eye[1] + right_eye[1]) / 2.0)
            )
            
            # Get rotation matrix
            M = cv2.getRotationMatrix2D(eyes_center, angle, 1.0)
            
            # Rotate image
            h, w = image_rgb.shape[:2]
            rotated = cv2.warpAffine(image_rgb, M, (w, h), flags=cv2.INTER_CUBIC)
            
            # Compute desired eye position in output image
            desired_left_eye = (0.35 * output_size[0], 0.35 * output_size[1])
            
            # Scale to output size
            dist = float(np.sqrt((dX ** 2) + (dY ** 2)))
            desired_dist = 0.3 * output_size[0]
            
            if dist > 1e-6:
                scale = float(desired_dist / dist)
            else:
                scale = 1.0
            
            # Update rotation matrix with translation
            M = cv2.getRotationMatrix2D(eyes_center, angle, scale)
            tX = output_size[0] * 0.5
            tY = output_size[1] * 0.35
            M[0, 2] += (tX - eyes_center[0])
            M[1, 2] += (tY - eyes_center[1])
            
            # Apply transformation
            aligned = cv2.warpAffine(rotated, M, output_size, flags=cv2.INTER_CUBIC)
            
            return aligned
            
        except Exception as e:
            print(f"Alignment error: {e}, falling back to resize")
            return cv2.resize(image_rgb, output_size)
    
    def extract_aligned_face(self, image_rgb, face_data, output_size=(160, 160), padding=0.2):
        """
        Extract and align face region
        
        Args:
            image_rgb: RGB image
            face_data: Face dictionary from detect_faces()
            output_size: Output size
            padding: Padding around face
            
        Returns:
            Aligned face image
        """
        x, y, w, h = face_data['bbox']
        landmarks = face_data.get('landmarks')
        
        # Add padding
        pad_w = int(w * padding)
        pad_h = int(h * padding)
        
        x1 = max(0, x - pad_w)
        y1 = max(0, y - pad_h)
        x2 = min(image_rgb.shape[1], x + w + pad_w)
        y2 = min(image_rgb.shape[0], y + h + pad_h)
        
        # Extract face region
        face_region = image_rgb[y1:y2, x1:x2]
        
        if face_region.size == 0:
            return None
        
        # Align if landmarks available
        if landmarks is not None and 'left_eye' in landmarks and 'right_eye' in landmarks:
            try:
                # Adjust landmarks to face region coordinates
                adjusted_landmarks = {}
                for key, (lx, ly) in landmarks.items():
                    adjusted_landmarks[key] = (lx - x1, ly - y1)
                
                return self.align_face(face_region, adjusted_landmarks, output_size)
            except Exception as e:
                print(f"Alignment failed: {e}, using simple resize")
                return cv2.resize(face_region, output_size)
        else:
            # Just resize
            return cv2.resize(face_region, output_size)
