#!/usr/bin/env python3
"""
MQTT Incident Reporter
Sends unknown person alerts to MQTT server with base64 image and timestamp
"""

import json
import base64
import time
from datetime import datetime
import numpy as np
import cv2
import paho.mqtt.client as mqtt
import config
import requests

class MQTTIncidentReporter:
    """Reports unknown person incidents to MQTT server"""
    
    def __init__(self, broker_host=None, broker_port=None, topic=None):
        """
        Initialize MQTT client
        
        Args:
            broker_host: MQTT broker IP address (defaults to config.MQTT_BROKER_HOST)
            broker_port: MQTT broker port (defaults to config.MQTT_BROKER_PORT)
            topic: MQTT topic for incidents (defaults to config.MQTT_TOPIC)
        """
        # Use config values if not provided
        self.broker_host = broker_host if broker_host is not None else config.MQTT_BROKER_HOST
        self.broker_port = broker_port if broker_port is not None else config.MQTT_BROKER_PORT
        self.topic = topic if topic is not None else config.MQTT_TOPIC
        
        self.client = None
        self.connected = False
        
        self._setup_client()
    
    def _setup_client(self):
        """Setup MQTT client"""
        try:
            self.client = mqtt.Client(client_id=f"attendance_system_{int(time.time())}")
            
            self.client.on_connect = self._on_connect
            self.client.on_disconnect = self._on_disconnect
            self.client.on_publish = self._on_publish
            
            print(f"Connecting to MQTT broker at {self.broker_host}:{self.broker_port}...")
            self.client.connect(self.broker_host, self.broker_port, 60)
            
            self.client.loop_start()
            
        except Exception as e:
            print(f"⚠️ MQTT connection failed: {e}")
            self.connected = False
    
    def _on_connect(self, client, userdata, flags, rc):
        """Callback when connected to MQTT broker"""
        if rc == 0:
            self.connected = True
            print(f"✓ Connected to MQTT broker at {self.broker_host}:{self.broker_port}")
        else:
            self.connected = False
            print(f"❌ MQTT connection failed with code {rc}")
    
    def _on_disconnect(self, client, userdata, rc):
        """Callback when disconnected from MQTT broker"""
        self.connected = False
        if rc != 0:
            print(f"⚠️ Unexpected MQTT disconnection. Reconnecting...")
    
    def _on_publish(self, client, userdata, mid):
        """Callback when message is published"""
        print(f"✓ MQTT message published (mid: {mid})")
    
    def send_incident(self, frame: np.ndarray, detection_time: datetime, 
                     duration: float, bbox: tuple = None,
                     unknown_person_id: str = None,
                     incident_number: int = 1) -> bool:
        """
        Send unknown person incident to MQTT server
        
        Args:
            frame: The frame containing unknown person (RGB numpy array)
            detection_time: When the person was first detected
            duration: How long they've been in frame (seconds)
            bbox: Bounding box (x, y, w, h) - if None, sends whole frame
            unknown_person_id: ID of the unknown person (e.g., "foreign_1")
            incident_number: Incident count for this person
        
        Returns:
            bool: True if sent successfully, False otherwise
        """
        if not self.connected:
            print("⚠️ Not connected to MQTT broker, cannot send incident")
            return False
        
        try:
            # Convert frame to base64
            frame_bgr = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
            
            # Only crop if bbox is provided, otherwise send whole frame
            if bbox:
                x, y, w, h = bbox
                padding = int(max(w, h) * 0.3)
                x1 = max(0, x - padding)
                y1 = max(0, y - padding)
                x2 = min(frame_bgr.shape[1], x + w + padding)
                y2 = min(frame_bgr.shape[0], y + h + padding)
                frame_bgr = frame_bgr[y1:y2, x1:x2]
            # Else: frame_bgr remains the whole frame
            
            # Encode to JPEG
            _, buffer = cv2.imencode('.jpg', frame_bgr, [cv2.IMWRITE_JPEG_QUALITY, 85])
            image_bytes = buffer.tobytes()
            image_base64 = base64.b64encode(image_bytes).decode('utf-8')
            image_base64 = base64.b64encode(buffer).decode('utf-8')
            
            # Create incident payload
            incident_data = {
                "type": "unknown_person",
                "unknown_person_id": unknown_person_id if unknown_person_id else "unknown",
                "incident_number": incident_number,
                "timestamp": int(detection_time.timestamp()),
                "duration": round(duration, 2),
                "image": image_base64,
                "image_format": "jpeg",
                "image_type": "whole_frame" if bbox is None else "cropped_face"
            }
            
            # Convert to JSON
            payload = json.dumps(incident_data)
            print('-'*60)
            print(f"Sending payload: {payload}")
            print('-'*60)
            
            # # post to emergency server
            # emergency_url = "http://192.168.1.200:8885/send-notification"
            # response = requests.post(emergency_url, json=incident_data)
            # if response.status_code == 200:
            #     print("✓ Incident reported to emergency server")
            # else:
            #     print(f"⚠️ Failed to report incident to emergency server (status: {response.status_code})")

            # Publish to MQTT
            result = self.client.publish(self.topic, payload, qos=1)
            
            if result.rc == mqtt.MQTT_ERR_SUCCESS:
                person_id_str = f" ({unknown_person_id})" if unknown_person_id else ""
                print(f"✓ Incident sent: Unknown person{person_id_str} detected for {duration:.1f}s (incident #{incident_number})")
                return True
            else:
                print(f"⚠️ Failed to publish incident (rc: {result.rc})")
                return False
                
        except Exception as e:
            print(f"❌ Error sending incident: {e}")
            return False
    
    def disconnect(self):
        """Disconnect from MQTT broker"""
        if self.client:
            self.client.loop_stop()
            self.client.disconnect()
            self.connected = False
            print("Disconnected from MQTT broker")
