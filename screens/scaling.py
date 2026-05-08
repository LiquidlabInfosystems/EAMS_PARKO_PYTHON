#!/usr/bin/env python3
"""
Screen-relative scaling helpers
Reference: 480 × 854  (portrait RPi 7" touchscreen)
pw(n) → scale a width-related pixel value
ph(n) → scale a height-related pixel value
pf(n) → scale a font-size (uses the shorter axis so text stays readable)
"""

from PySide6.QtWidgets import QApplication


def _scr():
    app = QApplication.instance()
    if app:
        # First try to get the main window's size
        for w in app.topLevelWidgets():
            if w.objectName() == "MainWindow" or w.__class__.__name__ == "AttendanceKioskGUI":
                return w.width(), w.height()
        s = app.primaryScreen()
        if s:
            g = s.availableGeometry()
            return g.width(), g.height()
    return 480, 854


def pw(n): w, h = _scr(); return max(1, int(n * w / 480))
def ph(n): w, h = _scr(); return max(1, int(n * h / 854))
def pf(n): w, h = _scr(); return max(8, int(n * min(w, h) / 480))
