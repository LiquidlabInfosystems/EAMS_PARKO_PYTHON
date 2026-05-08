#!/usr/bin/env python3
"""
Face List Screen for viewing and managing registered faces
"""

from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, 
                               QListWidget, QListWidgetItem, QMessageBox, QInputDialog)
from PySide6.QtCore import Qt, Signal
from modules.ui_utils import KioskInputDialog

class FaceListScreen(QWidget):
    """Screen for listing and managing registered faces"""
    
    back_requested = Signal()
    
    def __init__(self, face_recognizer, parent=None):
        super().__init__(parent)
        self.face_recognizer = face_recognizer
        self.init_ui()
        
    def init_ui(self):
        self.setStyleSheet("""
            QWidget { background-color: #1a1a1a; }
            QLabel#title { font-size: 20px; font-weight: bold; color: #00ff88; padding: 10px; }
            QListWidget { 
                background-color: #2d2d2d; border: 2px solid #4d4d4d; 
                border-radius: 8px; color: #ffffff; font-size: 16px;
            }
            QListWidget::item { padding: 10px; border-bottom: 1px solid #3d3d3d; }
            QListWidget::item:selected { background-color: #4a90e2; }
            QPushButton {
                background-color: #2d2d2d; color: #ffffff; border: 2px solid #4d4d4d;
                border-radius: 8px; font-size: 14px; font-weight: bold; padding: 10px;
            }
            QPushButton#back { background-color: #444444; }
            QPushButton#delete { background-color: #cc3333; }
            QPushButton#rename { background-color: #4a90e2; }
        """)
        
        main_layout = QVBoxLayout(self)
        
        title = QLabel("📋 Registered Faces")
        title.setObjectName("title")
        title.setAlignment(Qt.AlignCenter)
        main_layout.addWidget(title)
        
        self.list_widget = QListWidget()
        main_layout.addWidget(self.list_widget)
        
        actions_layout = QHBoxLayout()
        self.rename_btn = QPushButton("✏️ Rename")
        self.rename_btn.setObjectName("rename")
        self.rename_btn.clicked.connect(self.rename_selected)
        
        self.id_btn = QPushButton("🆔 ID")
        self.id_btn.clicked.connect(self.update_id_selected)
        
        self.delete_btn = QPushButton("🗑️ Delete")
        self.delete_btn.setObjectName("delete")
        self.delete_btn.clicked.connect(self.delete_selected)
        
        actions_layout.addWidget(self.rename_btn)
        actions_layout.addWidget(self.id_btn)
        actions_layout.addWidget(self.delete_btn)
        main_layout.addLayout(actions_layout)
        
        self.back_btn = QPushButton("⬅️ Back")
        self.back_btn.setObjectName("back")
        self.back_btn.clicked.connect(self.back_requested.emit)
        main_layout.addWidget(self.back_btn)
        
    def refresh_list(self):
        self.list_widget.clear()
        persons = sorted(list(self.face_recognizer.known_faces.keys()))
        for person in persons:
            emp_id = self.face_recognizer.get_employee_id(person)
            text = f"{person} (ID: {emp_id})" if emp_id else person
            item = QListWidgetItem(text)
            item.setData(Qt.UserRole, person)
            self.list_widget.addItem(item)
            
    def rename_selected(self):
        item = self.list_widget.currentItem()
        if not item: return
        person = item.data(Qt.UserRole)
        new_name, ok = KioskInputDialog.get_text(self, "Rename", f"New name for {person}:", person)
        if ok and new_name and new_name != person:
            if new_name in self.face_recognizer.known_faces:
                QMessageBox.warning(self, "Error", "Name already exists!")
                return
            data = self.face_recognizer.known_faces.pop(person)
            self.face_recognizer.known_faces[new_name] = data
            self.face_recognizer.save_database()
            self.refresh_list()
            
    def update_id_selected(self):
        item = self.list_widget.currentItem()
        if not item: return
        person = item.data(Qt.UserRole)
        curr_id = self.face_recognizer.get_employee_id(person) or ""
        new_id, ok = KioskInputDialog.get_text(self, "Update ID", f"New ID for {person}:", curr_id)
        if ok:
            self.face_recognizer.update_employee_id(person, new_id if new_id else None)
            self.refresh_list()
            
    def delete_selected(self):
        item = self.list_widget.currentItem()
        if not item: return
        person = item.data(Qt.UserRole)
        reply = QMessageBox.question(self, "Confirm", f"Delete {person}?", QMessageBox.Yes | QMessageBox.No)
        if reply == QMessageBox.Yes:
            self.face_recognizer.delete_person(person)
            self.refresh_list()
