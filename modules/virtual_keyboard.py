#!/usr/bin/env python3
"""
Built-in Virtual Keyboard for PySide6 Kiosk Applications
=========================================================
A modern, touch-friendly on-screen keyboard that works on any display server
(X11, Wayland, framebuffer). No external dependencies required.

Replaces the previous approach of spawning onboard/matchbox-keyboard/squeekboard
which broke after OS reinstalls and only worked on specific display servers.

Usage:
    from modules.virtual_keyboard import VKLineEdit, VirtualKeyboard
    # VKLineEdit auto-shows the keyboard on focus.
    # Or manage VirtualKeyboard manually via VirtualKeyboard.instance().
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QPushButton, QLineEdit, QApplication, QSizePolicy, QGraphicsOpacityEffect
)
from PySide6.QtCore import (
    Qt, Signal, QTimer, QPropertyAnimation, QEasingCurve, QRect, QPoint
)
from PySide6.QtGui import QFont


# ── KEYBOARD LAYOUTS ─────────────────────────────────────────────────────────

ROWS_LOWER = [
    ['1', '2', '3', '4', '5', '6', '7', '8', '9', '0'],
    ['q', 'w', 'e', 'r', 't', 'y', 'u', 'i', 'o', 'p'],
    ['a', 's', 'd', 'f', 'g', 'h', 'j', 'k', 'l'],
    ['⇧', 'z', 'x', 'c', 'v', 'b', 'n', 'm', '⌫'],
    ['#+=', ',', ' ', '.', '⏎'],
]

ROWS_UPPER = [
    ['1', '2', '3', '4', '5', '6', '7', '8', '9', '0'],
    ['Q', 'W', 'E', 'R', 'T', 'Y', 'U', 'I', 'O', 'P'],
    ['A', 'S', 'D', 'F', 'G', 'H', 'J', 'K', 'L'],
    ['⇧', 'Z', 'X', 'C', 'V', 'B', 'N', 'M', '⌫'],
    ['#+=', ',', ' ', '.', '⏎'],
]

ROWS_SYMBOLS = [
    ['!', '@', '#', '$', '%', '^', '&', '*', '(', ')'],
    ['-', '_', '=', '+', '[', ']', '{', '}', '|', '\\'],
    [':', ';', '"', "'", '<', '>', '/', '?', '~'],
    ['⇧', '`', '€', '£', '¥', '•', '…', '₹', '⌫'],
    ['ABC', ',', ' ', '.', '⏎'],
]

# Keys that get special wider sizing
WIDE_KEYS = {' ': 4.0, '⇧': 1.5, '⌫': 1.5, '⏎': 1.5, '#+=': 1.5, 'ABC': 1.5}

# ── THEME ─────────────────────────────────────────────────────────────────────

KB_STYLE = """
VirtualKeyboard {
    background-color: rgba(30, 30, 38, 245);
    border-top: 2px solid rgba(74, 144, 217, 0.5);
    border-top-left-radius: 12px;
    border-top-right-radius: 12px;
}
"""

def _key_style(font_size=16, is_special=False, is_action=False):
    """Generate stylesheet for a key button."""
    if is_action:  # Enter key
        return f"""
            QPushButton {{
                background-color: rgba(46, 204, 113, 200);
                color: #ffffff;
                border: 1px solid rgba(46, 204, 113, 120);
                border-radius: 6px;
                font-size: {font_size}px;
                font-weight: bold;
                padding: 2px;
            }}
            QPushButton:pressed {{
                background-color: rgba(39, 174, 96, 255);
                border-color: rgba(46, 204, 113, 200);
            }}
        """
    elif is_special:  # Shift, Backspace, Symbol toggle
        return f"""
            QPushButton {{
                background-color: rgba(74, 144, 217, 180);
                color: #ffffff;
                border: 1px solid rgba(74, 144, 217, 100);
                border-radius: 6px;
                font-size: {font_size}px;
                font-weight: bold;
                padding: 2px;
            }}
            QPushButton:pressed {{
                background-color: rgba(52, 108, 176, 255);
                border-color: rgba(74, 144, 217, 200);
            }}
        """
    else:  # Normal keys
        return f"""
            QPushButton {{
                background-color: rgba(60, 63, 78, 230);
                color: #e8edf2;
                border: 1px solid rgba(90, 95, 115, 150);
                border-radius: 6px;
                font-size: {font_size}px;
                padding: 2px;
            }}
            QPushButton:pressed {{
                background-color: rgba(74, 144, 217, 220);
                color: #ffffff;
                border-color: rgba(74, 144, 217, 200);
            }}
        """

# Active (toggled on) style for shift
def _shift_active_style(font_size=16):
    return f"""
        QPushButton {{
            background-color: rgba(46, 204, 113, 200);
            color: #ffffff;
            border: 2px solid rgba(46, 204, 113, 180);
            border-radius: 6px;
            font-size: {font_size}px;
            font-weight: bold;
            padding: 2px;
        }}
        QPushButton:pressed {{
            background-color: rgba(39, 174, 96, 255);
        }}
    """


class VirtualKeyboard(QWidget):
    """
    A modern, touch-friendly virtual keyboard overlay for PySide6 fullscreen apps.
    
    Singleton pattern: only one keyboard instance exists per application.
    Attach it to the main window and it positions itself at the bottom.
    """

    key_pressed = Signal(str)   # Emitted for character keys
    enter_pressed = Signal()     # Emitted when Enter/Return is pressed
    
    _instance = None

    def __init__(self, parent=None):
        super().__init__(parent)
        self._shift_on = False
        self._symbols_on = False
        self._target_input = None  # The QLineEdit that is currently focused
        self._key_buttons = []     # Store references for re-styling
        self._visible = False
        
        self.setObjectName("VirtualKeyboard")
        self.setStyleSheet(KB_STYLE)
        
        # Ensure we don't steal focus from the input field
        self.setFocusPolicy(Qt.NoFocus)
        self.setAttribute(Qt.WA_ShowWithoutActivating, True)
        
        self._build_ui()
        self.hide()

    @classmethod
    def instance(cls, parent=None):
        """Get or create the singleton keyboard instance."""
        if cls._instance is None or not cls._instance.isVisible() and cls._instance.parent() is None:
            cls._instance = cls(parent)
        # Re-parent if needed (e.g. called from a dialog with a different parent)
        if parent is not None and cls._instance.parent() != parent:
            cls._instance.setParent(parent)
        return cls._instance

    @classmethod
    def get_instance(cls):
        """Return existing instance or None — does NOT create a new one."""
        return cls._instance

    def _build_ui(self):
        """Construct the keyboard layout."""
        self._main_layout = QVBoxLayout(self)
        self._main_layout.setContentsMargins(4, 8, 4, 6)
        self._main_layout.setSpacing(4)
        self._rebuild_keys()

    def _rebuild_keys(self):
        """Build or rebuild all key rows based on current mode."""
        # Clear existing rows
        while self._main_layout.count():
            item = self._main_layout.takeAt(0)
            if item.layout():
                self._clear_layout(item.layout())
            elif item.widget():
                item.widget().deleteLater()

        self._key_buttons.clear()

        if self._symbols_on:
            rows = ROWS_SYMBOLS
        elif self._shift_on:
            rows = ROWS_UPPER
        else:
            rows = ROWS_LOWER

        parent_w = self.parent().width() if self.parent() else 480
        key_h = max(36, int(parent_w * 0.09))
        base_font_size = max(12, int(key_h * 0.42))

        for row in rows:
            row_layout = QHBoxLayout()
            row_layout.setContentsMargins(2, 0, 2, 0)
            row_layout.setSpacing(3)

            for key in row:
                btn = QPushButton(key)
                btn.setFocusPolicy(Qt.NoFocus)
                btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
                btn.setFixedHeight(key_h)
                btn.setCursor(Qt.PointingHandCursor)

                # Width stretch
                stretch = WIDE_KEYS.get(key, 1.0)

                # Styling
                is_special = key in ('⇧', '⌫', '#+=', 'ABC')
                is_action = key == '⏎'
                fs = base_font_size

                if key == '⇧' and self._shift_on and not self._symbols_on:
                    btn.setStyleSheet(_shift_active_style(fs))
                elif is_special:
                    btn.setStyleSheet(_key_style(fs, is_special=True))
                elif is_action:
                    btn.setStyleSheet(_key_style(fs, is_action=True))
                else:
                    btn.setStyleSheet(_key_style(fs))

                btn.clicked.connect(lambda checked, k=key: self._on_key_click(k))
                row_layout.addWidget(btn, int(stretch * 10))
                self._key_buttons.append(btn)

            self._main_layout.addLayout(row_layout)

    def _clear_layout(self, layout):
        """Recursively clear a layout."""
        while layout.count():
            item = layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
            elif item.layout():
                self._clear_layout(item.layout())

    def _on_key_click(self, key):
        """Handle a key press."""
        if key == '⇧':
            self._shift_on = not self._shift_on
            self._symbols_on = False
            self._rebuild_keys()
            return

        if key in ('#+=', 'ABC'):
            self._symbols_on = not self._symbols_on
            self._shift_on = False
            self._rebuild_keys()
            return

        if key == '⌫':
            if self._target_input:
                # Handle backspace — delete selected text or char before cursor
                if self._target_input.hasSelectedText():
                    self._target_input.del_()
                else:
                    self._target_input.backspace()
            return

        if key == '⏎':
            self.enter_pressed.emit()
            if self._target_input:
                self._target_input.returnPressed.emit()
            return

        # Regular character
        char = key if key != ' ' else ' '
        if self._target_input:
            self._target_input.insert(char)

        self.key_pressed.emit(char)

        # Auto-unshift after typing a character (like a phone keyboard)
        if self._shift_on and not self._symbols_on and key != ' ':
            self._shift_on = False
            self._rebuild_keys()

    def attach(self, line_edit):
        """Attach the keyboard to a specific QLineEdit."""
        self._target_input = line_edit

    def detach(self):
        """Detach from the current input."""
        self._target_input = None

    def show_keyboard(self):
        """Slide the keyboard up from the bottom."""
        if self._visible:
            return
        self._visible = True
        self._position_at_bottom()
        
        # Start off-screen (below bottom edge)
        final_geom = self.geometry()
        start_geom = QRect(final_geom.x(), final_geom.y() + final_geom.height(),
                           final_geom.width(), final_geom.height())
        self.setGeometry(start_geom)
        self.show()
        self.raise_()

        # Animate slide-up
        self._anim = QPropertyAnimation(self, b"geometry")
        self._anim.setDuration(200)
        self._anim.setStartValue(start_geom)
        self._anim.setEndValue(final_geom)
        self._anim.setEasingCurve(QEasingCurve.OutCubic)
        self._anim.start()

    def hide_keyboard(self):
        """Slide the keyboard down and hide."""
        if not self._visible:
            return
        self._visible = False

        current_geom = self.geometry()
        end_geom = QRect(current_geom.x(), current_geom.y() + current_geom.height(),
                         current_geom.width(), current_geom.height())

        self._anim = QPropertyAnimation(self, b"geometry")
        self._anim.setDuration(150)
        self._anim.setStartValue(current_geom)
        self._anim.setEndValue(end_geom)
        self._anim.setEasingCurve(QEasingCurve.InCubic)
        self._anim.finished.connect(self._on_hide_done)
        self._anim.start()

    def _on_hide_done(self):
        """Called after hide animation completes."""
        self.hide()
        self.detach()
        # Reset state
        self._shift_on = False
        self._symbols_on = False
        self._rebuild_keys()

    def _position_at_bottom(self):
        """Position the keyboard at the bottom of its parent widget."""
        parent = self.parent()
        if not parent:
            return
        pw = parent.width()
        # Keyboard height: ~45% of screen for good touch target on 7" display
        kb_h = max(200, int(parent.height() * 0.42))
        self.setGeometry(0, parent.height() - kb_h, pw, kb_h)
        # Rebuild keys to match new size
        self._rebuild_keys()


class VKLineEdit(QLineEdit):
    """
    A QLineEdit that automatically shows/hides the built-in VirtualKeyboard
    when it receives/loses focus. Drop-in replacement for QLineEdit.
    
    Works on X11, Wayland, framebuffer — no external dependencies.
    """
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
        # Delay hiding to handle tab-between-inputs without flickering
        if VKLineEdit._hide_timer is None:
            VKLineEdit._hide_timer = QTimer()
            VKLineEdit._hide_timer.setSingleShot(True)
            VKLineEdit._hide_timer.timeout.connect(VKLineEdit._do_hide_keyboard)
        VKLineEdit._hide_timer.start(250)

    def _show_keyboard(self):
        """Find the top-level window and show the virtual keyboard."""
        top = self._find_top_window()
        if not top:
            return
        kb = VirtualKeyboard.instance(top)
        kb.attach(self)
        kb.show_keyboard()

    @classmethod
    def _hide_keyboard(cls):
        """Class-level hide — can be called from anywhere (e.g. after dialog accept)."""
        kb = VirtualKeyboard.get_instance()
        if kb:
            kb.hide_keyboard()

    @classmethod
    def _do_hide_keyboard(cls):
        """Timer callback — hide only if no VKLineEdit has focus."""
        app = QApplication.instance()
        if app:
            focused = app.focusWidget()
            if isinstance(focused, VKLineEdit):
                # Another VKLineEdit got focus, re-attach keyboard to it
                kb = VirtualKeyboard.get_instance()
                if kb:
                    kb.attach(focused)
                return
        # No VKLineEdit has focus — hide the keyboard
        cls._hide_keyboard()

    def _find_top_window(self):
        """Walk up the widget tree to find the top-level window."""
        w = self.window()
        if w:
            return w
        # Fallback: walk parent chain
        w = self.parent()
        while w:
            if w.isWindow():
                return w
            w = w.parent()
        return None
