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
                               QSizePolicy, QLineEdit, QScrollArea, QScroller)
from PySide6.QtCore import Qt, QThread, Signal, Slot, QTimer, QPropertyAnimation, QEasingCurve
from PySide6.QtGui import QImage, QPixmap, QFont, QPainter, QPen, QColor
import threading
from picamera2 import Picamera2
import libcamera
import numpy as np
import time
from datetime import datetime
import cv2

from face_recognizer import FaceRecognizer
from modules.api_client import AttendanceAPIClient, OFFLINE_MESSAGE
from modules.attendance_state_manager import AttendanceStateManager
from modules.mqtt_incident_reporter import MQTTIncidentReporter
from modules.unknown_person_tracker import UnknownPersonTracker
from modules.welcome_screen import WelcomeScreen
from modules.mqtt_face_registration import MQTTFaceRegistrationHandler
from modules.temporal_buffer import TemporalRecognitionBuffer
from modules.admin_control import AdminControlPage
from modules.registration_gui import RegistrationPage
from modules.virtual_keyboard import VKLineEdit, VirtualKeyboard

import config

THEME = {
    "background_light": "#F0F4F8",
    "background_medium": "#E8EDF2",
    "accent_primary": "#1E3A5F",
    "accent_secondary": "#4A90D9",
    "text_primary": "#1E3A5F",
    "text_secondary": "#5A7A9A",
    "success": "#2ECC71",
    "warning": "#F39C12",
    "error": "#E74C3C",
}

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


# VKLineEdit and VirtualKeyboard are imported from modules.virtual_keyboard




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


class RecognitionWorker(QThread):
    """
    Runs face detection/recognition on a dedicated thread so the GUI thread
    never blocks on InsightFace inference. Reads the latest camera frame from
    the GUI, throttles to a target FPS, optionally downscales the frame, runs a
    single inference pass, and emits the results back to the GUI.

    onnxruntime / OpenCV release the GIL during native work, so this genuinely
    offloads CPU from the GUI event loop and keeps the UI responsive.
    """
    result_ready = Signal(dict)

    def __init__(self, gui):
        super().__init__()
        self.gui = gui
        self._running = False
        target_fps = max(getattr(config, 'RECOGNITION_TARGET_FPS', 8), 1)
        self._interval = 1.0 / target_fps
        self._downscale = float(getattr(config, 'RECOGNITION_DOWNSCALE', 1.0) or 1.0)
        self._preprocess = bool(getattr(config, 'RECOGNITION_PREPROCESS', True))

    @staticmethod
    def _scale_bbox(bbox, factor):
        x, y, w, h = bbox
        return (int(x * factor), int(y * factor), int(w * factor), int(h * factor))

    def run(self):
        self._running = True
        print("✓ Recognition worker thread started")
        while self._running:
            start = time.time()
            gui = self.gui

            # Skip while an action is in progress (the action worker may touch the
            # recognizer) or while the admin page (index 1) is showing (camera paused).
            frame = gui.latest_frame
            if (frame is None or gui.event_in_progress or
                    gui.pages_stack.currentIndex() == 1):
                time.sleep(self._interval)
                continue

            try:
                frame_rgb = frame.copy()
                registration = gui.registration_mode

                proc = frame_rgb
                scale = self._downscale
                if scale and scale != 1.0:
                    proc = cv2.resize(frame_rgb, None, fx=scale, fy=scale,
                                      interpolation=cv2.INTER_AREA)

                if registration:
                    processed = gui.face_recognizer.preprocess_image(proc)
                    detected = gui.face_recognizer.detect_faces(processed)
                    recognized = []
                else:
                    detected, recognized = gui.face_recognizer.process_frame(
                        proc, preprocess=self._preprocess)

                # Map bboxes back to full-resolution frame coordinates
                if scale and scale != 1.0:
                    inv = 1.0 / scale
                    for f in detected:
                        f['bbox'] = self._scale_bbox(f['bbox'], inv)
                    for f in recognized:
                        f['bbox'] = self._scale_bbox(f['bbox'], inv)

                self.result_ready.emit({
                    'detected': detected,
                    'recognized': recognized,
                    'registration': registration,
                    'frame': frame_rgb,
                })

            except Exception as e:
                print(f"Recognition worker error: {e}")
                import traceback
                traceback.print_exc()

            elapsed = time.time() - start
            if elapsed < self._interval:
                time.sleep(self._interval - elapsed)

    def stop(self):
        self._running = False
        self.wait(2000)


class ActionWorker(QThread):
    """
    Runs the heavy part of an attendance action (API validation, state update,
    local logging and adaptive learning) off the GUI thread so the button tap
    never freezes the interface. Emits the outcome back to the GUI.
    """
    done = Signal(bool, str, bool)  # success, message, should_reset

    def __init__(self, gui, action, person, frame, timestamp):
        super().__init__()
        self.gui = gui
        self.action = action
        self.person = person
        self.frame = frame
        self.timestamp = timestamp

    def run(self):
        gui = self.gui
        action = self.action
        person = self.person
        timestamp = self.timestamp
        try:
            # 1) Validate + send to API (server is source of truth)
            if gui.api_client:
                try:
                    employee_id = gui.face_recognizer.get_employee_id(person)
                    api_success, api_error = gui.api_client.validate_and_send_event(
                        name=person,
                        action=action,
                        timestamp=timestamp,
                        employee_id=employee_id
                    )
                    if not api_success:
                        self.done.emit(False, api_error or OFFLINE_MESSAGE, True)
                        return
                except Exception as e:
                    print(f"⚠️ API validation error: {e}")
                    self.done.emit(False, OFFLINE_MESSAGE, False)
                    return

            # 2) Update local state (only after API succeeded)
            action_map = {
                "TIME IN": gui.state_manager.time_in,
                "TIME OUT": gui.state_manager.time_out,
                "BREAK START": gui.state_manager.break_start,
                "BREAK END": gui.state_manager.break_end,
                "JOB START": gui.state_manager.job_start,
                "JOB END": gui.state_manager.job_end,
            }
            if action in action_map:
                success, state_msg = action_map[action](person)
                if not success:
                    self.done.emit(False, state_msg, False)
                    return

            # 3) Local file log
            gui.log_action_local_only(action, person, timestamp)

            # 4) Adaptive learning (best-effort)
            if self.frame is not None and gui.current_recognized_person == person:
                try:
                    faces = gui.face_recognizer.detect_faces(self.frame)
                    if faces:
                        face = max(faces, key=lambda f: f['bbox'][2] * f['bbox'][3])
                        face_img = gui.face_recognizer.extract_face_region(
                            self.frame, face, align=False)
                        if face_img is not None:
                            is_valid, msg, quality = gui.face_recognizer.validate_face_sample(
                                face_img, check_liveness=False)
                            if is_valid and quality >= 0.75:
                                embedding = gui.face_recognizer.extract_embedding(face_img)
                                if embedding is not None:
                                    added = gui.face_recognizer.add_embedding_to_existing_person(
                                        person, embedding, max_embeddings=50)
                                    if added:
                                        gui.adaptive_learning_count += 1
                except Exception as e:
                    print(f"Adaptive learning error: {e}")

            timestamp_str = timestamp.strftime("%H:%M:%S")
            api_note = "Recorded" if gui.api_client else "💾 Local"
            message = f"{action}\n{person}\n{timestamp_str}\n{api_note}"
            self.done.emit(True, message, True)

        except Exception as e:
            print(f"Action worker error: {e}")
            self.done.emit(False, OFFLINE_MESSAGE, False)


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
        self.password_input.setPlaceholderText("Enter admin passcode")
        self.password_input.setEchoMode(QLineEdit.Password)
        self.password_input.setProperty("keyboard_mode", "numeric")
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
                use_face_alignment=True,
                num_threads=getattr(config, 'ONNX_NUM_THREADS', 0)
            )

            if config.ENABLE_LIVENESS and self.face_recognizer.liveness_detector:
                print("✓ Blink-only liveness enabled (ultra-fast)")

            # ★★★ INITIALIZE API CLIENT ★★★
            if config.API_ENABLED:
                try:
                    self.api_client = AttendanceAPIClient(
                        server_ip=getattr(config, 'API_SERVER_IP', ''),
                        server_port=getattr(config, 'API_SERVER_PORT', 3008),
                        endpoint=config.API_ENDPOINT,
                        timeout=config.API_TIMEOUT,
                        health_endpoint=config.API_HEALTH_ENDPOINT,
                        health_check_interval=config.API_HEALTH_CHECK_INTERVAL,
                        storage_file=config.API_STORAGE_FILE
                    )
                    server_display = getattr(config, 'API_SERVER_DOMAIN', '') if getattr(config, 'SERVER_AS_DOMAIN', False) else f"{getattr(config, 'API_SERVER_IP', '')}:{getattr(config, 'API_SERVER_PORT', 3008)}"
                    print(f"✓ API Client enabled: {server_display}")
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

        self.feedback_timer = None

        # Welcome screen state
        self.no_face_timeout = None

        # Server connectivity (attendance gated when API enabled but server offline)
        self.server_available = True
        self._offline_notified = False

        # ★★★ FACE CONFIRMATION STATE (no frozen frame - live feed stays on) ★★★
        self.face_confirmed = False              # Is the current face confirmed?
        self.confirmed_person_name = None        # Name of confirmed person
        self.confirmed_person_similarity = 0.0   # Similarity score of confirmed person
        self.confirmed_frame = None              # Deprecated (kept for compatibility)
        self.confirmation_start_time = None      # When stable recognition started
        self.CONFIRMATION_DELAY = 1.0            # Seconds of stable recognition before confirming
        self.event_in_progress = False           # Is user performing an event action?
        self.last_stable_person = None           # Track person for stable recognition

        # ★★★ LIVE OVERLAY STATE (drawn cheaply over the live feed by display timer) ★★★
        self.overlay_state = {}                  # {'box','color','label','sublabel','banner'}
        self._overlay_lock = threading.Lock()    # Guards overlay_state across threads

        # Background status-sync coordination (non-blocking server fetch)
        self._status_sync_thread = None
        self._status_sync_inflight = set()
        self._status_sync_lock = threading.Lock()
        self._action_worker = None

        # ★★★ TEMPORAL RECOGNITION BUFFER - Anti-flicker ★★★
        self.temporal_buffer = TemporalRecognitionBuffer(
            buffer_size=config.TEMPORAL_BUFFER_SIZE,
            agreement_threshold=config.TEMPORAL_AGREEMENT_THRESHOLD
        )
        self.temporal_buffer.set_identity_lock_time(config.IDENTITY_LOCK_TIME)
        print(f"✓ Temporal Buffer: {config.TEMPORAL_BUFFER_SIZE} frames, {config.TEMPORAL_AGREEMENT_THRESHOLD*100:.0f}% agreement")

        # ★★★ CREATE NOTIFICATION OVERLAY ★★★
        self.notification_overlay = NotificationOverlay(self)

        self.init_ui()

        # Start camera
        QTimer.singleShot(200, self.init_camera)

        # ★★★ RECOGNITION WORKER - runs InsightFace off the GUI thread ★★★
        self.recognition_worker = RecognitionWorker(self)
        self.recognition_worker.result_ready.connect(
            self.on_recognition_result, Qt.QueuedConnection)
        self.recognition_worker.start()

        # ★★★ DISPLAY TIMER - lag-free live preview, independent of recognition ★★★
        display_fps = max(getattr(config, 'DISPLAY_FPS', 25), 1)
        self.display_timer = QTimer()
        self.display_timer.timeout.connect(self.update_display)
        self.display_timer.start(1000 // display_fps)

        # ★★★ DATABASE RELOAD TIMER - Check for updates every 30 seconds ★★★
        self.db_reload_timer = QTimer()
        self.db_reload_timer.timeout.connect(self._check_db_update)
        self.db_reload_timer.start(30000)  # 30 seconds

        # ★★★ STATUS SYNC TIMER - Refresh server status every 60 seconds ★★★
        self.status_sync_timer = QTimer()
        self.status_sync_timer.timeout.connect(self._sync_current_user_status)
        self.status_sync_timer.start(60000)  # 60 seconds

        if self.api_client:
            self.server_available = self.api_client.is_server_online()
            self.health_poll_timer = QTimer()
            self.health_poll_timer.timeout.connect(self._poll_server_health)
            self.health_poll_timer.start(10000)
            QTimer.singleShot(0, lambda: self._update_server_connectivity_state(self.server_available))


    def _poll_server_health(self):
        """Poll API client server status and react to connectivity changes."""
        if not self.api_client:
            return
        online = self.api_client.is_server_online()
        if online != self.server_available:
            self._update_server_connectivity_state(online)

    def _update_server_connectivity_state(self, online: bool):
        """Handle server online/offline transitions for attendance UI."""
        was_online = self.server_available
        self.server_available = online

        if online:
            if hasattr(self, 'welcome_widget'):
                self.welcome_widget.set_offline_mode(False)
            self.status_label.setText("Ready - Position face in front of camera")
            if not was_online:
                self.notification_overlay.show_notification(
                    "Success", "Server connected", "success", 2000
                )
            self._offline_notified = False
        else:
            if self.face_confirmed or self.display_stack.currentIndex() != 0:
                self._reset_face_confirmation()
            else:
                self.show_welcome_screen()
            if hasattr(self, 'welcome_widget'):
                self.welcome_widget.set_offline_mode(True, OFFLINE_MESSAGE)
            self.status_label.setText("⚠️ Network unavailable — please use mobile application")
            if not self._offline_notified:
                self.notification_overlay.show_notification(
                    "Error", OFFLINE_MESSAGE, "error", 4000
                )
                self._offline_notified = True

    def _guard_server_online(self) -> bool:
        """Return False and notify if attendance actions are blocked due to offline server."""
        if self.api_client and not self.api_client.is_server_online():
            self.notification_overlay.show_notification("Error", OFFLINE_MESSAGE, "error", 3000)
            return False
        return True

    def init_ui(self):
        """Initialize UI"""
        liveness_status = "🛡️ Blink Detection" if config.ENABLE_LIVENESS else "⚠️ Liveness Disabled"
        server_display = getattr(config, 'API_SERVER_DOMAIN', '') if getattr(config, 'SERVER_AS_DOMAIN', False) else getattr(config, 'API_SERVER_IP', '')
        api_status = f"📡 API: {server_display}" if config.API_ENABLED else "○ API Disabled"

        self.setWindowTitle(f"Employee Attendance System - {liveness_status} | {api_status}")

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        self.main_layout = QVBoxLayout(central_widget)
        self.main_layout.setContentsMargins(10, 10, 10, 10)
        self.main_layout.setSpacing(5)

        top_layout = QHBoxLayout()
        top_layout.setContentsMargins(0, 0, 0, 0)
        
        self.title_label = QLabel("Employee Attendance Management System")
        self.title_label.setObjectName("title")
        self.title_label.setAlignment(Qt.AlignCenter)
        self.title_label.setWordWrap(True)
        self.title_label.setMinimumWidth(10)
        
        self.admin_icon_btn = QPushButton("⚙️")
        self.admin_icon_btn.setObjectName("adminIcon")
        self.admin_icon_btn.clicked.connect(self.show_admin_page)
        self.admin_icon_btn.setCursor(Qt.PointingHandCursor)
        self.admin_icon_btn.setFixedSize(40, 40)
        
        spacer = QWidget()
        spacer.setFixedWidth(40)
        
        top_layout.addWidget(spacer)
        top_layout.addWidget(self.title_label, stretch=1)
        top_layout.addWidget(self.admin_icon_btn)
        
        self.main_layout.addLayout(top_layout)

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
        
        # Removed admin_button_container since it is moved to top_layout
        # Create pages stack for camera and admin pages
        self.pages_stack = QStackedWidget()
        
        # Page 0: Camera page
        self.pages_stack.addWidget(self.camera_page_widget)
        
        # Page 1: Admin control page
        self.admin_page = AdminControlPage(self.face_recognizer)
        self.admin_page.home_requested.connect(self.show_camera_page)
        self.admin_page.add_new_face_requested.connect(self.start_registration_from_admin)
        self.pages_stack.addWidget(self.admin_page)
        
        # Page 2: Registration page [NEW COMPONENT]
        self.registration_page = RegistrationPage(self.face_recognizer, self.notification_overlay)
        self.registration_page.registration_completed.connect(self.on_registration_finished)
        self.registration_page.registration_cancelled.connect(self.on_registration_finished)
        self.pages_stack.addWidget(self.registration_page)
        
        # Start with camera page
        self.pages_stack.setCurrentIndex(0)
        
        self.main_layout.addWidget(self.pages_stack, stretch=1)


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

        # Store all buttons in a list for easy management
        self.all_action_buttons = [
            self.time_in_btn, self.time_out_btn,
            self.break_in_btn, self.break_out_btn,
            self.job_in_btn, self.job_out_btn
        ]

        self.button_scroll = QScrollArea()
        self.button_scroll.setObjectName("buttonScroll")
        self.button_scroll.setWidgetResizable(True)
        self.button_scroll.setWidget(self.button_frame)
        self.button_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.button_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.button_scroll.setMinimumHeight(ph(220))
        self.button_scroll.setStyleSheet("QScrollArea { border: none; background: transparent; } QScrollArea > QWidget > QWidget { background: transparent; }")
        
        QScroller.grabGesture(self.button_scroll.viewport(), QScroller.LeftMouseButtonGesture)
        self.main_layout.addWidget(self.button_scroll)


        # Initially hide buttons
        self.button_scroll.setVisible(False)
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
            QMainWindow {{ background-color: {THEME['background_light']}; }}
            QLabel#title {{ color: {THEME['accent_primary']}; font-size: {_pf(16)}px; font-weight: bold; padding: {_ph(5)}px; }}
            QLabel#status {{ color: {THEME['text_secondary']}; font-size: {_pf(13)}px; padding: {_ph(3)}px; }}
            QLabel#instruction {{ color: {THEME['accent_secondary']}; font-size: {_pf(15)}px; font-weight: bold; padding: {_ph(5)}px; }}
            QLabel#feedback {{ color: {THEME['text_primary']}; font-size: {_pf(15)}px; font-weight: bold; padding: {_ph(5)}px; }}
            QLabel#camera {{ background-color: #000000; border: 3px solid {THEME['accent_secondary']}; border-radius: {_pw(10)}px; }}
            QPushButton {{
                background-color: #ffffff; color: {THEME['text_primary']}; border: 2px solid {THEME['background_medium']};
                border-radius: {_pw(8)}px; font-size: {_pf(14)}px; font-weight: bold; padding: {_ph(8)}px; min-height: {_ph(40)}px;
            }}
            QPushButton:hover {{ background-color: {THEME['background_medium']}; border-color: {THEME['accent_secondary']}; }}
            QPushButton:pressed {{ background-color: #d0d8e0; }}
            QPushButton#timeIn {{ border-color: {THEME['success']}; }}
            QPushButton#timeOut {{ border-color: {THEME['error']}; }}
            QPushButton#breakIn {{ border-color: {THEME['warning']}; }}
            QPushButton#breakOut {{ border-color: {THEME['warning']}; }}
            QPushButton#jobIn {{ border-color: {THEME['accent_secondary']}; }}
            QPushButton#jobOut {{ border-color: {THEME['accent_primary']}; }}
            QPushButton#addFace {{ border-color: {THEME['success']}; }}
            QPushButton#capture {{ background-color: {THEME['accent_secondary']}; color: white; border-color: {THEME['accent_secondary']}; font-size: {_pf(18)}px; }}
            QPushButton#cancelReg {{ background-color: {THEME['error']}; color: white; border-color: {THEME['error']}; font-size: {_pf(18)}px; }}
            QPushButton#adminIcon {{ background-color: {THEME['background_medium']}; border: none; font-size: {_pf(16)}px; border-radius: {_pw(20)}px; }}
            QPushButton#adminIcon:hover {{ background-color: #d0d8e0; }}
            QFrame#buttonContainer {{ background-color: transparent; border-top: 2px solid {THEME['background_medium']}; padding: {_ph(10)}px; }}
            QProgressBar {{
                border: 2px solid {THEME['accent_secondary']}; border-radius: {_pw(5)}px; text-align: center;
                color: {THEME['text_primary']}; font-weight: bold; min-height: {_ph(30)}px; font-size: {_pf(16)}px;
            }}
            QProgressBar::chunk {{ background-color: {THEME['accent_secondary']}; }}
            QScrollArea#buttonScroll {{ border: none; background: transparent; }}
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
        """Show the admin control page after password validation"""
        # Show password dialog
        dlg = AdminPasswordDialog(self)

        while True:
            if dlg.exec() != QDialog.Accepted:
                return  # User cancelled

            password = dlg.get_password().strip()
            if not password:
                dlg.show_error("Password cannot be empty")
                if dlg.exec() == QDialog.Rejected:
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

        # Hide keyboard after password is accepted
        VKLineEdit._hide_keyboard()
        
        # Hide action buttons
        self.button_scroll.setVisible(False)
        
        # Password validated, pause camera and show admin page
        if self.camera_thread and self.camera_thread.isRunning():
            self.camera_thread.stop()
            self.camera_thread.wait()
        if self.display_timer.isActive():
            self.display_timer.stop()
            
        self.pages_stack.setCurrentIndex(1)

    def show_camera_page(self):
        """Show the camera page and resume detection"""
        self.pages_stack.setCurrentIndex(0)
        
        # Resume camera and processing
        if not self.camera_thread or not self.camera_thread.isRunning():
            self.init_camera()
        if not self.display_timer.isActive():
            self.display_timer.start(1000 // max(getattr(config, 'DISPLAY_FPS', 25), 1))

    def start_registration_from_admin(self):
        """Start registration when triggered from admin page"""
        self.start_registration()

    @Slot()
    def on_registration_finished(self):
        """Handle registration completion or cancellation"""
        self.registration_mode = False
        self.event_in_progress = False
        
        # Restore main UI labels
        self.title_label.setVisible(True)
        self.status_label.setVisible(True)
        self.instruction_label.setVisible(False)
        self.feedback_label.setVisible(False)
        
        # Pause camera and return to admin page
        if self.camera_thread and self.camera_thread.isRunning():
            self.camera_thread.stop()
            self.camera_thread.wait()
        if self.display_timer.isActive():
            self.display_timer.stop()
            
        self.pages_stack.setCurrentIndex(1)
        # Reset liveness and state
        if self.face_recognizer.liveness_detector:
            self.face_recognizer.liveness_detector.reset()
        self.current_recognized_person = None
        self.last_recognized_person = None
        self.status_label.setText("✅ Ready")

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
            self._request_status_sync(self.current_recognized_person)

    def _request_status_sync(self, person_name: str):
        """
        Kick off a NON-BLOCKING server status fetch on a background thread.
        Results update the cached self.is_user_blocked / blocked_message so the
        GUI thread never blocks on the network. De-duplicates concurrent syncs
        for the same person.
        """
        if not self.api_client or not person_name:
            return
        with self._status_sync_lock:
            if person_name in self._status_sync_inflight:
                return
            self._status_sync_inflight.add(person_name)

        def _worker():
            try:
                self._sync_status_for_person(person_name)
            finally:
                with self._status_sync_lock:
                    self._status_sync_inflight.discard(person_name)

        threading.Thread(target=_worker, daemon=True).start()

    def _sync_status_for_person(self, person_name: str) -> bool:
        """
        Fetch and sync attendance status from server for a person with up to 3
        retries. Safe to call from a background thread (only touches plain
        attributes / network / state manager - no Qt widget calls).
        """
        if not self.api_client:
            return True  # No API client — local-only mode
        
        if not self.api_client.is_server_online():
            return False
        
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
        
        max_retries = 3
        for attempt in range(max_retries):
            try:
                # Fetch status from server
                timestamp = int(datetime.now().timestamp())
                api_response = self.api_client.get_attendance_status(employee_id, timestamp)
                
                if api_response is None:
                    return False
                
                # Update tracking
                self.last_status_sync_time = current_time
                self.last_synced_employee_id = employee_id
                
                # Sync with state manager
                success, message, is_blocked = self.state_manager.sync_from_server(person_name, api_response)
                
                self.is_user_blocked = is_blocked
                
                if is_blocked:
                    self.blocked_message = message
                    print(f"🚫 User blocked: {message}")
                    return False
                
                if success:
                    print(f"✅ Status synced for {person_name}")
                
                return success
                
            except Exception as e:
                print(f"❌ Attempt {attempt + 1} failed: {e}")
                if attempt < max_retries - 1:
                    time.sleep(0.5) # Short wait before retry
                    continue
                else:
                    print(f"❌ All {max_retries} attempts failed.")
                    self.is_user_blocked = False
                    return False
        
        return False

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
        self.button_scroll.setVisible(False)  # Hide buttons
        self.no_face_timeout = None
        # Resume animation
        if hasattr(self, 'welcome_widget'):
            self.welcome_widget.start_animation()
            if self.api_client and not self.api_client.is_server_online():
                self.welcome_widget.set_offline_mode(True, OFFLINE_MESSAGE)


    def _frame_to_pixmap(self, frame_rgb):
        """Convert a camera frame to a QPixmap (preserves existing color handling)."""
        frame_bgr = frame_rgb[:, :, ::-1].copy()
        height, width, _ = frame_bgr.shape
        q_image = QImage(frame_bgr.data, width, height, 3 * width, QImage.Format_RGB888)
        return QPixmap.fromImage(q_image)

    def display_frame(self, frame_rgb, overlay=None):
        """
        Paint a frame to the camera label, drawing any overlay cheaply with
        QPainter (no full-frame numpy/cvtColor passes in the hot path).
        """
        try:
            pixmap = self._frame_to_pixmap(frame_rgb)

            if overlay:
                painter = QPainter(pixmap)
                try:
                    box = overlay.get('box')
                    color = overlay.get('color', (0, 255, 0))
                    qcolor = QColor(color[0], color[1], color[2])

                    if box:
                        x, y, w, h = box
                        pen = QPen(qcolor)
                        pen.setWidth(4)
                        painter.setPen(pen)
                        painter.drawRect(int(x), int(y), int(w), int(h))

                        label = overlay.get('label')
                        if label:
                            font = painter.font()
                            font.setPointSize(20)
                            font.setBold(True)
                            painter.setFont(font)
                            ty = max(28, int(y) - 12)
                            painter.drawText(int(x) + 6, ty, label)

                        sublabel = overlay.get('sublabel')
                        if sublabel:
                            font = painter.font()
                            font.setPointSize(13)
                            font.setBold(False)
                            painter.setFont(font)
                            painter.drawText(int(x) + 6, int(y + h) + 24, sublabel)

                    banner = overlay.get('banner')
                    if banner:
                        bh = 90
                        painter.fillRect(0, 0, pixmap.width(), bh, QColor(0, 180, 120))
                        painter.setPen(QColor(255, 255, 255))
                        font = painter.font()
                        font.setPointSize(26)
                        font.setBold(True)
                        painter.setFont(font)
                        painter.drawText(24, 58, banner)
                finally:
                    painter.end()

            scaled_pixmap = pixmap.scaled(
                self.camera_label.size(),
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation
            )
            self.camera_label.setPixmap(scaled_pixmap)
        except Exception as e:
            print(f"Display error: {e}")

    def _set_overlay(self, overlay):
        """Thread-safe update of the overlay state drawn over the live feed."""
        with self._overlay_lock:
            self.overlay_state = overlay or {}

    def _get_overlay(self):
        with self._overlay_lock:
            return dict(self.overlay_state)

    def update_display(self):
        """
        Display-timer callback: paint the latest live frame plus the current
        overlay. Runs at DISPLAY_FPS, fully decoupled from recognition so the
        preview stays smooth even when inference is slow.
        """
        # Registration page renders its own camera feed
        if self.registration_mode:
            return
        # Only paint when the live camera view is active
        if self.pages_stack.currentIndex() != 0:
            return
        if self.display_stack.currentIndex() != 1:
            return
        frame = self.latest_frame
        if frame is None:
            return
        self.display_frame(frame, self._get_overlay())

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

        # Clear the live overlay
        self._set_overlay({})
        
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


    @Slot(dict)
    def on_recognition_result(self, result):
        """
        Handle one recognition result emitted by the RecognitionWorker.
        Runs the attendance state machine on the GUI thread (cheap), but never
        performs inference here. Display is handled separately by the display
        timer using the overlay state set below.
        """
        try:
            detected = result.get('detected') or []
            recognized = result.get('recognized') or []
            registration = result.get('registration', False)
            frame_rgb = result.get('frame')
            if frame_rgb is None:
                return

            self.current_frame = frame_rgb

            # Drop stale results that arrive while an action is being processed
            if self.event_in_progress:
                return

            GREEN_RGB = (0, 255, 0)
            RED_RGB = (255, 0, 0)
            YELLOW_RGB = (255, 255, 0)
            CYAN_RGB = (0, 255, 255)

            # ── REGISTRATION MODE ──
            if registration:
                self._handle_registration_result(detected, frame_rgb)
                return

            # Block attendance flow when server is offline
            if self.api_client and not self.api_client.is_server_online():
                if self.server_available:
                    self._update_server_connectivity_state(False)
                elif self.display_stack.currentIndex() != 0:
                    self.show_welcome_screen()
                self._set_overlay({})
                return

            has_face = bool(detected or recognized)

            # ── CONFIRMED STATE: keep the LIVE feed + banner, just monitor presence ──
            if self.face_confirmed:
                if not has_face:
                    if self.no_face_timeout is None:
                        self.no_face_timeout = QTimer()
                        self.no_face_timeout.setSingleShot(True)
                        self.no_face_timeout.timeout.connect(self._reset_face_confirmation)
                        self.no_face_timeout.start(3000)  # 3 seconds
                else:
                    if self.no_face_timeout:
                        self.no_face_timeout.stop()
                        self.no_face_timeout = None

                    # Different person appeared -> reset
                    if recognized:
                        current_person = recognized[0].get('name', 'Unknown')
                        if current_person != self.confirmed_person_name and current_person != 'Unknown':
                            print(f"👤 Different person detected: {current_person} (was: {self.confirmed_person_name})")
                            self._reset_face_confirmation()
                            return

                # Keep the confirmation banner over the live feed
                box = None
                if recognized:
                    box = recognized[0].get('bbox')
                elif detected:
                    box = detected[0].get('bbox')
                self._set_overlay({
                    'box': box,
                    'color': CYAN_RGB,
                    'banner': f"{self.confirmed_person_name}",
                })
                return

            # ── WELCOME <-> CAMERA TRANSITIONS ──
            if has_face:
                if self.display_stack.currentIndex() == 0:
                    print("👤 Face detected - showing camera view (awaiting confirmation)")
                    self.display_stack.setCurrentIndex(1)
                    self.button_scroll.setVisible(False)
                    if hasattr(self, 'welcome_widget'):
                        self.welcome_widget.stop_animation()
                if self.no_face_timeout:
                    self.no_face_timeout.stop()
                    self.no_face_timeout = None
            else:
                if self.display_stack.currentIndex() == 1:
                    if self.no_face_timeout is None:
                        self.no_face_timeout = QTimer()
                        self.no_face_timeout.setSingleShot(True)
                        self.no_face_timeout.timeout.connect(self.show_welcome_screen)
                        self.no_face_timeout.start(3000)  # 3 seconds

            # ── RECOGNITION ──
            if recognized:
                person = recognized[0]
                x, y, w, h = person['bbox']
                raw_name = person['name']
                similarity = person['similarity']
                is_confident = person['is_confident']

                # Temporal anti-flicker consensus
                self.temporal_buffer.add_result(raw_name, similarity)
                consensus_name, agreement, is_stable = self.temporal_buffer.get_consensus()
                if consensus_name and is_stable:
                    name = consensus_name
                    is_confident = agreement >= config.TEMPORAL_AGREEMENT_THRESHOLD
                else:
                    name = raw_name
                if consensus_name and consensus_name != raw_name and is_stable:
                    print(f"🔒 Anti-flicker: {raw_name} → {consensus_name} (agreement: {agreement:.0%})")

                # Smart liveness
                liveness_ok = True
                if is_confident and config.ENABLE_LIVENESS:
                    current_time = time.time()
                    if self.last_recognized_person != name:
                        if self.person_last_seen_time is not None:
                            time_elapsed = current_time - self.person_last_seen_time
                            if time_elapsed >= self.RESET_TIMEOUT:
                                if self.face_recognizer.liveness_detector:
                                    self.face_recognizer.liveness_detector.reset()
                                    print(f"🔄 Liveness RESET after {time_elapsed:.1f}s away")
                        self.last_recognized_person = name
                        self.person_last_seen_time = current_time
                    else:
                        self.person_last_seen_time = current_time

                    if self.face_recognizer.liveness_detector and not self.face_recognizer.liveness_detector.is_verified_live:
                        face_for_liveness = self.face_recognizer.extract_face_region(
                            frame_rgb, person, align=False)
                        if face_for_liveness is not None:
                            face_small = cv2.resize(face_for_liveness, (64, 64))
                            liveness_ok, _, _ = self.face_recognizer.liveness_detector.check_liveness(face_small)
                    else:
                        liveness_ok = True

                if is_confident and liveness_ok:
                    # Known person -> reset unknown timer
                    if self.unknown_person_start_time is not None:
                        print(f"✅ Known person detected, unknown timer reset")
                        self.unknown_person_start_time = None
                        self.unknown_person_embedding = None
                        self.unknown_person_id = None
                        self.update_button_visibility(None)

                    self.current_recognized_person = name

                    # Non-blocking pre-fetch of blocked status
                    if self.api_client and not self.face_confirmed:
                        self._request_status_sync(name)

                    # Confirmation timing
                    current_time = time.time()
                    if self.last_stable_person == name:
                        if self.confirmation_start_time is not None:
                            time_recognized = current_time - self.confirmation_start_time
                            if time_recognized >= self.CONFIRMATION_DELAY and not self.face_confirmed:
                                print(f"✅ Face CONFIRMED: {name} ({similarity:.0%}) after {time_recognized:.1f}s")
                                self.face_confirmed = True
                                self.confirmed_person_name = name
                                self.confirmed_person_similarity = similarity
                                self.confirmed_frame = None

                                state_display = self.state_manager.get_state_display(name)
                                self.status_label.setText(f"✅ CONFIRMED: {name} | {state_display}")

                                if self.is_user_blocked:
                                    self.notification_overlay.show_notification(
                                        "⚠️ Action Blocked",
                                        self.blocked_message or "Action not allowed",
                                        "warning", 5000
                                    )
                                    self.button_scroll.setVisible(False)
                                    QTimer.singleShot(4000, self._reset_face_confirmation)
                                else:
                                    self.button_scroll.setVisible(True)
                                    self.update_button_visibility(name)

                                # Show banner over the LIVE feed (no frozen frame)
                                self._set_overlay({
                                    'box': (x, y, w, h),
                                    'color': CYAN_RGB,
                                    'banner': f"{name}",
                                })
                                return
                        else:
                            self.confirmation_start_time = current_time
                    else:
                        self.last_stable_person = name
                        self.confirmation_start_time = current_time
                        self.face_confirmed = False
                        self.confirmed_person_name = None
                        self.confirmed_frame = None

                    verified = ""
                    if config.ENABLE_LIVENESS and self.face_recognizer.liveness_detector:
                        if self.face_recognizer.liveness_detector.is_verified_live:
                            verified = "✓"

                    if self.locked_person_for_action == name:
                        state_display = self.state_manager.get_state_display(name)
                        status_text = f"👤 {name} {verified} • {similarity:.0%} | {state_display}"
                    else:
                        if self.confirmation_start_time:
                            progress = min(1.0, (current_time - self.confirmation_start_time) / self.CONFIRMATION_DELAY)
                            status_text = f"👤 {name} {verified} • {similarity:.0%} | Confirming... {progress:.0%}"
                        else:
                            api_indicator = "📡" if config.API_ENABLED else ""
                            status_text = f"👤 {name} {verified} • {similarity:.0%} {api_indicator}"
                    self.status_label.setText(status_text)

                    self._set_overlay({
                        'box': (x, y, w, h),
                        'color': GREEN_RGB,
                        'label': name,
                        'sublabel': f"{similarity:.0%}",
                    })

                elif is_confident and not liveness_ok:
                    self.current_recognized_person = None
                    self.status_label.setText(f"👁️ {name} detected - Please blink")
                    self._set_overlay({
                        'box': (x, y, w, h),
                        'color': YELLOW_RGB,
                        'label': "Please Blink",
                    })

                else:
                    self.current_recognized_person = None
                    self._handle_unknown_person(person, frame_rgb, (x, y, w, h))
                    self._set_overlay({
                        'box': (x, y, w, h),
                        'color': RED_RGB,
                        'label': "Unknown",
                        'sublabel': f"{similarity:.0%}",
                    })

            elif detected:
                face = detected[0]
                x, y, w, h = face['bbox']
                self.current_recognized_person = None
                self.status_label.setText("⏳ Detecting...")
                self._set_overlay({
                    'box': (x, y, w, h),
                    'color': YELLOW_RGB,
                    'label': "DETECTING...",
                })

            else:
                # No face present
                if self.unknown_person_start_time is not None:
                    print("👤 Unknown person left frame, timer reset")
                    self.unknown_person_start_time = None
                    self.unknown_person_embedding = None
                    self.unknown_person_id = None
                    self.update_button_visibility(None)

                if self.last_recognized_person is not None and self.person_last_seen_time is not None:
                    time_elapsed = time.time() - self.person_last_seen_time
                    if time_elapsed >= self.RESET_TIMEOUT:
                        if self.face_recognizer.liveness_detector:
                            self.face_recognizer.liveness_detector.reset()
                            print(f"🔄 Auto-reset after {time_elapsed:.1f}s")
                        self.last_recognized_person = None
                        self.person_last_seen_time = None

                self.current_recognized_person = None
                self.status_label.setText("✅ Ready • No face")
                self._set_overlay({})

        except Exception as e:
            print(f"Recognition result error: {e}")
            import traceback
            traceback.print_exc()

    def _handle_registration_result(self, detected_faces, frame_rgb):
        """Draw registration guidance boxes and forward frames to the registration page."""
        current_step = getattr(self.registration_page, 'current_registration_step', 0)
        steps = getattr(self.registration_page, 'registration_steps', [])

        display = frame_rgb.copy()

        if steps and current_step >= len(steps):
            self.registration_page.display_camera_feed(display)
            return

        if detected_faces:
            face = max(detected_faces, key=lambda f: f['bbox'][2] * f['bbox'][3])
            x, y, w, h = face['bbox']
            self.draw_box_rgb(display, x, y, x + w, y + h, (0, 255, 0), thickness=4)
            if current_step < len(steps):
                icon = steps[current_step]["icon"]
                self.put_text_rgb(display, icon, x + w // 2 - 20, max(0, y - 20),
                                  (0, 255, 0), scale=2.0, thickness=4)

        # Capture logic uses the raw frame; display uses the annotated copy
        self.registration_page.set_current_frame(frame_rgb)
        self.registration_page.display_camera_feed(display)

    def _handle_unknown_person(self, person, frame_rgb, bbox):
        """Unknown-person monitoring (gated by ENABLE_MQTT_FEATURES)."""
        x, y, w, h = bbox
        if getattr(config, 'ENABLE_MQTT_FEATURES', False):
            current_time = time.time()

            if self.unknown_person_start_time is None:
                self.unknown_person_start_time = current_time
                self.unknown_person_last_frame = frame_rgb.copy()
                self.unknown_person_last_bbox = (x, y, w, h)
                self.unknown_person_embedding = None
                self.unknown_person_id = None
                self.update_button_visibility(None)
                self.button_scroll.setVisible(True)
                self.status_label.setText("⚠️ Unknown Person - Monitoring")
                print(f"⚠️ Unknown person detected, timer started")
            else:
                duration = current_time - self.unknown_person_start_time
                self.unknown_person_last_frame = frame_rgb.copy()
                self.unknown_person_last_bbox = (x, y, w, h)

                timer_text = f"Unknown: {int(duration)}s / {int(config.UNKNOWN_PERSON_TIMEOUT)}s"
                self.status_label.setText(f"⚠️ {timer_text}")

                if duration >= config.UNKNOWN_PERSON_TIMEOUT:
                    if self.unknown_person_embedding is None:
                        face_img = self.face_recognizer.extract_face_region(
                            self.unknown_person_last_frame, person, align=False)
                        if face_img is not None:
                            self.unknown_person_embedding = self.face_recognizer.extract_embedding(face_img)
                            if self.unknown_person_embedding is not None:
                                self.unknown_person_id, is_new = self.unknown_tracker.get_or_create_unknown(
                                    self.unknown_person_embedding)

                    if self.unknown_person_id:
                        can_send, reason = self.unknown_tracker.can_send_incident(self.unknown_person_id)
                        if can_send and self.mqtt_reporter and self.mqtt_reporter.connected:
                            person_info = self.unknown_tracker.get_person_info(self.unknown_person_id)
                            incident_num = person_info['incident_count'] + 1 if person_info else 1
                            incident_sent = self.mqtt_reporter.send_incident(
                                frame=self.unknown_person_last_frame,
                                detection_time=datetime.fromtimestamp(self.unknown_person_start_time),
                                duration=duration,
                                bbox=None,
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
            self.status_label.setText("⚠️ Unknown Person")
            self.update_button_visibility(None)
            self.button_scroll.setVisible(True)

    @Slot(str)
    def update_status(self, message):
        self.status_label.setText(message)

    def start_registration(self):
        """Start registration — password is validated via admin panel."""
        # Pause background face detection processing
        self.event_in_progress = True

        # Ensure camera is running for registration
        if not self.camera_thread or not self.camera_thread.isRunning():
            self.init_camera()
        if not self.display_timer.isActive():
            self.display_timer.start(1000 // max(getattr(config, 'DISPLAY_FPS', 25), 1))

        # ── Step 1: Collect name ─────────────────────────────────────────────
        name_dlg = TextInputDialog(self, title="Enter Person's Name",
                                   placeholder="Full name")
        if name_dlg.exec() != QDialog.Accepted:
            self.event_in_progress = False
            return
        name = name_dlg.get_text().strip()
        if not name:
            self.event_in_progress = False
            return

        # ── Step 2: Collect employee ID ───────────────────────────────────────
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

        # Hide keyboard after inputs are complete
        VKLineEdit._hide_keyboard()

        # ── Step 3: Begin registration via dedicated module ──────────────────
        self.event_in_progress = False  # Allow process_frame to run for registration bounding boxes
        self.face_confirmed = False     # Clear any confirmed state
        self.confirmed_frame = None
        self.registration_mode = True
        
        # Hide main UI labels to give full space to registration page
        self.title_label.setVisible(False)
        self.status_label.setVisible(False)
        self.instruction_label.setVisible(False)
        self.feedback_label.setVisible(False)
        
        self.registration_page.start_registration(name, employee_id, self.pages_stack)

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
        """Confirm with the user, then run the heavy work off the GUI thread."""

        if not self.locked_person_for_action:
            self.notification_overlay.show_notification("Error", "No person locked!", "error", 1000)
            return

        if not self._guard_server_online():
            return

        # ★★★ SET EVENT IN PROGRESS - Pause recognition during the action ★★★
        self.event_in_progress = True

        dialog = SimpleConfirmationDialog(self, self.locked_person_for_action, action)

        if dialog.exec() != QDialog.Accepted:
            # Cancelled - clear lock but keep face confirmation
            self.locked_person_for_action = None
            self.locked_person_timestamp = None
            self.event_in_progress = False
            return

        # Run API validation + state update + adaptive learning OFF the GUI thread
        person = self.locked_person_for_action
        self.status_label.setText(f"⏳ Recording {action}...")
        self._action_worker = ActionWorker(self, action, person, self.current_frame, datetime.now())
        self._action_worker.done.connect(self._on_action_done, Qt.QueuedConnection)
        self._action_worker.start()

    @Slot(bool, str, bool)
    def _on_action_done(self, success, message, should_reset):
        """Handle completion of an ActionWorker (runs on the GUI thread)."""
        if success:
            self.notification_overlay.show_notification("Success", message, "success", 2000)
            self.locked_person_for_action = None
            self.locked_person_timestamp = None
            # event_in_progress is cleared by _reset_face_confirmation
            self._reset_face_confirmation()
        else:
            title = "❌ Action Rejected" if should_reset else "Error"
            duration = 4000 if should_reset else 2000
            self.notification_overlay.show_notification(title, message, "error", duration)
            self.locked_person_for_action = None
            self.locked_person_timestamp = None
            self.event_in_progress = False
            if should_reset:
                QTimer.singleShot(4000, self._reset_face_confirmation)

    def update_button_visibility(self, person_name):
        if not person_name:
            for btn in self.all_action_buttons:
                btn.setVisible(False)
            self.is_user_blocked = False
            self._rearrange_button_grid()
            return
        
        # ★★★ NON-BLOCKING: kick off a background status sync, use cached result ★★★
        # The blocked status is pre-fetched during recognition, so we read the
        # cached value here instead of blocking the GUI thread on the network.
        self._request_status_sync(person_name)
        if self.is_user_blocked:
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
        
        self._rearrange_button_grid()

    def _rearrange_button_grid(self):
        """Dynamically arrange visible buttons in a grid: max 2 per row."""
        # 0. Get visible buttons BEFORE clearing layout (since setParent(None) hides them)
        visible_buttons = [btn for btn in self.all_action_buttons if not btn.isHidden()]
        
        # 1. Clear layout
        while self.button_layout.count():
            item = self.button_layout.takeAt(0)
            # Just remove, don't delete widgets
            if item.widget():
                item.widget().setParent(None)
        
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
        if not self._guard_server_online():
            return
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
        if not self._guard_server_online():
            return
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
        if not self._guard_server_online():
            return
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
        if not self._guard_server_online():
            return
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
        if not self._guard_server_online():
            return
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
        if not self._guard_server_online():
            return
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

        if hasattr(self, 'display_timer') and self.display_timer:
            self.display_timer.stop()

        if hasattr(self, 'recognition_worker') and self.recognition_worker:
            self.recognition_worker.stop()

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
        if hasattr(self, 'display_timer') and self.display_timer:
            self.display_timer.stop()

        if hasattr(self, 'recognition_worker') and self.recognition_worker:
            self.recognition_worker.stop()

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
