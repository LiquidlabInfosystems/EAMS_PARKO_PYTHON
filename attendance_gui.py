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
                               QStackedWidget, QDialog)
from PySide6.QtCore import Qt, QTimer, Slot
from PySide6.QtGui import QFont
import numpy as np
import time
from datetime import datetime
import subprocess

from face_recognizer import FaceRecognizer
from modules.api_client import AttendanceAPIClient
from modules.attendance_state_manager import AttendanceStateManager
from modules.mqtt_incident_reporter import MQTTIncidentReporter
from modules.unknown_person_tracker import UnknownPersonTracker
from modules.mqtt_face_registration import MQTTFaceRegistrationHandler
from modules.temporal_buffer import TemporalRecognitionBuffer
from modules.admin_control import AdminControlPage
from modules.registration_gui import RegistrationPage
from modules.ui_utils import VKLineEdit

from screens.scaling import pw, ph, pf
from screens.camera_controller import CameraThread
from screens.notification_overlay import NotificationOverlay
from screens.dialogs import TextInputDialog, AdminPasswordDialog
from screens.mark_attendance_screen import MarkAttendanceScreen
from screens.face_list_screen import FaceListScreen

import config


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

            # ★★★ TEMPORAL RECOGNITION BUFFER ★★★
            self.temporal_buffer = TemporalRecognitionBuffer(
                buffer_size=config.TEMPORAL_BUFFER_SIZE,
                agreement_threshold=config.TEMPORAL_AGREEMENT_THRESHOLD
            )
            self.temporal_buffer.set_identity_lock_time(config.IDENTITY_LOCK_TIME)
            print(f"✓ Temporal Buffer: {config.TEMPORAL_BUFFER_SIZE} frames, {config.TEMPORAL_AGREEMENT_THRESHOLD*100:.0f}% agreement")

            print("="*60 + "\n")
        except Exception as e:
            print(f"❌ Recognizer init error: {e}")
            import traceback
            traceback.print_exc()
            sys.exit(1)

        # ★★★ CREATE NOTIFICATION OVERLAY ★★★
        self.notification_overlay = NotificationOverlay(self)

        self.init_ui()

        # ★★★ STARTUP SYNC - Fetch fresh status for all users ★★★
        if config.API_ENABLED and self.api_client:
            print("\n🔄 Syncing attendance status from server...")
            self.attendance_screen._sync_all_users_on_startup()

        # Start camera
        self.camera_thread = None
        QTimer.singleShot(200, self.init_camera)

        # Processing timer
        self.process_timer = QTimer()
        self.process_timer.timeout.connect(self.attendance_screen.process_frame)
        self.process_timer.start(1000 // config.CAMERA_FPS)

        # ★★★ DATABASE RELOAD TIMER ★★★
        self.db_reload_timer = QTimer()
        self.db_reload_timer.timeout.connect(self._check_db_update)
        self.db_reload_timer.start(30000)

        # ★★★ STATUS SYNC TIMER ★★★
        self.status_sync_timer = QTimer()
        self.status_sync_timer.timeout.connect(self.attendance_screen._sync_current_user_status)
        self.status_sync_timer.start(60000)

    def init_ui(self):
        """Initialize UI with screen stack"""
        liveness_status = "🛡️ Blink Detection" if config.ENABLE_LIVENESS else "⚠️ Liveness Disabled"
        api_status = f"📡 API: {config.API_SERVER_IP}" if config.API_ENABLED else "○ API Disabled"
        self.setWindowTitle(f"Employee Attendance System - {liveness_status} | {api_status}")

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Pages stack
        self.pages_stack = QStackedWidget()

        # Page 0: Mark Attendance Screen
        self.attendance_screen = MarkAttendanceScreen(
            face_recognizer=self.face_recognizer,
            state_manager=self.state_manager,
            api_client=self.api_client,
            temporal_buffer=self.temporal_buffer,
            unknown_tracker=self.unknown_tracker,
            mqtt_reporter=self.mqtt_reporter,
            notification_overlay=self.notification_overlay
        )
        self.attendance_screen.admin_requested.connect(self.show_admin_page)
        self.pages_stack.addWidget(self.attendance_screen)

        # Page 1: Admin control page
        self.admin_page = AdminControlPage(self.face_recognizer)
        self.admin_page.home_requested.connect(self.show_camera_page)
        self.admin_page.add_new_face_requested.connect(self.start_registration_from_admin)
        self.admin_page.list_faces_requested.connect(self.show_face_list_page)
        self.pages_stack.addWidget(self.admin_page)

        # Page 2: Registration page
        self.registration_page = RegistrationPage(self.face_recognizer, self.notification_overlay)
        self.registration_page.registration_completed.connect(self.on_registration_finished)
        self.registration_page.registration_cancelled.connect(self.on_registration_finished)
        self.pages_stack.addWidget(self.registration_page)

        # Page 3: Face list screen
        self.face_list_page = FaceListScreen(self.face_recognizer)
        self.face_list_page.back_requested.connect(self.show_admin_from_face_list)
        self.pages_stack.addWidget(self.face_list_page)

        self.pages_stack.setCurrentIndex(0)
        main_layout.addWidget(self.pages_stack)

        self.showFullScreen()

        # Execute the Wayland rotation script after GUI is visible
        QTimer.singleShot(1000, self._rotate_screen)

    def _rotate_screen(self):
        """Automatically rotate the screen layout after OS boot if needed."""
        try:
            script_path = os.path.join(os.path.dirname(__file__), "rotate_screen.sh")
            if os.path.exists(script_path):
                subprocess.Popen(["bash", script_path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                print("🔄 Triggered screen rotation script")
        except Exception as e:
            print(f"⚠️ Failed to trigger screen rotation script: {e}")

    def show_admin_page(self):
        """Show the admin control page after password validation"""
        dlg = AdminPasswordDialog(self)

        while True:
            if dlg.exec() != QDialog.Accepted:
                return

            password = dlg.get_password().strip()
            if not password:
                dlg.show_error("Password cannot be empty")
                if dlg.exec() == QDialog.Rejected:
                    return
                continue

            if self.api_client:
                self.attendance_screen.status_label.setText("🔑 Validating admin password...")
                QApplication.processEvents()
                ok, err_msg = self.api_client.validate_admin_password(password)
            else:
                ok, err_msg = True, ""

            if ok:
                break

            dlg.show_error(err_msg or "Invalid password")
            self.attendance_screen.status_label.setText("❌ Invalid admin password")

        VKLineEdit._hide_keyboard()
        self.pages_stack.setCurrentIndex(1)

    def show_camera_page(self):
        """Show the camera page"""
        self.pages_stack.setCurrentIndex(0)

    def show_face_list_page(self):
        """Show the face list screen and refresh data"""
        self.face_list_page.refresh()
        self.pages_stack.setCurrentIndex(3)

    def show_admin_from_face_list(self):
        """Return from face list to admin page"""
        self.pages_stack.setCurrentIndex(1)

    def start_registration_from_admin(self):
        """Start registration when triggered from admin page"""
        self.start_registration()

    @Slot()
    def on_registration_finished(self):
        """Handle registration completion or cancellation"""
        self.attendance_screen.registration_mode = False
        self.attendance_screen.event_in_progress = False

        # Restore main UI labels
        self.attendance_screen.status_label.setVisible(True)
        self.attendance_screen.instruction_label.setVisible(False)
        self.attendance_screen.feedback_label.setVisible(False)

        self.show_camera_page()
        if self.face_recognizer.liveness_detector:
            self.face_recognizer.liveness_detector.reset()
        self.attendance_screen.current_recognized_person = None
        self.attendance_screen.last_recognized_person = None
        self.attendance_screen.status_label.setText("✅ Ready")

    def init_camera(self):
        """Initialize camera"""
        try:
            self.attendance_screen.status_label.setText("📷 Starting camera...")
            QApplication.processEvents()

            self.camera_thread = CameraThread(mirror=True)
            self.camera_thread.frame_ready.connect(self.on_frame_ready, Qt.QueuedConnection)
            self.camera_thread.status_update.connect(self.attendance_screen.update_status)
            self.camera_thread.start()

        except Exception as e:
            self.attendance_screen.status_label.setText("\u274C Camera Error")
            print(f"Camera init error: {e}")

    @Slot(np.ndarray)
    def on_frame_ready(self, frame_rgb):
        self.attendance_screen.latest_frame = frame_rgb.copy()

        # If in registration mode, update its feed and capture frame directly
        if self.attendance_screen.registration_mode:
            self.registration_page.set_current_frame(frame_rgb)
            self.registration_page.display_camera_feed(frame_rgb)

    def _check_db_update(self):
        """Check if database file was modified and reload if needed"""
        try:
            self.face_recognizer.reload_if_modified()
        except Exception as e:
            print(f"⚠️ Database reload check error: {e}")

    def start_registration(self):
        """Start registration — password is validated via admin panel."""
        self.attendance_screen.event_in_progress = True

        name_dlg = TextInputDialog(self, title="Enter Person's Name",
                                   placeholder="Full name")
        if name_dlg.exec() != QDialog.Accepted:
            self.attendance_screen.event_in_progress = False
            return
        name = name_dlg.get_text().strip()
        if not name:
            self.attendance_screen.event_in_progress = False
            return

        emp_dlg = TextInputDialog(self, title="Enter Employee ID",
                                  placeholder="Employee ID")
        if emp_dlg.exec() != QDialog.Accepted:
            self.notification_overlay.show_notification(
                "Cancelled", "Employee ID is required for registration", "warning", 2000
            )
            self.attendance_screen.event_in_progress = False
            return
        employee_id = emp_dlg.get_text().strip()
        if not employee_id:
            self.notification_overlay.show_notification(
                "Cancelled", "Employee ID is required for registration", "warning", 2000
            )
            self.attendance_screen.event_in_progress = False
            return

        VKLineEdit._hide_keyboard()

        self.attendance_screen.registration_mode = True
        self.attendance_screen.status_label.setVisible(False)
        self.attendance_screen.instruction_label.setVisible(False)
        self.attendance_screen.feedback_label.setVisible(False)

        self.registration_page.start_registration(name, employee_id, self.pages_stack)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            if self.attendance_screen.registration_mode:
                self.registration_page.cancel_registration()
            else:
                self.close_app()

    def close_app(self):
        """Close application gracefully"""
        print("\n🛑 Shutting down...")

        # Stop welcome screen animation
        if hasattr(self.attendance_screen, 'welcome_widget'):
            self.attendance_screen.welcome_widget.stop_animation()

        if self.process_timer:
            self.process_timer.stop()

        if hasattr(self, 'db_reload_timer') and self.db_reload_timer:
            self.db_reload_timer.stop()

        if hasattr(self, 'status_sync_timer') and self.status_sync_timer:
            self.status_sync_timer.stop()

        if self.camera_thread:
            self.camera_thread.stop()

        # Stop registration page threads
        if hasattr(self, 'registration_page'):
            self.registration_page.stop()

        # ★★★ STOP API CLIENT GRACEFULLY ★★★
        if hasattr(self, 'api_client') and self.api_client:
            print("Stopping API client...")
            self.api_client.stop()
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

        if hasattr(self, 'api_client') and self.api_client:
            self.api_client.stop()

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
