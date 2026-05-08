#!/usr/bin/env python3
"""
Screens package for EAMS Attendance Kiosk
"""

from screens.scaling import pw, ph, pf
from screens.camera_controller import CameraThread, display_frame, draw_box_rgb, draw_filled_box_rgb, put_text_rgb
from screens.notification_overlay import NotificationOverlay
from screens.dialogs import TextInputDialog, AdminPasswordDialog, SimpleConfirmationDialog
from screens.mark_attendance_screen import MarkAttendanceScreen

__all__ = [
    'pw', 'ph', 'pf',
    'CameraThread', 'display_frame', 'draw_box_rgb', 'draw_filled_box_rgb', 'put_text_rgb',
    'NotificationOverlay',
    'TextInputDialog', 'AdminPasswordDialog', 'SimpleConfirmationDialog',
    'MarkAttendanceScreen',
]
