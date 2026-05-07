#!/usr/bin/env python3
"""
User Registration GUI Page
Handles face registration with capture, validation, and progress tracking
"""

from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, 
                               QFrame, QProgressBar, QMessageBox)
from PySide6.QtCore import Qt, Signal, QTimer
from PySide6.QtGui import QImage, QPixmap
import numpy as np
import cv2


class RegistrationPage(QWidget):
    """Registration page with capture functionality"""
    
    # Signals
    registration_cancelled = Signal()
    registration_completed = Signal()
    
    def __init__(self, face_recognizer, notification_overlay, parent=None):
        super().__init__(parent)
        self.face_recognizer = face_recognizer
        self.notification_overlay = notification_overlay
        
        # Registration state
        self.registration_mode = False
        self.registration_person_name = ""
        self.registration_person_employee_id = None
        self.captured_faces = []
        self.current_registration_step = 0
        self.current_frame = None
        
        # Registration steps - 10 SAMPLES
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
        
        self.init_ui()
    
    def init_ui(self):
        """Initialize registration UI"""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(5)
        
        # Title
        self.title_label = QLabel("👤 Registering: ")
        self.title_label.setObjectName("title")
        self.title_label.setAlignment(Qt.AlignCenter)
        self.title_label.setWordWrap(True)
        self.title_label.setMinimumWidth(10)
        self.title_label.setVisible(False)
        main_layout.addWidget(self.title_label)
        
        # Instruction
        self.instruction_label = QLabel("")
        self.instruction_label.setObjectName("instruction")
        self.instruction_label.setAlignment(Qt.AlignCenter)
        self.instruction_label.setWordWrap(True)
        self.instruction_label.setMinimumWidth(10)
        self.instruction_label.setVisible(False)
        main_layout.addWidget(self.instruction_label)
        
        # Feedback
        self.feedback_label = QLabel("")
        self.feedback_label.setObjectName("feedback")
        self.feedback_label.setAlignment(Qt.AlignCenter)
        self.feedback_label.setWordWrap(True)
        self.feedback_label.setVisible(False)
        main_layout.addWidget(self.feedback_label)
        
        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setMinimum(0)
        self.progress_bar.setMaximum(len(self.registration_steps))
        self.progress_bar.setValue(0)
        self.progress_bar.setFormat(f"Accepted: %v of {len(self.registration_steps)}")
        self.progress_bar.setVisible(False)
        main_layout.addWidget(self.progress_bar)
        
        # Camera display area
        self.camera_label = QLabel()
        self.camera_label.setObjectName("camera")
        self.camera_label.setAlignment(Qt.AlignCenter)
        self.camera_label.setVisible(False)
        main_layout.addWidget(self.camera_label, stretch=1)
        
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
        
        self.cancel_reg_btn = QPushButton("✖ CANCEL")
        self.cancel_reg_btn.setObjectName("cancelReg")
        self.cancel_reg_btn.clicked.connect(self.cancel_registration)
        self.cancel_reg_btn.setCursor(Qt.PointingHandCursor)
        reg_button_layout.addWidget(self.cancel_reg_btn)
        
        self.reg_button_frame.setVisible(False)
        main_layout.addWidget(self.reg_button_frame)
        
        self.setLayout(main_layout)
    
    def start_registration(self, person_name, employee_id, display_stack):
        """Start a new registration session"""
        self.registration_mode = True
        self.registration_person_name = person_name
        self.registration_person_employee_id = employee_id
        self.captured_faces = []
        self.current_registration_step = 0
        
        # Show registration UI
        self.title_label.setText(f"👤 Registering: {person_name}")
        self.title_label.setVisible(True)
        self.instruction_label.setText(self.registration_steps[0]["instruction"])
        self.instruction_label.setVisible(True)
        self.progress_bar.setValue(0)
        self.progress_bar.setVisible(True)
        
        self.reg_button_frame.setVisible(True)
        self.capture_btn.setEnabled(True)
        
        # Switch to registration page in display stack
        if display_stack:
            display_stack.setCurrentIndex(2)  # Assuming index 2 is registration page
    
    def set_current_frame(self, frame_rgb):
        """Update current frame for processing"""
        self.current_frame = frame_rgb.copy()
    
    def display_camera_feed(self, frame_rgb):
        """Display current camera frame"""
        h, w, ch = frame_rgb.shape
        bytes_per_line = 3 * w
        qt_image = QImage(frame_rgb.data, w, h, bytes_per_line, QImage.Format_RGB888)
        pixmap = QPixmap.fromImage(qt_image)
        self.camera_label.setPixmap(pixmap)
        if not self.camera_label.isVisible():
            self.camera_label.setVisible(True)
    
    def show_feedback(self, message, is_success):
        """Show feedback message with auto-fade"""
        self.feedback_label.setText(message)
        self.feedback_label.setVisible(True)
        
        if is_success:
            self.feedback_label.setStyleSheet("color: #00ff88; font-weight: bold;")
        else:
            self.feedback_label.setStyleSheet("color: #ff4444; font-weight: bold;")
        
        # Auto-fade after 2 seconds
        QTimer.singleShot(2000, lambda: self.feedback_label.setVisible(False))
    
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
        
        final_samples = []
        for face_img in self.captured_faces:
            is_valid, msg, quality = self.face_recognizer.validate_face_sample(
                face_img, 
                check_liveness=False
            )
            if is_valid:
                final_samples.append(face_img)
        
        if len(final_samples) >= 8:
            success = self.face_recognizer.add_faces(
                final_samples, 
                self.registration_person_name, 
                self.registration_person_employee_id
            )
            
            if success:
                message = f"{self.registration_person_name} registered!\n{len(final_samples)} samples saved"
                self.notification_overlay.show_notification("Success", message, "success", 3000)
            else:
                self.notification_overlay.show_notification("Error", "Registration failed!", "error", 3000)
        else:
            message = f"Only {len(final_samples)}/10 samples passed check.\n\nPlease try again with better lighting."
            self.notification_overlay.show_notification("Warning", message, "warning", 3000)
        
        self.exit_registration_mode()
    
    def cancel_registration(self):
        """Cancel registration"""
        reply = QMessageBox.question(
            self, "Cancel", "Cancel registration?",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            self.exit_registration_mode()
    
    def exit_registration_mode(self):
        """Exit registration mode and cleanup"""
        self.registration_mode = False
        self.registration_person_name = ""
        self.registration_person_employee_id = None
        self.captured_faces = []
        self.current_registration_step = 0
        
        self.capture_btn.setEnabled(True)
        
        self.title_label.setVisible(False)
        self.instruction_label.setVisible(False)
        self.progress_bar.setVisible(False)
        self.feedback_label.setVisible(False)
        self.camera_label.setVisible(False)
        self.reg_button_frame.setVisible(False)
        
        self.registration_completed.emit()
