#!/usr/bin/env python3
"""
Attendance Screen - Main interface for marking attendance
"""

from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QPushButton, 
                               QFrame, QSizePolicy)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QImage, QPixmap
import numpy as np
import config

class AttendanceScreen(QWidget):
    """Screen for marking attendance with live camera and action buttons"""
    
    # Signals for actions
    admin_requested = Signal()
    action_clicked = Signal(str) # e.g., "timeIn", "timeOut"
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.init_ui()
        
    def init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(5)
        
        # Admin button row
        top_row = QHBoxLayout()
        top_row.addStretch()
        self.admin_btn = QPushButton("⚙️")
        self.admin_btn.setFixedSize(50, 50)
        self.admin_btn.clicked.connect(self.admin_requested.emit)
        self.admin_btn.setStyleSheet("""
            QPushButton {
                background-color: rgba(255, 255, 255, 0.1);
                border: 1px solid #4d4d4d;
                border-radius: 25px;
                font-size: 20px;
            }
        """)
        top_row.addWidget(self.admin_btn)
        main_layout.addLayout(top_row)
        
        # Camera display
        self.camera_label = QLabel()
        self.camera_label.setObjectName("camera")
        self.camera_label.setAlignment(Qt.AlignCenter)
        self.camera_label.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Ignored)
        self.camera_label.setMinimumHeight(350)
        main_layout.addWidget(self.camera_label, stretch=1)
        
        # Action buttons container
        self.button_frame = QFrame()
        self.button_frame.setObjectName("buttonContainer")
        self.button_layout = QGridLayout(self.button_frame)
        self.button_layout.setSpacing(10)
        
        self.time_in_btn = QPushButton("🕒 TIME IN")
        self.time_in_btn.setObjectName("timeIn")
        self.time_in_btn.clicked.connect(lambda: self.action_clicked.emit("timeIn"))
        
        self.time_out_btn = QPushButton("🕒 TIME OUT")
        self.time_out_btn.setObjectName("timeOut")
        self.time_out_btn.clicked.connect(lambda: self.action_clicked.emit("timeOut"))
        
        self.break_in_btn = QPushButton("☕ BREAK START")
        self.break_in_btn.setObjectName("breakIn")
        self.break_in_btn.clicked.connect(lambda: self.action_clicked.emit("breakIn"))
        
        self.break_out_btn = QPushButton("☕ BREAK END")
        self.break_out_btn.setObjectName("breakOut")
        self.break_out_btn.clicked.connect(lambda: self.action_clicked.emit("breakOut"))
        
        self.job_in_btn = QPushButton("💼 JOB START")
        self.job_in_btn.setObjectName("jobIn")
        self.job_in_btn.clicked.connect(lambda: self.action_clicked.emit("jobIn"))
        
        self.job_out_btn = QPushButton("💼 JOB END")
        self.job_out_btn.setObjectName("jobOut")
        self.job_out_btn.clicked.connect(lambda: self.action_clicked.emit("jobOut"))
        
        # Add to grid
        self.button_layout.addWidget(self.time_in_btn, 0, 0)
        self.button_layout.addWidget(self.time_out_btn, 0, 1)
        self.button_layout.addWidget(self.break_in_btn, 1, 0)
        self.button_layout.addWidget(self.break_out_btn, 1, 1)
        self.button_layout.addWidget(self.job_in_btn, 2, 0)
        self.button_layout.addWidget(self.job_out_btn, 2, 1)
        
        self.button_frame.setVisible(False)
        main_layout.addWidget(self.button_frame)
        
        self.update_styles()
        
    def update_styles(self):
        w, h = self.width(), self.height()
        def pf(n): return max(8, int(n * min(w, h) / 480))
        def pw(n): return max(1, int(n * w / 480))
        def ph(n): return max(1, int(n * h / 854))

        self.setStyleSheet(f"""
            QLabel#camera {{ background-color: #000000; border: 3px solid #00ff88; border-radius: {pw(10)}px; }}
            QPushButton {{
                background-color: #2d2d2d; color: #ffffff; border: 2px solid #4d4d4d;
                border-radius: {pw(8)}px; font-size: {pf(14)}px; font-weight: bold; padding: {ph(8)}px; min-height: {ph(40)}px;
            }}
            QPushButton:hover {{ background-color: #3d3d3d; border-color: #00ff88; }}
            QFrame#buttonContainer {{ background-color: #0d0d0d; border-top: 3px solid #00ff88; padding: {ph(5)}px; }}
        """)
        self.button_frame.setFixedHeight(ph(180))

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.update_styles()

    def display_frame(self, frame_rgb):
        if frame_rgb is None: return
        try:
            h, w, ch = frame_rgb.shape
            bytes_per_line = 3 * w
            qt_image = QImage(frame_rgb.data, w, h, bytes_per_line, QImage.Format_RGB888)
            pixmap = QPixmap.fromImage(qt_image)
            
            label_w = self.camera_label.width()
            label_h = self.camera_label.height()
            
            if label_w > 50:
                scaled_pixmap = pixmap.scaled(label_w, label_h, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                self.camera_label.setPixmap(scaled_pixmap)
            else:
                self.camera_label.setPixmap(pixmap)
        except Exception as e:
            print(f"Display error: {e}")
            
    def set_buttons_visible(self, visible):
        self.button_frame.setVisible(visible)
