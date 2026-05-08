#!/usr/bin/env python3
"""
Attendance System GUI - Production Version (Refactored)
Orchestrates screens and manages system state.
"""

import os
os.environ['GLOG_minloglevel'] = '2'
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'
os.environ['QT_LOGGING_RULES'] = '*.debug=false;qt.accessibility.atspi.warning=false'

import sys
import time
from datetime import datetime
import numpy as np
import cv2

from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                               QHBoxLayout, QLabel, QPushButton, QFrame, 
                               QStackedWidget, QDialog, QLineEdit)
from PySide6.QtCore import Qt, Signal, Slot, QPropertyAnimation, QEasingCurve, QTimer

# Import core modules
import config
from face_recognizer import FaceRecognizer
from modules.api_client import AttendanceAPIClient
from modules.attendance_state_manager import AttendanceStateManager
from modules.mqtt_incident_reporter import MQTTIncidentReporter
from modules.unknown_person_tracker import UnknownPersonTracker
from modules.temporal_buffer import TemporalRecognitionBuffer
from modules.mqtt_face_registration import MQTTFaceRegistrationHandler
from modules.ui_utils import VKLineEdit, KioskInputDialog

# Import New Screens
from screens.welcome_screen import WelcomeScreen
from screens.attendance_screen import AttendanceScreen
from screens.admin_screen import AdminScreen
from screens.registration_screen import RegistrationScreen
from screens.face_list_screen import FaceListScreen
from modules.camera_manager import CameraThread

# Scaling helpers
def _scr():
    app = QApplication.instance()
    if app:
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

class NotificationOverlay(QFrame):
    """Notification overlay for success/error messages"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("notificationOverlay")
        self.setFixedSize(pw(400), ph(100))
        self.setVisible(False)
        
        layout = QVBoxLayout(self)
        self.title_label = QLabel()
        self.title_label.setStyleSheet(f"font-weight: bold; font-size: {pf(18)}px; color: white; border: none;")
        self.msg_label = QLabel()
        self.msg_label.setStyleSheet(f"font-size: {pf(16)}px; color: white; border: none;")
        self.msg_label.setWordWrap(True)
        
        layout.addWidget(self.title_label)
        layout.addWidget(self.msg_label)
        
        self.timer = QTimer()
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self.hide_notification)

    def show_notification(self, title, message, type="success", duration=3000):
        self.title_label.setText(title)
        self.msg_label.setText(message)
        
        bg_color = "#2ECC71" if type == "success" else "#E74C3C" if type == "error" else "#F39C12"
        self.setStyleSheet(f"QFrame#notificationOverlay {{ background-color: {bg_color}; border-radius: {pw(10)}px; border: 2px solid rgba(255,255,255,0.3); }}")
        
        # Center the notification
        parent_rect = self.parent().rect()
        self.move((parent_rect.width() - self.width()) // 2, ph(50))
        self.raise_()
        self.setVisible(True)
        self.timer.start(duration)

    def hide_notification(self):
        self.setVisible(False)

class AdminAuthDialog(QDialog):
    """Admin password authentication dialog"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Admin Authentication")
        self.setModal(True)
        if parent: self.setFixedSize(parent.size())
        else: self.showFullScreen()
        self.setWindowFlags(Qt.Dialog | Qt.FramelessWindowHint)
        self.setStyleSheet(f"QDialog {{ background-color: rgba(26, 26, 26, 0.95); }}")
        
        layout = QVBoxLayout(self)
        layout.addStretch(1)
        
        container = QFrame()
        container.setStyleSheet(f"background-color: #2d2d2d; border: 2px solid #00ff88; border-radius: {pw(15)}px; padding: 20px;")
        root = QVBoxLayout(container)
        
        title = QLabel("🔐 Admin Access")
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet(f"color: #00ff88; font-size: {pf(22)}px; font-weight: bold; border: none;")
        root.addWidget(title)
        
        self.password_input = VKLineEdit()
        self.password_input.setPlaceholderText("Enter admin password")
        self.password_input.setEchoMode(QLineEdit.Password)
        self.password_input.setStyleSheet(f"background-color: #1a1a1a; color: white; border: 1px solid #444; border-radius: 8px; padding: 15px; font-size: {pf(18)}px;")
        root.addWidget(self.password_input)
        
        btn_layout = QHBoxLayout()
        confirm_btn = QPushButton("LOGIN")
        confirm_btn.clicked.connect(self.accept)
        confirm_btn.setStyleSheet(f"background-color: #00aa66; color: white; font-weight: bold; padding: 15px; border-radius: 8px;")
        cancel_btn = QPushButton("CANCEL")
        cancel_btn.clicked.connect(self.reject)
        cancel_btn.setStyleSheet(f"background-color: #444; color: white; padding: 15px; border-radius: 8px;")
        
        btn_layout.addWidget(cancel_btn)
        btn_layout.addWidget(confirm_btn)
        root.addLayout(btn_layout)
        
        layout.addWidget(container, 0, Qt.AlignCenter)
        layout.addStretch(1)

class AttendanceKioskGUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Kiosk Attendance System")
        self.setObjectName("MainWindow")
        self.showFullScreen()
        
        # Initialize Core Components
        self.face_recognizer = FaceRecognizer()
        self.api_client = AttendanceAPIClient() if config.API_ENABLED else None
        self.state_manager = AttendanceStateManager()
        self.incident_reporter = MQTTIncidentReporter() if config.MQTT_INCIDENT_REPORTING else None
        self.unknown_tracker = UnknownPersonTracker()
        self.temporal_buffer = TemporalRecognitionBuffer(config.TEMPORAL_BUFFER_SIZE, config.TEMPORAL_AGREEMENT_THRESHOLD)
        self.notification_overlay = NotificationOverlay(self)
        
        # Application State
        self.latest_frame = None
        self.current_recognized_person = None
        self.processing = False
        self.event_in_progress = False
        self.face_confirmed = False
        self.confirmed_person_name = None
        self.confirmed_frame = None
        self.is_user_blocked = False
        self.blocked_message = ""
        
        self.init_ui()
        
        # Timers
        self.process_timer = QTimer()
        self.process_timer.timeout.connect(self.process_frame)
        self.process_timer.start(1000 // config.CAMERA_FPS)
        
        # Start Camera
        QTimer.singleShot(500, self.init_camera)

    def init_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        self.main_layout = QVBoxLayout(central_widget)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        
        # Header (Optional, common for all screens)
        header = QFrame()
        header.setFixedHeight(ph(60))
        header.setStyleSheet("background-color: #1a1a1a; border-bottom: 2px solid #00ff88;")
        header_layout = QHBoxLayout(header)
        title = QLabel("🏢 EMS ATTENDANCE")
        title.setStyleSheet(f"color: #00ff88; font-weight: bold; font-size: {pf(18)}px;")
        header_layout.addWidget(title)
        header_layout.addStretch()
        self.admin_btn = QPushButton("⚙️ ADMIN")
        self.admin_btn.clicked.connect(self.request_admin_access)
        self.admin_btn.setStyleSheet("background-color: #444; color: white; padding: 5px 15px; border-radius: 5px;")
        header_layout.addWidget(self.admin_btn)
        self.main_layout.addWidget(header)
        
        # Status Bar
        self.status_bar = QLabel("System Ready")
        self.status_bar.setAlignment(Qt.AlignCenter)
        self.status_bar.setStyleSheet(f"background-color: #0d0d0d; color: #aaa; font-size: {pf(12)}px; padding: 5px;")
        self.main_layout.addWidget(self.status_bar)
        
        # Stacked Widget for Screens
        self.screens = QStackedWidget()
        
        # 0: Welcome Screen
        self.welcome_screen = WelcomeScreen()
        self.screens.addWidget(self.welcome_screen)
        
        # 1: Attendance Screen
        self.attendance_screen = AttendanceScreen()
        self.attendance_screen.action_clicked.connect(self.handle_attendance_action)
        self.screens.addWidget(self.attendance_screen)
        
        # 2: Admin Screen
        self.admin_screen = AdminScreen(self.face_recognizer)
        self.admin_screen.home_requested.connect(lambda: self.screens.setCurrentIndex(0))
        self.admin_screen.add_new_face_requested.connect(self.start_registration)
        self.admin_screen.list_faces_requested.connect(self.show_face_list)
        self.screens.addWidget(self.admin_screen)
        
        # 3: Registration Screen
        self.registration_screen = RegistrationScreen(self.face_recognizer, self.notification_overlay)
        self.registration_screen.registration_completed.connect(lambda: self.screens.setCurrentIndex(2))
        self.registration_screen.registration_cancelled.connect(lambda: self.screens.setCurrentIndex(2))
        self.screens.addWidget(self.registration_screen)
        
        # 4: Face List Screen
        self.face_list_screen = FaceListScreen(self.face_recognizer)
        self.face_list_screen.back_requested.connect(lambda: self.screens.setCurrentIndex(2))
        self.screens.addWidget(self.face_list_screen)
        
        self.main_layout.addWidget(self.screens)
        self.screens.setCurrentIndex(0)

    def init_camera(self):
        self.camera_thread = CameraThread(mirror=True)
        self.camera_thread.frame_ready.connect(self.on_frame_ready)
        self.camera_thread.status_update.connect(self.status_bar.setText)
        self.camera_thread.start()

    @Slot(np.ndarray)
    def on_frame_ready(self, frame_rgb):
        self.latest_frame = frame_rgb
        idx = self.screens.currentIndex()
        if idx == 0: # Welcome
            # Pass frame if welcome screen needs it for something
            pass
        elif idx == 1: # Attendance
            self.attendance_screen.display_frame(frame_rgb)
        elif idx == 3: # Registration
            self.registration_screen.set_current_frame(frame_rgb)
            self.registration_screen.display_camera_feed(frame_rgb)

    def process_frame(self):
        if self.latest_frame is None or self.processing or self.event_in_progress:
            return
        
        if self.screens.currentIndex() not in [0, 1]:
            return
            
        self.processing = True
        try:
            # Face recognition logic
            detected, recognized = self.face_recognizer.process_frame(self.latest_frame)
            
            if recognized:
                person = recognized[0]
                name = person.get('name', 'Unknown')
                self.temporal_buffer.add_result(name)
                stable_name = self.temporal_buffer.get_confirmed_identity()
                
                if stable_name and stable_name != "Unknown":
                    self.confirmed_person_name = stable_name
                    self.face_confirmed = True
                    self.screens.setCurrentIndex(1) # Switch to attendance screen
                    self.attendance_screen.set_buttons_visible(True)
                    self.status_bar.setText(f"Person: {stable_name}")
                else:
                    self.face_confirmed = False
                    self.attendance_screen.set_buttons_visible(False)
                    if self.screens.currentIndex() == 1: self.screens.setCurrentIndex(0)
            else:
                self.temporal_buffer.clear()
                self.face_confirmed = False
                self.attendance_screen.set_buttons_visible(False)
                if self.screens.currentIndex() == 1: self.screens.setCurrentIndex(0)
                
        finally:
            self.processing = False

    def handle_attendance_action(self, action_type):
        if not self.confirmed_person_name: return
        self.event_in_progress = True
        self.status_bar.setText(f"Processing {action_type}...")
        
        # Simulate API call or logic
        QTimer.singleShot(1500, lambda: self.complete_action(action_type))

    def complete_action(self, action_type):
        self.notification_overlay.show_notification("Success", f"{action_type} recorded for {self.confirmed_person_name}", "success")
        self.event_in_progress = False
        self.face_confirmed = False
        self.confirmed_person_name = None
        self.attendance_screen.set_buttons_visible(False)
        self.screens.setCurrentIndex(0)

    def request_admin_access(self):
        dialog = AdminAuthDialog(self)
        if dialog.exec() == QDialog.Accepted:
            password = dialog.password_input.text()
            if password == config.ADMIN_PASSWORD:
                self.screens.setCurrentIndex(2) # Admin Screen
            else:
                self.notification_overlay.show_notification("Error", "Invalid Password", "error")

    def start_registration(self):
        name, ok = KioskInputDialog.get_text(self, "Register New Face", "Enter person's name:")
        if ok and name:
            self.screens.setCurrentIndex(3) # Registration Screen
            self.registration_screen.start_registration(name, None)

    def show_face_list(self):
        self.face_list_screen.refresh_list()
        self.screens.setCurrentIndex(4) # Face List Screen

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = AttendanceKioskGUI()
    window.show()
    sys.exit(app.exec())
