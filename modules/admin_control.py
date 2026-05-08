#!/usr/bin/env python3
"""
Admin Control Page for Face Database Management
Modern UI with touch-friendly buttons.
Uses VKLineEdit-based dialogs for keyboard support.
"""

from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
                               QFrame, QMessageBox, QDialog, QLineEdit,
                               QScrollArea, QSizePolicy)
from PySide6.QtCore import Qt, Signal

from screens.scaling import pw, ph, pf
from screens.dialogs import TextInputDialog
from modules.ui_utils import VKLineEdit


class PersonSelectDialog(QDialog):
    """Touch-friendly person selection dialog with scrollable list"""

    def __init__(self, parent, title, persons):
        super().__init__(parent)
        self.selected_person = None
        self.setWindowTitle(title)
        self.setModal(True)
        # Use the top-level window size so the overlay fills the screen
        top = parent.window() if parent else None
        if top:
            self.setFixedSize(top.size())
        else:
            self.showFullScreen()
        self.setWindowFlags(Qt.Dialog | Qt.FramelessWindowHint)

        self.setStyleSheet(f"""
            QDialog {{
                background-color: rgba(10, 10, 20, 215);
            }}
            QFrame#selectContainer {{
                background-color: #12121e;
                border: 2px solid #2a2a4a;
                border-radius: {pw(16)}px;
            }}
            QLabel {{
                color: #ffffff;
                background: transparent;
                border: none;
            }}
            QPushButton#personBtn {{
                background-color: #1e1e2e;
                color: #ffffff;
                border: 1px solid #3a3a5e;
                border-radius: {pw(10)}px;
                font-size: {pf(13)}px;
                font-weight: bold;
                padding: {ph(12)}px {pw(14)}px;
                text-align: left;
                min-height: {ph(46)}px;
            }}
            QPushButton#personBtn:pressed {{
                background-color: #4a90e2;
                border-color: #6ab0ff;
            }}
            QPushButton#cancelSelectBtn {{
                background-color: transparent;
                color: #ff6b6b;
                border: 1px solid #ff6b6b;
                border-radius: {pw(10)}px;
                font-size: {pf(13)}px;
                padding: {ph(10)}px;
                font-weight: bold;
                min-height: {ph(44)}px;
            }}
            QPushButton#cancelSelectBtn:pressed {{
                background-color: rgba(255, 107, 107, 0.15);
            }}
        """)

        main = QVBoxLayout(self)
        main.setContentsMargins(pw(24), ph(24), pw(24), ph(24))
        main.addStretch(1)

        container = QFrame()
        container.setObjectName("selectContainer")
        container.setMaximumWidth(pw(440))
        clayout = QVBoxLayout(container)
        clayout.setContentsMargins(pw(20), ph(20), pw(20), ph(20))
        clayout.setSpacing(ph(10))

        # Header
        header_row = QHBoxLayout()
        lbl = QLabel(title)
        lbl.setAlignment(Qt.AlignCenter)
        lbl.setStyleSheet(
            f"font-size: {pf(16)}px; font-weight: bold; color: #4a90e2; padding: {ph(4)}px 0;"
        )
        header_row.addWidget(lbl)
        clayout.addLayout(header_row)

        # Divider
        divider = QFrame()
        divider.setFrameShape(QFrame.HLine)
        divider.setStyleSheet("color: #2a2a4a; background: #2a2a4a; max-height: 1px; border: none;")
        clayout.addWidget(divider)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setMaximumHeight(ph(480))
        scroll.setStyleSheet(f"""
            QScrollArea {{ background: transparent; border: none; }}
            QScrollArea > QWidget > QWidget {{ background: transparent; }}
            QScrollBar:vertical {{
                background: #1a1a2e; width: {pw(6)}px; border-radius: {pw(3)}px;
            }}
            QScrollBar::handle:vertical {{
                background: #4a90e2; border-radius: {pw(3)}px; min-height: {ph(20)}px;
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
        """)

        list_widget = QWidget()
        list_layout = QVBoxLayout(list_widget)
        list_layout.setSpacing(ph(6))
        list_layout.setContentsMargins(0, ph(4), 0, ph(4))

        for p in sorted(persons):
            btn = QPushButton(f"  👤  {p}")
            btn.setObjectName("personBtn")
            btn.setCursor(Qt.PointingHandCursor)
            btn.clicked.connect(lambda checked, name=p: self._select(name))
            list_layout.addWidget(btn)

        list_layout.addStretch()
        scroll.setWidget(list_widget)
        clayout.addWidget(scroll)

        cancel = QPushButton("✕  Cancel")
        cancel.setObjectName("cancelSelectBtn")
        cancel.setCursor(Qt.PointingHandCursor)
        cancel.clicked.connect(self.reject)
        clayout.addWidget(cancel)

        main.addWidget(container, alignment=Qt.AlignCenter)
        main.addStretch(1)

    def _select(self, name):
        self.selected_person = name
        self.accept()


class AdminControlPage(QWidget):
    """Admin control page for managing face database"""

    home_requested = Signal()
    add_new_face_requested = Signal()
    list_faces_requested = Signal()

    def __init__(self, face_recognizer, parent=None):
        super().__init__(parent)
        self.face_recognizer = face_recognizer
        self.init_ui()

    def init_ui(self):
        """Initialize modern admin UI"""
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── Header ─────────────────────────────────────────────
        header = QFrame()
        header.setObjectName("adminHeader")
        hlayout = QHBoxLayout(header)
        hlayout.setContentsMargins(pw(16), ph(16), pw(16), ph(16))

        title = QLabel("⚙  Admin Panel")
        title.setObjectName("adminTitle")
        title.setAlignment(Qt.AlignCenter)
        hlayout.addWidget(title, stretch=1)

        root.addWidget(header)

        # ── Scrollable button area ──────────────────────────────
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setObjectName("adminScroll")

        content = QWidget()
        btn_layout = QVBoxLayout(content)
        btn_layout.setContentsMargins(pw(20), ph(20), pw(20), ph(20))
        btn_layout.setSpacing(ph(12))

        # Section label
        section_lbl = QLabel("MANAGE DATABASE")
        section_lbl.setObjectName("sectionLabel")
        section_lbl.setAlignment(Qt.AlignLeft)
        btn_layout.addWidget(section_lbl)

        # Button definitions: (text, objectName, handler, accent_color, icon_emoji)
        buttons_def = [
            ("📋  List All Faces",       "listBtn",    self._list_faces,        "#4a90e2"),
            ("✏️   Rename Person",         "renameBtn",  self.rename_person,      "#f5a623"),
            ("🗑   Delete Person",         "deleteBtn",  self.delete_person,      "#e24a4a"),
            ("🆕  Add New Face",          "addBtn",     self.add_new_face,       "#50c878"),
            ("🆔  Update Employee ID",    "updateBtn",  self.update_employee_id, "#bd10e0"),
        ]

        for text, obj_name, handler, color in buttons_def:
            btn = self._make_action_button(text, obj_name, handler, color)
            btn_layout.addWidget(btn)

        btn_layout.addStretch()
        scroll.setWidget(content)
        root.addWidget(scroll, stretch=1)

        # ── Home button at bottom ───────────────────────────────
        footer = QFrame()
        footer.setObjectName("adminFooter")
        flayout = QHBoxLayout(footer)
        flayout.setContentsMargins(pw(20), ph(12), pw(20), ph(12))

        home_btn = QPushButton("🏠  Home")
        home_btn.setObjectName("homeBtn")
        home_btn.setCursor(Qt.PointingHandCursor)
        home_btn.clicked.connect(self.go_home)
        home_btn.setMinimumHeight(ph(48))
        flayout.addWidget(home_btn)

        root.addWidget(footer)

        self._apply_styles()

    def _make_action_button(self, text, obj_name, handler, color):
        btn = QPushButton(text)
        btn.setObjectName(obj_name)
        btn.setCursor(Qt.PointingHandCursor)
        btn.clicked.connect(handler)
        btn.setMinimumHeight(ph(52))
        btn.setStyleSheet(f"""
            QPushButton#{obj_name} {{
                background-color: #1a1a2e;
                color: #ffffff;
                border: 2px solid {color};
                border-left: 5px solid {color};
                border-radius: {pw(10)}px;
                font-size: {pf(14)}px;
                font-weight: bold;
                padding: {ph(14)}px {pw(18)}px;
                text-align: left;
            }}
            QPushButton#{obj_name}:pressed {{
                background-color: {color}22;
                border-color: {color};
            }}
        """)
        return btn

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._apply_styles()

    def _apply_styles(self):
        w = self.width()
        h = self.height()
        def _pf(n): return max(8, int(n * min(w, h) / 480))
        def _pw(n): return max(1, int(n * w / 480))
        def _ph(n): return max(1, int(n * h / 854))

        self.setStyleSheet(f"""
            QWidget {{ background-color: #0d0d1a; }}
            QFrame#adminHeader {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 #12122a, stop:1 #0f1f40);
                border-bottom: 2px solid #1a2a5e;
                min-height: {_ph(60)}px;
            }}
            QLabel#adminTitle {{
                color: #00ff88;
                font-size: {_pf(20)}px;
                font-weight: bold;
                background: transparent;
                letter-spacing: 1px;
            }}
            QLabel#sectionLabel {{
                color: #5a5a8a;
                font-size: {_pf(10)}px;
                font-weight: bold;
                letter-spacing: 2px;
                background: transparent;
                padding: {_ph(4)}px 0;
            }}
            QScrollArea#adminScroll {{
                background: #0d0d1a;
                border: none;
            }}
            QScrollArea#adminScroll > QWidget > QWidget {{ background: #0d0d1a; }}
            QScrollBar:vertical {{
                background: #1a1a2e; width: {_pw(6)}px; border-radius: {_pw(3)}px;
            }}
            QScrollBar::handle:vertical {{
                background: #4a90e2; border-radius: {_pw(3)}px; min-height: {_ph(20)}px;
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
            QFrame#adminFooter {{
                background-color: #12122a;
                border-top: 2px solid #1a2a5e;
            }}
            QPushButton#homeBtn {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #006633, stop:1 #00994d);
                color: #ffffff;
                border: none;
                border-radius: {_pw(10)}px;
                font-size: {_pf(15)}px;
                font-weight: bold;
                padding: {_ph(12)}px;
            }}
            QPushButton#homeBtn:pressed {{ background: #004d26; }}
        """)

    def get_all_persons(self):
        return list(self.face_recognizer.known_faces.keys())

    def _list_faces(self):
        """Emit signal to show face list screen"""
        self.list_faces_requested.emit()

    def rename_person(self):
        persons = self.get_all_persons()
        if not persons:
            QMessageBox.information(self, "Rename", "No faces registered yet.")
            return

        # Use window() so the dialog fills the full screen
        dlg = PersonSelectDialog(self.window(), "Select Person to Rename", persons)
        if dlg.exec() != QDialog.Accepted or not dlg.selected_person:
            return
        person = dlg.selected_person

        name_dlg = TextInputDialog(
            self.window(),
            title="Enter New Name",
            label=f"Rename '{person}' to:",
            placeholder="New name"
        )
        if name_dlg.exec() != QDialog.Accepted:
            return
        new_name = name_dlg.get_text().strip()
        if not new_name or new_name == person:
            return

        VKLineEdit._hide_keyboard()

        if new_name in persons:
            QMessageBox.warning(self, "Failed", f"'{new_name}' already exists.")
            return

        try:
            data = self.face_recognizer.known_faces.pop(person)
            self.face_recognizer.known_faces[new_name] = data
            self.face_recognizer.save_database()
            QMessageBox.information(self, "Success", f"Renamed '{person}' → '{new_name}'")
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))

    def delete_person(self):
        persons = self.get_all_persons()
        if not persons:
            QMessageBox.information(self, "Delete", "No faces registered yet.")
            return

        dlg = PersonSelectDialog(self.window(), "Select Person to Delete", persons)
        if dlg.exec() != QDialog.Accepted or not dlg.selected_person:
            return
        person = dlg.selected_person

        reply = QMessageBox.question(
            self, "Confirm", f"Delete '{person}'?\nThis cannot be undone.",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            if self.face_recognizer.delete_person(person):
                QMessageBox.information(self, "Deleted", f"'{person}' removed.")
            else:
                QMessageBox.critical(self, "Failed", f"Could not delete '{person}'.")

    def update_employee_id(self):
        persons = self.get_all_persons()
        if not persons:
            QMessageBox.information(self, "Update ID", "No faces registered yet.")
            return

        dlg = PersonSelectDialog(self.window(), "Select Person", persons)
        if dlg.exec() != QDialog.Accepted or not dlg.selected_person:
            return
        person = dlg.selected_person

        current_id = self.face_recognizer.get_employee_id(person) or ""

        id_dlg = TextInputDialog(
            self.window(),
            title="Update Employee ID",
            label=f"Employee ID for {person}  (current: {current_id or 'none'})",
            placeholder="New employee ID"
        )
        if id_dlg.exec() != QDialog.Accepted:
            return
        new_id = id_dlg.get_text().strip()

        VKLineEdit._hide_keyboard()

        if self.face_recognizer.update_employee_id(person, new_id if new_id else None):
            QMessageBox.information(self, "Success", f"Updated ID for '{person}'")
        else:
            QMessageBox.critical(self, "Failed", f"Could not update ID for '{person}'")

    def add_new_face(self):
        self.add_new_face_requested.emit()

    def go_home(self):
        self.home_requested.emit()
