"""
InsightFace Engine Module
Unified face detection + embedding extraction using InsightFace
Replaces MediaPipe (detection) + MobileFaceNet (encoding)
Optimized for Raspberry Pi 5 (CPU inference)
"""

import warnings
warnings.filterwarnings("ignore", category=FutureWarning)

import cv2
import numpy as np
import os


class InsightFaceEngine:
    """
    Face detection and embedding extraction using InsightFace.
    
    - Uses FaceAnalysis (buffalo_sc for RPi5, buffalo_l for GPU devices)
    - Produces 512-D L2-normalized embeddings
    - Provides same interface as FaceDetector + FaceEncoder combined
    - Works on Raspberry Pi 5 with CPU inference
    """
    
    def __init__(self, 
                 model_name='buffalo_sc',
                 det_size=(640, 640),
                 providers=None,
                 det_score_threshold=0.5):
        """
        Initialize InsightFace engine.
        
        Args:
            model_name: InsightFace model pack name ('buffalo_sc', 'buffalo_l', etc.)
            det_size: Detection input size (width, height)
            providers: ONNX Runtime execution providers list.
                       Default: auto-detect (try CUDA first, fallback to CPU)
            det_score_threshold: Minimum detection confidence score
        """
        self.model_name = model_name
        self.det_size = det_size
        self.det_score_threshold = det_score_threshold
        
        # Auto-detect providers for Raspberry Pi 5 (CPU only)
        if providers is None:
            providers = self._get_available_providers()
        
        print(f"🔄 Initializing InsightFace ({model_name})...")
        print(f"   Providers: {providers}")
        print(f"   Detection size: {det_size}")
        
        # Import insightface here to fail gracefully if not installed
        try:
            from insightface.app import FaceAnalysis
        except ImportError:
            raise ImportError(
                "InsightFace is not installed. Install with:\n"
                "  pip install insightface onnxruntime\n"
                "For GPU support: pip install onnxruntime-gpu"
            )
        
        # Initialize FaceAnalysis
        self.face_app = FaceAnalysis(
            name=model_name,
            providers=providers
        )
        self.face_app.prepare(ctx_id=0, det_size=det_size)
        
        print(f"✅ InsightFace Model Loaded ({model_name})")
    
    @staticmethod
    def _get_available_providers():
        """Auto-detect available ONNX Runtime execution providers."""
        try:
            import onnxruntime as ort
            available = ort.get_available_providers()
            
            if 'CUDAExecutionProvider' in available:
                print("   GPU (CUDA) detected")
                return ['CUDAExecutionProvider', 'CPUExecutionProvider']
            else:
                print("   Using CPU inference (Raspberry Pi 5)")
                return ['CPUExecutionProvider']
        except Exception:
            return ['CPUExecutionProvider']
    
    def detect_faces(self, image_rgb):
        """
        Detect faces and extract embeddings in one pass.
        
        Args:
            image_rgb: RGB image array (H, W, 3)
            
        Returns:
            List of face dictionaries with bbox, landmarks, confidence, embedding
        """
        # InsightFace expects BGR input
        image_bgr = cv2.cvtColor(image_rgb, cv2.COLOR_RGB2BGR)
        
        # Run detection + embedding extraction
        faces = self.face_app.get(image_bgr)
        
        results = []
        for face in faces:
            det_score = face.det_score if hasattr(face, 'det_score') else 0.0
            if det_score < self.det_score_threshold:
                continue
            
            # Convert bbox from [x1, y1, x2, y2] to [x, y, w, h]
            box = face.bbox.astype(int)
            x1, y1, x2, y2 = box[0], box[1], box[2], box[3]
            
            # Clamp to image boundaries
            h_img, w_img = image_rgb.shape[:2]
            x1 = max(0, x1)
            y1 = max(0, y1)
            x2 = min(w_img, x2)
            y2 = min(h_img, y2)
            
            w = x2 - x1
            h = y2 - y1
            
            if w <= 0 or h <= 0:
                continue
            
            # Extract 5-point landmarks
            landmarks = None
            if hasattr(face, 'kps') and face.kps is not None:
                kps = face.kps.astype(int)
                landmarks = {
                    'left_eye': (int(kps[0][0]), int(kps[0][1])),
                    'right_eye': (int(kps[1][0]), int(kps[1][1])),
                    'nose': (int(kps[2][0]), int(kps[2][1])),
                    'mouth_left': (int(kps[3][0]), int(kps[3][1])),
                    'mouth_right': (int(kps[4][0]), int(kps[4][1]))
                }
            
            # Get embedding (already computed during detection)
            embedding = None
            if hasattr(face, 'embedding') and face.embedding is not None:
                embedding = face.embedding.flatten().astype(np.float32)
                norm = np.linalg.norm(embedding)
                if norm > 1e-6:
                    embedding = embedding / norm
            
            results.append({
                'bbox': (x1, y1, w, h),
                'confidence': float(det_score),
                'landmarks': landmarks,
                'embedding': embedding,
                '_insightface_obj': face
            })
        
        return results
    
    def extract_face_region(self, image_rgb, face_data, output_size=(160, 160), padding=0.2):
        """
        Extract face region from image with padding.
        """
        x, y, w, h = face_data['bbox']
        
        pad_w = int(w * padding)
        pad_h = int(h * padding)
        
        x1 = max(0, x - pad_w)
        y1 = max(0, y - pad_h)
        x2 = min(image_rgb.shape[1], x + w + pad_w)
        y2 = min(image_rgb.shape[0], y + h + pad_h)
        
        face_region = image_rgb[y1:y2, x1:x2]
        
        if face_region.size == 0:
            return None
        
        return cv2.resize(face_region, output_size)
    
    def extract_embedding_from_image(self, face_rgb):
        """
        Extract embedding from a cropped face image (used during registration).
        
        InsightFace's detector needs context around the face to detect it.
        A tight 160x160 crop won't work directly, so we:
        1. Add padding (black border) around the crop
        2. Upscale to give the detector enough pixels to work with
        3. Retry with gray padding and larger size if first attempt fails
        
        Args:
            face_rgb: RGB face image (any size, typically 160x160 crop)
            
        Returns:
            512-D L2-normalized embedding vector, or None if no face detected
        """
        h, w = face_rgb.shape[:2]
        
        # === Attempt 1: Black padding + upscale ===
        pad = max(h, w) // 2
        padded = cv2.copyMakeBorder(
            face_rgb, pad, pad, pad, pad,
            cv2.BORDER_CONSTANT, value=[0, 0, 0]
        )
        
        # Upscale if too small for InsightFace detector
        ph, pw = padded.shape[:2]
        if ph < 256 or pw < 256:
            scale = max(256 / pw, 256 / ph)
            padded = cv2.resize(padded, (int(pw * scale), int(ph * scale)))
        
        face_bgr = cv2.cvtColor(padded, cv2.COLOR_RGB2BGR)
        faces = self.face_app.get(face_bgr)
        
        if not faces:
            # === Attempt 2: Gray padding + larger upscale ===
            pad2 = max(h, w)
            padded2 = cv2.copyMakeBorder(
                face_rgb, pad2, pad2, pad2, pad2,
                cv2.BORDER_CONSTANT, value=[128, 128, 128]
            )
            ph2, pw2 = padded2.shape[:2]
            if ph2 < 320 or pw2 < 320:
                scale = max(320 / pw2, 320 / ph2)
                padded2 = cv2.resize(padded2, (int(pw2 * scale), int(ph2 * scale)))
            
            face_bgr2 = cv2.cvtColor(padded2, cv2.COLOR_RGB2BGR)
            faces = self.face_app.get(face_bgr2)
        
        if not faces:
            print(f"  ⚠️ InsightFace could not detect face in crop ({w}x{h})")
            return None
        
        # Use the most confident face
        best_face = max(faces, key=lambda f: f.det_score if hasattr(f, 'det_score') else 0.0)
        
        if hasattr(best_face, 'embedding') and best_face.embedding is not None:
            embedding = best_face.embedding.flatten().astype(np.float32)
            norm = np.linalg.norm(embedding)
            if norm > 1e-6:
                embedding = embedding / norm
            return embedding
        
        return None
    
    def extract_embedding_from_full_frame(self, image_rgb, face_data):
        """
        Get embedding for a specific face from a full frame.
        Prefers cached embedding from detection pass.
        """
        if face_data.get('embedding') is not None:
            return face_data['embedding']
        
        face_region = self.extract_face_region(image_rgb, face_data, output_size=(160, 160))
        if face_region is None:
            return None
        
        return self.extract_embedding_from_image(face_region)
