#!/usr/bin/env python3
"""
Admin Control Page for Face Database Management
"""

from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, 
                               QFrame, QMessageBox, QDialog, QLineEdit)
from PySide6.QtCore import Qt, Signal, QTimer
from modules.ui_utils import VKLineEdit, KioskInputDialog

class AdminScreen(QWidget):
    """Admin control page for managing face database"""
    
    # Signals
    home_requested = Signal()
    add_new_face_requested = Signal()
    list_faces_requested = Signal()
    
    def __init__(self, face_recognizer, parent=None):
        super().__init__(parent)
        self.face_recognizer = face_recognizer
        self.init_ui()
    
    def init_ui(self):
        self.setStyleSheet("""
            QWidget { background-color: #1a1a1a; }
            QLabel#title { font-size: 20px; font-weight: bold; color: #00ff88; padding: 20px; }
            QPushButton {
                background-color: #2d2d2d; color: #ffffff; border: 2px solid #4d4d4d;
                border-radius: 8px; font-size: 14px; font-weight: bold; padding: 12px; 
                min-height: 50px;
            }
            QPushButton:hover { background-color: #3d3d3d; border-color: #00ff88; }
        """)
        
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(15)
        
        title = QLabel("🔧 Admin Control Panel")
        title.setObjectName("title")
        title.setAlignment(Qt.AlignCenter)
        main_layout.addWidget(title)
        
        buttons_layout = QVBoxLayout()
        buttons_layout.setSpacing(10)
        
        self.list_faces_btn = QPushButton("📋 List All Faces")
        self.list_faces_btn.clicked.connect(self.list_faces_requested.emit)
        buttons_layout.addWidget(self.list_faces_btn)
        
        self.add_face_btn = QPushButton("🆕 Add New Face")
        self.add_face_btn.clicked.connect(self.add_new_face_requested.emit)
        self.add_face_btn.setStyleSheet("QPushButton { background-color: #50c878; }")
        buttons_layout.addWidget(self.add_face_btn)
        
        self.home_btn = QPushButton("🏠 Home")
        self.home_btn.clicked.connect(self.home_requested.emit)
        self.home_btn.setStyleSheet("QPushButton { background-color: #00aa44; }")
        
        main_layout.addLayout(buttons_layout)
        main_layout.addStretch(1)
        main_layout.addWidget(self.home_btn)
