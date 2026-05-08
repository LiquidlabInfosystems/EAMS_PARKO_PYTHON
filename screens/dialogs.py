#!/usr/bin/env python3
"""
Dialog classes for Attendance Kiosk GUI
- TextInputDialog
- AdminPasswordDialog
- SimpleConfirmationDialog
"""

from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel,
                               QPushButton, QFrame, QLineEdit)
from PySide6.QtCore import Qt

from screens.scaling import pw, ph, pf
from modules.ui_utils import VKLineEdit


class TextInputDialog(QDialog):
    """
    Compact styled text-input dialog using VKLineEdit.
    All dimensions scale with the actual screen resolution.
    """
    def __init__(self, parent=None, title="Enter Text", label="",
                 echo_mode=QLineEdit.Normal, placeholder=""):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setModal(True)
        if parent:
            self.setFixedSize(parent.window().size())
        else:
            self.showFullScreen()
        self.setWindowFlags(Qt.Dialog | Qt.FramelessWindowHint)
        self.setStyleSheet(f"""
            QDialog {{
                background-color: rgba(10, 10, 20, 220);
                border: none;
            }}
            QLabel {{
                color: #cbd5e1;
                font-size: {pf(14)}px;
                font-family: 'Inter', 'Segoe UI', sans-serif;
                background: transparent;
                border: none;
            }}
            VKLineEdit, QLineEdit {{
                background-color: #1e293b;
                color: #f1f5f9;
                border: 1px solid #334155;
                border-radius: {pw(10)}px;
                padding: {ph(10)}px {pw(14)}px;
                font-size: {pf(17)}px;
            }}
            QLineEdit:focus, VKLineEdit:focus {{ border-color: #3b82f6; }}
            QPushButton#btn_confirm {{
                background-color: #10b981; color: #fff;
                border: none; border-radius: {pw(10)}px;
                font-size: {pf(14)}px; font-weight: 700;
                font-family: 'Inter', 'Segoe UI', sans-serif;
                padding: {ph(12)}px;
            }}
            QPushButton#btn_confirm:pressed {{ background-color: #059669; }}
            QPushButton#btn_cancel {{
                background-color: transparent; color: #94a3b8;
                border: 1px solid #334155; border-radius: {pw(10)}px;
                font-size: {pf(14)}px;
                font-family: 'Inter', 'Segoe UI', sans-serif;
                padding: {ph(12)}px;
            }}
            QPushButton#btn_cancel:pressed {{ background-color: rgba(255,255,255,0.04); }}
        """)

        main_layout = QVBoxLayout(self)
        main_layout.addStretch(1)

        container = QFrame()
        container.setStyleSheet(f"""
            QFrame {{
                background-color: #0f172a;
                border: 1px solid #1e2d45;
                border-radius: {pw(20)}px;
            }}
        """)
        container.setMaximumWidth(pw(400))
        root = QVBoxLayout(container)
        root.setContentsMargins(pw(28), ph(32), pw(28), ph(28))
        root.setSpacing(ph(14))

        title_lbl = QLabel(title)
        title_lbl.setAlignment(Qt.AlignCenter)
        title_lbl.setStyleSheet(
            f"font-size: {pf(18)}px; font-weight: 700; color: #f1f5f9;"
            f" font-family: 'Inter','Segoe UI',sans-serif; border: none;"
        )
        root.addWidget(title_lbl)

        if label:
            lbl = QLabel(label)
            lbl.setAlignment(Qt.AlignCenter)
            root.addWidget(lbl)

        self.input = VKLineEdit()
        self.input.setPlaceholderText(placeholder or title)
        self.input.setEchoMode(echo_mode)
        self.input.returnPressed.connect(self.accept)
        root.addWidget(self.input)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(pw(10))
        cancel_btn = QPushButton("Cancel")
        cancel_btn.setObjectName("btn_cancel")
        cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(cancel_btn)
        confirm_btn = QPushButton("✓  OK")
        confirm_btn.setObjectName("btn_confirm")
        confirm_btn.clicked.connect(self.accept)
        btn_row.addWidget(confirm_btn)
        root.addLayout(btn_row)

        main_layout.addWidget(container, alignment=Qt.AlignCenter)
        main_layout.addStretch(1)

    def showEvent(self, event):
        super().showEvent(event)
        self.activateWindow()
        self.input.setFocus()
        VKLineEdit._show_keyboard()

    def hideEvent(self, event):
        super().hideEvent(event)
        VKLineEdit._hide_keyboard()

    def get_text(self) -> str:
        return self.input.text()


class AdminPasswordDialog(QDialog):
    """Admin-password modal. All sizes scale with screen resolution."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Admin Authentication")
        self.setModal(True)
        if parent:
            self.setFixedSize(parent.window().size())
        else:
            self.showFullScreen()
        self.setWindowFlags(Qt.Dialog | Qt.FramelessWindowHint)
        self.setStyleSheet(f"""
            QDialog {{
                background-color: rgba(10, 10, 20, 220);
                border: none;
            }}
            QLabel {{
                color: #cbd5e1;
                font-size: {pf(15)}px;
                font-family: 'Inter', 'Segoe UI', sans-serif;
                background: transparent;
                border: none;
            }}
            QLabel#dlg_error {{
                color: #f87171;
                font-size: {pf(12)}px;
                background-color: transparent;
                border: none;
            }}
            VKLineEdit, QLineEdit {{
                background-color: #1e293b;
                color: #f1f5f9;
                border: 1px solid #334155;
                border-radius: {pw(10)}px;
                padding: {ph(10)}px {pw(14)}px;
                font-size: {pf(20)}px;
                letter-spacing: 4px;
            }}
            VKLineEdit:focus, QLineEdit:focus {{ border-color: #3b82f6; }}
            QPushButton#btn_confirm {{
                background-color: #10b981; color: #fff;
                border: none; border-radius: {pw(10)}px;
                font-size: {pf(14)}px; font-weight: 700;
                font-family: 'Inter', 'Segoe UI', sans-serif;
                padding: {ph(12)}px;
            }}
            QPushButton#btn_confirm:pressed {{ background-color: #059669; }}
            QPushButton#btn_cancel {{
                background-color: transparent; color: #94a3b8;
                border: 1px solid #334155; border-radius: {pw(10)}px;
                font-size: {pf(14)}px;
                font-family: 'Inter', 'Segoe UI', sans-serif;
                padding: {ph(12)}px;
            }}
            QPushButton#btn_cancel:pressed {{ background-color: rgba(255,255,255,0.04); }}
        """)

        main_layout = QVBoxLayout(self)
        main_layout.addStretch(1)

        container = QFrame()
        container.setStyleSheet(f"""
            QFrame {{
                background-color: #0f172a;
                border: 1px solid #1e2d45;
                border-radius: {pw(20)}px;
            }}
        """)
        container.setMaximumWidth(pw(400))
        root = QVBoxLayout(container)
        root.setContentsMargins(pw(28), ph(32), pw(28), ph(28))
        root.setSpacing(ph(14))

        title = QLabel("🔐  Admin Authentication")
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet(
            f"font-size: {pf(18)}px; font-weight: 700; color: #f1f5f9;"
            f" font-family: 'Inter','Segoe UI',sans-serif; border: none;"
        )
        root.addWidget(title)

        self.password_input = VKLineEdit()
        self.password_input.setPlaceholderText("Enter admin password")
        self.password_input.setEchoMode(QLineEdit.Password)
        self.password_input.returnPressed.connect(self.accept)
        root.addWidget(self.password_input)

        self.error_label = QLabel("")
        self.error_label.setObjectName("dlg_error")
        self.error_label.setAlignment(Qt.AlignCenter)
        root.addWidget(self.error_label)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(pw(10))
        cancel_btn = QPushButton("Cancel")
        cancel_btn.setObjectName("btn_cancel")
        cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(cancel_btn)
        confirm_btn = QPushButton("✓  Confirm")
        confirm_btn.setObjectName("btn_confirm")
        confirm_btn.clicked.connect(self.accept)
        btn_row.addWidget(confirm_btn)
        root.addLayout(btn_row)

        main_layout.addWidget(container, alignment=Qt.AlignCenter)
        main_layout.addStretch(1)

    def showEvent(self, event):
        super().showEvent(event)
        self.activateWindow()
        self.password_input.setFocus()
        VKLineEdit._show_keyboard()

    def hideEvent(self, event):
        super().hideEvent(event)
        VKLineEdit._hide_keyboard()

    def get_password(self) -> str:
        return self.password_input.text()

    def show_error(self, message: str):
        self.error_label.setText(f"⚠  {message}")
        self.password_input.clear()
        self.password_input.setFocus()
        VKLineEdit._show_keyboard()


class SimpleConfirmationDialog(QDialog):
    """Confirmation dialog — all sizes scale with screen."""

    def __init__(self, parent, person_name, action):
        super().__init__(parent)
        self.person_name = person_name
        self.action = action
        self.no_face_timeout = None
        self.init_ui()

    def init_ui(self):
        self.setWindowTitle("Confirm Identity")
        self.setModal(True)
        self.setMinimumSize(pw(350), ph(200))

        self.setStyleSheet(f"""
            QDialog {{ background-color: #0a0a14; }}
            QLabel {{
                color: #cbd5e1;
                font-size: {pf(13)}px;
                font-family: 'Inter', 'Segoe UI', sans-serif;
                padding: {ph(4)}px;
                background: transparent;
                border: none;
            }}
            QLabel#title {{ color: #10b981; font-size: {pf(15)}px; font-weight: 700; }}
            QLabel#name  {{ color: #60a5fa; font-size: {pf(17)}px; font-weight: 700; }}
            QLabel#action {{ color: #f59e0b; font-size: {pf(12)}px; }}
            QPushButton {{
                color: #f1f5f9;
                border: 1px solid #1e2535;
                border-radius: {pw(10)}px;
                font-size: {pf(12)}px;
                font-weight: 700;
                font-family: 'Inter', 'Segoe UI', sans-serif;
                padding: {ph(10)}px {pw(16)}px;
                min-width: {pw(100)}px;
            }}
            QPushButton#confirm {{
                background-color: #10b981;
                border-color: #059669;
            }}
            QPushButton#confirm:pressed {{ background-color: #059669; }}
            QPushButton#cancel  {{
                background-color: rgba(239,68,68,0.12);
                border-color: #ef4444;
            }}
            QPushButton#cancel:pressed  {{ background-color: rgba(239,68,68,0.2); }}
        """)

        layout = QVBoxLayout(self)
        layout.setSpacing(ph(10))
        layout.setContentsMargins(pw(24), ph(24), pw(24), ph(24))

        title = QLabel("⚠ Confirm Your Identity")
        title.setObjectName("title")
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)

        name_label = QLabel(f"👤 {self.person_name}")
        name_label.setObjectName("name")
        name_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(name_label)

        action_label = QLabel(f"➡️ {self.action}")
        action_label.setObjectName("action")
        action_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(action_label)

        question = QLabel("Is this you?")
        question.setAlignment(Qt.AlignCenter)
        question.setStyleSheet(f"font-size: {pf(12)}px; color: #aaaaaa; background: transparent; border: none;")
        layout.addWidget(question)

        button_layout = QHBoxLayout()
        button_layout.setSpacing(pw(12))

        confirm_btn = QPushButton("✅ Yes, Confirm")
        confirm_btn.setObjectName("confirm")
        confirm_btn.clicked.connect(self.accept)
        button_layout.addWidget(confirm_btn)

        cancel_btn = QPushButton("❌ No, Cancel")
        cancel_btn.setObjectName("cancel")
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(cancel_btn)

        layout.addLayout(button_layout)
