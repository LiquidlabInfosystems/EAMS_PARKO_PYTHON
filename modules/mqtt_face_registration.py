"""
MQTT Face Registration Handler
Handles remote face registration via MQTT messages

Subscribe topic: eams/addface
Publish topic: eams/addface/result

Payload format:
{
    "session_id": "unique_session_id",  # For tracking multiple simultaneous registrations
    "name": "Employee Name",
    "employee_id": "EMP001",
    "images": ["base64_image_1", "base64_image_2", ...]
}

Response format:
{
    "session_id": "unique_session_id",
    "success": true/false,
    "message": "Status message",
    "data": {
        "name": "Employee Name",
        "valid_samples": 8,
        "total_samples": 10,
        "validation_results": [...]
    }
}
"""

import json
import base64
import numpy as np
from io import BytesIO
from PIL import Image
import paho.mqtt.client as mqtt
from typing import Optional, Dict, List
import threading
import traceback


class MQTTFaceRegistrationHandler:
    """Handles face registration requests via MQTT"""
    
    def __init__(self, 
                 face_recognizer,
                 broker_host: str,
                 broker_port: int = 1883,
                 subscribe_topic: str = "eams/addface",
                 result_topic: str = "eams/addface/result"):
        """
        Initialize MQTT face registration handler
        
        Args:
            face_recognizer: FaceRecognizer instance to use for registration
            broker_host: MQTT broker hostname
            broker_port: MQTT broker port
            subscribe_topic: Topic to subscribe for registration requests
            result_topic: Topic to publish registration results
        """
        self.face_recognizer = face_recognizer
        self.broker_host = broker_host
        self.broker_port = broker_port
        self.subscribe_topic = subscribe_topic
        self.result_topic = result_topic
        
        self.client = None
        self.connected = False
        self._running = False
        
        # Track active registrations (session_id -> status)
        self.active_registrations: Dict[str, str] = {}
        
    def start(self):
        """Start the MQTT handler in a background thread"""
        self._running = True
        self.client = mqtt.Client()
        self.client.on_connect = self._on_connect
        self.client.on_disconnect = self._on_disconnect
        self.client.on_message = self._on_message
        
        try:
            self.client.connect(self.broker_host, self.broker_port, 60)
            self.client.loop_start()
            print(f"✓ MQTT Face Registration handler started - Listening on: {self.subscribe_topic}")
        except Exception as e:
            print(f"❌ MQTT Face Registration handler failed to connect: {e}")
    
    def stop(self):
        """Stop the MQTT handler"""
        self._running = False
        if self.client:
            self.client.loop_stop()
            self.client.disconnect()
            print("✓ MQTT Face Registration handler stopped")
    
    def _on_connect(self, client, userdata, flags, rc):
        """Handle MQTT connection"""
        if rc == 0:
            self.connected = True
            client.subscribe(self.subscribe_topic)
            print(f"✓ MQTT Face Registration: Connected and subscribed to {self.subscribe_topic}")
        else:
            print(f"❌ MQTT Face Registration: Connection failed with code {rc}")
    
    def _on_disconnect(self, client, userdata, rc):
        """Handle MQTT disconnection"""
        self.connected = False
        print(f"⚠️ MQTT Face Registration: Disconnected (rc={rc})")
        
        # Attempt reconnect if still running
        if self._running:
            try:
                client.reconnect()
            except Exception as e:
                print(f"❌ MQTT Face Registration: Reconnect failed: {e}")
    
    def _on_message(self, client, userdata, msg):
        """Handle incoming MQTT message"""
        print(f"📥 MQTT Face Registration: Message received on topic '{msg.topic}'")
        print(f"📥 MQTT Face Registration: Payload size: {len(msg.payload)} bytes")
        
        try:
            payload = json.loads(msg.payload.decode('utf-8'))
            session_id = payload.get('session_id', 'unknown')
            name = payload.get('name', 'unknown')
            employee_id = payload.get('employee_id', 'unknown')
            num_images = len(payload.get('images', []))
            
            print(f"📥 MQTT Face Registration: Parsed payload - Session: {session_id}, Name: {name}, Employee ID: {employee_id}, Images: {num_images}")
            
            # Process in a separate thread to not block MQTT
            thread = threading.Thread(target=self._process_registration, args=(payload,))
            thread.daemon = True
            thread.start()
            print(f"📥 MQTT Face Registration: Started processing thread for session {session_id}")
            
        except json.JSONDecodeError as e:
            print(f"❌ MQTT Face Registration: Invalid JSON payload: {e}")
            self._publish_error(None, "Invalid JSON payload")
        except Exception as e:
            print(f"❌ MQTT Face Registration: Error processing message: {e}")
            self._publish_error(None, str(e))
    
    def _process_registration(self, payload: Dict):
        """Process a face registration request"""
        session_id = payload.get('session_id', 'unknown')
        
        try:
            # Mark registration as active
            self.active_registrations[session_id] = 'processing'
            
            # Validate required fields
            name = payload.get('name', '').strip()
            employee_id = payload.get('employee_id', '').strip()
            images = payload.get('images', [])
            
            if not name:
                self._publish_result(session_id, False, "Name is required")
                return
            
            if not employee_id:
                self._publish_result(session_id, False, "Employee ID is required")
                return
            
            if not images or len(images) < 3:
                self._publish_result(session_id, False, "At least three images are required")
                return
            
            print(f"📸 MQTT Face Registration: Processing {len(images)} images for {name} (Session: {session_id})")
            
            # Process each image
            valid_face_images = []
            validation_results = []
            
            for i, base64_img in enumerate(images):
                try:
                    # Decode base64 image
                    face_rgb = self._decode_base64_image(base64_img)
                    
                    if face_rgb is None:
                        validation_results.append({
                            'image_index': i,
                            'valid': False,
                            'message': 'Failed to decode image'
                        })
                        continue
                    
                    # Preprocess image for consistent lighting/noise handling
                    # This is critical for cross-camera registration compatibility
                    preprocessed = self.face_recognizer.preprocess_image(face_rgb)
                    
                    # Detect face in preprocessed image
                    faces = self.face_recognizer.detect_faces(preprocessed)
                    
                    if not faces:
                        validation_results.append({
                            'image_index': i,
                            'valid': False,
                            'message': 'No face detected in image'
                        })
                        continue
                    
                    # Get the largest face
                    face = max(faces, key=lambda f: f['bbox'][2] * f['bbox'][3])
                    
                    # Extract face region from preprocessed image
                    face_img = self.face_recognizer.extract_face_region(preprocessed, face, align=True)
                    
                    if face_img is None:
                        validation_results.append({
                            'image_index': i,
                            'valid': False,
                            'message': 'Failed to extract face region'
                        })
                        continue
                    
                    # Validate face quality using existing system
                    is_valid, msg, quality = self.face_recognizer.validate_face_sample(
                        face_img,
                        check_liveness=False  # Can't check liveness from static image
                    )
                    
                    if is_valid:
                        valid_face_images.append(face_img)
                        validation_results.append({
                            'image_index': i,
                            'valid': True,
                            'message': 'Valid face',
                            'quality': quality
                        })
                    else:
                        validation_results.append({
                            'image_index': i,
                            'valid': False,
                            'message': msg,
                            'quality': quality
                        })
                        
                except Exception as e:
                    validation_results.append({
                        'image_index': i,
                        'valid': False,
                        'message': f'Error processing image: {str(e)}'
                    })
            
            # Check minimum valid samples
            min_samples = 3  # Minimum required for registration
            if len(valid_face_images) < min_samples:
                self._publish_result(
                    session_id, 
                    False, 
                    f"Not enough valid face samples. Got {len(valid_face_images)}, need at least {min_samples}",
                    {
                        'name': name,
                        'valid_samples': len(valid_face_images),
                        'total_samples': len(images),
                        'validation_results': validation_results
                    }
                )
                return
            
            # Register face using existing system
            print(f"🔄 MQTT Face Registration: Calling add_faces for {name} (Session: {session_id}) with {len(valid_face_images)} valid samples...")
            success = self.face_recognizer.add_faces(valid_face_images, name, employee_id)
            
            if success:
                print(f"✅ MQTT Face Registration: SUCCESS - Registered {name} (Employee ID: {employee_id}) with {len(valid_face_images)} samples (Session: {session_id})")
                print(f"✅ MQTT Face Registration: Registration complete for session {session_id}")
                self._publish_result(
                    session_id,
                    True,
                    f"Successfully registered {name}",
                    {
                        'name': name,
                        'employee_id': employee_id,
                        'valid_samples': len(valid_face_images),
                        'total_samples': len(images),
                        'validation_results': validation_results
                    }
                )
            else:
                print(f"❌ MQTT Face Registration: FAILED - Could not register {name} (Employee ID: {employee_id}) - database error (Session: {session_id})")
                self._publish_result(
                    session_id,
                    False,
                    "Failed to register face - database error",
                    {
                        'name': name,
                        'valid_samples': len(valid_face_images),
                        'total_samples': len(images),
                        'validation_results': validation_results
                    }
                )
                
        except Exception as e:
            print(f"❌ MQTT Face Registration: Error in registration: {e}")
            traceback.print_exc()
            self._publish_result(session_id, False, f"Registration error: {str(e)}")
        finally:
            # Remove from active registrations
            if session_id in self.active_registrations:
                del self.active_registrations[session_id]
    
    def _decode_base64_image(self, base64_str: str) -> Optional[np.ndarray]:
        """Decode base64 string to RGB numpy array"""
        try:
            # Remove data URL prefix if present
            if ',' in base64_str:
                base64_str = base64_str.split(',')[1]
            
            # Decode base64
            image_data = base64.b64decode(base64_str)
            
            # Open with PIL
            image = Image.open(BytesIO(image_data))
            
            # Convert to RGB if necessary
            if image.mode != 'RGB':
                image = image.convert('RGB')
            
            # Convert to numpy array
            return np.array(image)
            
        except Exception as e:
            print(f"❌ Error decoding base64 image: {e}")
            return None
    
    def _publish_result(self, session_id: str, success: bool, message: str, data: Dict = None):
        """Publish registration result to MQTT"""
        result = {
            'session_id': session_id,
            'success': success,
            'message': message
        }
        
        if data:
            result['data'] = data
        
        try:
            if self.client and self.connected:
                self.client.publish(self.result_topic, json.dumps(result))
                print(f"📤 MQTT Result published for session {session_id}: {message}")
            else:
                print(f"⚠️ Cannot publish result - MQTT not connected")
        except Exception as e:
            print(f"❌ Error publishing result: {e}")
    
    def _publish_error(self, session_id: Optional[str], error_message: str):
        """Publish error result to MQTT"""
        self._publish_result(session_id or 'unknown', False, error_message)
