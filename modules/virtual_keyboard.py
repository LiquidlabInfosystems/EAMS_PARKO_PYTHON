#!/usr/bin/env python3
"""
Built-in Virtual Keyboard for PySide6 Kiosk Applications
=========================================================
A modern, touch-friendly on-screen keyboard that works on any display server
(X11, Wayland, framebuffer). No external dependencies required.

Supports two modes:
  - ALPHANUMERIC (default): Full QWERTY with numbers, letters, symbols
  - NUMERIC: Compact numpad for PIN / passcode entry

Usage:
    from modules.virtual_keyboard import VKLineEdit, VirtualKeyboard

    # Alphanumeric (default)
    name_input = VKLineEdit()

    # Numeric-only (for passcodes)
    pin_input = VKLineEdit()
    pin_input.setProperty("keyboard_mode", "numeric")
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLineEdit, QApplication, QSizePolicy
)
from PySide6.QtCore import (
    Qt, Signal, QTimer, QPropertyAnimation, QEasingCurve, QRect
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

# Numeric-only keypad layout (for PIN / passcode)
ROWS_NUMERIC = [
    ['1', '2', '3'],
    ['4', '5', '6'],
    ['7', '8', '9'],
    ['⌫', '0', '⏎'],
]

# Keys that get special wider sizing (alphanumeric mode)
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

def _shift_active_style(font_size=16):
    """Active (toggled on) style for shift key."""
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


def _is_widget_alive(widget):
    """Check if a PySide6 widget's underlying C++ object is still alive."""
    if widget is None:
        return False
    try:
        widget.objectName()
        return True
    except RuntimeError:
        return False


# ── Keyboard modes ────────────────────────────────────────────────────────────
MODE_ALPHA = "alpha"
MODE_NUMERIC = "numeric"


class VirtualKeyboard(QWidget):
    """
    A modern, touch-friendly virtual keyboard overlay for PySide6 fullscreen apps.

    Supports two modes:
      - MODE_ALPHA:   Full QWERTY keyboard (default)
      - MODE_NUMERIC: Compact 3×4 numpad for PIN entry
    """

    key_pressed = Signal(str)
    enter_pressed = Signal()

    _instance = None

    def __init__(self, parent=None):
        super().__init__(parent)
        self._shift_on = False
        self._symbols_on = False
        self._mode = MODE_ALPHA
        self._target_input = None
        self._key_buttons = []
        self._visible = False

        self.setObjectName("VirtualKeyboard")
        self.setStyleSheet(KB_STYLE)

        self.setFocusPolicy(Qt.NoFocus)
        self.setAttribute(Qt.WA_ShowWithoutActivating, True)

        self._build_ui()
        self.hide()

    @classmethod
    def instance(cls, parent=None):
        """Get or create the keyboard instance for the given parent."""
        if not _is_widget_alive(cls._instance):
            cls._instance = None

        if cls._instance is None:
            cls._instance = cls(parent)
        elif parent is not None and cls._instance.parent() != parent:
            try:
                old = cls._instance
                old._visible = False
                old.hide()
                old.setParent(None)
                old.deleteLater()
            except RuntimeError:
                pass
            cls._instance = cls(parent)

        return cls._instance

    @classmethod
    def get_instance(cls):
        """Return existing instance or None."""
        if not _is_widget_alive(cls._instance):
            cls._instance = None
        return cls._instance

    def set_mode(self, mode):
        """Switch between MODE_ALPHA and MODE_NUMERIC."""
        if mode != self._mode:
            self._mode = mode
            self._shift_on = False
            self._symbols_on = False
            self._rebuild_keys()

    def _build_ui(self):
        self._main_layout = QVBoxLayout(self)
        self._main_layout.setContentsMargins(4, 6, 4, 8)
        self._main_layout.setSpacing(3)
        self._rebuild_keys()

    def _rebuild_keys(self):
        """Build or rebuild all key rows based on current mode."""
        while self._main_layout.count():
            item = self._main_layout.takeAt(0)
            if item.layout():
                self._clear_layout(item.layout())
            elif item.widget():
                item.widget().deleteLater()

        self._key_buttons.clear()

        if self._mode == MODE_NUMERIC:
            self._build_numeric_keys()
        else:
            self._build_alpha_keys()

    def _build_numeric_keys(self):
        """Build compact 3×4 numpad layout."""
        parent_w = self.parent().width() if self.parent() else 480
        # Numpad keys are bigger since there are fewer
        key_h = max(40, int(parent_w * 0.10))
        base_font_size = max(16, int(key_h * 0.50))

        for row in ROWS_NUMERIC:
            row_layout = QHBoxLayout()
            row_layout.setContentsMargins(int(parent_w * 0.15), 0, int(parent_w * 0.15), 0)
            row_layout.setSpacing(4)

            for key in row:
                if not key:  # Skip empty keys
                    continue
                btn = QPushButton(key)
                btn.setFocusPolicy(Qt.NoFocus)
                btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
                btn.setFixedHeight(key_h)
                btn.setCursor(Qt.PointingHandCursor)

                is_special = key == '⌫'
                is_action = key == '⏎'
                fs = base_font_size

                if is_special:
                    btn.setStyleSheet(_key_style(fs, is_special=True))
                elif is_action:
                    btn.setStyleSheet(_key_style(fs, is_action=True))
                else:
                    btn.setStyleSheet(_key_style(fs))

                btn.clicked.connect(lambda checked, k=key: self._on_key_click(k))
                row_layout.addWidget(btn)
                self._key_buttons.append(btn)

            self._main_layout.addLayout(row_layout)

    def _build_alpha_keys(self):
        """Build full QWERTY layout."""
        if self._symbols_on:
            rows = ROWS_SYMBOLS
        elif self._shift_on:
            rows = ROWS_UPPER
        else:
            rows = ROWS_LOWER

        parent_w = self.parent().width() if self.parent() else 480
        key_h = max(28, int(parent_w * 0.062))
        base_font_size = max(10, int(key_h * 0.45))

        for row in rows:
            row_layout = QHBoxLayout()
            row_layout.setContentsMargins(2, 0, 2, 0)
            row_layout.setSpacing(2)

            for key in row:
                btn = QPushButton(key)
                btn.setFocusPolicy(Qt.NoFocus)
                btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
                btn.setFixedHeight(key_h)
                btn.setCursor(Qt.PointingHandCursor)

                stretch = WIDE_KEYS.get(key, 1.0)
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
        while layout.count():
            item = layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
            elif item.layout():
                self._clear_layout(item.layout())

    def _on_key_click(self, key):
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
            if self._target_input and _is_widget_alive(self._target_input):
                if self._target_input.hasSelectedText():
                    self._target_input.del_()
                else:
                    self._target_input.backspace()
            return

        if key == '⏎':
            self.enter_pressed.emit()
            if self._target_input and _is_widget_alive(self._target_input):
                self._target_input.returnPressed.emit()
            return

        # Regular character
        if self._target_input and _is_widget_alive(self._target_input):
            self._target_input.insert(key)

        self.key_pressed.emit(key)

        # Auto-unshift after typing (phone-style)
        if self._shift_on and not self._symbols_on and key != ' ':
            self._shift_on = False
            self._rebuild_keys()

    def attach(self, line_edit):
        self._target_input = line_edit

    def detach(self):
        self._target_input = None

    def show_keyboard(self):
        if self._visible:
            return
        self._visible = True
        self._position_at_bottom()

        final_geom = self.geometry()
        start_geom = QRect(final_geom.x(), final_geom.y() + final_geom.height(),
                           final_geom.width(), final_geom.height())
        self.setGeometry(start_geom)
        self.show()
        self.raise_()

        self._anim = QPropertyAnimation(self, b"geometry")
        self._anim.setDuration(180)
        self._anim.setStartValue(start_geom)
        self._anim.setEndValue(final_geom)
        self._anim.setEasingCurve(QEasingCurve.OutCubic)
        self._anim.start()

    def hide_keyboard(self):
        if not self._visible:
            return
        self._visible = False

        current_geom = self.geometry()
        end_geom = QRect(current_geom.x(), current_geom.y() + current_geom.height(),
                         current_geom.width(), current_geom.height())

        self._anim = QPropertyAnimation(self, b"geometry")
        self._anim.setDuration(120)
        self._anim.setStartValue(current_geom)
        self._anim.setEndValue(end_geom)
        self._anim.setEasingCurve(QEasingCurve.InCubic)
        self._anim.finished.connect(self._on_hide_done)
        self._anim.start()

    def _on_hide_done(self):
        self.hide()
        self.detach()
        self._shift_on = False
        self._symbols_on = False

    def _position_at_bottom(self):
        """Position the keyboard at the bottom of its parent, with safe margin."""
        parent = self.parent()
        if not parent:
            return
        pw = parent.width()
        ph = parent.height()

        # Large bottom margin to prevent clipping on 7" touchscreen
        bottom_margin = max(20, int(ph * 0.04))

        if self._mode == MODE_NUMERIC:
            # Compact numpad: ~25% of screen
            kb_h = max(160, int(ph * 0.25))
        else:
            # Full keyboard: ~28% of screen
            kb_h = max(170, int(ph * 0.28))

        self.setGeometry(0, ph - kb_h - bottom_margin, pw, kb_h)
        self._rebuild_keys()


class VKLineEdit(QLineEdit):
    """
    A QLineEdit that auto-shows/hides the built-in VirtualKeyboard on focus.
    
    Set keyboard mode via property:
        line_edit.setProperty("keyboard_mode", "numeric")   # numpad only
        line_edit.setProperty("keyboard_mode", "alpha")      # full QWERTY (default)
    """
    _hide_timer = None

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setAttribute(Qt.WA_InputMethodEnabled, True)

    def focusInEvent(self, event):
        super().focusInEvent(event)
        if VKLineEdit._hide_timer and VKLineEdit._hide_timer.isActive():
            VKLineEdit._hide_timer.stop()
        self._show_keyboard()

    def focusOutEvent(self, event):
        super().focusOutEvent(event)
        if VKLineEdit._hide_timer is None:
            VKLineEdit._hide_timer = QTimer()
            VKLineEdit._hide_timer.setSingleShot(True)
            VKLineEdit._hide_timer.timeout.connect(VKLineEdit._do_hide_keyboard)
        VKLineEdit._hide_timer.start(300)

    def _get_keyboard_mode(self):
        """Read the keyboard_mode property, default to alpha."""
        mode = self.property("keyboard_mode")
        if mode == "numeric":
            return MODE_NUMERIC
        return MODE_ALPHA

    def _show_keyboard(self):
        top = self._find_top_window()
        if not top:
            return
        kb = VirtualKeyboard.instance(top)
        kb.set_mode(self._get_keyboard_mode())
        kb.attach(self)
        kb.show_keyboard()

    @classmethod
    def _hide_keyboard(cls):
        kb = VirtualKeyboard.get_instance()
        if kb:
            kb.hide_keyboard()

    @classmethod
    def _do_hide_keyboard(cls):
        app = QApplication.instance()
        if app:
            focused = app.focusWidget()
            if isinstance(focused, VKLineEdit):
                top = focused._find_top_window()
                if top:
                    kb = VirtualKeyboard.instance(top)
                    kb.set_mode(focused._get_keyboard_mode())
                    kb.attach(focused)
                    if not kb._visible:
                        kb.show_keyboard()
                return
        cls._hide_keyboard()

    def _find_top_window(self):
        w = self.window()
        if w:
            return w
        w = self.parent()
        while w:
            if w.isWindow():
                return w
            w = w.parent()
        return None
