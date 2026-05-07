#!/usr/bin/env python3
"""
Admin Control Page for Face Database Management
Provides interface for:
- List all faces
- Rename person
- Delete person
- Update employee ID
"""

from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, 
                               QFrame, QListWidget, QListWidgetItem, QInputDialog, 
                               QMessageBox, QDialog, QLineEdit, QComboBox, QScrollArea)
from PySide6.QtCore import Qt, Signal, QSize, QTimer
from PySide6.QtGui import QFont
from modules.ui_utils import VKLineEdit



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
        
        # Style the dialog
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
        
        # Focus the line edit after a short delay to ensure keyboard triggers
        QTimer.singleShot(100, self.line_edit.setFocus)

    def text_value(self):
        return self.line_edit.text()

    @staticmethod
    def get_text(parent, title, label, initial_text=""):
        dialog = KioskInputDialog(title, label, initial_text, parent)
        if dialog.exec() == QDialog.Accepted:
            return dialog.text_value(), True
        return "", False

class AdminControlPage(QWidget):
    """Admin control page for managing face database"""
    
    # Signal to go back to home page
    home_requested = Signal()
    
    # Signal to start face registration
    add_new_face_requested = Signal()
    
    def __init__(self, face_recognizer, parent=None):
        super().__init__(parent)
        self.face_recognizer = face_recognizer
        self.init_ui()
    
    def init_ui(self):
        """Initialize UI"""
        self.setStyleSheet("""
            QWidget { background-color: #1a1a1a; }
            QLabel { color: #ffffff; }
            QLabel#title { font-size: 20px; font-weight: bold; color: #00ff88; padding: 20px; }
            QPushButton {
                background-color: #2d2d2d; color: #ffffff; border: 2px solid #4d4d4d;
                border-radius: 8px; font-size: 14px; font-weight: bold; padding: 12px; 
                min-height: 50px;
            }
            QPushButton:hover { background-color: #3d3d3d; border-color: #00ff88; }
            QPushButton:pressed { background-color: #1d1d1d; }
            QListWidget { background-color: #2d2d2d; border: 2px solid #4d4d4d; border-radius: 8px; color: #ffffff; }
            QListWidget::item:selected { background-color: #4a90e2; }
        """)
        
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(15)
        
        # Title
        title = QLabel("🔧 Admin Control Panel")
        title.setObjectName("title")
        title.setAlignment(Qt.AlignCenter)
        main_layout.addWidget(title)
        
        # Control buttons layout
        buttons_layout = QVBoxLayout()
        buttons_layout.setSpacing(10)
        
        # List Faces Button
        self.list_faces_btn = QPushButton("📋 List All Faces")
        self.list_faces_btn.clicked.connect(self.list_faces)
        self.list_faces_btn.setCursor(Qt.PointingHandCursor)
        buttons_layout.addWidget(self.list_faces_btn)
        
        # Rename Person Button
        self.rename_person_btn = QPushButton("✏️  Rename Person")
        self.rename_person_btn.clicked.connect(self.rename_person)
        self.rename_person_btn.setCursor(Qt.PointingHandCursor)
        buttons_layout.addWidget(self.rename_person_btn)
        
        # Delete Person Button
        self.delete_person_btn = QPushButton("🗑️  Delete Person")
        self.delete_person_btn.clicked.connect(self.delete_person)
        self.delete_person_btn.setCursor(Qt.PointingHandCursor)
        buttons_layout.addWidget(self.delete_person_btn)
        
        # Add New Face Button
        self.add_face_btn = QPushButton("🆕 Add New Face")
        self.add_face_btn.clicked.connect(self.add_new_face)
        self.add_face_btn.setCursor(Qt.PointingHandCursor)
        self.add_face_btn.setStyleSheet("""
            QPushButton {
                background-color: #50c878; border-color: #66dd99;
            }
            QPushButton:hover { background-color: #66dd99; }
            QPushButton:pressed { background-color: #3a9e5a; }
        """)
        buttons_layout.addWidget(self.add_face_btn)
        
        # Update Employee ID Button
        self.update_emp_id_btn = QPushButton("🆔 Update Employee ID")
        self.update_emp_id_btn.clicked.connect(self.update_employee_id)
        self.update_emp_id_btn.setCursor(Qt.PointingHandCursor)
        buttons_layout.addWidget(self.update_emp_id_btn)
        
        # Add buttons and list directly back to main layout (no scroll)
        buttons_frame = QFrame()
        buttons_frame.setLayout(buttons_layout)
        main_layout.addWidget(buttons_frame)
        
        # List display area
        self.list_widget = QListWidget()
        self.list_widget.setVisible(False)
        self.list_widget.setMinimumHeight(200)
        main_layout.addWidget(self.list_widget)
        
        # Home button at bottom
        home_btn = QPushButton("🏠 Home")
        home_btn.clicked.connect(self.go_home)
        home_btn.setCursor(Qt.PointingHandCursor)
        home_btn.setStyleSheet("""
            QPushButton {
                background-color: #00aa44; border-color: #00ff88;
            }
            QPushButton:hover { background-color: #00cc55; }
            QPushButton:pressed { background-color: #008833; }
        """)
        main_layout.addWidget(home_btn, stretch=0)
        
        self.setLayout(main_layout)
    
    def get_all_persons(self):
        """Get list of all registered persons"""
        return list(self.face_recognizer.known_faces.keys())
    
    def list_faces(self):
        """Show list of all registered faces"""
        persons = self.get_all_persons()
        
        if not persons:
            QMessageBox.information(self, "List Faces", "No faces registered yet.")
            return
        
        self.list_widget.clear()
        for person in sorted(persons):
            employee_id = self.face_recognizer.get_employee_id(person)
            if employee_id:
                item_text = f"{person} (ID: {employee_id})"
            else:
                item_text = f"{person}"
            
            item = QListWidgetItem(item_text)
            self.list_widget.addItem(item)
        
        self.list_widget.setVisible(True)
        self.list_widget.scrollToTop()
    
    def rename_person(self):
        """Rename a registered person"""
        persons = self.get_all_persons()
        
        if not persons:
            QMessageBox.information(self, "Rename Person", "No faces registered yet.")
            return
        
        # Dialog to select person
        person, ok = QInputDialog.getItem(
            self, "Rename Person", "Select person to rename:",
            sorted(persons), 0, False
        )
        
        if not ok or not person:
            return
        
        # Dialog to enter new name using KioskInputDialog for keyboard support
        new_name, ok = KioskInputDialog.get_text(
            self, "Rename Person", f"Enter new name for {person}:", person
        )
        
        if not ok or not new_name or new_name == person:
            return
        
        # Check if new name already exists
        if new_name in persons:
            QMessageBox.warning(self, "Rename Failed", f"Person '{new_name}' already exists.")
            return
        
        # Perform rename
        try:
            data = self.face_recognizer.known_faces.pop(person)
            self.face_recognizer.known_faces[new_name] = data
            self.face_recognizer.save_database()
            QMessageBox.information(self, "Success", f"Renamed '{person}' to '{new_name}'")
        except Exception as e:
            QMessageBox.critical(self, "Rename Failed", f"Error: {str(e)}")
    
    def delete_person(self):
        """Delete a registered person"""
        persons = self.get_all_persons()
        
        if not persons:
            QMessageBox.information(self, "Delete Person", "No faces registered yet.")
            return
        
        # Dialog to select person
        person, ok = QInputDialog.getItem(
            self, "Delete Person", "Select person to delete:",
            sorted(persons), 0, False
        )
        
        if not ok or not person:
            return
        
        # Confirmation dialog
        reply = QMessageBox.question(
            self, "Confirm Deletion",
            f"Are you sure you want to delete '{person}'?\nThis cannot be undone.",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            if self.face_recognizer.delete_person(person):
                QMessageBox.information(self, "Success", f"Deleted '{person}' from database")
            else:
                QMessageBox.critical(self, "Deletion Failed", f"Could not delete '{person}'")
    
    def update_employee_id(self):
        """Update employee ID for a registered person"""
        persons = self.get_all_persons()
        
        if not persons:
            QMessageBox.information(self, "Update Employee ID", "No faces registered yet.")
            return
        
        # Dialog to select person
        person, ok = QInputDialog.getItem(
            self, "Update Employee ID", "Select person:",
            sorted(persons), 0, False
        )
        
        if not ok or not person:
            return
        
        # Get current employee ID
        current_id = self.face_recognizer.get_employee_id(person)
        current_id_str = current_id if current_id else ""
        
        # Dialog to enter new employee ID using KioskInputDialog for keyboard support
        new_id, ok = KioskInputDialog.get_text(
            self, "Update Employee ID",
            f"Enter new employee ID for {person}:", current_id_str
        )
        
        if not ok:
            return
        
        # Update employee ID
        if self.face_recognizer.update_employee_id(person, new_id if new_id else None):
            QMessageBox.information(self, "Success", f"Updated employee ID for '{person}'")
        else:
            QMessageBox.critical(self, "Update Failed", f"Could not update employee ID for '{person}'")
    
    def add_new_face(self):
        """Emit signal to start face registration from admin page"""
        self.add_new_face_requested.emit()
    
    def go_home(self):
        """Emit signal to go back to home page"""
        self.list_widget.setVisible(False)
        self.home_requested.emit()
