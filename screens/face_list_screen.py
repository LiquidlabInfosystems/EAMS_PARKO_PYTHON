#!/usr/bin/env python3
"""
Face List Screen - Scrollable list of all registered faces
with search bar and back button.
"""

from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
                               QPushButton, QFrame, QScrollArea, QSizePolicy)
from PySide6.QtCore import Qt, Signal
from modules.ui_utils import VKLineEdit
from screens.scaling import pw, ph, pf


class FaceListScreen(QWidget):
    """Scrollable face list screen with search"""

    back_requested = Signal()

    def __init__(self, face_recognizer, parent=None):
        super().__init__(parent)
        self.face_recognizer = face_recognizer
        self.init_ui()

    def init_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── Header bar ──────────────────────────────────────────────
        header = QFrame()
        header.setObjectName("header")
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(pw(12), ph(10), pw(12), ph(10))
        header_layout.setSpacing(pw(8))

        self.back_btn = QPushButton("← Back")
        self.back_btn.setObjectName("backBtn")
        self.back_btn.setCursor(Qt.PointingHandCursor)
        self.back_btn.clicked.connect(self._go_back)
        self.back_btn.setFixedWidth(pw(90))
        header_layout.addWidget(self.back_btn)

        title = QLabel("Registered Faces")
        title.setObjectName("listTitle")
        title.setAlignment(Qt.AlignCenter)
        header_layout.addWidget(title, stretch=1)

        self.count_label = QLabel("0")
        self.count_label.setObjectName("countBadge")
        self.count_label.setAlignment(Qt.AlignCenter)
        self.count_label.setFixedWidth(pw(50))
        header_layout.addWidget(self.count_label)

        root.addWidget(header)

        # ── Search bar ──────────────────────────────────────────────
        search_frame = QFrame()
        search_frame.setObjectName("searchFrame")
        search_layout = QHBoxLayout(search_frame)
        search_layout.setContentsMargins(pw(12), ph(6), pw(12), ph(6))

        self.search_input = VKLineEdit()
        self.search_input.setObjectName("searchInput")
        self.search_input.setPlaceholderText("🔍  Search by name or ID...")
        self.search_input.textChanged.connect(self._filter_list)
        search_layout.addWidget(self.search_input)

        root.addWidget(search_frame)

        # ── Scrollable list ─────────────────────────────────────────
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.scroll_area.setObjectName("scrollArea")

        self.list_container = QWidget()
        self.list_layout = QVBoxLayout(self.list_container)
        self.list_layout.setContentsMargins(pw(12), ph(6), pw(12), ph(6))
        self.list_layout.setSpacing(ph(6))
        self.list_layout.setAlignment(Qt.AlignTop)

        self.scroll_area.setWidget(self.list_container)
        root.addWidget(self.scroll_area, stretch=1)

        self._apply_styles()

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
            QWidget {{ background-color: #0a0a14; }}
            QFrame#header {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #0d1117, stop:1 #111827);
                border-bottom: 1px solid #1e2535;
            }}
            QPushButton#backBtn {{
                background-color: transparent;
                color: #60a5fa;
                border: 1px solid #334155;
                border-radius: {_pw(8)}px;
                font-size: {_pf(12)}px;
                font-weight: 700;
                font-family: 'Inter', 'Segoe UI', sans-serif;
                padding: {_ph(7)}px {_pw(12)}px;
            }}
            QPushButton#backBtn:pressed {{ background-color: rgba(96,165,250,0.1); }}
            QLabel#listTitle {{
                color: #f1f5f9;
                font-size: {_pf(15)}px;
                font-weight: 700;
                font-family: 'Inter', 'Segoe UI', sans-serif;
                background: transparent;
            }}
            QLabel#countBadge {{
                color: #ffffff;
                background-color: #3b82f6;
                border-radius: {_pw(12)}px;
                font-size: {_pf(11)}px;
                font-weight: 700;
                font-family: 'Inter', 'Segoe UI', sans-serif;
                padding: {_ph(4)}px;
            }}
            QFrame#searchFrame {{
                background-color: #0d1117;
                border-bottom: 1px solid #1e2535;
            }}
            VKLineEdit#searchInput, QLineEdit#searchInput {{
                background-color: #111827;
                color: #f1f5f9;
                border: 1px solid #334155;
                border-radius: {_pw(10)}px;
                padding: {_ph(10)}px {_pw(14)}px;
                font-size: {_pf(13)}px;
                font-family: 'Inter', 'Segoe UI', sans-serif;
            }}
            VKLineEdit#searchInput:focus {{ border-color: #3b82f6; }}
            QScrollArea#scrollArea {{
                background-color: #0a0a14;
                border: none;
            }}
            QScrollArea#scrollArea > QWidget > QWidget {{
                background-color: #0a0a14;
            }}
            QScrollBar:vertical {{
                background: #0d1117;
                width: {_pw(6)}px;
                border-radius: {_pw(3)}px;
            }}
            QScrollBar::handle:vertical {{
                background: #334155;
                border-radius: {_pw(3)}px;
                min-height: {_ph(30)}px;
            }}
            QScrollBar::handle:vertical:hover {{ background: #3b82f6; }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
        """)

    def refresh(self):
        """Reload the face list from recognizer database"""
        self.search_input.clear()
        self._build_list()
        # Auto-focus the search bar so the virtual keyboard appears
        self.search_input.setFocus()
        VKLineEdit._show_keyboard()

    def _build_list(self, filter_text=""):
        """Build the face list cards"""
        # Clear existing
        while self.list_layout.count():
            item = self.list_layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

        persons = sorted(self.face_recognizer.known_faces.keys())
        filtered = []
        filter_lower = filter_text.lower()

        for name in persons:
            emp_id = self.face_recognizer.get_employee_id(name) or ""
            if filter_lower and filter_lower not in name.lower() and filter_lower not in emp_id.lower():
                continue
            filtered.append((name, emp_id))

        self.count_label.setText(str(len(filtered)))

        if not filtered:
            empty = QLabel("No faces found" if filter_text else "No faces registered yet")
            empty.setAlignment(Qt.AlignCenter)
            empty.setStyleSheet(f"""
                color: #5a5a7a;
                font-size: {pf(14)}px;
                padding: {ph(40)}px;
                background: transparent;
            """)
            self.list_layout.addWidget(empty)
            return

        for idx, (name, emp_id) in enumerate(filtered):
            card = self._create_card(name, emp_id, idx)
            self.list_layout.addWidget(card)

    def _create_card(self, name, emp_id, index):
        """Create a single face card"""
        card = QFrame()
        card.setObjectName("faceCard")
        colors = ["#3b82f6", "#ef4444", "#10b981", "#f59e0b", "#8b5cf6", "#06b6d4"]
        accent = colors[index % len(colors)]
        card.setStyleSheet(f"""
            QFrame#faceCard {{
                background-color: #0d1117;
                border: 1px solid #1e2535;
                border-left: 3px solid {accent};
                border-radius: {pw(12)}px;
                padding: {ph(2)}px;
            }}
        """)

        layout = QHBoxLayout(card)
        layout.setContentsMargins(pw(12), ph(8), pw(12), ph(8))
        layout.setSpacing(pw(10))

        # Avatar circle
        avatar = QLabel(name[0].upper() if name else "?")
        avatar.setAlignment(Qt.AlignCenter)
        avatar.setFixedSize(pw(36), pw(36))
        colors = ["#3b82f6", "#ef4444", "#10b981", "#f59e0b", "#8b5cf6", "#06b6d4"]
        bg = colors[index % len(colors)]
        avatar.setStyleSheet(f"""
            background-color: {bg};
            color: #ffffff;
            border-radius: {pw(18)}px;
            font-size: {pf(14)}px;
            font-weight: 700;
            font-family: 'Inter', 'Segoe UI', sans-serif;
        """)
        layout.addWidget(avatar)

        # Info column
        info = QVBoxLayout()
        info.setSpacing(ph(2))

        name_label = QLabel(name)
        name_label.setStyleSheet(f"""
            color: #f1f5f9;
            font-size: {pf(13)}px;
            font-weight: 700;
            font-family: 'Inter', 'Segoe UI', sans-serif;
            background: transparent;
        """)
        info.addWidget(name_label)

        id_label = QLabel(f"ID: {emp_id}" if emp_id else "No ID assigned")
        id_label.setStyleSheet(f"""
            color: {'#475569' if not emp_id else '#60a5fa'};
            font-size: {pf(10)}px;
            font-family: 'Inter', 'Segoe UI', sans-serif;
            background: transparent;
        """)
        info.addWidget(id_label)

        layout.addLayout(info, stretch=1)

        # Number badge
        num = QLabel(f"#{index + 1}")
        num.setAlignment(Qt.AlignCenter)
        num.setStyleSheet(f"""
            color: #475569;
            font-size: {pf(10)}px;
            font-family: 'Inter', 'Segoe UI', sans-serif;
            background: transparent;
        """)
        layout.addWidget(num)

        return card

    def _filter_list(self, text):
        self._build_list(text)

    def _go_back(self):
        self.search_input.clear()
        VKLineEdit._hide_keyboard()
        self.back_requested.emit()
