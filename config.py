"""
Configuration file for Attendance System
InsightFace Edition - Raspberry Pi 5
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
CAMERA_RESOLUTION = (640, 480) # Use a standard 4:3 or 16:9 resolution
CAMERA_FPS = 30   

# ★★★ INSIGHTFACE MODEL SETTINGS ★★★
INSIGHTFACE_MODEL = 'buffalo_sc'          # Model pack: 'buffalo_l' (accurate) or 'buffalo_sc' (faster)
INSIGHTFACE_DET_SIZE = (640, 640)        # Detection input size (smaller = faster on RPi5)
INSIGHTFACE_PROVIDERS = None             # None = auto-detect (CPU on RPi5, CUDA on Jetson)

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
