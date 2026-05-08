#!/usr/bin/env python3
"""
Mark Attendance Screen - Main attendance screen with camera feed,
face recognition, confirmation, and action buttons.
"""

from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
                               QPushButton, QFrame, QGridLayout, QStackedWidget,
                               QSizePolicy, QApplication, QDialog)
from PySide6.QtCore import Qt, Signal, Slot, QTimer
from PySide6.QtGui import QImage, QPixmap
import numpy as np
import time
import cv2
from datetime import datetime

from screens.scaling import pw, ph, pf
from screens.camera_controller import display_frame, draw_box_rgb, draw_filled_box_rgb, put_text_rgb
from screens.dialogs import SimpleConfirmationDialog
from modules.welcome_screen import WelcomeScreen
from modules.ui_utils import VKLineEdit

import config


class MarkAttendanceScreen(QWidget):
    """Main attendance screen with camera feed and action buttons"""

    # Signals to orchestrator
    admin_requested = Signal()

    def __init__(self, face_recognizer, state_manager, api_client,
                 temporal_buffer, unknown_tracker, mqtt_reporter,
                 notification_overlay, parent=None):
        super().__init__(parent)
        self.face_recognizer = face_recognizer
        self.state_manager = state_manager
        self.api_client = api_client
        self.temporal_buffer = temporal_buffer
        self.unknown_tracker = unknown_tracker
        self.mqtt_reporter = mqtt_reporter
        self.notification_overlay = notification_overlay

        # Processing control
        self.registration_mode = False
        self.processing = False
        self.current_frame = None
        self.latest_frame = None

        # Person locking
        self.current_recognized_person = None
        self.locked_person_for_action = None
        self.locked_person_timestamp = None

        # Adaptive learning counter
        self.adaptive_learning_count = 0

        # Smart liveness state
        self.last_recognized_person = None
        self.person_last_seen_time = None
        self.RESET_TIMEOUT = 30.0

        # Server status sync tracking
        self.last_status_sync_time = 0
        self.status_sync_interval = 60
        self.is_user_blocked = False
        self.blocked_message = ""
        self.last_synced_employee_id = None

        self.feedback_timer = None
        self.no_face_timeout = None

        # Face confirmation & freeze state
        self.face_confirmed = False
        self.confirmed_person_name = None
        self.confirmed_person_similarity = 0.0
        self.confirmed_person_bbox = None
        self.confirmed_frame = None
        self.confirmation_start_time = None
        self.CONFIRMATION_DELAY = 1.0
        self.event_in_progress = False
        self.last_stable_person = None

        # Unknown person tracking
        self.unknown_person_start_time = None
        self.unknown_person_last_frame = None
        self.unknown_person_last_bbox = None
        self.unknown_person_embedding = None
        self.unknown_person_id = None

        self.init_ui()

    def init_ui(self):
        """Initialize UI"""
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(pw(8), ph(6), pw(8), ph(6))
        self.main_layout.setSpacing(ph(3))

        # ── Header row: title (centred) + admin button (right) ────────
        header_widget = QWidget()
        header_widget.setObjectName("headerBar")
        header_layout = QHBoxLayout(header_widget)
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(0)

        self.title_label = QLabel("ERP")
        self.title_label.setObjectName("title")
        self.title_label.setAlignment(Qt.AlignCenter)
        self.title_label.setWordWrap(True)
        header_layout.addStretch(1)
        header_layout.addWidget(self.title_label)
        header_layout.addStretch(1)

        self.admin_icon_btn = QPushButton("⚙️")
        self.admin_icon_btn.setObjectName("adminIcon")
        self.admin_icon_btn.clicked.connect(self.admin_requested.emit)
        self.admin_icon_btn.setCursor(Qt.PointingHandCursor)
        self.admin_icon_btn.setFixedSize(ph(36), ph(36))
        self.admin_icon_btn.setVisible(False)
        header_layout.addWidget(self.admin_icon_btn)

        self.main_layout.addWidget(header_widget)

        # ── Status / Instruction / Feedback labels ─────────────────────
        self.status_label = QLabel("Starting...")
        self.status_label.setObjectName("status")
        self.status_label.setAlignment(Qt.AlignCenter)
        self.status_label.setWordWrap(True)
        self.main_layout.addWidget(self.status_label)

        self.instruction_label = QLabel("")
        self.instruction_label.setObjectName("instruction")
        self.instruction_label.setAlignment(Qt.AlignCenter)
        self.instruction_label.setWordWrap(True)
        self.instruction_label.setVisible(False)
        self.main_layout.addWidget(self.instruction_label)

        self.feedback_label = QLabel("")
        self.feedback_label.setObjectName("feedback")
        self.feedback_label.setAlignment(Qt.AlignCenter)
        self.feedback_label.setWordWrap(True)
        self.feedback_label.setVisible(False)
        self.main_layout.addWidget(self.feedback_label)

        # ── Stacked widget: welcome screen ↔ camera feed ──────────────
        self.display_stack = QStackedWidget()

        # Welcome screen (index 0)
        self.welcome_widget = WelcomeScreen()
        self.display_stack.addWidget(self.welcome_widget)

        # Camera label (index 1)
        self.camera_label = QLabel()
        self.camera_label.setObjectName("camera")
        self.camera_label.setAlignment(Qt.AlignCenter)
        self.camera_label.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Ignored)
        self.camera_label.setMinimumHeight(ph(340))
        self.camera_label.setMaximumHeight(ph(760))
        self.display_stack.addWidget(self.camera_label)

        self.display_stack.setCurrentIndex(0)
        self.main_layout.addWidget(self.display_stack, stretch=1)

        # ── Action buttons container ───────────────────────────────────
        self.button_frame = QFrame()
        self.button_frame.setObjectName("buttonContainer")
        self.button_layout = QGridLayout(self.button_frame)
        self.button_layout.setHorizontalSpacing(pw(8))
        self.button_layout.setVerticalSpacing(ph(8))
        self.button_layout.setContentsMargins(pw(10), ph(15), pw(10), ph(10))

        btn_h = ph(50)

        self.time_in_btn = QPushButton("🕐 TIME IN")
        self.time_in_btn.setObjectName("timeIn")
        self.time_in_btn.clicked.connect(self.handle_time_in)
        self.time_in_btn.setCursor(Qt.PointingHandCursor)
        self.time_in_btn.setMinimumHeight(btn_h)

        self.time_out_btn = QPushButton("🕐 TIME OUT")
        self.time_out_btn.setObjectName("timeOut")
        self.time_out_btn.clicked.connect(self.handle_time_out)
        self.time_out_btn.setCursor(Qt.PointingHandCursor)
        self.time_out_btn.setMinimumHeight(btn_h)

        self.break_in_btn = QPushButton("☕ BREAK START")
        self.break_in_btn.setObjectName("breakIn")
        self.break_in_btn.clicked.connect(self.handle_break_in)
        self.break_in_btn.setCursor(Qt.PointingHandCursor)
        self.break_in_btn.setMinimumHeight(btn_h)

        self.break_out_btn = QPushButton("☕ BREAK END")
        self.break_out_btn.setObjectName("breakOut")
        self.break_out_btn.clicked.connect(self.handle_break_out)
        self.break_out_btn.setCursor(Qt.PointingHandCursor)
        self.break_out_btn.setMinimumHeight(btn_h)

        self.job_in_btn = QPushButton("💼 JOB START")
        self.job_in_btn.setObjectName("jobIn")
        self.job_in_btn.clicked.connect(self.handle_job_in)
        self.job_in_btn.setCursor(Qt.PointingHandCursor)
        self.job_in_btn.setMinimumHeight(btn_h)

        self.job_out_btn = QPushButton("💼 JOB END")
        self.job_out_btn.setObjectName("jobOut")
        self.job_out_btn.clicked.connect(self.handle_job_out)
        self.job_out_btn.setCursor(Qt.PointingHandCursor)
        self.job_out_btn.setMinimumHeight(btn_h)

        self.all_action_buttons = [
            self.time_in_btn, self.time_out_btn,
            self.break_in_btn, self.break_out_btn,
            self.job_in_btn, self.job_out_btn
        ]

        self.button_frame.setFixedHeight(ph(300))
        self.button_frame.setVisible(False)
        self.main_layout.addWidget(self.button_frame)

        self.update_styles()

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
            QWidget {{ background-color: #0d0d1a; }}
            QWidget#headerBar {{ background-color: transparent; }}
            QLabel#title {{
                color: #ffffff; font-size: {_pf(15)}px; font-weight: bold;
                padding: {_ph(2)}px; letter-spacing: 1px; background: transparent;
            }}
            QLabel#status {{
                color: #00ff88; font-size: {_pf(12)}px;
                padding: {_ph(2)}px; background: transparent;
            }}
            QLabel#instruction {{
                color: #00ff88; font-size: {_pf(14)}px; font-weight: bold;
                padding: {_ph(3)}px; background: transparent;
            }}
            QLabel#feedback {{
                color: #ffffff; font-size: {_pf(14)}px; font-weight: bold;
                padding: {_ph(3)}px; background: transparent;
            }}
            QLabel#camera {{
                background-color: #000000;
                border: 2px solid #1a3a5e;
                border-radius: {_pw(10)}px;
            }}
            QPushButton {{
                background-color: #1a1a2e;
                color: #ffffff;
                border: 2px solid #3a3a5e;
                border-radius: {_pw(8)}px;
                font-size: {_pf(13)}px;
                font-weight: bold;
                padding: {_ph(6)}px;
                min-height: {_ph(38)}px;
            }}
            QPushButton:hover {{ background-color: #252540; border-color: #00ff88; }}
            QPushButton:pressed {{ background-color: #111125; }}
            QPushButton#timeIn  {{ border-color: #4a90e2; border-left: 4px solid #4a90e2; }}
            QPushButton#timeOut {{ border-color: #e24a4a; border-left: 4px solid #e24a4a; }}
            QPushButton#breakIn {{ border-color: #f5a623; border-left: 4px solid #f5a623; }}
            QPushButton#breakOut{{ border-color: #ff8c00; border-left: 4px solid #ff8c00; }}
            QPushButton#jobIn   {{ border-color: #bd10e0; border-left: 4px solid #bd10e0; }}
            QPushButton#jobOut  {{ border-color: #9b10c0; border-left: 4px solid #9b10c0; }}
            QPushButton#addFace {{ border-color: #50c878; }}
            QPushButton#capture {{
                background-color: #1a3a6e; border-color: #4a90e2;
                font-size: {_pf(16)}px;
            }}
            QPushButton#cancelReg {{
                background-color: #3a1a1a; border-color: #e24a4a;
                font-size: {_pf(16)}px;
            }}
            QPushButton#adminIcon {{
                background-color: #2a1a00; border: 1px solid #ff8c00;
                border-radius: {_pw(18)}px;
                font-size: {_pf(14)}px; padding: 0;
            }}
            QPushButton#adminIcon:hover {{ background-color: #3a2500; }}
            QFrame#buttonContainer {{
                background-color: #080814;
                border-top: 2px solid #1a2a5e;
                padding: {_ph(4)}px;
            }}
            QProgressBar {{
                border: 2px solid #4a90e2; border-radius: {_pw(5)}px; text-align: center;
                color: #ffffff; font-weight: bold; min-height: {_ph(30)}px;
                font-size: {_pf(14)}px; background: #1a1a2e;
            }}
            QProgressBar::chunk {{ background-color: #00ff88; }}
        """)

        self.main_layout.setContentsMargins(_pw(8), _ph(4), _pw(8), _ph(4))
        self.main_layout.setSpacing(_ph(2))

        if self.feedback_label.text().startswith("✅"):
            self.feedback_label.setStyleSheet(
                f"color: #00ff88; font-size: {_pf(14)}px; font-weight: bold;"
                f" padding: {_ph(5)}px; background: transparent; border: none;"
            )
        elif self.feedback_label.text().startswith("❌"):
            self.feedback_label.setStyleSheet(
                f"color: #ff4444; font-size: {_pf(14)}px; font-weight: bold;"
                f" padding: {_ph(5)}px; background: transparent; border: none;"
            )

    def show_welcome_screen(self):
        """Switch to welcome screen when no face detected for 3 seconds"""
        print("📺 No face detected - showing welcome screen")
        self.display_stack.setCurrentIndex(0)
        print("🔴 Hiding buttons - no face detected (show_welcome_screen)")
        self.button_frame.setVisible(False)
        self.no_face_timeout = None
        if hasattr(self, 'welcome_widget'):
            self.welcome_widget.start_animation()

    def display_frame_on_label(self, frame_rgb):
        """Display frame"""
        display_frame(frame_rgb, self.camera_label)

    def _reset_face_confirmation(self):
        """Reset face confirmation state and return to live camera feed"""
        print("🔄 Resetting face confirmation")
        self.face_confirmed = False
        self.confirmed_person_name = None
        self.confirmed_person_similarity = 0.0
        self.confirmed_person_bbox = None
        self.confirmed_frame = None
        self.confirmation_start_time = None
        self.last_stable_person = None
        self.current_recognized_person = None
        self._buttons_shown_for_current_confirmation = None

        self.is_user_blocked = False
        self.blocked_message = ""
        self.last_synced_employee_id = None

        self.temporal_buffer.clear()

        if self.no_face_timeout:
            self.no_face_timeout.stop()
            self.no_face_timeout = None

        print("🔴 Hiding buttons - resetting face confirmation")
        self.button_frame.setVisible(False)

        self.show_welcome_screen()

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
        self.feedback_timer.start(int(config.IDENTITY_LOCK_TIME * 1000))

    def process_frame(self):
        """Process frame with face confirmation and freeze mechanism"""
        if self.latest_frame is None or self.processing:
            return

        # ★★★ SKIP PROCESSING IF EVENT IN PROGRESS ★★★
        if self.event_in_progress:
            if self.confirmed_frame is not None:
                self.display_frame_on_label(self.confirmed_frame)
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
                detected, recognized = self.face_recognizer.process_frame(frame_rgb, preprocess=True)
                has_face = bool(detected or recognized)

                if not has_face:
                    if self.no_face_timeout is None:
                        self.no_face_timeout = QTimer()
                        self.no_face_timeout.setSingleShot(True)
                        self.no_face_timeout.timeout.connect(self._reset_face_confirmation)
                        self.no_face_timeout.start(int(config.IDENTITY_LOCK_TIME * 1000))
                else:
                    if self.no_face_timeout:
                        self.no_face_timeout.stop()
                        self.no_face_timeout = None

                    if recognized:
                        current_person = recognized[0].get('name', 'Unknown')
                        if current_person != self.confirmed_person_name and current_person != 'Unknown':
                            print(f"👤 Different person detected: {current_person} (was: {self.confirmed_person_name})")
                            self._reset_face_confirmation()
                            self.processing = False
                            return

                if not self.button_frame.isVisible():
                    self.button_frame.setVisible(True)

                live_frame = frame_rgb.copy()
                if self.confirmed_person_bbox:
                    x, y, w, h = self.confirmed_person_bbox
                    draw_box_rgb(live_frame, x, y, x + w, y + h, CYAN_RGB, 6)
                banner_height = 80
                draw_filled_box_rgb(live_frame, 0, 0, live_frame.shape[1], banner_height, (0, 180, 120))
                name_text = f" {self.confirmed_person_name}"
                put_text_rgb(live_frame, name_text, 30, 50, (255, 255, 255), 2.0, 4)
                self.display_frame_on_label(live_frame)
                self.processing = False
                return
            # ★★★ END FROZEN FRAME LOGIC ★★★

            display_frame_local = frame_rgb.copy()

            # ★★★ WELCOME SCREEN LOGIC ★★★
            detected, recognized = self.face_recognizer.process_frame(frame_rgb, preprocess=True)
            has_face = bool(detected or recognized)

            if not self.registration_mode:
                self.admin_icon_btn.setVisible(has_face)

                if has_face:
                    if self.display_stack.currentIndex() == 0:
                        print("👤 Face detected - showing camera view (awaiting confirmation)")
                        self.display_stack.setCurrentIndex(1)
                        print("🔴 Hiding buttons - waiting for face confirmation")
                        self.button_frame.setVisible(False)
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
                            self.no_face_timeout.start(int(config.IDENTITY_LOCK_TIME * 1000))
            # ★★★ END WELCOME SCREEN LOGIC ★★★

            if self.registration_mode:
                self.processing = False
                return

            else:
                # Reuse already-computed detected/recognized results (no second call needed)
                if recognized:
                    person = recognized[0]
                    x, y, w, h = person['bbox']
                    raw_name = person['name']
                    similarity = person['similarity']
                    is_confident = person['is_confident']

                    # ★★★ TEMPORAL BUFFER INTEGRATION ★★★
                    self.temporal_buffer.add_result(raw_name, similarity)
                    consensus_name, agreement, is_stable = self.temporal_buffer.get_consensus()

                    if consensus_name and is_stable:
                        name = consensus_name
                        is_confident = agreement >= config.TEMPORAL_AGREEMENT_THRESHOLD
                    else:
                        name = raw_name

                    if consensus_name and consensus_name != raw_name and is_stable:
                        print(f"🔒 Anti-flicker: {raw_name} → {consensus_name} (agreement: {agreement:.0%})")

                    # ★★★ SMART LIVENESS LOGIC ★★★
                    liveness_ok = True
                    liveness_conf = 1.0

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
                            face_for_liveness = self.face_recognizer.extract_face_region(frame_rgb, person, align=False)
                            if face_for_liveness is not None:
                                face_small = cv2.resize(face_for_liveness, (64, 64))
                                liveness_ok, liveness_conf, details = self.face_recognizer.liveness_detector.check_liveness(face_small)
                        else:
                            liveness_ok = True
                            liveness_conf = 0.95

                    if is_confident and liveness_ok:
                        if self.unknown_person_start_time is not None:
                            print(f"✅ Known person detected, unknown timer reset")
                            self.unknown_person_start_time = None
                            self.unknown_person_embedding = None
                            self.unknown_person_id = None
                            self.update_button_visibility(None)

                        color_rgb = GREEN_RGB
                        self.current_recognized_person = name

                        if self.api_client and not self.face_confirmed:
                            self._sync_status_for_person(name)

                        # ★★★ FACE CONFIRMATION LOGIC ★★★
                        current_time = time.time()

                        if self.last_stable_person == name:
                            if self.confirmation_start_time is not None:
                                time_recognized = current_time - self.confirmation_start_time

                                if time_recognized >= self.CONFIRMATION_DELAY and not self.face_confirmed:
                                    print(f"✅ Face CONFIRMED: {name} ({similarity:.0%}) after {time_recognized:.1f}s")
                                    self.face_confirmed = True
                                    self.confirmed_person_name = name
                                    self.confirmed_person_similarity = similarity
                                    self.confirmed_person_bbox = (x, y, w, h)

                                    frozen = display_frame_local.copy()
                                    draw_box_rgb(frozen, x, y, x + w, y + h, CYAN_RGB, 6)
                                    banner_height = 120
                                    draw_filled_box_rgb(frozen, 0, 0, frozen.shape[1], banner_height, (0, 180, 120))
                                    name_text = f" {name}"
                                    put_text_rgb(frozen, name_text, 30, 70, (255, 255, 255), 2.0, 5)
                                    score_text = f"Confirmed : {similarity:.0%}"
                                    put_text_rgb(frozen, score_text, 30, 105, (200, 255, 220), 0.9, 2)
                                    instr_y = frozen.shape[0] - 40
                                    put_text_rgb(frozen, "Select an action below", frozen.shape[1]//2 - 180, instr_y, (255, 255, 255), 1.0, 2)

                                    self.confirmed_frame = frozen

                                    state_display = self.state_manager.get_state_display(name)
                                    self.status_label.setText(f"✅ CONFIRMED: {name} | {state_display}")

                                    if self.is_user_blocked:
                                        self.notification_overlay.show_notification(
                                            "⚠️ Action Blocked",
                                            self.blocked_message or "Action not allowed",
                                            "warning", 5000
                                        )
                                        print("🔴 Hiding buttons - user is blocked")
                                        self.button_frame.setVisible(False)
                                        QTimer.singleShot(4000, self._reset_face_confirmation)
                                    else:
                                        print("🔵 Setting button_frame.setVisible(True) - showing buttons")
                                        self.button_frame.setVisible(True)
                                        print(f"🔵 button_frame.isVisible() = {self.button_frame.isVisible()}")
                                        if not hasattr(self, '_buttons_shown_for_current_confirmation') or self._buttons_shown_for_current_confirmation != name:
                                            self._buttons_shown_for_current_confirmation = name
                                            self.update_button_visibility(name)

                                    self.display_frame_on_label(frozen)
                                    self.processing = False
                                    return
                            else:
                                self.confirmation_start_time = current_time
                        else:
                            self.last_stable_person = name
                            self.confirmation_start_time = current_time
                            self.face_confirmed = False
                            self.confirmed_person_name = None
                            self.confirmed_person_bbox = None
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
                        if self.face_confirmed:
                            self.update_button_visibility(name)

                    elif is_confident and not liveness_ok:
                        color_rgb = YELLOW_RGB
                        display_name = "👁️ Please Blink"
                        self.current_recognized_person = None
                        self.status_label.setText(f"👁️ {name} detected - Please blink")
                        name = display_name

                    else:
                        name = "Unknown"
                        color_rgb = RED_RGB
                        self.current_recognized_person = None

                        if getattr(config, 'ENABLE_MQTT_FEATURES', False):
                            current_time = time.time()
                            if self.unknown_person_start_time is None:
                                self.unknown_person_start_time = current_time
                                self.unknown_person_last_frame = frame_rgb.copy()
                                self.unknown_person_last_bbox = (x, y, w, h)
                                self.unknown_person_embedding = None
                                self.unknown_person_id = None
                                self.update_button_visibility(None)
                                self.button_frame.setVisible(True)
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
                            self.button_frame.setVisible(True)

                    draw_box_rgb(display_frame_local, x, y, x + w, y + h, color_rgb, 4)
                    draw_filled_box_rgb(display_frame_local, x, y - 70, x + w, y, color_rgb)
                    put_text_rgb(display_frame_local, name, x + 10, y - 40, BLACK_RGB, 1.0, 3)
                    put_text_rgb(display_frame_local, f"{similarity:.0%}", x + 10, y - 10, BLACK_RGB, 0.8, 2)

                elif detected:
                    face = detected[0]
                    x, y, w, h = face['bbox']
                    draw_box_rgb(display_frame_local, x, y, x + w, y + h, YELLOW_RGB, 4)
                    put_text_rgb(display_frame_local, "DETECTING...", x, y - 10, YELLOW_RGB, 0.7, 2)
                    self.current_recognized_person = None
                    self.status_label.setText("⏳ Detecting...")

                else:
                    if self.unknown_person_start_time is not None:
                        print("👤 Unknown person left frame, timer reset")
                        self.unknown_person_start_time = None
                        self.unknown_person_embedding = None
                        self.unknown_person_id = None
                        self.update_button_visibility(None)

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

                if self.display_stack.currentIndex() == 1:
                    self.display_frame_on_label(display_frame_local)

        except Exception as e:
            print(f"Processing error: {e}")
            import traceback
            traceback.print_exc()
        finally:
            self.processing = False

    def update_button_visibility(self, person_name):
        if not person_name:
            for btn in self.all_action_buttons:
                btn.setVisible(False)
            self.is_user_blocked = False
            self._rearrange_button_grid()
            return

        sync_result = self._sync_status_for_person(person_name, show_loading=True)
        print(f"🔵 _sync_status_for_person returned: {sync_result}")
        if not sync_result:
            print("🔴 USER BLOCKED - hiding all buttons in update_button_visibility")
            for btn in self.all_action_buttons:
                btn.setVisible(False)
            self._rearrange_button_grid()
            return

        can_time_in, _ = self.state_manager.can_time_in(person_name)
        can_time_out, _ = self.state_manager.can_time_out(person_name)
        can_break_start, _ = self.state_manager.can_break_start(person_name)
        can_break_end, _ = self.state_manager.can_break_end(person_name)
        can_job_start, _ = self.state_manager.can_job_start(person_name)
        can_job_end, _ = self.state_manager.can_job_end(person_name)

        print(f"🔵 Button visibility check for {person_name}: time_in={can_time_in}, time_out={can_time_out}, break_start={can_break_start}, break_end={can_break_end}, job_start={can_job_start}, job_end={can_job_end}")

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
        while self.button_layout.count():
            item = self.button_layout.takeAt(0)
            if item.widget():
                item.widget().setParent(None)

        visible_buttons = [btn for btn in self.all_action_buttons if btn.isVisible()]
        print(f"🔵 _rearrange_button_grid: {len(visible_buttons)} buttons visible, setting button_frame.setVisible({len(visible_buttons) > 0})")
        self.button_frame.setVisible(len(visible_buttons) > 0)
        print(f"🔵 After setVisible, button_frame.isVisible() = {self.button_frame.isVisible()}")

        num_visible = len(visible_buttons)
        for i, btn in enumerate(visible_buttons):
            row = i // 2
            col = i % 2
            if i == num_visible - 1 and col == 0:
                self.button_layout.addWidget(btn, row, 0, 1, 2)
            else:
                self.button_layout.addWidget(btn, row, col)
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

    def verify_and_log_action(self, action):
        """Verify and log with person locking and auto-fading success"""
        if not self.locked_person_for_action:
            self.notification_overlay.show_notification("Error", "No person locked!", "error", 1000)
            return

        self.event_in_progress = True
        dialog = SimpleConfirmationDialog(self, self.locked_person_for_action, action)

        if dialog.exec() == QDialog.Accepted:
            timestamp = datetime.now()

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
                        self.notification_overlay.show_notification("❌ Action Rejected", api_error, "error", 4000)
                        self.locked_person_for_action = None
                        self.locked_person_timestamp = None
                        self.event_in_progress = False
                        QTimer.singleShot(4000, self._reset_face_confirmation)
                        return
                except Exception as e:
                    print(f"⚠️ API validation error: {e}")

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
                            is_valid, msg, quality = self.face_recognizer.validate_face_sample(face_img, check_liveness=False)
                            if is_valid and quality >= 0.75:
                                embedding = self.face_recognizer.extract_embedding(face_img)
                                if embedding is not None:
                                    added = self.face_recognizer.add_embedding_to_existing_person(
                                        self.locked_person_for_action, embedding, max_embeddings=50)
                                    if added:
                                        self.adaptive_learning_count += 1
                except Exception as e:
                    print(f"Adaptive learning error: {e}")

            api_note = "Recorded" if self.api_client else "💾 Local"
            message = f"{action}\n{self.locked_person_for_action}\n{timestamp_str}\n{api_note}"
            self.notification_overlay.show_notification("Success", message, "success", 2000)
            if self.current_recognized_person:
                self.update_button_visibility(self.current_recognized_person)

            self.locked_person_for_action = None
            self.locked_person_timestamp = None
            self._reset_face_confirmation()

        else:
            self.locked_person_for_action = None
            self.locked_person_timestamp = None
            self.event_in_progress = False

    def log_action(self, action, person):
        """Log action to file AND send to API"""
        timestamp = datetime.now()
        timestamp_str = timestamp.strftime("%Y-%m-%d %H:%M:%S")
        log_entry = f"{timestamp_str} | {person} | {action}\n"
        print(f"📝 {log_entry.strip()}")

        try:
            with open("attendance_log.txt", "a") as f:
                f.write(log_entry)
        except Exception as e:
            print(f"⚠️ File logging error: {e}")

        if self.api_client:
            try:
                employee_id = self.face_recognizer.get_employee_id(person)
                self.api_client.send_attendance_event(
                    name=person, action=action, timestamp=timestamp, employee_id=employee_id)
            except Exception as e:
                print(f"⚠️ API send error: {e}")

        if self.api_client and hasattr(self, 'adaptive_learning_count'):
            if self.adaptive_learning_count % 5 == 0:
                stats = self.api_client.get_stats()
                print(f"📊 API Stats: Sent={stats['total_sent']}, Failed={stats['total_failed']}, Queued={stats['queued']}")

    def log_action_local_only(self, action, person, timestamp):
        """Log action to file only (API already sent separately)"""
        timestamp_str = timestamp.strftime("%Y-%m-%d %H:%M:%S")
        log_entry = f"{timestamp_str} | {person} | {action}\n"
        print(f"📝 {log_entry.strip()}")

        try:
            with open("attendance_log.txt", "a") as f:
                f.write(log_entry)
        except Exception as e:
            print(f"⚠️ File logging error: {e}")

    def _sync_status_for_person(self, person_name, show_loading=False):
        """Fetch and sync attendance status from server for a person with up to 3 retries."""
        current_time = time.time()
        employee_id = self.face_recognizer.get_employee_id(person_name)

        if (self.last_synced_employee_id == employee_id and
            current_time - self.last_status_sync_time < 5):
            print(f"🔵 _sync_status_for_person: using cached result, is_user_blocked={self.is_user_blocked}, returning {not self.is_user_blocked}")
            return not self.is_user_blocked

        if not employee_id or employee_id == "none":
            print(f"⚠️ No employee ID for {person_name} - using local state")
            self.is_user_blocked = False
            return True

        if show_loading:
            self.status_label.setText("🔄 Connecting to server...")
            QApplication.processEvents()

        max_retries = 3
        for attempt in range(max_retries):
            try:
                timestamp = int(datetime.now().timestamp())
                api_response = self.api_client.get_attendance_status(employee_id, timestamp)

                self.last_status_sync_time = current_time
                self.last_synced_employee_id = employee_id

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
                    time.sleep(0.5)
                    continue
                else:
                    print(f"❌ All {max_retries} attempts failed.")
                    if show_loading:
                        self.status_label.setText("⚠️ Server is Not Connected")
                        self.notification_overlay.show_notification("Error", "Server is Not Connected", "error", 2000)
                    self.is_user_blocked = False
                    return True

        return True

    def _sync_current_user_status(self):
        """Sync status from server for currently recognized person (called by timer)"""
        if self.current_recognized_person and self.api_client:
            self._sync_status_for_person(self.current_recognized_person)

    def _sync_all_users_on_startup(self):
        """Sync attendance status for all registered employees on startup"""
        if not self.api_client:
            return

        synced = 0
        failed = 0
        skipped = 0

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

    @Slot(str)
    def update_status(self, message):
        self.status_label.setText(message)

