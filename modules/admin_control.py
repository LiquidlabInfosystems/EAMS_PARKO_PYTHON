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
                               QMessageBox, QDialog, QLineEdit, QComboBox, QScrollArea, QApplication)
from PySide6.QtCore import Qt, Signal, QSize, QTimer
from PySide6.QtGui import QFont, QIcon
import subprocess

# --- Theme configuration from welcome_screen ---
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
        if VKLineEdit._hide_timer and VKLineEdit._hide_timer.isActive():
            VKLineEdit._hide_timer.stop()
        self._show_keyboard()

    def focusOutEvent(self, event):
        super().focusOutEvent(event)
        if VKLineEdit._hide_timer is None:
            VKLineEdit._hide_timer = QTimer()
            VKLineEdit._hide_timer.setSingleShot(True)
            VKLineEdit._hide_timer.timeout.connect(self._hide_keyboard)
        VKLineEdit._hide_timer.start(200)

    @classmethod
    def _show_keyboard(cls):
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
        try:
            subprocess.run(
                ['dbus-send', '--session', '--type=method_call',
                 '--dest=sm.puri.OSK0', '/sm/puri/OSK0',
                 'sm.puri.OSK0.SetVisible', 'boolean:false'],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
            )
        except Exception:
            pass
        if cls._kb_proc is not None and cls._kb_proc.poll() is None:
            cls._kb_proc.terminate()
            cls._kb_proc = None


class SearchableListDialog(QDialog):
    """A dialog to search and select an item from a list, using virtual keyboard."""
    def __init__(self, title, label_text, items, parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setModal(True)
        self.items = items
        self.selected_item = None
        
        # Make modal full screen or match parent
        if parent:
            self.setFixedSize(parent.size())
        else:
            self.showFullScreen()
            
        self.setWindowFlags(Qt.Dialog | Qt.FramelessWindowHint)
        self.setStyleSheet(f"""
            QDialog {{ background-color: rgba(240, 244, 248, 230); border: none; }}
            QLabel {{ color: {THEME['text_primary']}; font-size: 16px; font-weight: bold; }}
            VKLineEdit {{
                background-color: #ffffff; color: {THEME['text_primary']};
                border: 2px solid {THEME['accent_secondary']}; border-radius: 8px;
                padding: 10px; font-size: 18px;
            }}
            QListWidget {{
                background-color: #ffffff; color: {THEME['text_primary']};
                border: 2px solid #dddddd; border-radius: 8px; font-size: 18px;
            }}
            QListWidget::item {{ padding: 10px; border-bottom: 1px solid #eeeeee; }}
            QListWidget::item:selected {{ background-color: {THEME['accent_secondary']}; color: #ffffff; }}
            QPushButton#btn_confirm {{
                background-color: {THEME['success']}; color: #ffffff; border: none; border-radius: 8px;
                font-size: 16px; font-weight: bold; padding: 12px;
            }}
            QPushButton#btn_confirm:disabled {{ background-color: #aaaaaa; }}
            QPushButton#btn_cancel {{
                background-color: transparent; color: {THEME['text_secondary']};
                border: 2px solid #cccccc; border-radius: 8px; font-size: 16px; font-weight: bold; padding: 12px;
            }}
        """)
        
        main_layout = QVBoxLayout(self)
        main_layout.addStretch(1)
        
        container = QFrame()
        container.setStyleSheet(f"QFrame {{ background-color: #ffffff; border: 2px solid #e0e0e0; border-radius: 12px; }}")
        root = QVBoxLayout(container)
        root.setContentsMargins(25, 25, 25, 25)
        root.setSpacing(15)
        
        title_lbl = QLabel(label_text)
        title_lbl.setAlignment(Qt.AlignCenter)
        title_lbl.setStyleSheet("border: none;")
        root.addWidget(title_lbl)
        
        self.search_box = VKLineEdit()
        self.search_box.setPlaceholderText("Search...")
        self.search_box.textChanged.connect(self.filter_items)
        root.addWidget(self.search_box)
        
        self.list_widget = QListWidget()
        self.list_widget.addItems(self.items)
        self.list_widget.itemSelectionChanged.connect(self.check_selection)
        self.list_widget.itemDoubleClicked.connect(self.accept_selection)
        root.addWidget(self.list_widget)
        
        btn_row = QHBoxLayout()
        btn_row.setSpacing(10)
        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.setObjectName("btn_cancel")
        self.cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(self.cancel_btn)
        
        self.confirm_btn = QPushButton("✓ Select")
        self.confirm_btn.setObjectName("btn_confirm")
        self.confirm_btn.clicked.connect(self.accept_selection)
        self.confirm_btn.setEnabled(False)
        btn_row.addWidget(self.confirm_btn)
        
        root.addLayout(btn_row)
        main_layout.addWidget(container, alignment=Qt.AlignCenter)
        main_layout.addStretch(1)

    def filter_items(self, text):
        for i in range(self.list_widget.count()):
            item = self.list_widget.item(i)
            item.setHidden(text.lower() not in item.text().lower())
            
    def check_selection(self):
        self.confirm_btn.setEnabled(len(self.list_widget.selectedItems()) > 0)
        
    def accept_selection(self):
        selected = self.list_widget.selectedItems()
        if selected:
            self.selected_item = selected[0].text()
            self.accept()



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
        self.setStyleSheet(f"""
            QWidget {{ background-color: {THEME['background_light']}; }}
            QLabel {{ color: {THEME['text_primary']}; }}
            QLabel#title {{ font-size: 24px; font-weight: bold; color: {THEME['accent_primary']}; padding: 20px; }}
            QPushButton {{
                background-color: #ffffff; color: {THEME['text_primary']}; border: 2px solid {THEME['background_medium']};
                border-radius: 8px; font-size: 14px; font-weight: bold; padding: 10px; 
                min-height: 45px;
            }}
            QPushButton:hover {{ background-color: {THEME['background_medium']}; border-color: {THEME['accent_secondary']}; }}
            QPushButton:pressed {{ background-color: #d0d8e0; }}
            QScrollArea {{ border: none; background-color: transparent; }}
            QScrollArea > QWidget > QWidget {{ background-color: transparent; }}
            QListWidget {{ background-color: #ffffff; border: 2px solid {THEME['background_medium']}; border-radius: 8px; color: {THEME['text_primary']}; font-size: 16px; padding: 5px; }}
            QListWidget::item {{ padding: 10px; border-bottom: 1px solid {THEME['background_medium']}; }}
            QListWidget::item:selected {{ background-color: {THEME['accent_secondary']}; color: #ffffff; }}
        """)
        
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(15)
        
        # Title
        title = QLabel("🔧 Admin Control Panel")
        title.setObjectName("title")
        title.setAlignment(Qt.AlignCenter)
        main_layout.addWidget(title)
        
        # Wrap buttons in a scroll area
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        
        scroll_content = QWidget()
        scroll_layout = QVBoxLayout(scroll_content)
        scroll_layout.setContentsMargins(0, 0, 0, 0)
        scroll_layout.setSpacing(10)
        
        # List Faces Button
        self.list_faces_btn = QPushButton("📋 List All Faces")
        self.list_faces_btn.clicked.connect(self.list_faces)
        self.list_faces_btn.setCursor(Qt.PointingHandCursor)
        scroll_layout.addWidget(self.list_faces_btn)
        
        # Rename Person Button
        self.rename_person_btn = QPushButton("✏️  Rename Person")
        self.rename_person_btn.clicked.connect(self.rename_person)
        self.rename_person_btn.setCursor(Qt.PointingHandCursor)
        scroll_layout.addWidget(self.rename_person_btn)
        
        # Delete Person Button
        self.delete_person_btn = QPushButton("🗑️  Delete Person")
        self.delete_person_btn.clicked.connect(self.delete_person)
        self.delete_person_btn.setCursor(Qt.PointingHandCursor)
        scroll_layout.addWidget(self.delete_person_btn)
        
        # Add New Face Button
        self.add_face_btn = QPushButton("🆕 Add New Face")
        self.add_face_btn.clicked.connect(self.add_new_face)
        self.add_face_btn.setCursor(Qt.PointingHandCursor)
        self.add_face_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {THEME['success']}; color: white; border-color: #27ae60;
            }}
            QPushButton:hover {{ background-color: #27ae60; }}
        """)
        scroll_layout.addWidget(self.add_face_btn)
        
        # Update Employee ID Button
        self.update_emp_id_btn = QPushButton("🆔 Update Employee ID")
        self.update_emp_id_btn.clicked.connect(self.update_employee_id)
        self.update_emp_id_btn.setCursor(Qt.PointingHandCursor)
        scroll_layout.addWidget(self.update_emp_id_btn)
        
        # Change Admin Password Button
        self.change_pwd_btn = QPushButton("🔑 Change Admin Password")
        self.change_pwd_btn.clicked.connect(self.change_admin_password)
        self.change_pwd_btn.setCursor(Qt.PointingHandCursor)
        scroll_layout.addWidget(self.change_pwd_btn)
        
        scroll_layout.addStretch(1)
        scroll_area.setWidget(scroll_content)
        main_layout.addWidget(scroll_area, stretch=1)
        
        # List display area
        self.list_widget = QListWidget()
        self.list_widget.setVisible(False)
        self.list_widget.setMinimumHeight(200)
        main_layout.addWidget(self.list_widget)
        
        # Home button at bottom
        home_btn = QPushButton("🏠 Home")
        home_btn.clicked.connect(self.go_home)
        home_btn.setCursor(Qt.PointingHandCursor)
        home_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {THEME['accent_primary']}; color: white; border-color: {THEME['accent_secondary']};
            }}
            QPushButton:hover {{ background-color: {THEME['accent_secondary']}; }}
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
        
        # Custom searchable dialog to select person
        dialog = SearchableListDialog("Rename Person", "Select person to rename:", sorted(persons), self)
        if dialog.exec() != QDialog.Accepted or not dialog.selected_item:
            return
            
        person = dialog.selected_item
        
        # Dialog to enter new name
        # We also want virtual keyboard for QInputDialog here... but QInputDialog doesn't support VKLineEdit directly.
        # We'll use a custom TextInputDialog if available, or just fallback to system dialog.
        # Assuming we can just use the VKLineEdit by creating a quick custom dialog.
        
        from attendance_gui import TextInputDialog
        name_dialog = TextInputDialog(self, "Rename Person", f"Enter new name for {person}:")
        if name_dialog.exec() != QDialog.Accepted:
            return
            
        new_name = name_dialog.get_text().strip()
        
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
        dialog = SearchableListDialog("Delete Person", "Select person to delete:", sorted(persons), self)
        if dialog.exec() != QDialog.Accepted or not dialog.selected_item:
            return
            
        person = dialog.selected_item
        
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
        # Map sorted persons to include employee ID
        display_items = []
        person_map = {}
        for p in sorted(persons):
            emp_id = self.face_recognizer.get_employee_id(p)
            display_text = f"{p} (ID: {emp_id})" if emp_id else p
            display_items.append(display_text)
            person_map[display_text] = p
            
        dialog = SearchableListDialog("Update Employee ID", "Select person:", display_items, self)
        if dialog.exec() != QDialog.Accepted or not dialog.selected_item:
            return
            
        person = person_map[dialog.selected_item]
        
        # Get current employee ID
        current_id = self.face_recognizer.get_employee_id(person)
        current_id_str = current_id if current_id else ""
        
        from attendance_gui import TextInputDialog
        id_dialog = TextInputDialog(self, "Update Employee ID", f"Enter new ID for {person} (Current: {current_id_str}):")
        if id_dialog.exec() != QDialog.Accepted:
            return
            
        new_id = id_dialog.get_text().strip()
        
        # Update employee ID
        if self.face_recognizer.update_employee_id(person, new_id if new_id else None):
            QMessageBox.information(self, "Success", f"Updated employee ID for '{person}'")
        else:
            QMessageBox.critical(self, "Update Failed", f"Could not update employee ID for '{person}'")

    def change_admin_password(self):
        """UI placeholder for changing admin password via API"""
        QMessageBox.information(self, "Change Admin Password", "This feature will be implemented in a future update to change the password via the server API.")

    def add_new_face(self):
        """Emit signal to start face registration from admin page"""
        self.add_new_face_requested.emit()
    
    def go_home(self):
        """Emit signal to go back to home page"""
        self.list_widget.setVisible(False)
        self.home_requested.emit()
