#!/usr/bin/env python3
"""
Simple MQTT Test Script
Connects to broker, sends JSON, and checks for responses
"""

import json
import time
import paho.mqtt.client as mqtt

# Configuration
BROKER_HOST = "13.233.174.50"
BROKER_PORT = 1869
TOPIC = "/incidents"

# Flags
connected = False
message_sent = False
response_received = False


def on_connect(client, userdata, flags, rc):
    """Called when connected to broker"""
    global connected
    if rc == 0:
        connected = True
        print(f"✓ Connected to {BROKER_HOST}:{BROKER_PORT}")
        # Subscribe to same topic to see our message
        client.subscribe(TOPIC)
        print(f"✓ Subscribed to topic: {TOPIC}")
    else:
        print(f"✗ Connection failed with code {rc}")


def on_publish(client, userdata, mid):
    """Called when message is published"""
    global message_sent
    message_sent = True
    print(f"✓ Message published (ID: {mid})")


def on_message(client, userdata, msg):
    """Called when message is received"""
    global response_received
    response_received = True
    print(f"\n📥 Message received on topic: {msg.topic}")
    try:
        payload = json.loads(msg.payload.decode('utf-8'))
        print("📦 Payload:")
        print(json.dumps(payload, indent=2))
    except Exception as e:
        print(f"Raw payload: {msg.payload.decode('utf-8')}")


def main():
    print("="*60)
    print("SIMPLE MQTT CONNECTION TEST")
    print("="*60)
    print(f"Broker: {BROKER_HOST}:{BROKER_PORT}")
    print(f"Topic: {TOPIC}")
    print("="*60)
    print()
    
    # Create client
    client = mqtt.Client(client_id="simple_test_123")
    
    # Set callbacks
    client.on_connect = on_connect
    client.on_publish = on_publish
    client.on_message = on_message
    
    try:
        # Connect to broker
        print(f"🔌 Connecting to broker...")
        client.connect(BROKER_HOST, BROKER_PORT, 60)
        
        # Start loop in background
        client.loop_start()
        
        # Wait for connection
        timeout = 10
        elapsed = 0
        while not connected and elapsed < timeout:
            time.sleep(0.5)
            elapsed += 0.5
        
        if not connected:
            print("\n✗ Failed to connect within 10 seconds")
            client.loop_stop()
            return
        
        print()
        
        # Create dummy JSON payload
        dummy_data = {
            "type": "unknown_person",
            "unknown_person_id": "foreign_1",
            "incident_number": 1,
            "timestamp": int(time.time()),
            "duration": 25.5,
            "message": "Test incident from simple script",
            "device_id": "test_device",
            "location": "test_location"
        }
        
        # Publish message
        print("📤 Publishing dummy JSON...")
        print(json.dumps(dummy_data, indent=2))
        print()
        
        result = client.publish(TOPIC, json.dumps(dummy_data), qos=1)
        
        # Wait for publish confirmation
        timeout = 5
        elapsed = 0
        while not message_sent and elapsed < timeout:
            time.sleep(0.5)
            elapsed += 0.5
        
        if not message_sent:
            print("⚠ Message may not have been sent")
        
        # Wait for responses (our own message or others)
        print("\n⏳ Waiting for messages (5 seconds)...")
        time.sleep(5)
        
        # Disconnect
        print("\n🔌 Disconnecting...")
        client.loop_stop()
        client.disconnect()
        
        # Summary
        print()
        print("="*60)
        print("TEST RESULTS")
        print("="*60)
        print(f"Connected:        {'✓' if connected else '✗'}")
        print(f"Message Sent:     {'✓' if message_sent else '✗'}")
        print(f"Message Received: {'✓' if response_received else '✗'}")
        print("="*60)
        
        if connected and message_sent:
            print("\n✅ Test PASSED - MQTT connection working!")
        else:
            print("\n❌ Test FAILED - Check your MQTT broker")
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
