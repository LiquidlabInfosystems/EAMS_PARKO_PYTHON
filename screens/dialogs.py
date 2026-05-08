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
            self.setFixedSize(parent.size())
        else:
            self.showFullScreen()
        self.setWindowFlags(Qt.Dialog | Qt.FramelessWindowHint)
        self.setStyleSheet(f"""
            QDialog {{
                background-color: rgba(255, 255, 255, 230);
                border: none;
            }}
            QLabel {{ color: #333333; font-size: {pf(14)}px; }}
            VKLineEdit, QLineEdit {{
                background-color: #f9f9f9;
                color: #000000;
                border: 2px solid #dddddd;
                border-radius: {pw(8)}px;
                padding: {ph(8)}px {pw(12)}px;
                font-size: {pf(18)}px;
            }}
            QLineEdit:focus {{ border-color: #4a90e2; }}
            QPushButton#btn_confirm {{
                background-color: #00aa66; color: #fff;
                border: none; border-radius: {pw(8)}px;
                font-size: {pf(14)}px; font-weight: bold; padding: {ph(9)}px;
            }}
            QPushButton#btn_confirm:pressed {{ background-color: #008855; }}
            QPushButton#btn_cancel {{
                background-color: transparent; color: #666666;
                border: 1px solid #cccccc; border-radius: {pw(8)}px;
                font-size: {pf(14)}px; padding: {ph(9)}px;
            }}
            QPushButton#btn_cancel:pressed {{ background-color: #f0f0f0; }}
        """)

        main_layout = QVBoxLayout(self)
        main_layout.addStretch(1)

        container = QFrame()
        container.setStyleSheet(f"""
            QFrame {{
                background-color: #ffffff;
                border: 2px solid #e0e0e0;
                border-radius: {pw(12)}px;
            }}
        """)
        root = QVBoxLayout(container)
        root.setContentsMargins(pw(25), ph(25), pw(25), ph(25))
        root.setSpacing(ph(12))

        title_lbl = QLabel(title)
        title_lbl.setAlignment(Qt.AlignCenter)
        title_lbl.setStyleSheet(f"font-size: {pf(18)}px; font-weight: bold; color: #333333; border: none;")
        root.addWidget(title_lbl)

        if label:
            root.addWidget(QLabel(label))

        self.input = VKLineEdit()
        self.input.setPlaceholderText(placeholder or title)
        self.input.setEchoMode(echo_mode)
        self.input.returnPressed.connect(self.accept)
        root.addWidget(self.input)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(pw(8))
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

        self.input.setFocus()

    def get_text(self) -> str:
        return self.input.text()


class AdminPasswordDialog(QDialog):
    """Admin-password modal. All sizes scale with screen resolution."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Admin Authentication")
        self.setModal(True)
        if parent:
            self.setFixedSize(parent.size())
        else:
            self.showFullScreen()
        self.setWindowFlags(Qt.Dialog | Qt.FramelessWindowHint)
        self.setStyleSheet(f"""
            QDialog {{
                background-color: rgba(255, 255, 255, 230);
                border: none;
            }}
            QLabel {{ color: #333333; font-size: {pf(15)}px; }}
            QLabel#dlg_error {{ color: #E74C3C; font-size: {pf(12)}px; background-color: transparent; border: none; }}
            VKLineEdit, QLineEdit {{
                background-color: #f9f9f9;
                color: #000000;
                border: 2px solid #dddddd;
                border-radius: {pw(8)}px;
                padding: {ph(8)}px {pw(12)}px;
                font-size: {pf(20)}px;
                letter-spacing: 4px;
            }}
            VKLineEdit:focus, QLineEdit:focus {{ border-color: #4a90e2; }}
            QPushButton#btn_confirm {{
                background-color: #00aa66; color: #fff;
                border: none; border-radius: {pw(8)}px;
                font-size: {pf(14)}px; font-weight: bold; padding: {ph(9)}px;
            }}
            QPushButton#btn_confirm:pressed {{ background-color: #008855; }}
            QPushButton#btn_cancel {{
                background-color: transparent; color: #666666;
                border: 1px solid #cccccc; border-radius: {pw(8)}px;
                font-size: {pf(14)}px; padding: {ph(9)}px;
            }}
            QPushButton#btn_cancel:pressed {{ background-color: #f0f0f0; }}
        """)

        main_layout = QVBoxLayout(self)
        main_layout.addStretch(1)

        container = QFrame()
        container.setStyleSheet(f"""
            QFrame {{
                background-color: #ffffff;
                border: 2px solid #e0e0e0;
                border-radius: {pw(12)}px;
            }}
        """)
        root = QVBoxLayout(container)
        root.setContentsMargins(pw(25), ph(25), pw(25), ph(25))
        root.setSpacing(ph(12))

        title = QLabel("🔐  Admin Authentication")
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet(f"font-size: {pf(18)}px; font-weight: bold; color: #333333; border: none;")
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
        btn_row.setSpacing(pw(8))
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

        self.password_input.setFocus()

    def get_password(self) -> str:
        return self.password_input.text()

    def show_error(self, message: str):
        self.error_label.setText(f"⚠  {message}")
        self.password_input.clear()
        self.password_input.setFocus()


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
            QDialog {{ background-color: #1a1a1a; }}
            QLabel {{ color: #ffffff; font-size: {pf(14)}px; padding: {ph(6)}px; }}
            QLabel#title {{ color: #00ff88; font-size: {pf(16)}px; font-weight: bold; }}
            QLabel#name  {{ color: #4a90e2; font-size: {pf(18)}px; font-weight: bold; }}
            QLabel#action {{ color: #f5a623; font-size: {pf(12)}px; }}
            QPushButton {{
                color: #ffffff; border: 2px solid; border-radius: {pw(8)}px;
                font-size: {pf(12)}px; font-weight: bold;
                padding: {ph(8)}px {pw(16)}px; min-width: {pw(100)}px;
            }}
            QPushButton#confirm {{ background-color: #00aa66; border-color: #00ff88; }}
            QPushButton#confirm:hover {{ background-color: #00cc77; }}
            QPushButton#cancel  {{ background-color: #cc3333; border-color: #ff4444; }}
            QPushButton#cancel:hover  {{ background-color: #dd4444; }}
        """)

        layout = QVBoxLayout(self)
        layout.setSpacing(ph(10))
        layout.setContentsMargins(pw(20), ph(20), pw(20), ph(20))

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
        question.setStyleSheet(f"font-size: {pf(12)}px; color: #aaaaaa;")
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
