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
# Qt handles system input methods natively

import sys
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                               QHBoxLayout, QLabel, QPushButton, QFrame, QInputDialog, 
                               QGridLayout, QMessageBox, QDialog, QProgressBar, QStackedWidget,
                               QSizePolicy, QLineEdit)
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
from modules.mqtt_face_registration import MQTTFaceRegistrationHandler
from modules.temporal_buffer import TemporalRecognitionBuffer
from modules.admin_control import AdminControlPage

import subprocess

import config

# ── Screen-relative scaling helpers ──────────────────────────────────────────
# Reference: 480 × 854  (portrait RPi 7" touchscreen)
# pw(n) → scale a width-related pixel value
# ph(n) → scale a height-related pixel value
# pf(n) → scale a font-size (uses the shorter axis so text stays readable)
def _scr():
    app = QApplication.instance()
    if app:
        # First try to get the main window's size
        for w in app.topLevelWidgets():
            if w.objectName() == "MainWindow" or w.__class__.__name__ == "AttendanceKioskGUI":
                return w.width(), w.height()
        s = app.primaryScreen()
        if s:
            g = s.availableGeometry()
            return g.width(), g.height()
    return 480, 854

def pw(n): w, h = _scr(); return max(1, int(n * w / 480))
def ph(n): w, h = _scr(); return max(1, int(n * h / 854))
def pf(n): w, h = _scr(); return max(8, int(n * min(w, h) / 480))
# ─────────────────────────────────────────────────────────────────────────────

import subprocess

class VKLineEdit(QLineEdit):
    """
    Triggers the default system virtual keyboard (squeekboard on Wayland, onboard on X11).
    Includes auto-hide logic on focus loss.
    """
    _kb_proc = None
    _hide_timer = None

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setAttribute(Qt.WA_InputMethodEnabled, True)

    def focusInEvent(self, event):
        super().focusInEvent(event)
        # Cancel any pending hide
        if VKLineEdit._hide_timer and VKLineEdit._hide_timer.isActive():
            VKLineEdit._hide_timer.stop()
        self._show_keyboard()

    def focusOutEvent(self, event):
        super().focusOutEvent(event)
        # Delay hiding to see if another VKLineEdit gets focus (e.g. tabbing)
        if VKLineEdit._hide_timer is None:
            VKLineEdit._hide_timer = QTimer()
            VKLineEdit._hide_timer.setSingleShot(True)
            VKLineEdit._hide_timer.timeout.connect(self._hide_keyboard)
        
        VKLineEdit._hide_timer.start(200) # 200ms delay

    @classmethod
    def _show_keyboard(cls):
        # 1. Default device virtual keyboard (squeekboard via dbus)
        try:
            subprocess.run(
                ['dbus-send', '--session', '--type=method_call',
                 '--dest=sm.puri.OSK0', '/sm/puri/OSK0',
                 'sm.puri.OSK0.SetVisible', 'boolean:true'],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                check=True
            )
            return
        except Exception:
            pass

        # 2. X11 default keyboards
        if cls._kb_proc is not None and cls._kb_proc.poll() is None:
            return

        for cmd in (['onboard'], ['matchbox-keyboard']):
            try:
                cls._kb_proc = subprocess.Popen(
                    cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
                )
                return
            except FileNotFoundError:
                continue

    @classmethod
    def _hide_keyboard(cls):
        # 1. Hide squeekboard
        try:
            subprocess.run(
                ['dbus-send', '--session', '--type=method_call',
                 '--dest=sm.puri.OSK0', '/sm/puri/OSK0',
                 'sm.puri.OSK0.SetVisible', 'boolean:false'],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
            )
        except Exception:
            pass

        # 2. Hide X11 keyboards
        if cls._kb_proc is not None and cls._kb_proc.poll() is None:
            cls._kb_proc.terminate()
            cls._kb_proc = None






class TextInputDialog(QDialog):
    """
    Compact styled text-input dialog using VKLineEdit.
    All dimensions scale with the actual screen resolution.
    """
    def __init__(self, parent=None, title="Enter Text", label="",
                 echo_mode=QLineEdit.Normal, placeholder=""):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setModal(True)
        if parent:
            self.setFixedSize(parent.size())
        else:
            self.showFullScreen()
        self.setWindowFlags(Qt.Dialog | Qt.FramelessWindowHint)
        self.setStyleSheet(f"""
            QDialog {{
                background-color: rgba(255, 255, 255, 230);
                border: none;
            }}
            QLabel {{ color: #333333; font-size: {pf(14)}px; }}
            VKLineEdit, QLineEdit {{
                background-color: #f9f9f9;
                color: #000000;
                border: 2px solid #dddddd;
                border-radius: {pw(8)}px;
                padding: {ph(8)}px {pw(12)}px;
                font-size: {pf(18)}px;
            }}
            QLineEdit:focus {{ border-color: #4a90e2; }}
            QPushButton#btn_confirm {{
                background-color: #00aa66; color: #fff;
                border: none; border-radius: {pw(8)}px;
                font-size: {pf(14)}px; font-weight: bold; padding: {ph(9)}px;
            }}
            QPushButton#btn_confirm:pressed {{ background-color: #008855; }}
            QPushButton#btn_cancel {{
                background-color: transparent; color: #666666;
                border: 1px solid #cccccc; border-radius: {pw(8)}px;
                font-size: {pf(14)}px; padding: {ph(9)}px;
            }}
            QPushButton#btn_cancel:pressed {{ background-color: #f0f0f0; }}
        """)

        main_layout = QVBoxLayout(self)
        main_layout.addStretch(1)

        container = QFrame()
        container.setStyleSheet(f"""
            QFrame {{
                background-color: #ffffff;
                border: 2px solid #e0e0e0;
                border-radius: {pw(12)}px;
            }}
        """)
        root = QVBoxLayout(container)
        root.setContentsMargins(pw(25), ph(25), pw(25), ph(25))
        root.setSpacing(ph(12))

        title_lbl = QLabel(title)
        title_lbl.setAlignment(Qt.AlignCenter)
        title_lbl.setStyleSheet(f"font-size: {pf(18)}px; font-weight: bold; color: #333333; border: none;")
        root.addWidget(title_lbl)

        if label:
            root.addWidget(QLabel(label))

        self.input = VKLineEdit()
        self.input.setPlaceholderText(placeholder or title)
        self.input.setEchoMode(echo_mode)
        self.input.returnPressed.connect(self.accept)
        root.addWidget(self.input)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(pw(8))
        cancel_btn = QPushButton("Cancel")
        cancel_btn.setObjectName("btn_cancel")
        cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(cancel_btn)
        confirm_btn = QPushButton("✓  OK")
        confirm_btn.setObjectName("btn_confirm")
        confirm_btn.clicked.connect(self.accept)
        btn_row.addWidget(confirm_btn)
        root.addLayout(btn_row)

        main_layout.addWidget(container, alignment=Qt.AlignCenter)
        main_layout.addStretch(1)

        self.input.setFocus()

    def get_text(self) -> str:
        return self.input.text()




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
        self.container_layout = QVBoxLayout(self.container)

        self.icon_label = QLabel("✅")
        self.icon_label.setAlignment(Qt.AlignCenter)

        self.title_label = QLabel("SUCCESS")
        self.title_label.setAlignment(Qt.AlignCenter)

        self.message_label = QLabel("")
        self.message_label.setAlignment(Qt.AlignCenter)
        self.message_label.setWordWrap(True)

        self.container_layout.addWidget(self.icon_label)
        self.container_layout.addWidget(self.title_label)
        self.container_layout.addWidget(self.message_label)

        layout.addWidget(self.container)

        # Base style config updated in show_notification
        self.bg_color = "rgba(0, 170, 102, 220)"
        self.border_color = "#00ff88"

        # Fade animation
        self.fade_timer = QTimer()
        self.fade_timer.setSingleShot(True)
        self.fade_timer.timeout.connect(self.start_fade_out)

        self.hide()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.update_styles()

    def update_styles(self):
        w = self.width()
        h = self.height()
        def _pf(n): return max(8, int(n * min(w, h) / 480))
        def _pw(n): return max(1, int(n * w / 480))
        def _ph(n): return max(1, int(n * h / 854))

        self.container_layout.setSpacing(_ph(8))

        self.container.setStyleSheet(f"""
            QFrame {{
                background-color: {self.bg_color};
                border: 3px solid {self.border_color};
                border-radius: {_pw(8)}px;
                padding: {_ph(15)}px;
                min-width: {_pw(150)}px;
                max-width: {_pw(250)}px;
            }}
            QLabel {{
                color: #ffffff;
                background: transparent;
                border: none;
            }}
        """)
        self.icon_label.setStyleSheet(f"font-size: {_pf(30)}px;")
        self.title_label.setStyleSheet(f"font-size: {_pf(16)}px; font-weight: bold;")
        self.message_label.setStyleSheet(f"font-size: {_pf(12)}px;")

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

        self.bg_color = bg_color
        self.border_color = border_color
        
        # Trigger style update to apply new colors
        self.update_styles()

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
    """Camera thread - optimized for Raspberry Pi 4"""
    frame_ready = Signal(np.ndarray)
    status_update = Signal(str)

    def __init__(self, mirror=True):
        super().__init__()
        self._running = False
        self.picam2 = None
        self.mirror = mirror


    def run(self):
        """Capture frames in RGB888."""
        try:
            self.picam2 = Picamera2()

            # libcamera.Transform handles mirror only (vc4 pipeline does not
            # support rotation here). Rotation is done per-frame via cv2.rotate.
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
            time.sleep(0.5)  # slightly longer warm-up helps Pi 4 AE settle

            self._running = True
            self.status_update.emit("✅ Camera Ready")

            frame_interval = 1.0 / max(config.CAMERA_FPS, 1)

            rotation = getattr(config, 'CAMERA_ROTATION', 0)
            _rotate_map = {
                90:  cv2.ROTATE_90_CLOCKWISE,
                180: cv2.ROTATE_180,
                270: cv2.ROTATE_90_COUNTERCLOCKWISE,
            }

            while self._running:
                try:
                    frame_rgb = self.picam2.capture_array()

                    if rotation in _rotate_map:
                        frame_rgb = cv2.rotate(frame_rgb, _rotate_map[rotation])

                    self.frame_ready.emit(frame_rgb)

                    time.sleep(frame_interval)

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
class AdminPasswordDialog(QDialog):
    """Admin-password modal. All sizes scale with screen resolution."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Admin Authentication")
        self.setModal(True)
        if parent:
            self.setFixedSize(parent.size())
        else:
            self.showFullScreen()
        self.setWindowFlags(Qt.Dialog | Qt.FramelessWindowHint)
        self.setStyleSheet(f"""
            QDialog {{
                background-color: rgba(255, 255, 255, 230);
                border: none;
            }}
            QLabel {{ color: #333333; font-size: {pf(15)}px; }}
            QLabel#dlg_error {{ color: #E74C3C; font-size: {pf(12)}px; background-color: transparent; border: none; }}
            VKLineEdit, QLineEdit {{
                background-color: #f9f9f9;
                color: #000000;
                border: 2px solid #dddddd;
                border-radius: {pw(8)}px;
                padding: {ph(8)}px {pw(12)}px;
                font-size: {pf(20)}px;
                letter-spacing: 4px;
            }}
            VKLineEdit:focus, QLineEdit:focus {{ border-color: #4a90e2; }}
            QPushButton#btn_confirm {{
                background-color: #00aa66; color: #fff;
                border: none; border-radius: {pw(8)}px;
                font-size: {pf(14)}px; font-weight: bold; padding: {ph(9)}px;
            }}
            QPushButton#btn_confirm:pressed {{ background-color: #008855; }}
            QPushButton#btn_cancel {{
                background-color: transparent; color: #666666;
                border: 1px solid #cccccc; border-radius: {pw(8)}px;
                font-size: {pf(14)}px; padding: {ph(9)}px;
            }}
            QPushButton#btn_cancel:pressed {{ background-color: #f0f0f0; }}
        """)

        main_layout = QVBoxLayout(self)
        main_layout.addStretch(1)

        container = QFrame()
        container.setStyleSheet(f"""
            QFrame {{
                background-color: #ffffff;
                border: 2px solid #e0e0e0;
                border-radius: {pw(12)}px;
            }}
        """)
        root = QVBoxLayout(container)
        root.setContentsMargins(pw(25), ph(25), pw(25), ph(25))
        root.setSpacing(ph(12))

        title = QLabel("🔐  Admin Authentication")
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet(f"font-size: {pf(18)}px; font-weight: bold; color: #333333; border: none;")
        root.addWidget(title)

        self.password_input = VKLineEdit()
        self.password_input.setPlaceholderText("Enter admin password")
        self.password_input.setEchoMode(QLineEdit.Password)
        self.password_input.returnPressed.connect(self.accept)
        root.addWidget(self.password_input)

        self.error_label = QLabel("")
        self.error_label.setObjectName("dlg_error")
        self.error_label.setAlignment(Qt.AlignCenter)
        root.addWidget(self.error_label)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(pw(8))
        cancel_btn = QPushButton("Cancel")
        cancel_btn.setObjectName("btn_cancel")
        cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(cancel_btn)
        confirm_btn = QPushButton("✓  Confirm")
        confirm_btn.setObjectName("btn_confirm")
        confirm_btn.clicked.connect(self.accept)
        btn_row.addWidget(confirm_btn)
        root.addLayout(btn_row)

        main_layout.addWidget(container, alignment=Qt.AlignCenter)
        main_layout.addStretch(1)

        self.password_input.setFocus()

    def get_password(self) -> str:
        return self.password_input.text()

    def show_error(self, message: str):
        self.error_label.setText(f"⚠  {message}")
        self.password_input.clear()
        self.password_input.setFocus()







class SimpleConfirmationDialog(QDialog):
    """Confirmation dialog — all sizes scale with screen."""

    def __init__(self, parent, person_name, action):
        super().__init__(parent)
        self.person_name = person_name
        self.action = action
        self.no_face_timeout = None
        self.init_ui()

    def init_ui(self):
        self.setWindowTitle("Confirm Identity")
        self.setModal(True)
        self.setMinimumSize(pw(350), ph(200))

        self.setStyleSheet(f"""
            QDialog {{ background-color: #1a1a1a; }}
            QLabel {{ color: #ffffff; font-size: {pf(14)}px; padding: {ph(6)}px; }}
            QLabel#title {{ color: #00ff88; font-size: {pf(16)}px; font-weight: bold; }}
            QLabel#name  {{ color: #4a90e2; font-size: {pf(18)}px; font-weight: bold; }}
            QLabel#action {{ color: #f5a623; font-size: {pf(12)}px; }}
            QPushButton {{
                color: #ffffff; border: 2px solid; border-radius: {pw(8)}px;
                font-size: {pf(12)}px; font-weight: bold;
                padding: {ph(8)}px {pw(16)}px; min-width: {pw(100)}px;
            }}
            QPushButton#confirm {{ background-color: #00aa66; border-color: #00ff88; }}
            QPushButton#confirm:hover {{ background-color: #00cc77; }}
            QPushButton#cancel  {{ background-color: #cc3333; border-color: #ff4444; }}
            QPushButton#cancel:hover  {{ background-color: #dd4444; }}
        """)

        layout = QVBoxLayout(self)
        layout.setSpacing(ph(10))
        layout.setContentsMargins(pw(20), ph(20), pw(20), ph(20))

        title = QLabel("⚠ Confirm Your Identity")
        title.setObjectName("title")
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)

        name_label = QLabel(f"👤 {self.person_name}")
        name_label.setObjectName("name")
        name_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(name_label)

        action_label = QLabel(f"➡️ {self.action}")
        action_label.setObjectName("action")
        action_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(action_label)

        question = QLabel("Is this you?")
        question.setAlignment(Qt.AlignCenter)
        question.setStyleSheet(f"font-size: {pf(12)}px; color: #aaaaaa;")
        layout.addWidget(question)

        button_layout = QHBoxLayout()
        button_layout.setSpacing(pw(12))

        confirm_btn = QPushButton("✅ Yes, Confirm")
        confirm_btn.setObjectName("confirm")
        confirm_btn.clicked.connect(self.accept)
        button_layout.addWidget(confirm_btn)

        cancel_btn = QPushButton("❌ No, Cancel")
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

        # MQTT Reporter - Gated by ENABLE_MQTT_FEATURES
        if config.MQTT_ENABLED and getattr(config, 'ENABLE_MQTT_FEATURES', False):
            self.mqtt_reporter = MQTTIncidentReporter(
                broker_host=config.MQTT_BROKER_HOST,
                broker_port=config.MQTT_BROKER_PORT,
                topic=config.MQTT_TOPIC
            )
        else:
            self.mqtt_reporter = None
            if not getattr(config, 'ENABLE_MQTT_FEATURES', False):
                print("○ MQTT Reporter disabled (ENABLE_MQTT_FEATURES is False)")

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
                model_name=config.INSIGHTFACE_MODEL,
                det_size=config.INSIGHTFACE_DET_SIZE,
                providers=config.INSIGHTFACE_PROVIDERS,
                detection_confidence=config.DETECTION_CONFIDENCE,
                recognition_threshold=config.RECOGNITION_THRESHOLD,
                margin_threshold=config.MARGIN_THRESHOLD,
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

            # ★★★ INITIALIZE MQTT FACE REGISTRATION HANDLER ★★★
            if (config.MQTT_ENABLED and 
                getattr(config, 'MQTT_FACE_REGISTRATION_ENABLED', False) and 
                getattr(config, 'ENABLE_MQTT_FEATURES', False)):
                try:
                    self.mqtt_face_handler = MQTTFaceRegistrationHandler(
                        face_recognizer=self.face_recognizer,
                        broker_host=config.MQTT_BROKER_HOST,
                        broker_port=config.MQTT_BROKER_PORT,
                        subscribe_topic=config.MQTT_FACE_REGISTRATION_TOPIC,
                        result_topic=config.MQTT_FACE_REGISTRATION_RESULT_TOPIC
                    )
                    self.mqtt_face_handler.start()
                    print(f"✓ MQTT Face Registration enabled - Topic: {config.MQTT_FACE_REGISTRATION_TOPIC}")
                except Exception as e:
                    print(f"⚠️ MQTT Face Registration failed: {e}")
                    self.mqtt_face_handler = None
            else:
                self.mqtt_face_handler = None

            # Validate existing database
            print("\n🔍 Validating database quality...")
            self.face_recognizer.validate_all_embeddings()

            # ★★★ STARTUP SYNC - Fetch fresh status for all users ★★★
            if config.API_ENABLED and self.api_client:
                print("\n🔄 Syncing attendance status from server...")
                self._sync_all_users_on_startup()

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

        # ★★★ SERVER STATUS SYNC TRACKING ★★★
        self.last_status_sync_time = 0  # Last time we synced status from server
        self.status_sync_interval = 60  # Sync every 60 seconds
        self.is_user_blocked = False  # True if server blocks this user (task running, approval required)
        self.blocked_message = ""  # Store the blocking message for display after confirmation
        self.last_synced_employee_id = None  # Cache to avoid redundant syncs

        # Registration state - 10 SAMPLES
        self.registration_person_name = ""
        self.registration_person_employee_id = None  # NEW: Store employee ID during registration
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

        # ★★★ FACE CONFIRMATION & FREEZE STATE ★★★
        self.face_confirmed = False              # Is face confirmed and frozen?
        self.confirmed_person_name = None        # Name of confirmed person
        self.confirmed_person_similarity = 0.0   # Similarity score of confirmed person
        self.confirmed_frame = None              # Frozen frame to display
        self.confirmation_start_time = None      # When stable recognition started
        self.CONFIRMATION_DELAY = 1.0            # Seconds of stable recognition before confirming
        self.event_in_progress = False           # Is user performing an event action?
        self.last_stable_person = None           # Track person for stable recognition

        # ★★★ TEMPORAL RECOGNITION BUFFER - Anti-flicker ★★★
        self.temporal_buffer = TemporalRecognitionBuffer(
            buffer_size=config.TEMPORAL_BUFFER_SIZE,
            agreement_threshold=config.TEMPORAL_AGREEMENT_THRESHOLD
        )
        self.temporal_buffer.set_identity_lock_time(config.IDENTITY_LOCK_TIME)
        print(f"✓ Temporal Buffer: {config.TEMPORAL_BUFFER_SIZE} frames, {config.TEMPORAL_AGREEMENT_THRESHOLD*100:.0f}% agreement")

        self.init_ui()

        # ★★★ CREATE NOTIFICATION OVERLAY ★★★
        self.notification_overlay = NotificationOverlay(self)

        # Start camera
        QTimer.singleShot(200, self.init_camera)

        # Processing timer
        self.process_timer = QTimer()
        self.process_timer.timeout.connect(self.process_frame)
        self.process_timer.start(1000 // config.CAMERA_FPS)

        # ★★★ DATABASE RELOAD TIMER - Check for updates every 30 seconds ★★★
        self.db_reload_timer = QTimer()
        self.db_reload_timer.timeout.connect(self._check_db_update)
        self.db_reload_timer.start(30000)  # 30 seconds

        # ★★★ STATUS SYNC TIMER - Refresh server status every 60 seconds ★★★
        self.status_sync_timer = QTimer()
        self.status_sync_timer.timeout.connect(self._sync_current_user_status)
        self.status_sync_timer.start(60000)  # 60 seconds


    def init_ui(self):
        """Initialize UI"""
        liveness_status = "🛡️ Blink Detection" if config.ENABLE_LIVENESS else "⚠️ Liveness Disabled"
        api_status = f"📡 API: {config.API_SERVER_IP}" if config.API_ENABLED else "○ API Disabled"

        self.setWindowTitle(f"Employee Attendance System - {liveness_status} | {api_status}")

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        self.main_layout = QVBoxLayout(central_widget)
        self.main_layout.setContentsMargins(10, 10, 10, 10)
        self.main_layout.setSpacing(5)

        self.title_label = QLabel("Employee Attendance Management System")
        self.title_label.setObjectName("title")
        self.title_label.setAlignment(Qt.AlignCenter)
        self.title_label.setWordWrap(True)
        self.title_label.setMinimumWidth(10)
        self.main_layout.addWidget(self.title_label)

        self.status_label = QLabel("Starting...")
        self.status_label.setObjectName("status")
        self.status_label.setAlignment(Qt.AlignCenter)
        self.status_label.setWordWrap(True)
        self.status_label.setMinimumWidth(10)
        self.main_layout.addWidget(self.status_label)

        self.instruction_label = QLabel("")
        self.instruction_label.setObjectName("instruction")
        self.instruction_label.setAlignment(Qt.AlignCenter)
        self.instruction_label.setWordWrap(True)
        self.instruction_label.setMinimumWidth(10)
        self.instruction_label.setVisible(False)
        self.main_layout.addWidget(self.instruction_label)

        self.feedback_label = QLabel("")
        self.feedback_label.setObjectName("feedback")
        self.feedback_label.setAlignment(Qt.AlignCenter)
        self.feedback_label.setWordWrap(True)
        self.feedback_label.setVisible(False)
        self.main_layout.addWidget(self.feedback_label)

        # Stacked widget for welcome screen and camera feed
        self.display_stack = QStackedWidget()
        # Removed fixed minimum size to allow fitting on smaller screens

        # Welcome screen (index 0)
        self.welcome_widget = WelcomeScreen()
        self.display_stack.addWidget(self.welcome_widget)

        # Camera label (index 1)
        self.camera_label = QLabel()
        self.camera_label.setObjectName("camera")
        self.camera_label.setAlignment(Qt.AlignCenter)
        self.camera_label.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Ignored)
        self.display_stack.addWidget(self.camera_label)

        # Start with welcome screen
        self.display_stack.setCurrentIndex(0)

        # Create camera page widget with admin button
        self.camera_page_widget = QWidget()
        camera_page_layout = QVBoxLayout(self.camera_page_widget)
        camera_page_layout.setContentsMargins(0, 0, 0, 0)
        camera_page_layout.setSpacing(0)
        
        # Add display stack to camera page
        camera_page_layout.addWidget(self.display_stack, stretch=1)
        
        # Add admin button in bottom right corner
        admin_button_container = QFrame()
        admin_button_layout = QHBoxLayout(admin_button_container)
        admin_button_layout.setContentsMargins(0, 0, 10, 10)
        admin_button_layout.addStretch()
        
        self.admin_icon_btn = QPushButton("⚙️ ADMIN")
        self.admin_icon_btn.setObjectName("adminIcon")
        self.admin_icon_btn.clicked.connect(self.show_admin_page)
        self.admin_icon_btn.setCursor(Qt.PointingHandCursor)
        self.admin_icon_btn.setMinimumHeight(40)
        self.admin_icon_btn.setMaximumWidth(100)
        admin_button_layout.addWidget(self.admin_icon_btn)
        
        admin_button_container.setStyleSheet("background: transparent; border: none;")
        camera_page_layout.addWidget(admin_button_container)
        
        # Create pages stack for camera and admin pages
        self.pages_stack = QStackedWidget()
        
        # Page 0: Camera page
        self.pages_stack.addWidget(self.camera_page_widget)
        
        # Page 1: Admin control page
        self.admin_page = AdminControlPage(self.face_recognizer)
        self.admin_page.home_requested.connect(self.show_camera_page)
        self.pages_stack.addWidget(self.admin_page)
        
        # Start with camera page
        self.pages_stack.setCurrentIndex(0)
        
        self.main_layout.addWidget(self.pages_stack, stretch=1)

        self.progress_bar = QProgressBar()
        self.progress_bar.setMinimum(0)
        self.progress_bar.setMaximum(len(self.registration_steps))
        self.progress_bar.setValue(0)
        self.progress_bar.setFormat(f"Accepted: %v of {len(self.registration_steps)}")
        self.progress_bar.setVisible(False)
        self.main_layout.addWidget(self.progress_bar)

        # Action buttons container - switched to QGridLayout for 2-column layout
        self.button_frame = QFrame()
        self.button_frame.setObjectName("buttonContainer")
        self.button_layout = QGridLayout(self.button_frame)
        self.button_layout.setSpacing(ph(10))
        # Reduced side padding for better width usage
        self.button_layout.setContentsMargins(pw(15), ph(10), pw(15), ph(10))

        self.time_in_btn = QPushButton("\U0001F551 TIME IN")
        self.time_in_btn.setObjectName("timeIn")
        self.time_in_btn.clicked.connect(self.handle_time_in)
        self.time_in_btn.setCursor(Qt.PointingHandCursor)

        self.time_out_btn = QPushButton("\U0001F551 TIME OUT")
        self.time_out_btn.setObjectName("timeOut")
        self.time_out_btn.clicked.connect(self.handle_time_out)
        self.time_out_btn.setCursor(Qt.PointingHandCursor)

        self.break_in_btn = QPushButton("\U00002615 BREAK START")
        self.break_in_btn.setObjectName("breakIn")
        self.break_in_btn.clicked.connect(self.handle_break_in)
        self.break_in_btn.setCursor(Qt.PointingHandCursor)

        self.break_out_btn = QPushButton("\U00002615 BREAK END")
        self.break_out_btn.setObjectName("breakOut")
        self.break_out_btn.clicked.connect(self.handle_break_out)
        self.break_out_btn.setCursor(Qt.PointingHandCursor)

        self.job_in_btn = QPushButton("\U0001F4BC JOB START")
        self.job_in_btn.setObjectName("jobIn")
        self.job_in_btn.clicked.connect(self.handle_job_in)
        self.job_in_btn.setCursor(Qt.PointingHandCursor)

        self.job_out_btn = QPushButton("\U0001F4BC JOB END")
        self.job_out_btn.setObjectName("jobOut")
        self.job_out_btn.clicked.connect(self.handle_job_out)
        self.job_out_btn.setCursor(Qt.PointingHandCursor)

        self.add_face_btn = QPushButton("\U0001F464 ADD NEW FACE")
        self.add_face_btn.setObjectName("addFace")
        self.add_face_btn.clicked.connect(self.start_registration)
        self.add_face_btn.setCursor(Qt.PointingHandCursor)

        # Store all buttons in a list for easy management
        self.all_action_buttons = [
            self.time_in_btn, self.time_out_btn,
            self.break_in_btn, self.break_out_btn,
            self.job_in_btn, self.job_out_btn,
            self.add_face_btn
        ]

        self.main_layout.addWidget(self.button_frame)

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
        self.main_layout.addWidget(self.reg_button_frame)

        # Initially hide buttons
        self.button_frame.setVisible(False)
        self.update_styles()

        self.showFullScreen()
        
        # Execute the Wayland rotation script after GUI is visible
        QTimer.singleShot(1000, self._rotate_screen)

    def _rotate_screen(self):
        """Automatically rotate the screen layout after OS boot if needed."""
        try:
            import subprocess
            import os
            script_path = os.path.join(os.path.dirname(__file__), "rotate_screen.sh")
            if os.path.exists(script_path):
                subprocess.Popen(["bash", script_path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                print("🔄 Triggered screen rotation script")
        except Exception as e:
            print(f"⚠️ Failed to trigger screen rotation script: {e}")

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.update_styles()

    def update_styles(self):
        """Update GUI elements relative to actual window width and height."""
        w = self.width()
        h = self.height()
        def _pf(n): return max(8, int(n * min(w, h) / 480))
        def _pw(n): return max(1, int(n * w / 480))
        def _ph(n): return max(1, int(n * h / 854))

        self.setStyleSheet(f"""
            QMainWindow {{ background-color: #1a1a1a; }}
            QLabel#title {{ color: #ffffff; font-size: {_pf(16)}px; font-weight: bold; padding: {_ph(5)}px; }}
            QLabel#status {{ color: #00ff88; font-size: {_pf(13)}px; padding: {_ph(3)}px; }}
            QLabel#instruction {{ color: #00ff88; font-size: {_pf(15)}px; font-weight: bold; padding: {_ph(5)}px; }}
            QLabel#feedback {{ color: #ffffff; font-size: {_pf(15)}px; font-weight: bold; padding: {_ph(5)}px; }}
            QLabel#camera {{ background-color: #000000; border: 3px solid #00ff88; border-radius: {_pw(10)}px; }}
            QPushButton {{
                background-color: #2d2d2d; color: #ffffff; border: 2px solid #4d4d4d;
                border-radius: {_pw(8)}px; font-size: {_pf(14)}px; font-weight: bold; padding: {_ph(8)}px; min-height: {_ph(40)}px;
            }}
            QPushButton:hover {{ background-color: #3d3d3d; border-color: #00ff88; }}
            QPushButton:pressed {{ background-color: #1d1d1d; }}
            QPushButton#timeIn {{ border-color: #4a90e2; }}
            QPushButton#timeOut {{ border-color: #e24a4a; }}
            QPushButton#breakIn {{ border-color: #f5a623; }}
            QPushButton#breakOut {{ border-color: #ff8c00; }}
            QPushButton#jobIn {{ border-color: #bd10e0; }}
            QPushButton#jobOut {{ border-color: #9b10c0; }}
            QPushButton#addFace {{ border-color: #50c878; }}
            QPushButton#capture {{ background-color: #4a90e2; border-color: #6ab0ff; font-size: {_pf(18)}px; }}
            QPushButton#cancelReg {{ background-color: #cc3333; border-color: #ff4444; font-size: {_pf(18)}px; }}
            QPushButton#adminIcon {{ background-color: #ff8c00; border-color: #ffaa00; font-size: {_pf(12)}px; }}
            QPushButton#adminIcon:hover {{ background-color: #ffaa00; }}
            QFrame#buttonContainer {{ background-color: #0d0d0d; border-top: 3px solid #00ff88; padding: {_ph(10)}px; }}
            QProgressBar {{
                border: 2px solid #4a90e2; border-radius: {_pw(5)}px; text-align: center;
                color: #ffffff; font-weight: bold; min-height: {_ph(30)}px; font-size: {_pf(16)}px;
            }}
            QProgressBar::chunk {{ background-color: #00ff88; }}
        """)

        # Adjust main layout spacing dynamically
        self.main_layout.setContentsMargins(_pw(10), _ph(10), _pw(10), _ph(10))
        self.main_layout.setSpacing(_ph(5))
        
        # We can also update feedback label manually if it has overrides
        if self.feedback_label.text().startswith("✅"):
            self.feedback_label.setStyleSheet(f"color: #00ff88; font-size: {_pf(15)}px; font-weight: bold; padding: {_ph(5)}px; background: transparent; border: none;")
        elif self.feedback_label.text().startswith("❌"):
            self.feedback_label.setStyleSheet(f"color: #ff4444; font-size: {_pf(15)}px; font-weight: bold; padding: {_ph(5)}px; background: transparent; border: none;")

    def show_admin_page(self):
        """Show the admin control page"""
        self.pages_stack.setCurrentIndex(1)

    def show_camera_page(self):
        """Show the camera page"""
        self.pages_stack.setCurrentIndex(0)

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

    def _check_db_update(self):
        """Check if database file was modified and reload if needed"""
        try:
            self.face_recognizer.reload_if_modified()
        except Exception as e:
            print(f"⚠️ Database reload check error: {e}")

    def _sync_current_user_status(self):
        """Sync status from server for currently recognized person (called by timer)"""
        if self.current_recognized_person and self.api_client:
            self._sync_status_for_person(self.current_recognized_person)

    def _sync_status_for_person(self, person_name: str) -> bool:
        """
        Fetch and sync attendance status from server for a person
        
        Args:
            person_name: Name of the person to sync
            
        Returns:
            True if sync succeeded and user is NOT blocked
        """
        if not self.api_client:
            return True  # Offline mode - allow actions
        
        # Get employee ID for this person
        employee_id = self.face_recognizer.get_employee_id(person_name)
        
        if not employee_id or employee_id == "none":
            print(f"⚠️ No employee ID for {person_name} - using local state")
            self.is_user_blocked = False
            return True
        
        # Check if we need to sync (avoid redundant API calls)
        current_time = time.time()
        if (self.last_synced_employee_id == employee_id and 
            current_time - self.last_status_sync_time < 5):  # Min 5 seconds between syncs
            return not self.is_user_blocked
        
        try:
            # Fetch status from server
            timestamp = int(datetime.now().timestamp())
            api_response = self.api_client.get_attendance_status(employee_id, timestamp)
            
            # Update tracking
            self.last_status_sync_time = current_time
            self.last_synced_employee_id = employee_id
            
            # Sync with state manager
            success, message, is_blocked = self.state_manager.sync_from_server(person_name, api_response)
            
            self.is_user_blocked = is_blocked
            
            if is_blocked:
                # Store message for display after confirmation
                self.blocked_message = message
                # Don't show notification here - will show after face confirmation
                print(f"🚫 User blocked (will notify after confirmation): {message}")
                return False
            
            if success:
                print(f"✅ Status synced for {person_name}")
            
            return success
            
        except Exception as e:
            print(f"❌ Status sync error: {e}")
            self.is_user_blocked = False
            return True  # Allow on error (fallback to local)

    def _sync_all_users_on_startup(self):
        """Sync attendance status for all registered employees on startup"""
        if not self.api_client:
            return
        
        synced = 0
        failed = 0
        skipped = 0
        
        # Iterate through all registered faces
        for name in self.face_recognizer.known_faces.keys():
            employee_id = self.face_recognizer.get_employee_id(name)
            
            if not employee_id or employee_id == "none":
                skipped += 1
                continue
            
            try:
                timestamp = int(datetime.now().timestamp())
                api_response = self.api_client.get_attendance_status(employee_id, timestamp)
                
                if api_response:
                    success, _, _ = self.state_manager.sync_from_server(name, api_response)
                    if success:
                        synced += 1
                    else:
                        failed += 1
                else:
                    failed += 1
                    
            except Exception as e:
                print(f"  ⚠️ Failed to sync {name}: {e}")
                failed += 1
        
        print(f"✓ Startup sync complete: {synced} synced, {failed} failed, {skipped} skipped (no employee ID)")

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

    def _reset_face_confirmation(self):
        """Reset face confirmation state and return to live camera feed"""
        print("🔄 Resetting face confirmation")
        self.face_confirmed = False
        self.confirmed_person_name = None
        self.confirmed_person_similarity = 0.0
        self.confirmed_frame = None
        self.confirmation_start_time = None
        self.last_stable_person = None
        self.event_in_progress = False
        self.current_recognized_person = None
        
        # Reset blocking state for new detection
        self.is_user_blocked = False
        self.blocked_message = ""
        self.last_synced_employee_id = None  # Force fresh sync for next person
        
        # Clear temporal buffer for fresh recognition
        self.temporal_buffer.clear()
        
        # Cancel any pending timeout
        if self.no_face_timeout:
            self.no_face_timeout.stop()
            self.no_face_timeout = None
        
        # Show welcome screen after reset
        self.show_welcome_screen()

    def put_text_rgb(self, frame, text, x, y, color_rgb, scale=1.0, thickness=2):
        """Put text"""
        frame_bgr = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
        color_bgr = (color_rgb[2], color_rgb[1], color_rgb[0])
        cv2.putText(frame_bgr, text, (x, y), cv2.FONT_HERSHEY_SIMPLEX, scale, color_bgr, thickness)
        frame[:] = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)

    def show_feedback(self, message, is_success):
        """Show feedback with 3-second auto-fade using scaled UI"""
        color = "#00ff88" if is_success else "#ff4444"
        
        self.feedback_label.setStyleSheet(f"""
            color: {color}; 
            font-size: {pf(15)}px; 
            font-weight: bold; 
            padding: {ph(5)}px;
            background: transparent;
            border: none;
        """)

        self.feedback_label.setText(message)
        self.feedback_label.setVisible(True)

        if self.feedback_timer:
            self.feedback_timer.stop()

        self.feedback_timer = QTimer()
        self.feedback_timer.timeout.connect(lambda: self.feedback_label.setVisible(False))
        self.feedback_timer.setSingleShot(True)
        self.feedback_timer.start(3000)  # 3 seconds


    def process_frame(self):
        """Process frame with face confirmation and freeze mechanism"""
        if self.latest_frame is None or self.processing:
            return

        # ★★★ SKIP PROCESSING IF EVENT IN PROGRESS ★★★
        if self.event_in_progress:
            # Just display the frozen frame, don't process
            if self.confirmed_frame is not None:
                self.display_frame(self.confirmed_frame)
            return

        self.processing = True

        try:
            frame_rgb = self.latest_frame.copy()
            self.current_frame = frame_rgb

            GREEN_RGB = (0, 255, 0)
            RED_RGB = (255, 0, 0)
            YELLOW_RGB = (255, 255, 0)
            ORANGE_RGB = (255, 165, 0)
            BLACK_RGB = (0, 0, 0)
            CYAN_RGB = (0, 255, 255)

            # ★★★ IF FACE IS CONFIRMED, DISPLAY FROZEN FRAME ★★★
            if self.face_confirmed and self.confirmed_frame is not None:
                # Still check if face is present to detect when person leaves
                detected, recognized = self.face_recognizer.process_frame(frame_rgb, preprocess=True)
                has_face = bool(detected or recognized)
                
                if not has_face:
                    # Start timeout to reset confirmation if face disappears
                    if self.no_face_timeout is None:
                        self.no_face_timeout = QTimer()
                        self.no_face_timeout.setSingleShot(True)
                        self.no_face_timeout.timeout.connect(self._reset_face_confirmation)
                        self.no_face_timeout.start(3000)  # 3 seconds
                else:
                    # Face still present, cancel any timeout
                    if self.no_face_timeout:
                        self.no_face_timeout.stop()
                        self.no_face_timeout = None
                    
                    # Check if a DIFFERENT person appeared
                    if recognized:
                        current_person = recognized[0].get('name', 'Unknown')
                        if current_person != self.confirmed_person_name and current_person != 'Unknown':
                            # Different person detected - reset confirmation
                            print(f"👤 Different person detected: {current_person} (was: {self.confirmed_person_name})")
                            self._reset_face_confirmation()
                            self.processing = False
                            return
                
                # Display the frozen frame with confirmation overlay
                self.display_frame(self.confirmed_frame)
                self.processing = False
                return
            # ★★★ END FROZEN FRAME LOGIC ★★★

            display_frame = frame_rgb.copy()

            # ★★★ WELCOME SCREEN LOGIC ★★★
            if not self.registration_mode:
                # Check if any face is present
                detected, recognized = self.face_recognizer.process_frame(frame_rgb, preprocess=True)
                has_face = bool(detected or recognized)

                if has_face:
                    # Face detected - show camera view but NOT buttons yet (wait for confirmation)
                    if self.display_stack.currentIndex() == 0:
                        print("👤 Face detected - showing camera view (awaiting confirmation)")
                        self.display_stack.setCurrentIndex(1)
                        # ★★★ BUTTONS STAY HIDDEN until face is confirmed ★★★
                        self.button_frame.setVisible(False)
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
                    raw_name = person['name']
                    similarity = person['similarity']
                    is_confident = person['is_confident']

                    # ★★★ TEMPORAL BUFFER INTEGRATION ★★★
                    # Add raw recognition to buffer and get consensus
                    self.temporal_buffer.add_result(raw_name, similarity)
                    
                    # Get stable identity from buffer consensus
                    consensus_name, agreement, is_stable = self.temporal_buffer.get_consensus()
                    
                    # Use consensus name if available and stable, otherwise use raw
                    if consensus_name and is_stable:
                        name = consensus_name
                        # Recalculate is_confident based on consensus
                        is_confident = agreement >= config.TEMPORAL_AGREEMENT_THRESHOLD
                    else:
                        name = raw_name
                    
                    # Log flicker prevention (only if consensus overrides raw)
                    if consensus_name and consensus_name != raw_name and is_stable:
                        print(f"🔒 Anti-flicker: {raw_name} → {consensus_name} (agreement: {agreement:.0%})")
                    # ★★★ END TEMPORAL BUFFER ★★★

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

                        # ★★★ BACKGROUND SYNC - Run during detection, before confirmation ★★★
                        # This pre-fetches blocked status so we know immediately on confirmation
                        if self.api_client and not self.face_confirmed:
                            self._sync_status_for_person(name)

                        # ★★★ FACE CONFIRMATION LOGIC ★★★
                        current_time = time.time()
                        
                        if self.last_stable_person == name:
                            # Same person - check if confirmation delay reached
                            if self.confirmation_start_time is not None:
                                time_recognized = current_time - self.confirmation_start_time
                                
                                if time_recognized >= self.CONFIRMATION_DELAY and not self.face_confirmed:
                                    # CONFIRM THE FACE - Create frozen frame with name overlay
                                    print(f"✅ Face CONFIRMED: {name} ({similarity:.0%}) after {time_recognized:.1f}s")
                                    self.face_confirmed = True
                                    self.confirmed_person_name = name
                                    self.confirmed_person_similarity = similarity
                                    
                                    # Create frozen frame with prominent name display
                                    frozen = display_frame.copy()
                                    
                                    # Draw face box
                                    self.draw_box_rgb(frozen, x, y, x + w, y + h, CYAN_RGB, 6)
                                    
                                    # Draw confirmation banner at top
                                    banner_height = 120
                                    self.draw_filled_box_rgb(frozen, 0, 0, frozen.shape[1], banner_height, (0, 180, 120))
                                    
                                    # Draw prominent name on banner
                                    name_text = f" {name}"
                                    self.put_text_rgb(frozen, name_text, 30, 70, (255, 255, 255), 2.0, 5)
                                    
                                    # Draw similarity score
                                    score_text = f"Confirmed : {similarity:.0%}"
                                    self.put_text_rgb(frozen, score_text, 30, 105, (200, 255, 220), 0.9, 2)
                                    
                                    # Draw instruction at bottom
                                    instr_y = frozen.shape[0] - 40
                                    self.put_text_rgb(frozen, "Select an action below", frozen.shape[1]//2 - 180, instr_y, (255, 255, 255), 1.0, 2)
                                    
                                    self.confirmed_frame = frozen
                                    
                                    # ★★★ SHOW NOTIFICATION & BUTTONS ONLY AFTER CONFIRMATION ★★★
                                    state_display = self.state_manager.get_state_display(name)
                                    self.status_label.setText(f"✅ CONFIRMED: {name} | {state_display}")
                                    
                                    # Check if user is blocked (already synced in background)
                                    if self.is_user_blocked:
                                        # Show blocked notification NOW (after confirmation)
                                        self.notification_overlay.show_notification(
                                            "⚠️ Action Blocked", 
                                            self.blocked_message or "Action not allowed", 
                                            "warning", 5000
                                        )
                                        # Keep buttons hidden
                                        self.button_frame.setVisible(False)
                                        
                                        # ★★★ AUTO-RESET to welcome screen after notification ★★★
                                        # Wait for notification to display, then reset
                                        QTimer.singleShot(4000, self._reset_face_confirmation)
                                    else:
                                        # Not blocked - show buttons
                                        self.button_frame.setVisible(True)
                                        self.update_button_visibility(name)
                                    
                                    # Display frozen frame immediately
                                    self.display_frame(frozen)
                                    self.processing = False
                                    return
                            else:
                                self.confirmation_start_time = current_time
                        else:
                            # Different person - reset confirmation timer
                            self.last_stable_person = name
                            self.confirmation_start_time = current_time
                            self.face_confirmed = False
                            self.confirmed_person_name = None
                            self.confirmed_frame = None
                        # ★★★ END FACE CONFIRMATION LOGIC ★★★

                        verified = ""
                        if config.ENABLE_LIVENESS and self.face_recognizer.liveness_detector:
                            if self.face_recognizer.liveness_detector.is_verified_live:
                                verified = "✓"

                        if self.locked_person_for_action == name:
                            state_display = self.state_manager.get_state_display(name)
                            status_text = f"👤 {name} {verified} • {similarity:.0%} | {state_display}"
                        else:
                            # Show confirmation progress
                            if self.confirmation_start_time:
                                progress = min(1.0, (current_time - self.confirmation_start_time) / self.CONFIRMATION_DELAY)
                                status_text = f"👤 {name} {verified} • {similarity:.0%} | Confirming... {progress:.0%}"
                            else:
                                api_indicator = "📡" if config.API_ENABLED else ""
                                status_text = f"👤 {name} {verified} • {similarity:.0%} {api_indicator}"

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
                        
                        # ★★★ UNKNOWN PERSON MONITORING - Gated by ENABLE_MQTT_FEATURES ★★★
                        if getattr(config, 'ENABLE_MQTT_FEATURES', False):
                            current_time = time.time()
                            
                            if self.unknown_person_start_time is None:
                                # First detection of unknown person
                                self.unknown_person_start_time = current_time
                                self.unknown_person_last_frame = frame_rgb.copy()
                                self.unknown_person_last_bbox = (x, y, w, h)
                                self.unknown_person_embedding = None
                                self.unknown_person_id = None
                                self.update_button_visibility(None)
                                # Show button frame so "ADD NEW FACE" is accessible for unknown persons
                                self.button_frame.setVisible(True)

                                self.status_label.setText("⚠️ Unknown Person - Monitoring")
                                print(f"⚠️ Unknown person detected, timer started")
                            else:
                                # Unknown person still in frame
                                duration = current_time - self.unknown_person_start_time
                                self.unknown_person_last_frame = frame_rgb.copy()
                                self.unknown_person_last_bbox = (x, y, w, h)
                                
                                # ===== TIMER DISPLAY =====
                                timer_text = f"Unknown: {int(duration)}s / {int(config.UNKNOWN_PERSON_TIMEOUT)}s"
                                self.status_label.setText(f"⚠️ {timer_text}")
                                
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
                        else:
                            # MQTT Features disabled - just show status and "ADD NEW FACE" button
                            self.status_label.setText("⚠️ Unknown Person")
                            self.update_button_visibility(None)
                            self.button_frame.setVisible(True)



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
        """Start registration — guarded by admin password validation."""
        # Pause background face detection processing
        self.event_in_progress = True

        # ── Step 1: Admin password gate ──────────────────────────────────────
        dlg = AdminPasswordDialog(self)

        while True:
            if dlg.exec() != QDialog.Accepted:
                self.event_in_progress = False
                return  # User cancelled

            password = dlg.get_password().strip()
            if not password:
                dlg.show_error("Password cannot be empty")
                if dlg.exec() == QDialog.Rejected:
                    self.event_in_progress = False
                    return
                continue

            # Validate via API (or skip validation if API is disabled)
            if self.api_client:
                self.status_label.setText("🔑 Validating admin password...")
                QApplication.processEvents()
                ok, err_msg = self.api_client.validate_admin_password(password)
            else:
                # API disabled — allow locally without validation
                ok, err_msg = True, ""

            if ok:
                break  # Password accepted, proceed

            # Show error inline and loop for retry
            dlg.show_error(err_msg or "Invalid password")
            self.status_label.setText("❌ Invalid admin password")

        # Hide keyboard after admin password is accepted
        VKLineEdit._hide_keyboard()

        # ── Step 2: Collect name ─────────────────────────────────────────────
        name_dlg = TextInputDialog(self, title="Enter Person's Name",
                                   placeholder="Full name")
        if name_dlg.exec() != QDialog.Accepted:
            self.event_in_progress = False
            return
        name = name_dlg.get_text().strip()
        if not name:
            self.event_in_progress = False
            return

        # ── Step 3: Collect employee ID ───────────────────────────────────────
        emp_dlg = TextInputDialog(self, title="Enter Employee ID",
                                  placeholder="Employee ID")
        if emp_dlg.exec() != QDialog.Accepted:
            self.notification_overlay.show_notification(
                "Cancelled", "Employee ID is required for registration", "warning", 2000
            )
            self.event_in_progress = False
            return
        employee_id = emp_dlg.get_text().strip()
        if not employee_id:
            self.notification_overlay.show_notification(
                "Cancelled", "Employee ID is required for registration", "warning", 2000
            )
            self.event_in_progress = False
            return

        # ── Step 4: Begin registration ────────────────────────────────────────
        # Unpause face detection so we can capture
        self.event_in_progress = False

        # Force camera view during registration
        self.display_stack.setCurrentIndex(1)

        self.registration_mode = True
        self.registration_person_name = name.strip()
        self.registration_person_employee_id = employee_id.strip()
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

        self.status_label.setText("📸 Position and CAPTURE (10 samples required)")


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

            success = self.face_recognizer.add_faces(final_samples, self.registration_person_name, self.registration_person_employee_id)

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
        self.registration_person_employee_id = None  # Reset employee ID
        self.captured_faces = []
        self.current_registration_step = 0
        
        # Ensure keyboard is hidden
        VKLineEdit._hide_keyboard()

        self.capture_btn.setEnabled(True)

        self.title_label.setText(f"Employee Attendance Management System")
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
                # Get employee ID for this person (None if not set)
                employee_id = self.face_recognizer.get_employee_id(person)
                self.api_client.send_attendance_event(
                    name=person,
                    action=action,
                    timestamp=timestamp,
                    employee_id=employee_id
                )
            except Exception as e:
                print(f"⚠️ API send error: {e}")

        # Show API stats periodically
        if self.api_client and hasattr(self, 'adaptive_learning_count'):
            if self.adaptive_learning_count % 5 == 0:
                stats = self.api_client.get_stats()
                print(f"📊 API Stats: Sent={stats['total_sent']}, Failed={stats['total_failed']}, Queued={stats['queued']}")

    def log_action_local_only(self, action, person, timestamp):
        """Log action to file only (API already sent separately)"""
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

    def verify_and_log_action(self, action):
        """Verify and log with person locking and auto-fading success"""

        if not self.locked_person_for_action:
            # ★★★ CHANGED: Use auto-fading overlay instead of QMessageBox ★★★
            self.notification_overlay.show_notification("Error", "No person locked!", "error", 1000)
            return

        # ★★★ SET EVENT IN PROGRESS - Pause face processing during dialog ★★★
        self.event_in_progress = True

        dialog = SimpleConfirmationDialog(self, self.locked_person_for_action, action)

        if dialog.exec() == QDialog.Accepted:
            timestamp = datetime.now()
            
            # ★★★ VALIDATE WITH API FIRST ★★★
            if self.api_client:
                try:
                    employee_id = self.face_recognizer.get_employee_id(self.locked_person_for_action)
                    api_success, api_error = self.api_client.validate_and_send_event(
                        name=self.locked_person_for_action,
                        action=action,
                        timestamp=timestamp,
                        employee_id=employee_id
                    )
                    
                    if not api_success and api_error:
                        # API rejected the action - show error and reset
                        self.notification_overlay.show_notification("❌ Action Rejected", api_error, "error", 4000)
                        self.locked_person_for_action = None
                        self.locked_person_timestamp = None
                        self.event_in_progress = False
                        
                        # Auto-reset to welcome screen after notification
                        QTimer.singleShot(4000, self._reset_face_confirmation)
                        return
                except Exception as e:
                    print(f"⚠️ API validation error: {e}")
                    # Continue with local update if API check fails unexpectedly
            
            # ★★★ UPDATE LOCAL STATE (only if API succeeded or offline) ★★★
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
    
            # Log to file (API already sent above)
            self.log_action_local_only(action, self.locked_person_for_action, timestamp)
            timestamp_str = timestamp.strftime("%H:%M:%S")

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
            message = f"{action}\n{self.locked_person_for_action}\n{timestamp_str}\n{api_note}"
            self.notification_overlay.show_notification("Success", message, "success", 2000)
            if self.current_recognized_person:
                self.update_button_visibility(self.current_recognized_person)

            
            self.locked_person_for_action = None
            self.locked_person_timestamp = None
            
            # ★★★ RESET FACE CONFIRMATION AFTER SUCCESSFUL ACTION ★★★
            self._reset_face_confirmation()

        else:
            self.locked_person_for_action = None
            self.locked_person_timestamp = None
            
            # ★★★ CLEAR EVENT FLAG BUT KEEP CONFIRMATION ON CANCEL ★★★
            self.event_in_progress = False

    def update_button_visibility(self, person_name):
        if not person_name:
            for btn in self.all_action_buttons:
                btn.setVisible(False)
            self.add_face_btn.setVisible(True)
            self.is_user_blocked = False
            self._rearrange_button_grid()
            return
        
        # ★★★ SYNC STATUS FROM SERVER FIRST ★★★
        if not self._sync_status_for_person(person_name):
            # User is blocked - buttons hidden, grid needs refresh
            for btn in self.all_action_buttons:
                btn.setVisible(False)
            self._rearrange_button_grid()
            return
        
        # Use local state (now synced with server) for button visibility
        can_time_in, _ = self.state_manager.can_time_in(person_name)
        can_time_out, _ = self.state_manager.can_time_out(person_name)
        can_break_start, _ = self.state_manager.can_break_start(person_name)
        can_break_end, _ = self.state_manager.can_break_end(person_name)
        can_job_start, _ = self.state_manager.can_job_start(person_name)
        can_job_end, _ = self.state_manager.can_job_end(person_name)

        # Logic override: If person is currently ON A JOB, only show JOB END button
        if can_job_end:
            self.time_in_btn.setVisible(False)
            self.time_out_btn.setVisible(False)
            self.break_in_btn.setVisible(False)
            self.break_out_btn.setVisible(False)
            self.job_in_btn.setVisible(False)
            self.job_out_btn.setVisible(True)
        else:
            self.time_in_btn.setVisible(can_time_in)
            self.time_out_btn.setVisible(can_time_out)
            self.break_in_btn.setVisible(can_break_start)
            self.break_out_btn.setVisible(can_break_end)
            self.job_in_btn.setVisible(can_job_start)
            self.job_out_btn.setVisible(False)
            
        self.add_face_btn.setVisible(True)
        self._rearrange_button_grid()

    def _rearrange_button_grid(self):
        """Dynamically arrange visible buttons in a grid: max 2 per row."""
        # 1. Clear layout
        while self.button_layout.count():
            item = self.button_layout.takeAt(0)
            # Just remove, don't delete widgets
            if item.widget():
                item.widget().setParent(None)

        # 2. Get visible buttons
        visible_buttons = [btn for btn in self.all_action_buttons if btn.isVisible()]
        
        # 3. Add back to grid
        num_visible = len(visible_buttons)
        for i, btn in enumerate(visible_buttons):
            row = i // 2
            col = i % 2
            
            # If it's the last button and it's starting a new row, make it full width
            if i == num_visible - 1 and col == 0:
                self.button_layout.addWidget(btn, row, 0, 1, 2)
            else:
                self.button_layout.addWidget(btn, row, col)
            
            # Ensure it's parented to the frame so it shows up
            btn.setParent(self.button_frame)
            btn.setVisible(True)

    
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

        if self.process_timer:
            self.process_timer.stop()

        if hasattr(self, 'db_reload_timer') and self.db_reload_timer:
            self.db_reload_timer.stop()

        if hasattr(self, 'status_sync_timer') and self.status_sync_timer:
            self.status_sync_timer.stop()

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

        # ★★★ STOP MQTT FACE REGISTRATION HANDLER ★★★
        if hasattr(self, 'mqtt_face_handler') and self.mqtt_face_handler:
            print("Stopping MQTT Face Registration handler...")
            self.mqtt_face_handler.stop()

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

        # ★★★ STOP MQTT FACE REGISTRATION HANDLER ★★★
        if hasattr(self, 'mqtt_face_handler') and self.mqtt_face_handler:
            self.mqtt_face_handler.stop()

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
