"""
Face Encoding Module
Wraps MobileFaceNet TFLite model
"""

import cv2
import numpy as np
import tensorflow as tf
import os


class FaceEncoder:
    """
    Face embedding extraction using MobileFaceNet
    """
    
    def __init__(self, model_path="models/mobilefacenet.tflite", input_size=(160, 160)):
        """
        Args:
            model_path: Path to TFLite model
            input_size: Model input size
        """
        self.model_path = model_path
        self.input_size = input_size
        
        if not os.path.exists(model_path):
            raise FileNotFoundError(f"Model not found: {model_path}")
        
        # Load TFLite model
        self.interpreter = tf.lite.Interpreter(model_path=model_path)
        self.interpreter.allocate_tensors()
        
        self.input_details = self.interpreter.get_input_details()
        self.output_details = self.interpreter.get_output_details()
        
        # Check if quantized
        input_dtype = self.input_details[0]['dtype']
        self.is_quantized = input_dtype in [np.uint8, np.int8]
        
        if self.is_quantized:
            quant_params = self.input_details[0]['quantization_parameters']
            self.input_scale = quant_params['scales'][0] if len(quant_params['scales']) > 0 else 1.0
            self.input_zero_point = quant_params['zero_points'][0] if len(quant_params['zero_points']) > 0 else 0
            
            output_quant = self.output_details[0]['quantization_parameters']
            self.output_scale = output_quant['scales'][0] if len(output_quant['scales']) > 0 else 1.0
            self.output_zero_point = output_quant['zero_points'][0] if len(output_quant['zero_points']) > 0 else 0
    
    def preprocess(self, face_rgb):
        """
        Preprocess face for model input
        
        Args:
            face_rgb: RGB face image
            
        Returns:
            Preprocessed tensor
        """
        # Resize to model input size
        face_resized = cv2.resize(face_rgb, self.input_size)
        
        if self.is_quantized:
            # Quantized model
            input_dtype = self.input_details[0]['dtype']
            
            if input_dtype == np.uint8:
                face_input = face_resized.astype(np.uint8)
            else:
                face_normalized = face_resized.astype(np.float32) / 255.0
                face_input = (face_normalized / self.input_scale + self.input_zero_point).astype(input_dtype)
        else:
            # Float model
            face_input = face_resized.astype(np.float32) / 255.0
        
        # Add batch dimension
        return np.expand_dims(face_input, axis=0)
    
    def extract_embedding(self, face_rgb):
        """
        Extract face embedding vector
        
        Args:
            face_rgb: RGB face image
            
        Returns:
            Normalized embedding vector (128-D)
        """
        try:
            # Preprocess
            input_data = self.preprocess(face_rgb)
            
            # Run inference
            self.interpreter.set_tensor(self.input_details[0]['index'], input_data)
            self.interpreter.invoke()
            
            # Get output
            embedding = self.interpreter.get_tensor(self.output_details[0]['index'])
            
            # Dequantize if needed
            if self.is_quantized:
                embedding = self.output_scale * (embedding.astype(np.float32) - self.output_zero_point)
            
            # L2 normalize
            embedding = embedding.flatten()
            norm = np.linalg.norm(embedding)
            if norm > 0:
                embedding = embedding / norm
            
            return embedding
            
        except Exception as e:
            print(f"Embedding extraction error: {e}")
            return None
