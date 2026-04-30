#!/usr/bin/env python3
"""
Simple Face Recognition using MobileFaceNet TFLite
Lightweight face recognition with TensorFlow Lite model
Supports both float32 and quantized (uint8/int8) models
"""


import cv2
import numpy as np
import mediapipe as mp
from picamera2 import Picamera2
import tensorflow as tf
import time
import argparse
import os
import pickle
from sklearn.metrics.pairwise import cosine_similarity
import json



class MobileFaceNetTFLite:
    def __init__(self, model_path="models/mobilefacenet.tflite"):
        """
        Initialize MobileFaceNet TFLite model
        
        Args:
            model_path: Path to TFLite model file
        """
        self.model_path = model_path
        self.interpreter = None
        self.input_details = None
        self.output_details = None
        self.input_shape = None
        self.is_quantized = False
        self.input_scale = None
        self.input_zero_point = None
        self.output_scale = None
        self.output_zero_point = None
        
        self._load_model()
    
    def _load_model(self):
        """Load TFLite model and detect quantization parameters"""
        if not os.path.exists(self.model_path):
            print(f"Model file not found: {self.model_path}")
            print("Please place the MobileFaceNet TFLite model in the models/ directory")
            raise FileNotFoundError(f"Model file not found: {self.model_path}")
        
        try:
            # Load TFLite model
            self.interpreter = tf.lite.Interpreter(model_path=self.model_path)
            self.interpreter.allocate_tensors()
            
            # Get input and output details
            self.input_details = self.interpreter.get_input_details()
            self.output_details = self.interpreter.get_output_details()
            
            # Get input shape
            self.input_shape = self.input_details[0]['shape'][1:3]  # Height, Width
            
            # Check if model is quantized
            input_dtype = self.input_details[0]['dtype']
            output_dtype = self.output_details[0]['dtype']
            
            if input_dtype in [np.uint8, np.int8]:
                self.is_quantized = True
                
                # Get quantization parameters
                input_quant_params = self.input_details[0]['quantization_parameters']
                self.input_scale = input_quant_params['scales'][0] if len(input_quant_params['scales']) > 0 else 1.0
                self.input_zero_point = input_quant_params['zero_points'][0] if len(input_quant_params['zero_points']) > 0 else 0
                
                output_quant_params = self.output_details[0]['quantization_parameters']
                self.output_scale = output_quant_params['scales'][0] if len(output_quant_params['scales']) > 0 else 1.0
                self.output_zero_point = output_quant_params['zero_points'][0] if len(output_quant_params['zero_points']) > 0 else 0
                
                print(f"MobileFaceNet TFLite model loaded successfully!")
                print(f"Model Type: QUANTIZED ({input_dtype.__name__})")
                print(f"Input shape: {self.input_shape}")
                print(f"Input quantization: scale={self.input_scale:.6f}, zero_point={self.input_zero_point}")
                print(f"Output shape: {self.output_details[0]['shape']}")
                print(f"Output quantization: scale={self.output_scale:.6f}, zero_point={self.output_zero_point}")
            else:
                print(f"MobileFaceNet TFLite model loaded successfully!")
                print(f"Model Type: FLOAT32")
                print(f"Input shape: {self.input_shape}")
                print(f"Output shape: {self.output_details[0]['shape']}")
            
        except Exception as e:
            print(f"Error loading TFLite model: {e}")
            raise
    
    def preprocess_face(self, face_img):
        """
        Preprocess face image for MobileFaceNet
        Handles both float32 and quantized (uint8/int8) models
        
        Args:
            face_img: Input face image (BGR format)
            
        Returns:
            Preprocessed image ready for inference
        """
        # Convert BGR to RGB
        face_rgb = cv2.cvtColor(face_img, cv2.COLOR_BGR2RGB)
        
        # Resize to model input size
        face_resized = cv2.resize(face_rgb, tuple(self.input_shape))
        
        if self.is_quantized:
            # For quantized models (uint8/int8)
            # Input should be uint8 [0, 255] or normalized then quantized
            input_dtype = self.input_details[0]['dtype']
            
            if input_dtype == np.uint8:
                # If model expects uint8, use raw pixel values [0, 255]
                face_input = face_resized.astype(np.uint8)
            else:
                # For int8, quantize normalized values
                # Normalize to [0, 1] then apply quantization formula
                face_normalized = face_resized.astype(np.float32) / 255.0
                # Quantization formula: q = (r / scale) + zero_point
                face_input = (face_normalized / self.input_scale + self.input_zero_point).astype(input_dtype)
        else:
            # For float32 models
            # Normalize to [0, 1]
            face_input = face_resized.astype(np.float32) / 255.0
        
        # Add batch dimension
        face_batch = np.expand_dims(face_input, axis=0)
        
        return face_batch
    
    def dequantize_output(self, output):
        """
        Dequantize output tensor if model is quantized
        Formula: r = scale * (q - zero_point)
        
        Args:
            output: Quantized output tensor
            
        Returns:
            Dequantized float output
        """
        if self.is_quantized:
            return self.output_scale * (output.astype(np.float32) - self.output_zero_point)
        else:
            return output
    
    def extract_embedding(self, face_img):
        """
        Extract face embedding using MobileFaceNet
        
        Args:
            face_img: Input face image
            
        Returns:
            Face embedding vector
        """
        try:
            # Preprocess image
            input_data = self.preprocess_face(face_img)
            
            # Set input tensor
            self.interpreter.set_tensor(self.input_details[0]['index'], input_data)
            
            # Run inference
            self.interpreter.invoke()
            
            # Get output
            embedding = self.interpreter.get_tensor(self.output_details[0]['index'])
            
            # Dequantize output if quantized
            embedding = self.dequantize_output(embedding)
            
            # Normalize embedding (L2 normalization)
            embedding = embedding / np.linalg.norm(embedding)
            
            return embedding.flatten()
            
        except Exception as e:
            print(f"Embedding extraction error: {e}")
            return None



class SimpleFaceRecognizer:
    def __init__(self, model_path="models/mobilefacenet.tflite", 
                 detection_confidence=0.7, recognition_threshold=0.6):
        """
        Initialize simple face recognizer
        
        Args:
            model_path: Path to MobileFaceNet TFLite model
            detection_confidence: MediaPipe detection confidence
            recognition_threshold: Face recognition similarity threshold
        """
        self.detection_confidence = detection_confidence
        self.recognition_threshold = recognition_threshold
        
        # Initialize MediaPipe Face Detection
        self.mp_face_detection = mp.solutions.face_detection
        self.face_detection = self.mp_face_detection.FaceDetection(
            model_selection=0,
            min_detection_confidence=detection_confidence
        )
        
        # Initialize MobileFaceNet
        self.face_encoder = MobileFaceNetTFLite(model_path)
        
        # Initialize camera
        self.picam2 = Picamera2()
        config = self.picam2.create_preview_configuration(
            main={"format": 'RGB888', "size": (1280, 1080)}
        )
        self.picam2.configure(config)
        
        # Load face database
        self.known_faces = self.load_database()
        
        print("Simple face recognizer initialized!")
    
    def load_database(self, db_path="simple_faces.pkl"):
        """Load face database"""
        if os.path.exists(db_path):
            with open(db_path, 'rb') as f:
                faces = pickle.load(f)
            print(f"Loaded {len(faces)} known faces")
            return faces
        else:
            print("No face database found, starting fresh")
            return {}
    
    def save_database(self, db_path="simple_faces.pkl"):
        """Save face database"""
        with open(db_path, 'wb') as f:
            pickle.dump(self.known_faces, f)
        print("Face database saved!")
    
    def detect_faces(self, frame):
        """Detect faces in frame using MediaPipe"""
        results = self.face_detection.process(frame)
        
        faces = []
        if results.detections:
            h, w = frame.shape[:2]
            
            for detection in results.detections:
                bbox = detection.location_data.relative_bounding_box
                
                x = int(bbox.xmin * w)
                y = int(bbox.ymin * h)
                width = int(bbox.width * w)
                height = int(bbox.height * h)
                
                # Ensure coordinates are within bounds
                x = max(0, x)
                y = max(0, y)
                width = min(width, w - x)
                height = min(height, h - y)
                
                confidence = detection.score[0] if detection.score else 0.0
                
                faces.append({
                    'bbox': (x, y, width, height),
                    'confidence': confidence
                })
        
        return faces
    
    def extract_face_region(self, frame, bbox, padding=0.1):
        """Extract face region from frame"""
        x, y, width, height = bbox
        h, w = frame.shape[:2]
        
        # Add padding
        pad_w = int(width * padding)
        pad_h = int(height * padding)
        
        x1 = max(0, x - pad_w)
        y1 = max(0, y - pad_h)
        x2 = min(w, x + width + pad_w)
        y2 = min(h, y + height + pad_h)
        
        face_region = frame[y1:y2, x1:x2]
        return face_region if face_region.size > 0 else None
    
    def recognize_face(self, embedding):
        """Recognize face using stored embeddings"""
        if not self.known_faces:
            return "Unknown", 0.0
        
        best_match = "Unknown"
        best_similarity = 0.0
        
        for name, stored_embeddings in self.known_faces.items():
            for stored_embedding in stored_embeddings:
                similarity = cosine_similarity([embedding], [stored_embedding])[0][0]
                if similarity > best_similarity:
                    best_similarity = similarity
                    best_match = name
        
        if best_similarity >= self.recognition_threshold:
            return best_match, best_similarity
        else:
            return "Unknown", best_similarity
    
    def add_face(self, face_img, name):
        """Add face to database"""
        embedding = self.face_encoder.extract_embedding(face_img)
        if embedding is None:
            return False
        
        if name not in self.known_faces:
            self.known_faces[name] = []
        
        self.known_faces[name].append(embedding)
        self.save_database()
        print(f"Added face for {name}!")
        return True
    
    def run_recognition(self, show_display=True):
        """Run face recognition"""
        self.picam2.start()
        
        try:
            print("Starting face recognition...")
            print("Press 'q' to quit, 'a' to add face")
            
            add_mode = False
            add_name = None
            
            # Create fullscreen window if display is enabled
            if show_display:
                cv2.namedWindow('MobileFaceNet Recognition', cv2.WINDOW_NORMAL)
                cv2.setWindowProperty('MobileFaceNet Recognition', cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN)
            
            while True:
                # Capture frame
                frame = self.picam2.capture_array()
                frame_bgr = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
                
                # Detect faces
                faces = self.detect_faces(frame)
                
                # Process each face
                for face in faces:
                    bbox = face['bbox']
                    x, y, width, height = bbox
                    
                    # Extract face region
                    face_img = self.extract_face_region(frame_bgr, bbox)
                    
                    if face_img is not None:
                        # Get embedding and recognize
                        embedding = self.face_encoder.extract_embedding(face_img)
                        
                        if embedding is not None:
                            name, similarity = self.recognize_face(embedding)
                            
                            # Draw bounding box and label
                            color = (0, 255, 0) if name != "Unknown" else (0, 0, 255)
                            cv2.rectangle(frame_bgr, (x, y), (x + width, y + height), color, 2)
                            
                            label = f"{name} ({similarity:.2f})"
                            cv2.putText(frame_bgr, label, (x, y - 10), 
                                      cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)
                
                # Add mode overlay
                if add_mode and add_name:
                    cv2.putText(frame_bgr, f"ADD MODE: {add_name} - Press 's' to save", 
                              (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)
                
                # Display frame
                if show_display:
                    cv2.imshow('MobileFaceNet Recognition', frame_bgr)
                    
                    key = cv2.waitKey(1) & 0xFF
                    if key == ord('q'):
                        break
                    elif key == ord('a'):
                        name = input("\nEnter name for new face: ")
                        if name.strip():
                            add_mode = True
                            add_name = name.strip()
                            print(f"ADD MODE: Position face and press 's' to save as '{add_name}'")
                    elif key == ord('s') and add_mode and add_name and faces:
                        # Save first detected face
                        face = faces[0]
                        face_img = self.extract_face_region(frame_bgr, face['bbox'])
                        if face_img is not None:
                            success = self.add_face(face_img, add_name)
                            if success:
                                add_mode = False
                                add_name = None
                
                time.sleep(0.03)  # ~30 FPS
                
        except KeyboardInterrupt:
            print("\nStopping recognition...")
        
        finally:
            self.picam2.stop()
            if show_display:
                cv2.destroyAllWindows()
            print("Cleanup completed")
    
    def recognize_from_image(self, image_path):
        """Recognize faces in an image file"""
        try:
            image = cv2.imread(image_path)
            if image is None:
                print(f"Could not load image: {image_path}")
                return
            
            # Convert BGR to RGB for MediaPipe
            image_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
            
            # Detect faces
            faces = self.detect_faces(image_rgb)
            
            if not faces:
                print("No faces detected in image")
                return
            
            print(f"Found {len(faces)} face(s) in {image_path}:")
            
            for i, face in enumerate(faces):
                face_img = self.extract_face_region(image, face['bbox'])
                
                if face_img is not None:
                    embedding = self.face_encoder.extract_embedding(face_img)
                    
                    if embedding is not None:
                        name, similarity = self.recognize_face(embedding)
                        print(f"  Face {i+1}: {name} (similarity: {similarity:.3f})")
                        
                        # Draw on image
                        x, y, width, height = face['bbox']
                        color = (0, 255, 0) if name != "Unknown" else (0, 0, 255)
                        cv2.rectangle(image, (x, y), (x + width, y + height), color, 2)
                        cv2.putText(image, f"{name} ({similarity:.2f})", (x, y - 10), 
                                  cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)
            
            # Save result
            output_path = f"result_{os.path.basename(image_path)}"
            cv2.imwrite(output_path, image)
            print(f"Result saved to {output_path}")
            
        except Exception as e:
            print(f"Error processing image: {e}")



def main():
    parser = argparse.ArgumentParser(description='Simple Face Recognition with MobileFaceNet TFLite')
    parser.add_argument('--model', default='models/mobilefacenet.tflite',
                       help='Path to MobileFaceNet TFLite model')
    parser.add_argument('--detection-confidence', type=float, default=0.7,
                       help='MediaPipe detection confidence (default: 0.7)')
    parser.add_argument('--recognition-threshold', type=float, default=0.6,
                       help='Face recognition threshold (default: 0.6)')
    parser.add_argument('--no-display', action='store_true',
                       help='Run without display')
    parser.add_argument('--image', type=str,
                       help='Process single image file')
    
    args = parser.parse_args()
    
    try:
        # Create recognizer
        recognizer = SimpleFaceRecognizer(
            model_path=args.model,
            detection_confidence=args.detection_confidence,
            recognition_threshold=args.recognition_threshold
        )
        
        if args.image:
            # Process single image
            recognizer.recognize_from_image(args.image)
        else:
            # Run live recognition
            recognizer.run_recognition(show_display=not args.no_display)
            
    except Exception as e:
        print(f"Error: {e}")
        print("\nMake sure you have the MobileFaceNet TFLite model in models/mobilefacenet.tflite")
        print("You can download it from: https://github.com/sirius-ai/MobileFaceNet_TF")



if __name__ == "__main__":
    main()
