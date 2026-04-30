#!/usr/bin/env python3
"""
Advanced Face Recognition System - InsightFace Version
Replaces MediaPipe + MobileFaceNet with InsightFace (buffalo_l)
With adaptive learning and quality validation
"""

# Suppress warnings
import os
os.environ['GLOG_minloglevel'] = '2'
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'

import cv2
import numpy as np
import pickle
from typing import List, Dict, Tuple, Optional

from modules.insightface_engine import InsightFaceEngine
from modules.preprocessing import ImagePreprocessor
from modules.quality_checker import QualityChecker
from modules.liveness_detector import LivenessDetector
from modules.face_matcher import FaceMatcher


class FaceRecognizer:
    """
    Complete face recognition system using InsightFace:
    - CLAHE + advanced preprocessing for varying lighting/cameras
    - InsightFace detection with 512-D embedding extraction
    - Quality assessment
    - Liveness detection (blink)
    - Robust matching with cosine similarity
    - Adaptive learning
    """
    
    def __init__(self,
                 db_path: str = "simple_faces.pkl",
                 model_name: str = 'buffalo_l',
                 det_size: Tuple[int, int] = (640, 640),
                 providers: List[str] = None,
                 detection_confidence: float = 0.5,
                 recognition_threshold: float = 0.35,
                 margin_threshold: float = 0.05,
                 preprocessing_method: str = 'clahe',
                 enable_liveness: bool = False,
                 strict_quality: bool = False,
                 use_face_alignment: bool = False,
                 # Legacy parameter - ignored, kept for backward compatibility
                 model_path: str = None):
        """
        Initialize face recognizer with InsightFace engine.
        
        Args:
            db_path: Path to face database pickle file
            model_name: InsightFace model pack name ('buffalo_l', 'buffalo_sc')
            det_size: Detection input size (width, height)
            providers: ONNX Runtime execution providers (auto-detect if None)
            detection_confidence: Minimum detection confidence
            recognition_threshold: Similarity threshold for recognition
                                   (InsightFace typical: 0.30-0.45)
            margin_threshold: Minimum margin between top matches
            preprocessing_method: 'clahe', 'histogram', 'gamma', 'msr', 'weber'
            enable_liveness: Enable liveness detection (anti-spoofing)
            strict_quality: Use strict quality checks
            use_face_alignment: Enable landmark-based face alignment
            model_path: IGNORED - kept for backward compatibility with old config
        """
        print("🚀 Initializing Face Recognition System (InsightFace)...")
        
        if model_path is not None:
            print("   ⚠️ model_path parameter is ignored - using InsightFace engine")
        
        # Configuration
        self.db_path = db_path
        self.recognition_threshold = recognition_threshold
        self.enable_liveness = enable_liveness
        self.use_face_alignment = use_face_alignment
        
        # Initialize modules
        print("📦 Loading modules...")
        
        # 1. Preprocessing (handles varying lighting, different cameras)
        self.preprocessor = ImagePreprocessor(method=preprocessing_method)
        print(f"✓ Preprocessor: {preprocessing_method.upper()}")
        
        # 2. InsightFace Engine (replaces MediaPipe + MobileFaceNet)
        self.engine = InsightFaceEngine(
            model_name=model_name,
            det_size=det_size,
            providers=providers,
            det_score_threshold=detection_confidence
        )
        print(f"✓ Face Detector + Encoder: InsightFace ({model_name}) - 512-D embeddings")
        
        # 3. Quality Checker
        self.quality_checker = QualityChecker(strict_mode=strict_quality)
        print(f"✓ Quality Checker: {'Strict' if strict_quality else 'Normal'}")
        
        # 4. Liveness Detector
        if enable_liveness:
            self.liveness_detector = LivenessDetector(method='multi')
            print(f"✓ Liveness Detector: ✅ ENABLED (Multi-method: Blink+Moiré+Motion+Color)")
        else:
            self.liveness_detector = None
            print(f"○ Liveness Detector: Disabled")

        # 5. Face Matcher - Cosine similarity works well for InsightFace's L2-normalized 512-D embeddings
        self.matcher = FaceMatcher(
            primary_metric='cosine',
            threshold=recognition_threshold,
            margin_threshold=margin_threshold,
            use_ensemble=False
        )
        print(f"✓ Face Matcher: Cosine similarity (threshold={recognition_threshold})")
        
        # Load database
        self.known_faces = self.load_database()
        self.db_last_modified = self._get_db_modified_time()
        print(f"✓ Database: {len(self.known_faces)} persons loaded")
    
    def _get_db_modified_time(self) -> float:
        """Get the last modified time of the database file"""
        if os.path.exists(self.db_path):
            return os.path.getmtime(self.db_path)
        return 0.0
    
    def load_database(self) -> Dict:
        """Load face database from pickle file"""
        if os.path.exists(self.db_path):
            with open(self.db_path, 'rb') as f:
                faces = pickle.load(f)
            return faces
        else:
            print("No face database found, starting fresh")
            return {}
    
    def reload_database(self) -> bool:
        """Reload database from disk (hot-reload)"""
        try:
            self.known_faces = self.load_database()
            self.db_last_modified = self._get_db_modified_time()
            print(f"🔄 Database reloaded: {len(self.known_faces)} persons")
            return True
        except Exception as e:
            print(f"❌ Failed to reload database: {e}")
            return False
    
    def reload_if_modified(self) -> bool:
        """Reload database only if the file has been modified"""
        current_mtime = self._get_db_modified_time()
        if current_mtime > self.db_last_modified:
            print(f"📁 Database file changed, reloading...")
            return self.reload_database()
        return False
    
    def save_database(self):
        """Save face database to pickle file"""
        with open(self.db_path, 'wb') as f:
            pickle.dump(self.known_faces, f)
        print(f"Database saved: {len(self.known_faces)} persons")
    
    def detect_faces(self, image_rgb: np.ndarray) -> List[Dict]:
        """
        Detect faces in image (also extracts embeddings in same pass).
        
        Args:
            image_rgb: RGB image array
            
        Returns:
            List of face dictionaries with bbox, landmarks, confidence, embedding
        """
        return self.engine.detect_faces(image_rgb)
    
    def preprocess_image(self, image_rgb: np.ndarray) -> np.ndarray:
        """
        Preprocess image for better face detection.
        Handles varying lighting conditions and different cameras.
        
        Args:
            image_rgb: RGB image
            
        Returns:
            Preprocessed RGB image
        """
        return self.preprocessor.preprocess(
            image_rgb, 
            denoise=True, 
            sharpen=False
        )
    
    def extract_face_region(self, 
                           image_rgb: np.ndarray, 
                           face_data: Dict,
                           align: bool = None) -> Optional[np.ndarray]:
        """
        Extract face region from image.
        
        Args:
            image_rgb: RGB image
            face_data: Face detection data
            align: Alignment flag (kept for API compatibility)
            
        Returns:
            Extracted face image or None
        """
        return self.engine.extract_face_region(
            image_rgb, 
            face_data, 
            output_size=(160, 160),
            padding=0.2
        )
    
    def check_face_quality(self, 
                          face_rgb: np.ndarray,
                          landmarks: Optional[Dict] = None,
                          is_registration: bool = False) -> Tuple[bool, float, List[str]]:
        """
        Check face image quality
        
        Args:
            face_rgb: RGB face image
            landmarks: Optional facial landmarks
            is_registration: True if checking for registration
            
        Returns:
            (is_good, quality_score, issues_list)
        """
        is_good, quality_score, issues = self.quality_checker.check_quality(
            face_rgb, 
            landmarks
        )
        
        return is_good, quality_score, issues
    
    def check_liveness(self, face_rgb: np.ndarray) -> Tuple[bool, float]:
        """
        Check if face is live (not spoofed)
        
        Args:
            face_rgb: RGB face image
            
        Returns:
            (is_live, confidence, details)
        """
        if self.liveness_detector is None:
            return True, 1.0, {}  # Assume live if disabled
        
        # Use advanced multi-method detection
        is_live, confidence, details = self.liveness_detector.check_liveness(face_rgb)
        
        return is_live, confidence

    
    def extract_embedding(self, face_rgb: np.ndarray) -> Optional[np.ndarray]:
        """
        Extract face embedding vector from a cropped face image.
        Uses InsightFace to detect face in the crop and extract embedding.
        
        Args:
            face_rgb: RGB face image (any size)
            
        Returns:
            512-D L2-normalized embedding vector or None
        """
        return self.engine.extract_embedding_from_image(face_rgb)
    
    def validate_face_sample(self, 
                            face_rgb: np.ndarray,
                            landmarks: Optional[Dict] = None,
                            check_liveness: bool = None) -> Tuple[bool, str, float]:
        """
        Complete validation pipeline for a face sample
        
        Args:
            face_rgb: RGB face image
            landmarks: Optional facial landmarks
            check_liveness: Override liveness check setting
            
        Returns:
            (is_valid, message, quality_score)
        """
        if face_rgb is None or face_rgb.size == 0:
            return False, "Invalid image", 0.0
        
        # 1. Quality check
        is_good, quality_score, issues = self.check_face_quality(
            face_rgb, 
            landmarks, 
            is_registration=True
        )
        
        if not is_good:
            message = issues[0] if issues else "Poor quality"
            return False, message, quality_score

        # 2. Liveness check (if enabled)
        check_liveness = check_liveness if check_liveness is not None else self.enable_liveness

        if check_liveness:
            is_live, liveness_conf = self.check_liveness(face_rgb)
            if not is_live:
                return False, "Photo/screen detected (spoofing)", quality_score * liveness_conf

        # 3. Embedding extraction
        embedding = self.extract_embedding(face_rgb)
        if embedding is None:
            return False, "Feature extraction failed", quality_score

        return True, "Good quality", quality_score

    
    def recognize_face(self, 
                      query_embedding: np.ndarray) -> Tuple[str, float, bool]:
        """
        Recognize face from embedding
        
        Args:
            query_embedding: Query face embedding vector (512-D)
            
        Returns:
            (name, similarity, is_confident)
        """
        if not self.known_faces:
            return "Unknown", 0.0, False
        
        # Get list of names
        names = list(self.known_faces.keys())
        
        # Match against database
        best_name, similarity, is_confident = self.matcher.match_face(
            query_embedding,
            self.known_faces,
            names
        )
        
        return best_name, similarity, is_confident
    
    def process_frame(self, 
                     image_rgb: np.ndarray,
                     preprocess: bool = True) -> Tuple[List[Dict], List[Dict]]:
        """
        Complete frame processing pipeline.
        
        InsightFace extracts embeddings during detection, so this is
        more efficient than the old detect → crop → encode pipeline.
        
        Args:
            image_rgb: RGB image
            preprocess: Apply preprocessing (CLAHE for lighting normalization)
            
        Returns:
            (detected_faces, recognized_faces)
        """
        # Optional preprocessing (handles varying lighting/cameras)
        if preprocess:
            processed = self.preprocess_image(image_rgb)
        else:
            processed = image_rgb
        
        # Detect faces (embeddings extracted in same pass)
        detected_faces = self.detect_faces(processed)
        
        # Process each face
        recognized_faces = []
        
        for face_data in detected_faces:
            # Get embedding (already computed during detection)
            embedding = face_data.get('embedding')
            
            if embedding is None:
                continue
            
            # Check quality using cropped face
            face_img = self.extract_face_region(processed, face_data)
            if face_img is None:
                continue
            
            landmarks = face_data.get('landmarks')
            is_good, quality, issues = self.check_face_quality(face_img, landmarks)
            
            if not is_good:
                continue
            
            # Recognize using embedding from detection pass
            name, similarity, is_confident = self.recognize_face(embedding)
            
            recognized_faces.append({
                'bbox': face_data['bbox'],
                'landmarks': landmarks,
                'name': name,
                'similarity': similarity,
                'is_confident': is_confident,
                'quality': quality,
                'embedding': embedding  # Include for adaptive learning
            })
        
        return detected_faces, recognized_faces
    
    def register_face(self,
                     face_images_rgb: List[np.ndarray],
                     name: str,
                     employee_id: Optional[str] = None) -> bool:
        """
        Register a person with multiple face samples.
        
        This is the SINGLE registration function used by both:
        - GUI registration (attendance_gui.py)
        - MQTT remote registration (mqtt_face_registration.py)
        
        Process:
        1. For each face image, detect face + extract 512-D embedding
        2. Validate quality (brightness, blur, size)
        3. Store individual embeddings + compute averaged embedding
        4. Save to PKL database
        
        10 diverse photos (front, left, right, up, down, smile, neutral)
        provide robust recognition across varying conditions.
        
        Args:
            face_images_rgb: List of RGB face images
            name: Person's name
            employee_id: Optional employee ID
            
        Returns:
            True if successful (at least 3 valid samples)
        """
        embeddings_to_add = []
        added_count = 0
        rejected_count = 0
        
        print(f"\nProcessing {len(face_images_rgb)} samples for {name}:")
        
        for i, face_img in enumerate(face_images_rgb):
            # Validate quality
            is_valid, message, quality = self.validate_face_sample(
                face_img, 
                check_liveness=False  # Skip liveness for registration
            )
            
            if not is_valid:
                print(f"  Sample {i+1}: ✗ REJECTED - {message} (quality: {quality:.2f})")
                rejected_count += 1
                continue
            
            # Extract embedding using InsightFace
            embedding = self.extract_embedding(face_img)
            
            if embedding is not None:
                embeddings_to_add.append(embedding)
                added_count += 1
                print(f"  Sample {i+1}: ✓ ACCEPTED (quality: {quality:.2f}, embedding: {len(embedding)}-D)")
            else:
                print(f"  Sample {i+1}: ✗ REJECTED - Embedding extraction failed")
                rejected_count += 1
        
        # Save to database
        if added_count > 0:
            # Compute averaged embedding for stable matching
            averaged = np.mean(embeddings_to_add, axis=0)
            averaged = averaged / (np.linalg.norm(averaged) + 1e-10)
            
            self.known_faces[name] = {
                'individual': embeddings_to_add,
                'averaged': averaged,
                'employee_id': employee_id
            }
            
            self.save_database()
            
            print(f"\n✅ Successfully registered {name}!")
            print(f"   Accepted: {added_count}/{len(face_images_rgb)} samples")
            print(f"   Embedding dimension: {len(embeddings_to_add[0])}-D")
            if rejected_count > 0:
                print(f"   Rejected: {rejected_count} low-quality samples")
            
            return True
        
        print(f"\n❌ Registration failed - all samples rejected")
        return False
    
    # Keep add_faces as alias for backward compatibility
    def add_faces(self, 
                 face_images_rgb: List[np.ndarray], 
                 name: str,
                 employee_id: Optional[str] = None) -> bool:
        """
        Add multiple face samples for a person.
        Alias for register_face() - kept for backward compatibility.
        """
        return self.register_face(face_images_rgb, name, employee_id)
    
    def add_embedding_to_existing_person(self, 
                                        person_name: str, 
                                        new_embedding: np.ndarray, 
                                        max_embeddings: int = 50) -> bool:
        """
        Add new embedding to existing person (adaptive learning)
        
        Args:
            person_name: Name of person
            new_embedding: New embedding vector to add (512-D)
            max_embeddings: Maximum embeddings to keep per person
            
        Returns:
            True if added successfully
        """
        if person_name not in self.known_faces:
            return False
        
        person_data = self.known_faces[person_name]
        
        if isinstance(person_data, dict):
            embeddings = person_data['individual']
        else:
            embeddings = person_data
        
        # Check if embedding is unique enough (avoid duplicates)
        from sklearn.metrics.pairwise import cosine_similarity
        
        is_unique = True
        for existing_emb in embeddings[-5:]:  # Check last 5
            sim = cosine_similarity([new_embedding], [existing_emb])[0][0]
            if sim > 0.95:  # Too similar, skip
                is_unique = False
                break
        
        if not is_unique:
            return False
        
        # Add new embedding
        embeddings.append(new_embedding)
        
        # Keep only the most recent embeddings
        if len(embeddings) > max_embeddings:
            embeddings = embeddings[-max_embeddings:]
        
        # Recalculate averaged embedding
        avg_emb = np.mean(embeddings, axis=0)
        avg_emb = avg_emb / (np.linalg.norm(avg_emb) + 1e-10)
        
        # Preserve existing employee_id when updating
        existing_employee_id = person_data.get('employee_id') if isinstance(person_data, dict) else None
        
        self.known_faces[person_name] = {
            'individual': embeddings,
            'averaged': avg_emb,
            'employee_id': existing_employee_id  # Preserve employee_id
        }
        
        self.save_database()
        
        print(f"  ✓ Adaptive learning: {person_name} now has {len(embeddings)} samples")
        
        return True
    
    def validate_all_embeddings(self) -> Dict:
        """
        Validate quality of all stored embeddings.
        Remove low-quality ones.
        
        Returns:
            Dictionary with validation results
        """
        print("\n🔍 Validating all stored embeddings...")
        
        results = {
            'checked': 0,
            'removed': 0,
            'persons_updated': []
        }
        
        for name, data in list(self.known_faces.items()):
            if isinstance(data, dict):
                embeddings = data['individual']
            else:
                embeddings = data
            
            # Check embedding quality (norm should be close to 1.0 for L2-normalized)
            valid_embeddings = []
            
            for emb in embeddings:
                norm = np.linalg.norm(emb)
                results['checked'] += 1
                
                # Valid if norm is between 0.95 and 1.05
                if 0.95 <= norm <= 1.05:
                    valid_embeddings.append(emb)
                else:
                    results['removed'] += 1
            
            # Update if embeddings were removed
            if len(valid_embeddings) != len(embeddings):
                if len(valid_embeddings) >= 3:
                    # Recalculate averaged
                    avg_emb = np.mean(valid_embeddings, axis=0)
                    avg_emb = avg_emb / (np.linalg.norm(avg_emb) + 1e-10)
                    
                    # Preserve employee_id
                    existing_employee_id = data.get('employee_id') if isinstance(data, dict) else None
                    
                    self.known_faces[name] = {
                        'individual': valid_embeddings,
                        'averaged': avg_emb,
                        'employee_id': existing_employee_id
                    }
                    
                    results['persons_updated'].append(name)
                    print(f"  ✓ {name}: {len(embeddings)} → {len(valid_embeddings)} samples")
                else:
                    print(f"  ⚠️ {name}: Too few valid samples ({len(valid_embeddings)}), keeping original")
        
        if results['removed'] > 0:
            self.save_database()
            print(f"\n✓ Validation complete: {results['removed']} invalid embeddings removed")
        else:
            print(f"\n✓ All embeddings valid")
        
        return results
    
    def delete_person(self, name: str) -> bool:
        """Delete person from database"""
        if name in self.known_faces:
            del self.known_faces[name]
            self.save_database()
            print(f"✓ Deleted {name} from database")
            return True
        else:
            print(f"✗ {name} not found in database")
            return False
    
    def get_employee_id(self, name: str) -> Optional[str]:
        """
        Get employee ID for a registered person
        
        Args:
            name: Person's name
            
        Returns:
            Employee ID or None if not found/not set
        """
        if name not in self.known_faces:
            return None
        
        data = self.known_faces[name]
        if isinstance(data, dict):
            return data.get('employee_id', None)
        return None
    
    def update_employee_id(self, name: str, employee_id: str) -> bool:
        """
        Update employee ID for an existing person without deleting face data
        
        Args:
            name: Person's name
            employee_id: New employee ID
            
        Returns:
            True if updated successfully
        """
        if name not in self.known_faces:
            print(f"✗ {name} not found in database")
            return False
        
        data = self.known_faces[name]
        
        # Handle legacy data format (list instead of dict)
        if isinstance(data, list):
            # Convert to new format
            self.known_faces[name] = {
                'individual': data,
                'averaged': np.mean(data, axis=0) / (np.linalg.norm(np.mean(data, axis=0)) + 1e-10),
                'employee_id': employee_id
            }
        else:
            # Standard format - just update employee_id
            self.known_faces[name]['employee_id'] = employee_id
        
        self.save_database()
        print(f"✓ Updated employee ID for {name}: {employee_id}")
        return True
    
    def list_persons(self) -> Dict[str, int]:
        """List all registered persons with sample counts"""
        persons = {}
        for name, data in self.known_faces.items():
            if isinstance(data, dict):
                count = len(data.get('individual', []))
            else:
                count = len(data)
            persons[name] = count
        return persons
    
    def get_statistics(self) -> Dict:
        """Get system statistics"""
        total_persons = len(self.known_faces)
        total_samples = sum(
            len(data['individual']) if isinstance(data, dict) else len(data)
            for data in self.known_faces.values()
        )
        
        return {
            'total_persons': total_persons,
            'total_samples': total_samples,
            'avg_samples_per_person': total_samples / total_persons if total_persons > 0 else 0,
            'preprocessing': self.preprocessor.method,
            'liveness_enabled': self.enable_liveness,
            'face_alignment': self.use_face_alignment,
            'recognition_threshold': self.recognition_threshold,
            'engine': 'InsightFace',
            'embedding_dim': 512
        }
    
    def get_person_details(self, name: str) -> Optional[Dict]:
        """
        Get detailed information about a registered person
        
        Args:
            name: Person's name
            
        Returns:
            Dictionary with person details or None
        """
        if name not in self.known_faces:
            return None
        
        data = self.known_faces[name]
        
        if isinstance(data, dict):
            embeddings = data['individual']
            has_averaged = data.get('averaged') is not None
        else:
            embeddings = data
            has_averaged = False
        
        # Calculate embedding quality
        norms = [np.linalg.norm(emb) for emb in embeddings]
        avg_norm = np.mean(norms)
        
        # Calculate diversity (average distance between embeddings)
        from sklearn.metrics.pairwise import cosine_similarity
        
        if len(embeddings) > 1:
            similarities = []
            for i in range(len(embeddings)):
                for j in range(i + 1, len(embeddings)):
                    sim = cosine_similarity([embeddings[i]], [embeddings[j]])[0][0]
                    similarities.append(sim)
            diversity = 1.0 - np.mean(similarities)  # Higher = more diverse
        else:
            diversity = 0.0
        
        return {
            'name': name,
            'sample_count': len(embeddings),
            'has_averaged': has_averaged,
            'avg_norm': avg_norm,
            'diversity_score': diversity,
            'quality_status': 'Good' if 0.95 <= avg_norm <= 1.05 else 'Poor',
            'employee_id': data.get('employee_id') if isinstance(data, dict) else None,
            'embedding_dim': len(embeddings[0]) if embeddings else 0
        }
