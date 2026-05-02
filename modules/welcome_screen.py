#!/usr/bin/env python3
"""
Welcome Screen Module - Employee Attendance Management System
Light blue-gray background with diagonal stripes and professional design
"""

from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QHBoxLayout
from PySide6.QtCore import Qt, QTimer, QPropertyAnimation, QEasingCurve, Property, QDateTime
from PySide6.QtGui import QPainter, QColor, QFont, QPen, QBrush, QPixmap
import os
import math

# Import theme from config
try:
    import config
    THEME = config.THEME
except ImportError:
    # Fallback theme if config not available
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


class WelcomeScreen(QWidget):
    """Employee Attendance Management System Welcome Screen with professional theme"""

    def __init__(self, parent=None):
        super().__init__(parent)
        
        # Opacity for fade animations
        self._opacity = 1.0
        
        # Animation state for subtle pulse effect
        self.pulse_value = 0
        self.pulse_direction = 1
        
        # Animation timer for clock and effects - 10 FPS to reduce CPU load
        self.animation_timer = QTimer()
        self.animation_timer.timeout.connect(self._update_animation)
        self.animation_timer.start(100)  # 10 FPS (was 20 FPS @ 50ms)
        
        # Logo path (optional)
        self.logo_path = os.path.join(os.path.dirname(__file__), '..', 'assets', 'logo.png')
        self.logo_pixmap = None
        self._load_logo()
        
        # Setup UI
        self.init_ui()
        
    def _load_logo(self):
        """Load logo if available"""
        if os.path.exists(self.logo_path):
            self.logo_pixmap = QPixmap(self.logo_path)
            if not self.logo_pixmap.isNull():
                # Initial scale - will be refined in resizeEvent
                self.logo_pixmap = self.logo_pixmap.scaledToWidth(
                    300, Qt.SmoothTransformation
                )
        
    def init_ui(self):
        """Initialize the user interface"""
        # Main layout with 40px margins
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(40, 40, 40, 40)
        main_layout.setSpacing(0)
        
        # ===== CLOCK AT TOP =====
        clock_layout = QHBoxLayout()
        clock_layout.addStretch()
        
        # Time label
        self.time_label = QLabel()
        self.time_label.setAlignment(Qt.AlignCenter)
        self.time_label.setStyleSheet(f"""
            color: {THEME['text_primary']};
            font-size: 24px;
            font-weight: bold;
            font-family: 'Inter', 'SF Pro Display', 'Segoe UI', 'Roboto', sans-serif;
            background: transparent;
        """)
        clock_layout.addWidget(self.time_label)
        clock_layout.addStretch()
        
        main_layout.addLayout(clock_layout)
        main_layout.addSpacing(10)
        
        # Date label
        self.date_label = QLabel()
        self.date_label.setAlignment(Qt.AlignCenter)
        self.date_label.setStyleSheet(f"""
            color: {THEME['text_secondary']};
            font-size: 14px;
            font-weight: 400;
            font-family: 'Inter', 'SF Pro Display', 'Segoe UI', 'Roboto', sans-serif;
            background: transparent;
        """)
        main_layout.addWidget(self.date_label)
        
        # Update clock immediately
        self._update_clock()
        
        # Top stretch
        main_layout.addStretch(2)
        
        # Logo placeholder (drawn in paintEvent if available)
        if self.logo_pixmap:
            self.logo_label = QLabel()
            self.logo_label.setAlignment(Qt.AlignCenter)
            self.logo_label.setPixmap(self.logo_pixmap)
            self.logo_label.setStyleSheet("background: transparent;")
            main_layout.addWidget(self.logo_label)
            main_layout.addSpacing(20)
        
        # Subtitle - "Employee Attendance Management System"
        self.subtitle_label = QLabel("Employee Attendance Management System")
        self.subtitle_label.setAlignment(Qt.AlignCenter)
        self.subtitle_label.setStyleSheet(f"""
            color: {THEME['text_secondary']};
            font-size: 16px;
            font-weight: 500;
            font-family: 'Inter', 'SF Pro Display', 'Segoe UI', 'Roboto', sans-serif;
            padding: 5px;
            background: transparent;
        """)
        self.subtitle_label.setWordWrap(True)
        self.subtitle_label.setMinimumWidth(10)
        main_layout.addWidget(self.subtitle_label)
        
        # Stretch between logo/subtitle and welcome text
        main_layout.addStretch(2)
        
        # Welcome text - 90px bold dark blue
        self.title_label = QLabel("Welcome")
        self.title_label.setAlignment(Qt.AlignCenter)
        self.title_label.setStyleSheet(f"""
            color: {THEME['text_primary']};
            font-size: 32px;
            font-weight: bold;
            font-family: 'Inter', 'SF Pro Display', 'Segoe UI', 'Roboto', sans-serif;
            letter-spacing: 1px;
            padding: 5px;
            background: transparent;
        """)
        self.title_label.setWordWrap(True)
        self.title_label.setMinimumWidth(10)
        main_layout.addWidget(self.title_label)
        main_layout.addSpacing(30)
        
        # Instruction with styled container (will have pulse animation)
        self.instruction_label = QLabel("Position your face in front of the camera")
        self.instruction_label.setAlignment(Qt.AlignCenter)
        self.instruction_label.setStyleSheet(f"""
            color: {THEME['accent_secondary']};
            font-size: 14px;
            font-weight: 400;
            font-family: 'Inter', 'SF Pro Display', 'Segoe UI', 'Roboto', sans-serif;
            padding: 8px 15px;
            background: rgba(74, 144, 226, 0.1);
            border: 1px solid rgba(74, 144, 226, 0.3);
            border-radius: 8px;
        """)
        self.instruction_label.setWordWrap(True)
        self.instruction_label.setMinimumWidth(10)
        main_layout.addWidget(self.instruction_label)
        main_layout.addSpacing(20)
        
        # Status indicator
        self.status_label = QLabel("Waiting for face detection...")
        self.status_label.setAlignment(Qt.AlignCenter)
        self.status_label.setStyleSheet(f"""
            color: {THEME['text_secondary']};
            font-size: 18px;
            font-style: italic;
            padding: 10px;
            background: transparent;
        """)
        main_layout.addWidget(self.status_label)
        
        # Bottom stretch
        main_layout.addStretch(3)
    
    def _update_animation(self):
        """Update animation state and clock"""
        # Update clock
        self._update_clock()
        
        # Update pulse animation (0 to 100 and back)
        self.pulse_value += 2 * self.pulse_direction
        if self.pulse_value >= 100:
            self.pulse_direction = -1
        elif self.pulse_value <= 0:
            self.pulse_direction = 1
        
        # Trigger repaint for animation effects
        self.update()
    
    def _update_clock(self):
        """Update the clock display"""
        now = QDateTime.currentDateTime()
        self.time_label.setText(now.toString("hh:mm:ss AP"))
        self.date_label.setText(now.toString("dddd, MMMM d, yyyy"))
    
    def paintEvent(self, event):
        """Custom paint event for background with diagonal stripes"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        width = self.width()
        height = self.height()
        
        # Draw base background color
        painter.fillRect(0, 0, width, height, QColor(THEME['background_light']))
        
        # Draw diagonal stripes at 135 degrees
        self._draw_diagonal_stripes(painter, width, height)
        
        # Draw decorative animated element at bottom
        self._draw_bottom_decoration(painter, width, height)
        
        # Draw logo glow if logo exists (drawn behind the QLabel)
        if self.logo_pixmap and hasattr(self, 'logo_label'):
            self._draw_logo_glow(painter)
        
        painter.end()
    
    def _draw_diagonal_stripes(self, painter, width, height):
        """Draw subtle diagonal stripes at 135 degree angle"""
        stripe_color = QColor(30, 58, 95, 15)  # rgba(30, 58, 95, 0.06) - very subtle
        stripe_spacing = 40  # pixels between stripes
        stripe_width = 2  # pixels
        
        pen = QPen(stripe_color, stripe_width)
        painter.setPen(pen)
        
        # Draw lines from top-right to bottom-left (135 degree angle)
        start = -height
        end = width + height
        
        for offset in range(start, end, stripe_spacing):
            x1 = offset
            y1 = 0
            x2 = offset - height
            y2 = height
            painter.drawLine(x1, y1, x2, y2)
    
    def _draw_bottom_decoration(self, painter, width, height):
        """Draw animated decorative line at bottom"""
        y_base = height - 40
        
        # Animated gradient color based on pulse
        alpha = int(80 + 40 * math.sin(self.pulse_value * math.pi / 100))
        
        # Draw animated dots
        dot_color = QColor(THEME['accent_secondary'])
        dot_color.setAlpha(alpha)
        painter.setBrush(QBrush(dot_color))
        painter.setPen(Qt.NoPen)
        
        center_x = width // 2
        dot_spacing = 40
        dot_count = 5
        
        for i in range(-dot_count // 2, dot_count // 2 + 1):
            # Calculate dot size with pulse effect (center dot is largest)
            distance_from_center = abs(i)
            base_size = 20 - distance_from_center * 2
            pulse_effect = 4 * math.sin((self.pulse_value + i * 20) * math.pi / 100)
            size = max(6, base_size + pulse_effect)
            
            x = center_x + i * dot_spacing
            painter.drawEllipse(int(x - size/2), int(y_base - size/2), int(size), int(size))
    
    def _draw_logo_glow(self, painter):
        """Draw glow effect behind logo"""
        if not hasattr(self, 'logo_label') or not self.logo_pixmap:
            return
            
        # Get logo label geometry
        logo_rect = self.logo_label.geometry()
        center_x = logo_rect.center().x()
        center_y = logo_rect.center().y()
        
        # Draw glow circles with pulse effect
        glow_color = QColor(THEME['accent_secondary'])
        pulse_alpha = int(10 + 10 * math.sin(self.pulse_value * math.pi / 100))
        
        for i in range(3, 0, -1):
            alpha = pulse_alpha // i
            glow_color.setAlpha(alpha)
            painter.setBrush(QBrush(glow_color))
            painter.setPen(Qt.NoPen)
            radius = 230 + (i * 20)
            painter.drawEllipse(
                center_x - radius,
                center_y - radius,
                radius * 2,
                radius * 2
            )
    
    def set_instruction(self, text):
        """Update the instruction text"""
        self.instruction_label.setText(text)
    
    # Opacity property for fade animations
    def get_opacity(self):
        return self._opacity
    
    def set_opacity(self, value):
        self._opacity = value
        self.setWindowOpacity(value)
        self.update()
    
    opacity = Property(float, get_opacity, set_opacity)
    
    def fade_in(self, duration=300):
        """Fade in animation with OutCubic easing"""
        self.show()
        self._opacity = 0.0
        self.setWindowOpacity(0.0)
        
        self.fade_animation = QPropertyAnimation(self, b"opacity")
        self.fade_animation.setDuration(duration)
        self.fade_animation.setStartValue(0.0)
        self.fade_animation.setEndValue(1.0)
        self.fade_animation.setEasingCurve(QEasingCurve.OutCubic)
        self.fade_animation.start()
    
    def fade_out(self, duration=300):
        """Fade out animation with InCubic easing"""
        self.fade_animation = QPropertyAnimation(self, b"opacity")
        self.fade_animation.setDuration(duration)
        self.fade_animation.setStartValue(1.0)
        self.fade_animation.setEndValue(0.0)
        self.fade_animation.setEasingCurve(QEasingCurve.InCubic)
        self.fade_animation.finished.connect(self.hide)
        self.fade_animation.start()
    
    def stop_animation(self):
        """Stop any running animations"""
        if self.animation_timer.isActive():
            self.animation_timer.stop()

    def start_animation(self):
        """Start animations"""
        if not self.animation_timer.isActive():
            self.animation_timer.start(50)
    
    def resizeEvent(self, event):
        """Handle resize events - scale logo dynamically"""
        super().resizeEvent(event)
        
        # Scale logo to 70% of screen width if logo label exists
        if self.logo_pixmap and not self.logo_pixmap.isNull() and hasattr(self, 'logo_label'):
            target_width = int(self.width() * 0.7)
            scaled_logo = self.logo_pixmap.scaledToWidth(target_width, Qt.SmoothTransformation)
            self.logo_label.setPixmap(scaled_logo)
            
        self.update()
