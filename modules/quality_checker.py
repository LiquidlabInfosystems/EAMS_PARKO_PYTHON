"""
Face Quality Assessment Module
Checks blur, brightness, size, pose, etc.
"""

import cv2
import numpy as np


class QualityChecker:
    """
    Comprehensive face quality assessment
    """
    
    def __init__(self, strict_mode=False):
        """
        Args:
            strict_mode: Use stricter thresholds
        """
        self.strict_mode = strict_mode
        
        if strict_mode:
            self.min_face_size = 80
            self.min_blur_score = 150
            self.min_brightness = 40
            self.max_brightness = 220
            self.max_pose_angle = 25
        else:
            self.min_face_size = 50
            self.min_blur_score = 80
            self.min_brightness = 25
            self.max_brightness = 235
            self.max_pose_angle = 35
    
    def check_quality(self, face_rgb, landmarks=None):
        """
        Comprehensive quality check
        
        Args:
            face_rgb: RGB face image
            landmarks: Optional facial landmarks
            
        Returns:
            (is_good: bool, quality_score: float, issues: list)
        """
        issues = []
        scores = []
        
        # 1. Size check
        size_ok, size_score = self._check_size(face_rgb)
        scores.append(size_score)
        if not size_ok:
            issues.append("Face too small")
        
        # 2. Blur check
        blur_ok, blur_score = self._check_blur(face_rgb)
        scores.append(blur_score)
        if not blur_ok:
            issues.append("Image too blurry")
        
        # 3. Brightness check
        bright_ok, bright_score = self._check_brightness(face_rgb)
        scores.append(bright_score)
        if not bright_ok:
            issues.append("Poor lighting")
        
        # 4. Contrast check
        contrast_ok, contrast_score = self._check_contrast(face_rgb)
        scores.append(contrast_score)
        if not contrast_ok:
            issues.append("Low contrast")
        
        # 5. Pose check (if landmarks available)
        if landmarks is not None:
            pose_ok, pose_score = self._check_pose(landmarks)
            scores.append(pose_score)
            if not pose_ok:
                issues.append("Face angle too large")
        
        # Overall quality score
        quality_score = np.mean(scores)
        is_good = len(issues) == 0
        
        return is_good, quality_score, issues
    
    def _check_size(self, face_rgb):
        """Check if face is large enough"""
        h, w = face_rgb.shape[:2]
        min_dim = min(h, w)
        
        if min_dim < self.min_face_size:
            return False, min_dim / self.min_face_size
        return True, 1.0
    
    def _check_blur(self, face_rgb):
        """Check image sharpness using Laplacian variance"""
        gray = cv2.cvtColor(face_rgb, cv2.COLOR_RGB2GRAY)
        laplacian_var = cv2.Laplacian(gray, cv2.CV_64F).var()
        
        score = min(1.0, laplacian_var / self.min_blur_score)
        is_good = laplacian_var >= self.min_blur_score
        
        return is_good, score
    
    def _check_brightness(self, face_rgb):
        """Check brightness levels"""
        gray = cv2.cvtColor(face_rgb, cv2.COLOR_RGB2GRAY)
        brightness = np.mean(gray)
        
        if brightness < self.min_brightness or brightness > self.max_brightness:
            # Calculate how far from acceptable range
            if brightness < self.min_brightness:
                score = brightness / self.min_brightness
            else:
                score = (255 - brightness) / (255 - self.max_brightness)
            return False, max(0.0, score)
        
        return True, 1.0
    
    def _check_contrast(self, face_rgb):
        """Check image contrast"""
        gray = cv2.cvtColor(face_rgb, cv2.COLOR_RGB2GRAY)
        contrast = gray.std()
        
        min_contrast = 30
        score = min(1.0, contrast / min_contrast)
        is_good = contrast >= min_contrast
        
        return is_good, score
    
    def _check_pose(self, landmarks):
        """
        Check face pose angle using landmarks
        
        Args:
            landmarks: Dictionary with 'left_eye', 'right_eye', 'nose'
            
        Returns:
            (is_frontal: bool, score: float)
        """
        if landmarks is None:
            return True, 1.0
        
        left_eye = np.array(landmarks.get('left_eye', [0, 0]))
        right_eye = np.array(landmarks.get('right_eye', [0, 0]))
        nose = np.array(landmarks.get('nose', [0, 0]))
        
        # Calculate eye center
        eye_center = (left_eye + right_eye) / 2
        
        # Calculate angle from eyes
        eye_diff = right_eye - left_eye
        eye_angle = np.abs(np.degrees(np.arctan2(eye_diff[1], eye_diff[0])))
        
        # Check if nose is centered between eyes
        nose_offset = np.abs(nose[0] - eye_center[0])
        eye_distance = np.linalg.norm(right_eye - left_eye)
        
        if eye_distance > 0:
            nose_ratio = nose_offset / eye_distance
        else:
            nose_ratio = 0
        
        # Combined pose score
        angle_score = 1.0 - min(1.0, eye_angle / self.max_pose_angle)
        center_score = 1.0 - min(1.0, nose_ratio)
        pose_score = (angle_score + center_score) / 2
        
        is_frontal = eye_angle < self.max_pose_angle and nose_ratio < 0.3
        
        return is_frontal, pose_score
