#!/usr/bin/env python3
"""
Notification Overlay Widget
Auto-fading notification overlay - SQUARE SHAPE
"""

from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QFrame
from PySide6.QtCore import Qt, QTimer, QPropertyAnimation, QEasingCurve


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

        self.container_layout.setSpacing(_ph(6))

        self.container.setStyleSheet(f"""
            QFrame {{
                background-color: {self.bg_color};
                border: 2px solid {self.border_color};
                border-radius: {_pw(16)}px;
                padding: {_ph(14)}px {_pw(18)}px;
                min-width: {_pw(160)}px;
                max-width: {_pw(260)}px;
            }}
            QLabel {{
                color: #ffffff;
                background: transparent;
                border: none;
                font-family: 'Inter', 'Segoe UI', sans-serif;
            }}
        """)
        self.icon_label.setStyleSheet(f"font-size: {_pf(32)}px;")
        self.title_label.setStyleSheet(
            f"font-size: {_pf(15)}px; font-weight: 700;"
            f" font-family: 'Inter','Segoe UI',sans-serif;"
        )
        self.message_label.setStyleSheet(
            f"font-size: {_pf(11)}px; font-family: 'Inter','Segoe UI',sans-serif;"
        )

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
