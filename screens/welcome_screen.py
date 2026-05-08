#!/usr/bin/env python3
"""
Welcome Screen Module - Employee Attendance Management System
"""

from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QHBoxLayout, QPushButton
from PySide6.QtCore import Qt, QTimer, Property, QDateTime, Signal
from PySide6.QtGui import QPainter, QColor, QFont, QPen, QBrush, QPixmap
import os
import math
import config

THEME = getattr(config, 'THEME', {
    "background_light": "#F0F4F8",
    "background_medium": "#E8EDF2",
    "accent_primary": "#1E3A5F",
    "accent_secondary": "#4A90D9",
    "text_primary": "#1E3A5F",
    "text_secondary": "#5A7A9A",
    "success": "#2ECC71",
    "warning": "#F39C12",
    "error": "#E74C3C",
})

class WelcomeScreen(QWidget):
    """Employee Attendance Management System Welcome Screen with professional theme"""
    admin_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._opacity = 1.0
        self.pulse_value = 0
        self.pulse_direction = 1
        
        self.animation_timer = QTimer()
        self.animation_timer.timeout.connect(self._update_animation)
        self.animation_timer.start(100)
        
        self.logo_path = os.path.join(os.path.dirname(__file__), '..', 'assets', 'logo.png')
        self.logo_pixmap = None
        self._load_logo()
        self.init_ui()
        
    def _load_logo(self):
        if os.path.exists(self.logo_path):
            self.logo_pixmap = QPixmap(self.logo_path)
            if not self.logo_pixmap.isNull():
                self.logo_pixmap = self.logo_pixmap.scaledToWidth(300, Qt.SmoothTransformation)
        
    def init_ui(self):
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(40, 40, 40, 40)
        self.main_layout.setSpacing(0)
        
        # Top bar for Admin button
        top_bar = QHBoxLayout()
        top_bar.addStretch()
        self.admin_btn = QPushButton("⚙️")
        self.admin_btn.setObjectName("adminBtn")
        self.admin_btn.setFixedSize(50, 50)
        self.admin_btn.clicked.connect(self.admin_requested.emit)
        top_bar.addWidget(self.admin_btn)
        self.main_layout.addLayout(top_bar)
        
        clock_layout = QHBoxLayout()
        clock_layout.addStretch()
        
        self.time_label = QLabel()
        self.time_label.setAlignment(Qt.AlignCenter)
        clock_layout.addWidget(self.time_label)
        clock_layout.addStretch()
        
        self.main_layout.addLayout(clock_layout)
        self.main_layout.addSpacing(10)
        
        self.date_label = QLabel()
        self.date_label.setAlignment(Qt.AlignCenter)
        self.main_layout.addWidget(self.date_label)
        self._update_clock()
        
        self.main_layout.addStretch(2)
        
        if self.logo_pixmap:
            self.logo_label = QLabel()
            self.logo_label.setAlignment(Qt.AlignCenter)
            self.logo_label.setPixmap(self.logo_pixmap)
            self.logo_label.setStyleSheet("background: transparent;")
            self.main_layout.addWidget(self.logo_label)
            self.main_layout.addSpacing(20)
        
        self.subtitle_label = QLabel("Employee Attendance Management System")
        self.subtitle_label.setAlignment(Qt.AlignCenter)
        self.subtitle_label.setWordWrap(True)
        self.main_layout.addWidget(self.subtitle_label)
        
        self.main_layout.addStretch(2)
        
        self.title_label = QLabel("Welcome")
        self.title_label.setAlignment(Qt.AlignCenter)
        self.title_label.setWordWrap(True)
        self.main_layout.addWidget(self.title_label)
        self.main_layout.addSpacing(30)
        
        self.instruction_label = QLabel("Position your face in front of the camera")
        self.instruction_label.setAlignment(Qt.AlignCenter)
        self.instruction_label.setWordWrap(True)
        self.main_layout.addWidget(self.instruction_label)
        self.main_layout.addSpacing(20)
        
        self.status_label = QLabel("Waiting for face detection...")
        self.status_label.setAlignment(Qt.AlignCenter)
        self.main_layout.addWidget(self.status_label)
        
        self.main_layout.addStretch(3)
        self.update_styles()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.update_styles()
        if self.logo_pixmap and not self.logo_pixmap.isNull() and hasattr(self, 'logo_label'):
            target_width = int(self.width() * 0.7)
            scaled_logo = self.logo_pixmap.scaledToWidth(target_width, Qt.SmoothTransformation)
            self.logo_label.setPixmap(scaled_logo)

    def update_styles(self):
        w, h = self.width(), self.height()
        def pf(n): return max(8, int(n * min(w, h) / 480))
        def pw(n): return max(1, int(n * w / 480))
        def ph(n): return max(1, int(n * h / 854))

        self.main_layout.setContentsMargins(pw(40), ph(40), pw(40), ph(40))
        self.time_label.setStyleSheet(f"color: {THEME['text_primary']}; font-size: {pf(24)}px; font-weight: bold; background: transparent;")
        self.date_label.setStyleSheet(f"color: {THEME['text_secondary']}; font-size: {pf(14)}px; font-weight: 400; background: transparent;")
        self.subtitle_label.setStyleSheet(f"color: {THEME['text_secondary']}; font-size: {pf(16)}px; font-weight: 500; padding: {ph(5)}px; background: transparent;")
        self.title_label.setStyleSheet(f"color: {THEME['text_primary']}; font-size: {pf(32)}px; font-weight: bold; padding: {ph(5)}px; background: transparent;")
        self.instruction_label.setStyleSheet(f"color: {THEME['accent_secondary']}; font-size: {pf(14)}px; font-weight: 400; padding: {ph(8)}px {pw(15)}px; background: rgba(74, 144, 226, 0.1); border: 1px solid rgba(74, 144, 226, 0.3); border-radius: {pw(8)}px;")
        self.status_label.setStyleSheet(f"color: {THEME['text_secondary']}; font-size: {pf(18)}px; font-style: italic; padding: {ph(10)}px; background: transparent;")
        self.admin_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: rgba(30, 58, 95, 0.1);
                border: 1px solid rgba(30, 58, 95, 0.2);
                border-radius: 25px;
                font-size: 24px;
                color: {THEME['text_secondary']};
            }}
            QPushButton:hover {{
                background-color: rgba(30, 58, 95, 0.2);
                border-color: {THEME['accent_secondary']};
            }}
        """)

    def _update_animation(self):
        self._update_clock()
        self.pulse_value += 2 * self.pulse_direction
        if self.pulse_value >= 100: self.pulse_direction = -1
        elif self.pulse_value <= 0: self.pulse_direction = 1
        self.update()
    
    def _update_clock(self):
        now = QDateTime.currentDateTime()
        self.time_label.setText(now.toString("hh:mm:ss AP"))
        self.date_label.setText(now.toString("dddd, MMMM d, yyyy"))
    
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        width, height = self.width(), self.height()
        painter.fillRect(0, 0, width, height, QColor(THEME['background_light']))
        self._draw_diagonal_stripes(painter, width, height)
        self._draw_bottom_decoration(painter, width, height)
        painter.end()
    
    def _draw_diagonal_stripes(self, painter, width, height):
        stripe_color = QColor(30, 58, 95, 15)
        pen = QPen(stripe_color, 2)
        painter.setPen(pen)
        for offset in range(-height, width + height, 40):
            painter.drawLine(offset, 0, offset - height, height)
    
    def _draw_bottom_decoration(self, painter, width, height):
        y_base = height - 40
        alpha = int(80 + 40 * math.sin(self.pulse_value * math.pi / 100))
        dot_color = QColor(THEME['accent_secondary'])
        dot_color.setAlpha(alpha)
        painter.setBrush(QBrush(dot_color))
        painter.setPen(Qt.NoPen)
        center_x = width // 2
        for i in range(-2, 3):
            size = max(6, (20 - abs(i) * 2) + 4 * math.sin((self.pulse_value + i * 20) * math.pi / 100))
            painter.drawEllipse(int(center_x + i * 40 - size/2), int(y_base - size/2), int(size), int(size))
    
    def set_instruction(self, text):
        self.instruction_label.setText(text)
    
    def stop_animation(self):
        if self.animation_timer.isActive(): self.animation_timer.stop()

    def start_animation(self):
        if not self.animation_timer.isActive(): self.animation_timer.start(100)
