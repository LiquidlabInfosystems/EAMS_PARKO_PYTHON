"""
Configuration file for Attendance System
InsightFace Edition - Raspberry Pi 4
"""

# ★★★ API CONFIGURATION ★★★
API_ENABLED = True  # Set to False to disable API sending

# Server configuration
API_SERVER_IP = "35.154.40.8"
# API_SERVER_IP = "192.168.1.18"

API_SERVER_PORT = 3008
API_ENDPOINT = "/api/attendance/record"  # ← API endpoint path
API_TIMEOUT = 15  # Request timeout in seconds

# API Health Check Settings
API_HEALTH_ENDPOINT = "/health"
API_HEALTH_CHECK_INTERVAL = 30  # seconds

# API Retry Settings
API_STORAGE_FILE = "failed_api_requests.json"

# ★★★ LIVENESS CONFIGURATION ★★★
ENABLE_LIVENESS = False  # Blink detection

# ★★★ CAMERA SETTINGS ★★★
# Pi 4 note: 640×640 @ 15 FPS is a safe operating point.
# Rotation is applied at libcamera ISP level (not per-frame in Python),
# so changing CAMERA_ROTATION has zero CPU cost at runtime.
CAMERA_RESOLUTION = (640, 640)
CAMERA_FPS = 15           # Pi 4 safe value (Pi 5 could run 30-60)
CAMERA_ROTATION = 90      # Applied once at camera init via libcamera.Transform
CAMERA_FRAME_SKIP = 2     # Emit every 2nd captured frame → halves processing load

# ★★★ INSIGHTFACE MODEL SETTINGS ★★★
# buffalo_sc is the only practical choice on Pi 4 (buffalo_l is too slow).
# Halving det_size from 640→320 cuts inference time roughly 4× with minimal
# accuracy drop for normal webcam distances.
INSIGHTFACE_MODEL = 'buffalo_sc'          # Must use 'buffalo_sc' on Pi 4 (buffalo_l too slow)
INSIGHTFACE_DET_SIZE = (320, 320)        # Smaller = faster; 320×320 is Pi 4 sweet-spot
INSIGHTFACE_PROVIDERS = None             # None = auto-detect (CPU on Pi 4, CUDA on Jetson)

# ★★★ RECOGNITION SETTINGS ★★★
DETECTION_CONFIDENCE = 0.5
# InsightFace cosine similarity thresholds (typical range: 0.25-0.50)
# Lower than MobileFaceNet because InsightFace produces different similarity distributions
RECOGNITION_THRESHOLD = 0.35            # Match threshold (was 0.60 for MobileFaceNet)
MARGIN_THRESHOLD = 0.05                 # Minimum margin between top 2 matches (was 0.10)

# ★★★ TEMPORAL RECOGNITION SETTINGS ★★★
TEMPORAL_BUFFER_SIZE = 5  # Number of frames to consider for voting
TEMPORAL_AGREEMENT_THRESHOLD = 0.6  # 60% agreement required for consensus
IDENTITY_LOCK_TIME = 2.0  # Seconds to lock identity after recognition (anti-flicker)


# MQTT Settings
MQTT_ENABLED = True
MQTT_BROKER_HOST = "3.109.106.154"
# MQTT_BROKER_HOST = "192.168.1.18"
MQTT_BROKER_PORT = 1869
MQTT_TOPIC = "incidents/"

# MQTT Face Registration (Remote registration via admin page)
MQTT_FACE_REGISTRATION_ENABLED = True
MQTT_FACE_REGISTRATION_TOPIC = "eams/addface"
MQTT_FACE_REGISTRATION_RESULT_TOPIC = "eams/addface/result"

# Unknown Person Tracking
UNKNOWN_PERSON_TIMEOUT = 15.0 # seconds
UNKNOWN_PERSON_SIMILARITY_THRESHOLD = 0.7 # cosine similarity
UNKNOWN_PERSON_COOLDOWN = 300.0 # seconds
UNKNOWN_PERSON_CLEANUP_DAYS = 30 # days

# ★★★ THEME CONFIGURATION ★★★
THEME = {
    "background_light": "#F0F4F8",
    "background_medium": "#E8EDF2",
    "accent_primary": "#1E3A5F",      # Dark blue
    "accent_secondary": "#4A90D9",     # Light blue
    "text_primary": "#1E3A5F",
    "text_secondary": "#5A7A9A",
    "success": "#2ECC71",
    "warning": "#F39C12",
    "error": "#E74C3C",
}

# Lane Configuration
LANE_NAME = "Lane 1"
