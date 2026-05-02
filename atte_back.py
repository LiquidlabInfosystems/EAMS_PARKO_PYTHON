#!/usr/bin/env python3
"""
Attendance System GUI - Production Version (COMPLETE)
✓ Blink-only liveness detection (ultra-fast)
✓ Smart reset: Only after 30 seconds out of frame
✓ Adaptive learning enabled
✓ Person locking on button click
✓ API integration for remote logging
✓ Auto-fading notifications for ALL messages (success, error, warning) - SQUARE SHAPE
"""

# Suppress warnings
import os
os.environ['GLOG_minloglevel'] = '2'
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'
os.environ['QT_LOGGING_RULES'] = '*.debug=false;qt.accessibility.atspi.warning=false'

import sys
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                               QHBoxLayout, QLabel, QPushButton, QFrame, QInputDialog, 
                               QGridLayout, QMessageBox, QDialog, QProgressBar, QStackedWidget, QSizePolicy)
from PySide6.QtCore import Qt, QThread, Signal, Slot, QTimer, QPropertyAnimation, QEasingCurve
from PySide6.QtGui import QImage, QPixmap, QFont
from picamera2 import Picamera2
import libcamera
import numpy as np
import time
from datetime import datetime
import cv2

from face_recognizer import FaceRecognizer
from modules.api_client import AttendanceAPIClient
from modules.attendance_state_manager import AttendanceStateManager
from modules.mqtt_incident_reporter import MQTTIncidentReporter
from modules.unknown_person_tracker import UnknownPersonTracker
from modules.welcome_screen import WelcomeScreen

import config


class NotificationOverlay(QWidget):
    """Auto-fading notification overlay widget - SQUARE SHAPE"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
       
        # Setup UI
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignCenter)
        
        self.container = QFrame()
        # Square shape with minimal border-radius (10px)
        self.container.setStyleSheet("""
            QFrame {
                background-color: rgba(0, 170, 102, 220);
                border: 4px solid #00ff88;
                border-radius: 10px;
                padding: 40px;
                min-width: 400px;
                max-width: 600px;
            }
            QLabel {
                color: #ffffff;
                background: transparent;
                border: none;
            }
        """)

        container_layout = QVBoxLayout(self.container)
        container_layout.setSpacing(20)

        self.icon_label = QLabel("✅")
        self.icon_label.setAlignment(Qt.AlignCenter)
        self.icon_label.setStyleSheet("font-size: 72px;")

        self.title_label = QLabel("SUCCESS")
        self.title_label.setAlignment(Qt.AlignCenter)
        self.title_label.setStyleSheet("font-size: 36px; font-weight: bold;")

        self.message_label = QLabel("")
        self.message_label.setAlignment(Qt.AlignCenter)
        self.message_label.setStyleSheet("font-size: 24px;")
        self.message_label.setWordWrap(True)

        container_layout.addWidget(self.icon_label)
        container_layout.addWidget(self.title_label)
        container_layout.addWidget(self.message_label)

        layout.addWidget(self.container)

        # Fade animation
        self.fade_timer = QTimer()
        self.fade_timer.setSingleShot(True)
        self.fade_timer.timeout.connect(self.start_fade_out)

        self.hide()

    def show_notification(self, title, message, notification_type="success", duration_ms=3000):
        """
        Show notification with auto-fade
        notification_type: 'success', 'error', 'warning', 'info'
        """
        # Set icon and colors based on type
        if notification_type == "success":
            icon = "✅"
            bg_color = "rgba(0, 170, 102, 220)"
            border_color = "#00ff88"
        elif notification_type == "error":
            icon = "❌"
            bg_color = "rgba(204, 51, 51, 220)"
            border_color = "#ff4444"
        elif notification_type == "warning":
            icon = "⚠️"
            bg_color = "rgba(245, 166, 35, 220)"
            border_color = "#ff8c00"
        else:  # info
            icon = "ℹ️"
            bg_color = "rgba(74, 144, 226, 220)"
            border_color = "#6ab0ff"

        # Update styling
        self.container.setStyleSheet(f"""
            QFrame {{
                background-color: {bg_color};
                border: 4px solid {border_color};
                border-radius: 10px;
                padding: 40px;
                min-width: 400px;
                max-width: 600px;
            }}
            QLabel {{
                color: #ffffff;
                background: transparent;
                border: none;
            }}
        """)

        self.icon_label.setText(icon)
        self.title_label.setText(title.upper())
        self.message_label.setText(message)

        # Position in center of parent
        if self.parent():
            parent_rect = self.parent().geometry()
            self.setGeometry(parent_rect)

        # Show with full opacity
        self.setWindowOpacity(1.0)
        self.show()
        self.raise_()

        # Start fade timer
        self.fade_timer.start(duration_ms - 500)  # Start fade 500ms before hiding

    def start_fade_out(self):
        """Fade out animation"""
        self.fade_animation = QPropertyAnimation(self, b"windowOpacity")
        self.fade_animation.setDuration(500)
        self.fade_animation.setStartValue(1.0)
        self.fade_animation.setEndValue(0.0)
        self.fade_animation.setEasingCurve(QEasingCurve.InOutQuad)
        self.fade_animation.finished.connect(self.hide)
        self.fade_animation.start()


class CameraThread(QThread):
    """Camera thread - optimized"""
    frame_ready = Signal(np.ndarray)
    status_update = Signal(str)

    def __init__(self, mirror=True):
        super().__init__()
        self._running = False
        self.picam2 = None
        self.mirror = mirror

    def run(self):
        """Capture frames in RGB888"""
        try:
            self.picam2 = Picamera2()

            transform = libcamera.Transform(hflip=1 if self.mirror else 0, vflip=0)

            preview_config = self.picam2.create_preview_configuration(
                main={"size": config.CAMERA_RESOLUTION, "format": "RGB888"},
                buffer_count=2,
                transform=transform
            )

            self.picam2.configure(preview_config)
            self.picam2.set_controls({
                "AwbEnable": True,
                "AeEnable": True,
                "AwbMode": libcamera.controls.AwbModeEnum.Auto,
            })

            self.picam2.start()
            time.sleep(0.3)

            self._running = True
            self.status_update.emit("✅ Camera Ready")

            while self._running:
                try:
                    frame_rgb = self.picam2.capture_array()
                    
                    rotation = getattr(config, 'CAMERA_ROTATION', 0)
                    if rotation == 90:
                        frame_rgb = cv2.rotate(frame_rgb, cv2.ROTATE_90_CLOCKWISE)
                    elif rotation == 180:
                        frame_rgb = cv2.rotate(frame_rgb, cv2.ROTATE_180)
                    elif rotation == 270:
                        frame_rgb = cv2.rotate(frame_rgb, cv2.ROTATE_90_COUNTERCLOCKWISE)

                    self.frame_ready.emit(frame_rgb)
                    time.sleep(1.0 / config.CAMERA_FPS)

                except Exception as e:
                    print(f"Capture error: {e}")
                    time.sleep(0.05)

        except Exception as e:
            self.status_update.emit(f"❌ Camera Error")
            print(f"Camera init error: {e}")

    def stop(self):
        """Stop camera"""
        self._running = False
        if self.picam2:
            try:
                self.picam2.stop()
                self.picam2.close()
            except:
                pass
        self.quit()
        self.wait()


class SimpleConfirmationDialog(QDialog):
    """Confirmation dialog"""

    def __init__(self, parent, person_name, action):
        super().__init__(parent)
        self.person_name = person_name
        self.action = action
        # Welcome screen state
        self.no_face_timeout = None

        self.init_ui()

    def init_ui(self):
        self.setWindowTitle("Confirm Identity")
        self.setModal(True)
        self.setMinimumSize(500, 300)

        self.setStyleSheet("""
            QDialog { background-color: #1a1a1a; }
            QLabel { color: #ffffff; font-size: 20px; padding: 15px; }
            QLabel#title { color: #00ff88; font-size: 28px; font-weight: bold; }
            QLabel#name { color: #4a90e2; font-size: 36px; font-weight: bold; }
            QLabel#action { color: #f5a623; font-size: 24px; }
            QPushButton {
                color: #ffffff; border: 2px solid; border-radius: 10px;
                font-size: 20px; font-weight: bold; padding: 20px 40px; min-width: 180px;
            }
            QPushButton#confirm { background-color: #00aa66; border-color: #00ff88; }
            QPushButton#confirm:hover { background-color: #00cc77; }
            QPushButton#cancel { background-color: #cc3333; border-color: #ff4444; }
            QPushButton#cancel:hover { background-color: #dd4444; }
        """)

        layout = QVBoxLayout(self)
        layout.setSpacing(25)
        layout.setContentsMargins(40, 40, 40, 40)

        title = QLabel("\U000026A0 Confirm Your Identity")
        title.setObjectName("title")
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)

        layout.addSpacing(20)

        name_label = QLabel(f"👤 {self.person_name}")
        name_label.setObjectName("name")
        name_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(name_label)

        action_label = QLabel(f"➡️ {self.action}")
        action_label.setObjectName("action")
        action_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(action_label)

        layout.addSpacing(20)

        question = QLabel("Is this you?")
        question.setAlignment(Qt.AlignCenter)
        question.setStyleSheet("font-size: 22px; color: #aaaaaa;")
        layout.addWidget(question)

        layout.addSpacing(30)

        button_layout = QHBoxLayout()
        button_layout.setSpacing(20)

        confirm_btn = QPushButton("\U00002705 Yes, Confirm")
        confirm_btn.setObjectName("confirm")
        confirm_btn.clicked.connect(self.accept)
        button_layout.addWidget(confirm_btn)

        cancel_btn = QPushButton("\U0000274C No, Cancel")
        cancel_btn.setObjectName("cancel")
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(cancel_btn)

        layout.addLayout(button_layout)


class AttendanceKioskGUI(QMainWindow):
    def __init__(self):
        super().__init__()
        
        # Initialize State Manager
        self.state_manager = AttendanceStateManager()
        print("✓ State Manager initialized")
        
        # Unknown Person Tracker
        self.unknown_tracker = UnknownPersonTracker(
            similarity_threshold=config.UNKNOWN_PERSON_SIMILARITY_THRESHOLD,
            storage_file="unknown_persons.json",
            cooldown_seconds=config.UNKNOWN_PERSON_COOLDOWN
        )

        # MQTT Reporter
        if config.MQTT_ENABLED:
            self.mqtt_reporter = MQTTIncidentReporter(
                broker_host=config.MQTT_BROKER_HOST,
                broker_port=config.MQTT_BROKER_PORT,
                topic=config.MQTT_TOPIC
            )
        else:
            self.mqtt_reporter = None

        # Tracking variables
        self.unknown_person_start_time = None
        self.unknown_person_last_frame = None
        self.unknown_person_last_bbox = None
        self.unknown_person_embedding = None
        self.unknown_person_id = None

        # Initialize face recognizer
        try:
            print("\n" + "="*60)
            print("INITIALIZING ATTENDANCE SYSTEM")
            print("="*60 + "\n")

            self.face_recognizer = FaceRecognizer(
                model_path="models/mobilefacenet.tflite",
                detection_confidence=config.DETECTION_CONFIDENCE,
                recognition_threshold=config.RECOGNITION_THRESHOLD,
                margin_threshold=0.05,
                preprocessing_method='clahe',
                enable_liveness=config.ENABLE_LIVENESS,
                strict_quality=False,
                use_face_alignment=True
            )

            if config.ENABLE_LIVENESS and self.face_recognizer.liveness_detector:
                print("✓ Blink-only liveness enabled (ultra-fast)")

            # ★★★ INITIALIZE API CLIENT ★★★
            if config.API_ENABLED:
                try:
                    self.api_client = AttendanceAPIClient(
                        server_ip=config.API_SERVER_IP,
                        server_port=config.API_SERVER_PORT,
                        endpoint=config.API_ENDPOINT,
                        timeout=config.API_TIMEOUT,
                        health_endpoint=config.API_HEALTH_ENDPOINT,
                        health_check_interval=config.API_HEALTH_CHECK_INTERVAL,
                        storage_file=config.API_STORAGE_FILE
                    )
                    print(f"✓ API Client enabled: {config.API_SERVER_IP}:{config.API_SERVER_PORT}")
                except Exception as e:
                    print(f"⚠️ API Client initialization failed: {e}")
                    self.api_client = None
            else:
                self.api_client = None
                print("○ API Client disabled")

            # Validate existing database
            print("\n🔍 Validating database quality...")
            self.face_recognizer.validate_all_embeddings()

            print("="*60 + "\n")
        except Exception as e:
            print(f"❌ Recognizer init error: {e}")
            import traceback
            traceback.print_exc()
            sys.exit(1)

        self.camera_thread = None
        self.current_frame = None
        self.latest_frame = None

        # Processing control
        self.registration_mode = False
        self.processing = False

        # Person locking
        self.current_recognized_person = None
        self.locked_person_for_action = None
        self.locked_person_timestamp = None

        # Adaptive learning counter
        self.adaptive_learning_count = 0

        # Smart liveness state (resets only after 30s out of frame)
        self.last_recognized_person = None
        self.person_last_seen_time = None
        self.RESET_TIMEOUT = 30.0  # Seconds

        # Registration state - 10 SAMPLES
        self.registration_person_name = ""
        self.captured_faces = []
        self.current_registration_step = 0
        self.feedback_timer = None

        # 10 diverse samples
        self.registration_steps = [
            {"instruction": "📸 Look Straight - Sample 1", "icon": "1️⃣"},
            {"instruction": "📸 Look Straight - Sample 2", "icon": "2️⃣"},
            {"instruction": "⬅️ Turn Head Left", "icon": "⬅️"},
            {"instruction": "⬅️ Turn Left More", "icon": "⬅️"},
            {"instruction": "➡️ Turn Head Right", "icon": "➡️"},
            {"instruction": "➡️ Turn Right More", "icon": "➡️"},
            {"instruction": "⬆️ Tilt Head Up", "icon": "⬆️"},
            {"instruction": "⬇️ Tilt Head Down", "icon": "⬇️"},
            {"instruction": "😊 Smile", "icon": "😊"},
            {"instruction": "😐 Neutral Expression", "icon": "😐"}
        ]

        # Welcome screen state
        self.no_face_timeout = None

        self.init_ui()

        # ★★★ CREATE NOTIFICATION OVERLAY ★★★
        self.notification_overlay = NotificationOverlay(self)

        # Start camera
        QTimer.singleShot(200, self.init_camera)

        # Processing timer
        self.process_timer = QTimer()
        self.process_timer.timeout.connect(self.process_frame)
        self.process_timer.start(1000 // config.CAMERA_FPS)


    def init_ui(self):
        """Initialize UI"""
        liveness_status = "🛡️ Blink Detection" if config.ENABLE_LIVENESS else "⚠️ Liveness Disabled"
        api_status = f"📡 API: {config.API_SERVER_IP}" if config.API_ENABLED else "○ API Disabled"

        self.setWindowTitle(f"Employee Attendance System - {liveness_status} | {api_status}")
        self.setStyleSheet("""
            QMainWindow { background-color: #1a1a1a; }
            QLabel#title { color: #ffffff; font-size: 18px; font-weight: bold; padding: 10px; }
            QLabel#status { color: #00ff88; font-size: 14px; padding: 5px; }
            QLabel#instruction { color: #00ff88; font-size: 16px; font-weight: bold; padding: 8px; }
            QLabel#feedback { color: #ffffff; font-size: 14px; font-weight: bold; padding: 5px; }
            QLabel#camera { background-color: #000000; border: 3px solid #00ff88; border-radius: 10px; }
            QPushButton {
                background-color: #2d2d2d; color: #ffffff; border: 2px solid #4d4d4d;
                border-radius: 8px; font-size: 14px; font-weight: bold; padding: 8px; min-height: 40px;
            }
            QPushButton:hover { background-color: #3d3d3d; border-color: #00ff88; }
            QPushButton:pressed { background-color: #1d1d1d; }
            QPushButton#timeIn { border-color: #4a90e2; }
            QPushButton#timeOut { border-color: #e24a4a; }
            QPushButton#breakIn { border-color: #f5a623; }
            QPushButton#breakOut { border-color: #ff8c00; }
            QPushButton#jobIn { border-color: #bd10e0; }
            QPushButton#jobOut { border-color: #9b10c0; }
            QPushButton#addFace { border-color: #50c878; }
            QPushButton#capture { background-color: #4a90e2; border-color: #6ab0ff; font-size: 18px; }
            QPushButton#cancelReg { background-color: #cc3333; border-color: #ff4444; font-size: 18px; }
            QFrame#buttonContainer { background-color: #0d0d0d; border-top: 3px solid #00ff88; padding: 10px; }
            QProgressBar {
                border: 2px solid #4a90e2; border-radius: 5px; text-align: center;
                color: #ffffff; font-weight: bold; min-height: 30px; font-size: 16px;
            }
            QProgressBar::chunk { background-color: #00ff88; }
        """)

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(5)

        title_emoji = "🛡️" if config.ENABLE_LIVENESS else "👁️"
        self.title_label = QLabel(f"{title_emoji} Employee Attendance Management System")
        self.title_label.setObjectName("title")
        self.title_label.setAlignment(Qt.AlignCenter)
        self.title_label.setWordWrap(True)
        self.title_label.setMinimumWidth(10)
        main_layout.addWidget(self.title_label)

        self.status_label = QLabel("Starting...")
        self.status_label.setObjectName("status")
        self.status_label.setAlignment(Qt.AlignCenter)
        self.status_label.setWordWrap(True)
        self.status_label.setMinimumWidth(10)
        main_layout.addWidget(self.status_label)

        self.instruction_label = QLabel("")
        self.instruction_label.setObjectName("instruction")
        self.instruction_label.setAlignment(Qt.AlignCenter)
        self.instruction_label.setWordWrap(True)
        self.instruction_label.setMinimumWidth(10)
        self.instruction_label.setVisible(False)
        main_layout.addWidget(self.instruction_label)

        self.feedback_label = QLabel("")
        self.feedback_label.setObjectName("feedback")
        self.feedback_label.setAlignment(Qt.AlignCenter)
        self.feedback_label.setVisible(False)
        main_layout.addWidget(self.feedback_label)

        # Stacked widget for welcome screen and camera feed
        self.display_stack = QStackedWidget()
        # Removed fixed size to allow fitting on any screen

        # Welcome screen (index 0)
        self.welcome_widget = WelcomeScreen()
        self.display_stack.addWidget(self.welcome_widget)

        # Camera label (index 1)
        self.camera_label = QLabel()
        self.camera_label.setObjectName("camera")
        self.camera_label.setAlignment(Qt.AlignCenter)
        self.camera_label.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Ignored)
        # Removed fixed size to allow fitting on any screen
        self.display_stack.addWidget(self.camera_label)

        # Start with welcome screen
        self.display_stack.setCurrentIndex(0)

        # Center the display stack
        display_container = QWidget()
        display_layout = QHBoxLayout(display_container)
        display_layout.addStretch()
        display_layout.addWidget(self.display_stack)
        display_layout.addStretch()
        main_layout.addWidget(display_container)

        # Large Clock Display
        self.clock_label = QLabel()
        self.clock_label.setAlignment(Qt.AlignCenter)
        self.clock_label.setStyleSheet("""
            QLabel {
                color: #00ff88;
                font-size: 32px;
                font-weight: bold;
                padding: 8px;
                background-color: #0d0d0d;
                border: 2px solid #00ff88;
                border-radius: 10px;
                min-width: 100px;
            }
        """)
        self.update_clock()  # Initial update
        main_layout.addWidget(self.clock_label, alignment=Qt.AlignCenter)

        # Clock timer
        self.clock_timer = QTimer()
        self.clock_timer.timeout.connect(self.update_clock)
        self.clock_timer.start(1000)  # Update every second

        self.progress_bar = QProgressBar()
        self.progress_bar.setMinimum(0)
        self.progress_bar.setMaximum(len(self.registration_steps))
        self.progress_bar.setValue(0)
        self.progress_bar.setFormat(f"Accepted: %v of {len(self.registration_steps)}")
        self.progress_bar.setVisible(False)
        main_layout.addWidget(self.progress_bar)

        # Normal buttons
        self.button_frame = QFrame()
        self.button_frame.setObjectName("buttonContainer")
        button_layout = QGridLayout(self.button_frame)
        button_layout.setSpacing(10)
        button_layout.setContentsMargins(20, 10, 20, 10)

        self.time_in_btn = QPushButton("\U0001F551 TIME IN")
        self.time_in_btn.setObjectName("timeIn")
        self.time_in_btn.clicked.connect(self.handle_time_in)
        self.time_in_btn.setCursor(Qt.PointingHandCursor)
        button_layout.addWidget(self.time_in_btn, 0, 0)

        self.time_out_btn = QPushButton("\U0001F551 TIME OUT")
        self.time_out_btn.setObjectName("timeOut")
        self.time_out_btn.clicked.connect(self.handle_time_out)
        self.time_out_btn.setCursor(Qt.PointingHandCursor)
        button_layout.addWidget(self.time_out_btn, 0, 1)

        self.break_in_btn = QPushButton("\U00002615 BREAK START")
        self.break_in_btn.setObjectName("breakIn")
        self.break_in_btn.clicked.connect(self.handle_break_in)
        self.break_in_btn.setCursor(Qt.PointingHandCursor)
        button_layout.addWidget(self.break_in_btn, 1, 0)

        self.break_out_btn = QPushButton("\U00002615 BREAK END")
        self.break_out_btn.setObjectName("breakOut")
        self.break_out_btn.clicked.connect(self.handle_break_out)
        self.break_out_btn.setCursor(Qt.PointingHandCursor)
        button_layout.addWidget(self.break_out_btn, 1, 1)

        self.job_in_btn = QPushButton("\U0001F4BC JOB START")
        self.job_in_btn.setObjectName("jobIn")
        self.job_in_btn.clicked.connect(self.handle_job_in)
        self.job_in_btn.setCursor(Qt.PointingHandCursor)
        button_layout.addWidget(self.job_in_btn, 2, 0)

        self.job_out_btn = QPushButton("\U0001F4BC JOB END")
        self.job_out_btn.setObjectName("jobOut")
        self.job_out_btn.clicked.connect(self.handle_job_out)
        self.job_out_btn.setCursor(Qt.PointingHandCursor)
        button_layout.addWidget(self.job_out_btn, 2, 1)

        self.add_face_btn = QPushButton("\U0001F464 ADD NEW FACE")
        self.add_face_btn.setObjectName("addFace")
        self.add_face_btn.clicked.connect(self.start_registration)
        self.add_face_btn.setCursor(Qt.PointingHandCursor)
        button_layout.addWidget(self.add_face_btn, 3, 0, 1, 2)

        main_layout.addWidget(self.button_frame)

        # Registration buttons
        self.reg_button_frame = QFrame()
        self.reg_button_frame.setObjectName("buttonContainer")
        reg_button_layout = QHBoxLayout(self.reg_button_frame)
        reg_button_layout.setSpacing(20)
        reg_button_layout.setContentsMargins(30, 20, 30, 20)

        self.capture_btn = QPushButton("📸 CAPTURE")
        self.capture_btn.setObjectName("capture")
        self.capture_btn.clicked.connect(self.capture_registration_face)
        self.capture_btn.setCursor(Qt.PointingHandCursor)
        reg_button_layout.addWidget(self.capture_btn)

        self.cancel_reg_btn = QPushButton("\U0000274C CANCEL")
        self.cancel_reg_btn.setObjectName("cancelReg")
        self.cancel_reg_btn.clicked.connect(self.cancel_registration)
        self.cancel_reg_btn.setCursor(Qt.PointingHandCursor)
        reg_button_layout.addWidget(self.cancel_reg_btn)

        self.reg_button_frame.setVisible(False)
        main_layout.addWidget(self.reg_button_frame)

        # Initially hide buttons
        self.button_frame.setVisible(False)

        self.showFullScreen()

    def init_camera(self):
        """Initialize camera"""
        try:
            self.status_label.setText("📷 Starting camera...")
            QApplication.processEvents()

            self.camera_thread = CameraThread(mirror=True)
            self.camera_thread.frame_ready.connect(self.on_frame_ready, Qt.QueuedConnection)
            self.camera_thread.status_update.connect(self.update_status)
            self.camera_thread.start()

        except Exception as e:
            self.status_label.setText(f"\U0000274C Camera Error")
            print(f"Camera init error: {e}")

    @Slot(np.ndarray)
    def on_frame_ready(self, frame_rgb):
        self.latest_frame = frame_rgb.copy()


    def show_welcome_screen(self):
        """Switch to welcome screen when no face detected for 3 seconds"""
        print("📺 No face detected - showing welcome screen")
        self.display_stack.setCurrentIndex(0)  # Switch to welcome
        self.button_frame.setVisible(False)  # Hide buttons
        self.no_face_timeout = None
        # Resume animation
        if hasattr(self, 'welcome_widget'):
            self.welcome_widget.start_animation()


    def display_frame(self, frame_rgb):
        """Display frame"""
        try:
            frame_bgr = frame_rgb[:, :, ::-1].copy()

            height, width, channel = frame_bgr.shape
            bytes_per_line = 3 * width

            q_image = QImage(frame_bgr.data, width, height, bytes_per_line, QImage.Format_RGB888)

            scaled_pixmap = QPixmap.fromImage(q_image).scaled(
                self.camera_label.size(),
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation
            )

            self.camera_label.setPixmap(scaled_pixmap)
        except Exception as e:
            print(f"Display error: {e}")

    def draw_box_rgb(self, frame, x1, y1, x2, y2, color_rgb, thickness=4):
        """Draw rectangle"""
        h, w = frame.shape[:2]
        x1, y1 = max(0, x1), max(0, y1)
        x2, y2 = min(w, x2), min(h, y2)

        for t in range(thickness):
            if y1+t < h:
                frame[y1+t, x1:x2] = color_rgb
            if y2-t-1 >= 0:
                frame[y2-t-1, x1:x2] = color_rgb
            if x1+t < w:
                frame[y1:y2, x1+t] = color_rgb
            if x2-t-1 >= 0:
                frame[y1:y2, x2-t-1] = color_rgb

    def draw_filled_box_rgb(self, frame, x1, y1, x2, y2, color_rgb):
        """Draw filled rectangle"""
        h, w = frame.shape[:2]
        x1, y1 = max(0, x1), max(0, y1)
        x2, y2 = min(w, x2), min(h, y2)
        frame[y1:y2, x1:x2] = color_rgb

    def put_text_rgb(self, frame, text, x, y, color_rgb, scale=1.0, thickness=2):
        """Put text"""
        frame_bgr = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
        color_bgr = (color_rgb[2], color_rgb[1], color_rgb[0])
        cv2.putText(frame_bgr, text, (x, y), cv2.FONT_HERSHEY_SIMPLEX, scale, color_bgr, thickness)
        frame[:] = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)

    def show_feedback(self, message, is_success):
        """Show feedback with 3-second auto-fade"""
        if is_success:
            self.feedback_label.setStyleSheet("color: #00ff88; font-size: 20px; font-weight: bold; padding: 10px;")
        else:
            self.feedback_label.setStyleSheet("color: #ff4444; font-size: 20px; font-weight: bold; padding: 10px;")

        self.feedback_label.setText(message)
        self.feedback_label.setVisible(True)

        if self.feedback_timer:
            self.feedback_timer.stop()

        # ★★★ CHANGED: 3 seconds instead of 2 ★★★
        self.feedback_timer = QTimer()
        self.feedback_timer.timeout.connect(lambda: self.feedback_label.setVisible(False))
        self.feedback_timer.setSingleShot(True)
        self.feedback_timer.start(3000)  # 3 seconds


    def process_frame(self):
        """Process frame with smart liveness"""
        if self.latest_frame is None or self.processing:
            return

        self.processing = True

        try:
            frame_rgb = self.latest_frame.copy()
            self.current_frame = frame_rgb
            display_frame = frame_rgb.copy()

            GREEN_RGB = (0, 255, 0)
            RED_RGB = (255, 0, 0)
            YELLOW_RGB = (255, 255, 0)
            ORANGE_RGB = (255, 165, 0)
            BLACK_RGB = (0, 0, 0)

            # ★★★ WELCOME SCREEN LOGIC ★★★
            if not self.registration_mode:
                # Check if any face is present
                detected, recognized = self.face_recognizer.process_frame(frame_rgb, preprocess=True)
                has_face = bool(detected or recognized)

                if has_face:
                    # Face detected - show camera and buttons
                    if self.display_stack.currentIndex() == 0:
                        print("👤 Face detected - showing camera view")
                        self.display_stack.setCurrentIndex(1)
                        self.button_frame.setVisible(True)
                        # Pause animation to save CPU for camera
                        if hasattr(self, 'welcome_widget'):
                            self.welcome_widget.stop_animation()


                    # Cancel no-face timeout
                    if self.no_face_timeout:
                        self.no_face_timeout.stop()
                        self.no_face_timeout = None

                else:
                    # No face - start timeout for welcome screen
                    if self.display_stack.currentIndex() == 1:
                        if self.no_face_timeout is None:
                            self.no_face_timeout = QTimer()
                            self.no_face_timeout.setSingleShot(True)
                            self.no_face_timeout.timeout.connect(self.show_welcome_screen)
                            self.no_face_timeout.start(3000)  # 3 seconds
            # ★★★ END WELCOME SCREEN LOGIC ★★★

            if self.registration_mode:
                if self.current_registration_step >= len(self.registration_steps):
                    self.display_frame(display_frame)
                    self.processing = False
                    return

                faces = self.face_recognizer.detect_faces(frame_rgb)

                if faces:
                    face = max(faces, key=lambda f: f['bbox'][2] * f['bbox'][3])
                    x, y, w, h = face['bbox']

                    self.draw_box_rgb(display_frame, x, y, x + w, y + h, GREEN_RGB, 4)

                    icon = self.registration_steps[self.current_registration_step]["icon"]
                    self.put_text_rgb(display_frame, icon, x + w//2 - 20, y - 20, GREEN_RGB, 2.0, 4)

                self.display_frame(display_frame)

            else:
                # Recognition mode with SMART liveness
                detected, recognized = self.face_recognizer.process_frame(frame_rgb, preprocess=True)

                if recognized:
                    person = recognized[0]
                    x, y, w, h = person['bbox']
                    name = person['name']
                    similarity = person['similarity']
                    is_confident = person['is_confident']

                    # ★★★ SMART LIVENESS LOGIC ★★★
                    liveness_ok = True
                    liveness_conf = 1.0

                    if is_confident and config.ENABLE_LIVENESS:
                        current_time = time.time()

                        # Check if person changed
                        if self.last_recognized_person != name:
                            # Different person - check if need reset
                            if self.person_last_seen_time is not None:
                                time_elapsed = current_time - self.person_last_seen_time

                                # Only reset if gone 30+ seconds
                                if time_elapsed >= self.RESET_TIMEOUT:
                                    if self.face_recognizer.liveness_detector:
                                        self.face_recognizer.liveness_detector.reset()
                                        print(f"🔄 Liveness RESET after {time_elapsed:.1f}s away")

                            self.last_recognized_person = name
                            self.person_last_seen_time = current_time
                        else:
                            # Same person
                            self.person_last_seen_time = current_time

                        # Check liveness (if not verified yet)
                        if self.face_recognizer.liveness_detector and not self.face_recognizer.liveness_detector.is_verified_live:
                            face_for_liveness = self.face_recognizer.extract_face_region(
                                frame_rgb, 
                                person, 
                                align=False
                            )
                            if face_for_liveness is not None:
                                face_small = cv2.resize(face_for_liveness, (64, 64))
                                liveness_ok, liveness_conf, details = self.face_recognizer.liveness_detector.check_liveness(face_small)
                        else:
                            # Already verified
                            liveness_ok = True
                            liveness_conf = 0.95

                    # Determine status
                    if is_confident and liveness_ok:
                        # REAL PERSON - Reset unknown timer
                        if self.unknown_person_start_time is not None:
                            print(f"✅ Known person detected, unknown timer reset")
                            self.unknown_person_start_time = None
                            self.unknown_person_embedding = None
                            self.unknown_person_id = None
                            self.update_button_visibility(None)

                        color_rgb = GREEN_RGB
                        self.current_recognized_person = name

                        verified = ""
                        if config.ENABLE_LIVENESS and self.face_recognizer.liveness_detector:
                            if self.face_recognizer.liveness_detector.is_verified_live:
                                verified = "✓"

                        if self.locked_person_for_action == name:
                            state_display = self.state_manager.get_state_display(name)
                            status_text = f"👤 {name} {verified} • {similarity:.0%} | {state_display}"
                        else:
                            api_indicator = "📡" if config.API_ENABLED else ""
                            status_text = f"👤 {name} {verified} • {similarity:.0%} {api_indicator}[AL:{self.adaptive_learning_count}]"

                        self.status_label.setText(status_text)
                        self.update_button_visibility(name)


                    elif is_confident and not liveness_ok:
                        # WAITING FOR BLINK
                        color_rgb = YELLOW_RGB
                        display_name = "👁️ Please Blink"
                        self.current_recognized_person = None
                        self.status_label.setText(f"👁️ {name} detected - Please blink")
                        name = display_name

                    else:
                        name = "Unknown"
                        color_rgb = RED_RGB
                        self.current_recognized_person = None
                        current_time = time.time()
                        
                        # if self.unknown_person_start_time is None:
                        #     self.unknown_person_start_time = current_time
                        #     self.unknown_person_last_frame = frame_rgb.copy()
                        #     self.unknown_person_last_bbox = (x, y, w, h)
                        #     self.status_label.setText("⚠️ Unknown Person - Monitoring")
                        if self.unknown_person_start_time is None:
                            # First detection of unknown person
                            self.unknown_person_start_time = current_time
                            self.unknown_person_last_frame = frame_rgb.copy()
                            self.unknown_person_last_bbox = (x, y, w, h)
                            self.unknown_person_embedding = None
                            self.unknown_person_id = None
                            self.update_button_visibility(None)

                            self.status_label.setText("⚠️ Unknown Person - Monitoring")
                            print(f"⚠️ Unknown person detected, timer started")
                        else:
                            # Unknown person still in frame
                            duration = current_time - self.unknown_person_start_time
                            self.unknown_person_last_frame = frame_rgb.copy()
                            self.unknown_person_last_bbox = (x, y, w, h)
                            
                            # ===== TIMER DISPLAY - MUST BE HERE, NOT NESTED! =====
                            timer_text = f"Unknown: {int(duration)}s / {int(config.UNKNOWN_PERSON_TIMEOUT)}s"
                            self.status_label.setText(f"⚠️ {timer_text}")
                            
                            # Draw timer on video
                            # timer_display = f"UNKNOWN: {int(duration)}s"
                            # self.draw_filled_box_rgb(display_frame, 10, 30, 400, 100, (255, 255, 255))
                            # self.put_text_rgb(display_frame, timer_display, 30, 80, (255, 0, 0), 2.0, 4)
                            # ======================================================
                            
                            # Check if threshold exceeded
                            if duration >= config.UNKNOWN_PERSON_TIMEOUT:
                                # Extract embedding if not done yet
                                if self.unknown_person_embedding is None:
                                    face_img = self.face_recognizer.extract_face_region(
                                        self.unknown_person_last_frame, person, align=False)
                                    if face_img is not None:
                                        self.unknown_person_embedding = self.face_recognizer.extract_embedding(face_img)
                                        
                                        if self.unknown_person_embedding is not None:
                                            self.unknown_person_id, is_new = self.unknown_tracker.get_or_create_unknown(
                                                self.unknown_person_embedding)
                                
                                # Check cooldown and send incident
                                if self.unknown_person_id:
                                    can_send, reason = self.unknown_tracker.can_send_incident(self.unknown_person_id)
                                    
                                    if can_send and self.mqtt_reporter and self.mqtt_reporter.connected:
                                        person_info = self.unknown_tracker.get_person_info(self.unknown_person_id)
                                        incident_num = person_info['incident_count'] + 1 if person_info else 1
                                        
                                        incident_sent = self.mqtt_reporter.send_incident(
                                            frame=self.unknown_person_last_frame,
                                            detection_time=datetime.fromtimestamp(self.unknown_person_start_time),
                                            duration=duration,
                                            bbox=None,  # Send whole frame
                                            unknown_person_id=self.unknown_person_id,
                                            incident_number=incident_num
                                        )
                                        
                                        if incident_sent:
                                            self.unknown_tracker.record_incident(self.unknown_person_id)
                                            self.unknown_person_start_time = None
                                            self.unknown_person_embedding = None
                                            
                                            self.notification_overlay.show_notification(
                                                "Security Alert",
                                                f"{self.unknown_person_id} detected\nDuration: {duration:.1f}s\nIncident #{incident_num}",
                                                "warning", 4000
                                            )



                    self.draw_box_rgb(display_frame, x, y, x + w, y + h, color_rgb, 4)
                    self.draw_filled_box_rgb(display_frame, x, y - 70, x + w, y, color_rgb)

                    self.put_text_rgb(display_frame, name, x + 10, y - 40, BLACK_RGB, 1.0, 3)
                    self.put_text_rgb(display_frame, f"{similarity:.0%}", x + 10, y - 10, BLACK_RGB, 0.8, 2)

                elif detected:
                    face = detected[0]
                    x, y, w, h = face['bbox']
                    self.draw_box_rgb(display_frame, x, y, x + w, y + h, YELLOW_RGB, 4)
                    self.put_text_rgb(display_frame, "DETECTING...", x, y - 10, YELLOW_RGB, 0.7, 2)
                    self.current_recognized_person = None
                    self.status_label.setText("⏳ Detecting...")

                else:
                    # ★★★ NO FACE - RESET UNKNOWN TIMER ★★★
                    if self.unknown_person_start_time is not None:
                        print("👤 Unknown person left frame, timer reset")
                        self.unknown_person_start_time = None
                        self.unknown_person_embedding = None
                        self.unknown_person_id = None
                        self.update_button_visibility(None)


                    # No face - track time
                    if self.last_recognized_person is not None:
                        if self.person_last_seen_time is not None:
                            current_time = time.time()
                            time_elapsed = current_time - self.person_last_seen_time

                            if time_elapsed >= self.RESET_TIMEOUT:
                                if self.face_recognizer.liveness_detector:
                                    self.face_recognizer.liveness_detector.reset()
                                    print(f"🔄 Auto-reset after {time_elapsed:.1f}s")

                                self.last_recognized_person = None
                                self.person_last_seen_time = None

                    self.current_recognized_person = None
                    self.status_label.setText("✅ Ready • No face")

                # Only display frame if camera view is active
                if self.display_stack.currentIndex() == 1:
                    self.display_frame(display_frame)

        except Exception as e:
            print(f"Processing error: {e}")
            import traceback
            traceback.print_exc()
        finally:
            self.processing = False

    @Slot(str)
    def update_status(self, message):
        self.status_label.setText(message)

    def start_registration(self):
        """Start registration"""
        name, ok = QInputDialog.getText(self, "Add New Face", "Enter person's name:")

        if ok and name.strip():
            # Force camera view during registration
            self.display_stack.setCurrentIndex(1)
            
            self.registration_mode = True
            self.registration_person_name = name.strip()
            self.captured_faces = []
            self.current_registration_step = 0

            self.title_label.setText(f"👤 Registering: {self.registration_person_name}")
            self.instruction_label.setText(self.registration_steps[0]["instruction"])
            self.instruction_label.setVisible(True)
            self.progress_bar.setValue(0)
            self.progress_bar.setVisible(True)

            self.button_frame.setVisible(False)
            self.reg_button_frame.setVisible(True)
            self.capture_btn.setEnabled(True)

            self.status_label.setText(f"📸 Position and CAPTURE (10 samples required)")

    def capture_registration_face(self):
        """Capture with quality validation"""
        if self.current_frame is None:
            return

        if self.current_registration_step >= len(self.registration_steps):
            return

        faces = self.face_recognizer.detect_faces(self.current_frame)

        if not faces:
            self.show_feedback("❌ No face detected!", False)
            return

        face = max(faces, key=lambda f: f['bbox'][2] * f['bbox'][3])
        face_img = self.face_recognizer.extract_face_region(self.current_frame, face, align=False)

        if face_img is not None:
            landmarks = face.get('landmarks')

            is_valid, message, quality = self.face_recognizer.validate_face_sample(
                face_img, 
                landmarks, 
                check_liveness=False
            )

            if is_valid and quality >= 0.7:
                self.captured_faces.append(face_img)
                self.current_registration_step += 1
                self.progress_bar.setValue(len(self.captured_faces))

                self.show_feedback(f"✅ ACCEPTED! (Quality: {quality:.0%})", True)

                if self.current_registration_step >= len(self.registration_steps):
                    self.capture_btn.setEnabled(False)
                    self.complete_registration()
                else:
                    self.instruction_label.setText(
                        self.registration_steps[self.current_registration_step]["instruction"]
                    )
            else:
                self.show_feedback(f"❌ {message} (Quality: {quality:.0%}) - RETAKE!", False)
        else:
            self.show_feedback("❌ Failed to extract face", False)

    def complete_registration(self):
        """Complete registration with auto-fading success"""
        self.registration_mode = False

        self.status_label.setText("🔍 Final quality check...")
        QApplication.processEvents()

        final_samples = []
        for face_img in self.captured_faces:
            is_valid, msg, quality = self.face_recognizer.validate_face_sample(
                face_img, 
                check_liveness=False
            )
            if is_valid:
                final_samples.append(face_img)

        if len(final_samples) >= 8:
            self.status_label.setText("💾 Saving to database...")
            QApplication.processEvents()

            success = self.face_recognizer.add_faces(final_samples, self.registration_person_name)

            if success:
                # ★★★ CHANGED: Use auto-fading overlay instead of QMessageBox ★★★
                message = f"{self.registration_person_name} registered!\n{len(final_samples)} samples saved"
                self.notification_overlay.show_notification("Success", message, "success", 3000)
            else:
                # ★★★ CHANGED: Use auto-fading overlay ★★★
                self.notification_overlay.show_notification("Error", "Registration failed!", "error", 3000)
        else:
            # ★★★ CHANGED: Use auto-fading overlay ★★★
            message = f"Only {len(final_samples)}/10 samples passed check.\n\nPlease try again with better lighting."
            self.notification_overlay.show_notification("Warning", message, "warning", 3000)

        self.exit_registration_mode()

    def cancel_registration(self):
        """Cancel registration"""
        reply = QMessageBox.question(self, "Cancel", "Cancel registration?",
                                    QMessageBox.Yes | QMessageBox.No)
        if reply == QMessageBox.Yes:
            self.exit_registration_mode()

    def exit_registration_mode(self):
        """Exit registration"""
        self.registration_mode = False
        self.registration_person_name = ""
        self.captured_faces = []
        self.current_registration_step = 0

        self.capture_btn.setEnabled(True)

        title_emoji = "🛡️" if config.ENABLE_LIVENESS else "👁️"
        self.title_label.setText(f"{title_emoji} Employee Attendance Management System")
        self.instruction_label.setVisible(False)
        self.progress_bar.setVisible(False)
        self.feedback_label.setVisible(False)

        self.button_frame.setVisible(True)
        self.reg_button_frame.setVisible(False)

        self.status_label.setText("✅ Ready")

    def log_action(self, action, person):
        """Log action to file AND send to API"""
        timestamp = datetime.now()
        timestamp_str = timestamp.strftime("%Y-%m-%d %H:%M:%S")
        log_entry = f"{timestamp_str} | {person} | {action}\n"

        # Console log
        print(f"📝 {log_entry.strip()}")

        # File log
        try:
            with open("attendance_log.txt", "a") as f:
                f.write(log_entry)
        except Exception as e:
            print(f"⚠️ File logging error: {e}")

        # ★★★ API LOG ★★★
        if self.api_client:
            try:
                self.api_client.send_attendance_event(
                    name=person,
                    action=action,
                    timestamp=timestamp
                )
            except Exception as e:
                print(f"⚠️ API send error: {e}")

        # Show API stats periodically
        if self.api_client and hasattr(self, 'adaptive_learning_count'):
            if self.adaptive_learning_count % 5 == 0:
                stats = self.api_client.get_stats()
                print(f"📊 API Stats: Sent={stats['total_sent']}, Failed={stats['total_failed']}, Queued={stats['queued']}")

    def verify_and_log_action(self, action):
        """Verify and log with person locking and auto-fading success"""

        if not self.locked_person_for_action:
            # ★★★ CHANGED: Use auto-fading overlay instead of QMessageBox ★★★
            self.notification_overlay.show_notification("Error", "No person locked!", "error", 1000)
            return

        dialog = SimpleConfirmationDialog(self, self.locked_person_for_action, action)

        if dialog.exec() == QDialog.Accepted:
            action_map = {
                "TIME IN": self.state_manager.time_in,
                "TIME OUT": self.state_manager.time_out,
                "BREAK START": self.state_manager.break_start,
                "BREAK END": self.state_manager.break_end,
                "JOB START": self.state_manager.job_start,
                "JOB END": self.state_manager.job_end
            }
    
            if action in action_map:
                success, state_msg = action_map[action](self.locked_person_for_action)
                if not success:
                    self.notification_overlay.show_notification("Error", state_msg, "error", 2000)
                    self.locked_person_for_action = None
                    self.locked_person_timestamp = None
                    return
    
            self.log_action(action, self.locked_person_for_action)
            timestamp = datetime.now().strftime("%H:%M:%S")

            # Adaptive learning
            if self.current_frame is not None and self.current_recognized_person == self.locked_person_for_action:
                try:
                    faces = self.face_recognizer.detect_faces(self.current_frame)
                    if faces:
                        face = max(faces, key=lambda f: f['bbox'][2] * f['bbox'][3])
                        face_img = self.face_recognizer.extract_face_region(self.current_frame, face, align=False)

                        if face_img is not None:
                            is_valid, msg, quality = self.face_recognizer.validate_face_sample(
                                face_img, 
                                check_liveness=False
                            )

                            if is_valid and quality >= 0.75:
                                embedding = self.face_recognizer.extract_embedding(face_img)
                                if embedding is not None:
                                    added = self.face_recognizer.add_embedding_to_existing_person(
                                        self.locked_person_for_action, 
                                        embedding,
                                        max_embeddings=50
                                    )
                                    if added:
                                        self.adaptive_learning_count += 1
                except Exception as e:
                    print(f"Adaptive learning error: {e}")

            # ★★★ CHANGED: Use auto-fading overlay instead of QMessageBox ★★★
            api_note = "Recorded" if self.api_client else "💾 Local"
            # state_display = self.state_manager.get_state_display(self.locked_person_for_action)
            message = f"{action}\n{self.locked_person_for_action}\n{timestamp}\n{api_note}"
            self.notification_overlay.show_notification("Success", message, "success", 2000)
            if self.current_recognized_person:
                self.update_button_visibility(self.current_recognized_person)

            
            self.locked_person_for_action = None
            self.locked_person_timestamp = None

        else:
            self.locked_person_for_action = None
            self.locked_person_timestamp = None

    def update_clock(self):
        """Update clock display with current time"""
        current_time = datetime.now().strftime("%H:%M:%S")
        current_date = datetime.now().strftime("%A, %B %d, %Y")
        self.clock_label.setText(f"🕐 {current_time}\n{current_date}")

    def update_button_visibility(self, person_name):
        if not person_name:
            self.time_in_btn.setVisible(False)
            self.time_out_btn.setVisible(False)
            self.break_in_btn.setVisible(False)
            self.break_out_btn.setVisible(False)
            self.job_in_btn.setVisible(False)
            self.job_out_btn.setVisible(False)
            self.add_face_btn.setVisible(True)
            return
        can_time_in, _ = self.state_manager.can_time_in(person_name)
        can_time_out, _ = self.state_manager.can_time_out(person_name)
        can_break_start, _ = self.state_manager.can_break_start(person_name)
        can_break_end, _ = self.state_manager.can_break_end(person_name)
        can_job_start, _ = self.state_manager.can_job_start(person_name)
        can_job_end, _ = self.state_manager.can_job_end(person_name)
        self.time_in_btn.setVisible(can_time_in)
        self.time_out_btn.setVisible(can_time_out)
        self.break_in_btn.setVisible(can_break_start)
        self.break_out_btn.setVisible(can_break_end)
        self.job_in_btn.setVisible(can_job_start)
        self.job_out_btn.setVisible(can_job_end)
        self.add_face_btn.setVisible(True)

    
    def handle_time_in(self):
        if not self.current_recognized_person:
            self.notification_overlay.show_notification("Error", "No face recognized!", "error", 1000)
            return
        can_do, msg = self.state_manager.can_time_in(self.current_recognized_person)
        if not can_do:
            self.notification_overlay.show_notification("Warning", msg, "warning", 2000)
            return
        self.locked_person_for_action = self.current_recognized_person
        self.locked_person_timestamp = datetime.now()
        self.verify_and_log_action("TIME IN")

    def handle_time_out(self):
        if not self.current_recognized_person:
            self.notification_overlay.show_notification("Error", "No face recognized!", "error", 1000)
            return
        can_do, msg = self.state_manager.can_time_out(self.current_recognized_person)
        if not can_do:
            self.notification_overlay.show_notification("Warning", msg, "warning", 2000)
            return
        self.locked_person_for_action = self.current_recognized_person
        self.locked_person_timestamp = datetime.now()
        self.verify_and_log_action("TIME OUT")

    def handle_break_in(self):
        if not self.current_recognized_person:
            self.notification_overlay.show_notification("Error", "No face recognized!", "error", 1000)
            return
        can_do, msg = self.state_manager.can_break_start(self.current_recognized_person)
        if not can_do:
            self.notification_overlay.show_notification("Warning", msg, "warning", 2000)
            return
        self.locked_person_for_action = self.current_recognized_person
        self.locked_person_timestamp = datetime.now()
        self.verify_and_log_action("BREAK START")

    def handle_break_out(self):
        if not self.current_recognized_person:
            self.notification_overlay.show_notification("Error", "No face recognized!", "error", 1000)
            return
        can_do, msg = self.state_manager.can_break_end(self.current_recognized_person)
        if not can_do:
            self.notification_overlay.show_notification("Warning", msg, "warning", 2000)
            return
        self.locked_person_for_action = self.current_recognized_person
        self.locked_person_timestamp = datetime.now()
        self.verify_and_log_action("BREAK END")

    def handle_job_in(self):
        if not self.current_recognized_person:
            self.notification_overlay.show_notification("Error", "No face recognized!", "error", 1000)
            return
        can_do, msg = self.state_manager.can_job_start(self.current_recognized_person)
        if not can_do:
            self.notification_overlay.show_notification("Warning", msg, "warning", 2000)
            return
        self.locked_person_for_action = self.current_recognized_person
        self.locked_person_timestamp = datetime.now()
        self.verify_and_log_action("JOB START")

    def handle_job_out(self):
        if not self.current_recognized_person:
            self.notification_overlay.show_notification("Error", "No face recognized!", "error", 1000)
            return
        can_do, msg = self.state_manager.can_job_end(self.current_recognized_person)
        if not can_do:
            self.notification_overlay.show_notification("Warning", msg, "warning", 2000)
            return
        self.locked_person_for_action = self.current_recognized_person
        self.locked_person_timestamp = datetime.now()
        self.verify_and_log_action("JOB END")


    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            if self.registration_mode:
                self.cancel_registration()
            else:
                self.close_app()

    def close_app(self):
        """Close application gracefully"""
        print("\n🛑 Shutting down...")

        # Stop welcome screen animation
        if hasattr(self, 'welcome_widget'):
            self.welcome_widget.stop_animation()

        # Stop clock timer
        if hasattr(self, 'clock_timer'):
            self.clock_timer.stop()

        if self.process_timer:
            self.process_timer.stop()

        if self.camera_thread:
            self.camera_thread.stop()

        # ★★★ STOP API CLIENT GRACEFULLY ★★★
        if hasattr(self, 'api_client') and self.api_client:
            print("Stopping API client...")
            self.api_client.stop()

            # Show final stats
            stats = self.api_client.get_stats()
            print(f"📊 Final API Stats:")
            print(f"   ✅ Sent: {stats['total_sent']}")
            print(f"   ❌ Failed: {stats['total_failed']}")
            print(f"   ⏳ Remaining: {stats['queued']}")

        print("✓ Shutdown complete\n")
        self.close()

    def closeEvent(self, event):
        """Handle window close event"""
        if self.process_timer:
            self.process_timer.stop()

        if self.camera_thread:
            self.camera_thread.stop()

        # ★★★ STOP API CLIENT ON WINDOW CLOSE ★★★
        if hasattr(self, 'api_client') and self.api_client:
            self.api_client.stop()

        event.accept()


def main():
    app = QApplication(sys.argv)
    font = QFont("Ubuntu", 12)
    app.setFont(font)

    window = AttendanceKioskGUI()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
