
import subprocess
from PySide6.QtWidgets import QLineEdit
from PySide6.QtCore import Qt, QTimer

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

from PySide6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton

class KioskInputDialog(QDialog):
    """Custom input dialog that uses VKLineEdit for virtual keyboard support"""
    def __init__(self, title, label, initial_text="", parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setMinimumWidth(300)
        
        layout = QVBoxLayout(self)
        self.label = QLabel(label)
        layout.addWidget(self.label)
        
        self.line_edit = VKLineEdit(initial_text)
        layout.addWidget(self.line_edit)
        
        button_layout = QHBoxLayout()
        self.ok_button = QPushButton("OK")
        self.ok_button.clicked.connect(self.accept)
        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.clicked.connect(self.reject)
        
        button_layout.addWidget(self.ok_button)
        button_layout.addWidget(self.cancel_button)
        layout.addLayout(button_layout)
        
        self.setStyleSheet("""
            QDialog { background-color: #1a1a1a; border: 2px solid #00ff88; border-radius: 10px; }
            QLabel { color: #ffffff; font-size: 14px; margin-bottom: 5px; }
            QLineEdit { 
                background-color: #2d2d2d; color: #ffffff; border: 1px solid #4d4d4d; 
                border-radius: 5px; padding: 10px; font-size: 16px;
            }
            QPushButton {
                background-color: #2d2d2d; color: #ffffff; border: 1px solid #4d4d4d;
                border-radius: 5px; padding: 8px; min-width: 80px;
            }
            QPushButton:hover { border-color: #00ff88; }
        """)
        QTimer.singleShot(100, self.line_edit.setFocus)

    def text_value(self):
        return self.line_edit.text()

    @staticmethod
    def get_text(parent, title, label, initial_text=""):
        dialog = KioskInputDialog(title, label, initial_text, parent)
        if dialog.exec() == QDialog.Accepted:
            return dialog.text_value(), True
        return "", False
