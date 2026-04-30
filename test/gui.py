"""
Raspberry Pi Kiosk Attendance System with Camera Feed
PySide6 GUI with Picamera2 Integration - Thread-Safe Version
"""

import sys
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                               QHBoxLayout, QLabel, QPushButton, QFrame)
from PySide6.QtCore import Qt, QTimer, QThread, Signal, Slot
from PySide6.QtGui import QImage, QPixmap, QFont
from picamera2 import Picamera2
import numpy as np
import time


class CameraThread(QThread):
    """Separate thread for camera capture to prevent blocking"""
    frame_ready = Signal(np.ndarray)
    
    def __init__(self):
        super().__init__()
        self._running = False
        self.picam2 = None
        
    def run(self):
        """Initialize camera and start continuous capture"""
        try:
            self.picam2 = Picamera2()
            
            # Configure camera for preview
            preview_config = self.picam2.create_preview_configuration(
                main={"size": (1280, 960), "format": "RGB888"},
                buffer_count=4
            )
            self.picam2.configure(preview_config)
            self.picam2.start()
            
            self._running = True
            
            # Continuous capture loop
            while self._running:
                try:
                    frame = self.picam2.capture_array()
                    self.frame_ready.emit(frame)
                    time.sleep(0.033)  # ~30 fps
                except Exception as e:
                    print(f"Frame capture error: {e}")
                    
        except Exception as e:
            print(f"Camera initialization error: {e}")
    
    def stop(self):
        """Stop the camera thread safely"""
        self._running = False
        if self.picam2:
            try:
                self.picam2.stop()
                self.picam2.close()
            except:
                pass
        self.quit()
        self.wait()


class AttendanceKioskGUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.camera_thread = None
        self.time_in_active = False
        self.break_active = False
        self.job_active = False
        
        self.init_ui()
        self.init_camera()
        
    def init_ui(self):
        """Initialize the user interface"""
        self.setWindowTitle("Attendance Kiosk System")
        self.setStyleSheet("""
            QMainWindow {
                background-color: #1a1a1a;
            }
            QLabel#title {
                color: #ffffff;
                font-size: 32px;
                font-weight: bold;
                padding: 20px;
            }
            QLabel#status {
                color: #00ff88;
                font-size: 18px;
                padding: 10px;
            }
            QLabel#camera {
                background-color: #000000;
                border: 3px solid #00ff88;
                border-radius: 10px;
            }
            QPushButton {
                background-color: #2d2d2d;
                color: #ffffff;
                border: 2px solid #4d4d4d;
                border-radius: 15px;
                font-size: 20px;
                font-weight: bold;
                padding: 25px;
                min-height: 80px;
            }
            QPushButton:hover {
                background-color: #3d3d3d;
                border-color: #00ff88;
            }
            QPushButton:pressed {
                background-color: #1d1d1d;
            }
            QPushButton#activeButton {
                background-color: #00aa66;
                border-color: #00ff88;
            }
            QPushButton#timeInOut {
                border-color: #4a90e2;
            }
            QPushButton#timeInOut:hover {
                border-color: #6ab0ff;
            }
            QPushButton#breakButton {
                border-color: #f5a623;
            }
            QPushButton#breakButton:hover {
                border-color: #ffbe4a;
            }
            QPushButton#jobButton {
                border-color: #bd10e0;
            }
            QPushButton#jobButton:hover {
                border-color: #dd40ff;
            }
            QFrame#buttonContainer {
                background-color: #0d0d0d;
                border-top: 3px solid #00ff88;
                padding: 20px;
            }
        """)
        
        # Create central widget and main layout
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # Title bar
        title_label = QLabel("🎯 Attendance System")
        title_label.setObjectName("title")
        title_label.setAlignment(Qt.AlignCenter)
        main_layout.addWidget(title_label)
        
        # Status label
        self.status_label = QLabel("Ready • Waiting for face recognition")
        self.status_label.setObjectName("status")
        self.status_label.setAlignment(Qt.AlignCenter)
        main_layout.addWidget(self.status_label)
        
        # Camera feed label
        self.camera_label = QLabel()
        self.camera_label.setObjectName("camera")
        self.camera_label.setAlignment(Qt.AlignCenter)
        self.camera_label.setMinimumSize(800, 600)
        self.camera_label.setScaledContents(False)
        main_layout.addWidget(self.camera_label, stretch=1)
        
        # Button container frame
        button_frame = QFrame()
        button_frame.setObjectName("buttonContainer")
        button_layout = QHBoxLayout(button_frame)
        button_layout.setSpacing(20)
        button_layout.setContentsMargins(30, 20, 30, 20)
        
        # Time In/Out Button
        self.time_in_out_btn = QPushButton("⏱️ TIME IN/OUT")
        self.time_in_out_btn.setObjectName("timeInOut")
        self.time_in_out_btn.clicked.connect(self.toggle_time_in_out)
        self.time_in_out_btn.setCursor(Qt.PointingHandCursor)
        button_layout.addWidget(self.time_in_out_btn)
        
        # Break On/Off Button
        self.break_btn = QPushButton("☕ BREAK ON/OFF")
        self.break_btn.setObjectName("breakButton")
        self.break_btn.clicked.connect(self.toggle_break)
        self.break_btn.setCursor(Qt.PointingHandCursor)
        button_layout.addWidget(self.break_btn)
        
        # Job In/Out Button
        self.job_btn = QPushButton("💼 JOB IN/OUT")
        self.job_btn.setObjectName("jobButton")
        self.job_btn.clicked.connect(self.toggle_job)
        self.job_btn.setCursor(Qt.PointingHandCursor)
        button_layout.addWidget(self.job_btn)
        
        main_layout.addWidget(button_frame)
        
        # Set fullscreen and hide cursor for kiosk mode
        self.showFullScreen()
        # Comment out the next line during development to keep cursor visible
        # QApplication.setOverrideCursor(Qt.BlankCursor)
        
    def init_camera(self):
        """Initialize camera in separate thread"""
        try:
            self.camera_thread = CameraThread()
            self.camera_thread.frame_ready.connect(self.update_camera_feed)
            self.camera_thread.start()
            
            self.status_label.setText("✅ Camera Active • Ready for scanning")
            
        except Exception as e:
            self.status_label.setText(f"❌ Camera Error: {str(e)}")
            print(f"Camera initialization error: {e}")
    
    @Slot(np.ndarray)
    def update_camera_feed(self, frame):
        """Update display with new camera frame"""
        try:
            # Convert numpy array to QImage
            height, width, channel = frame.shape
            bytes_per_line = 3 * width
            q_image = QImage(frame.data, width, height, bytes_per_line, 
                           QImage.Format_RGB888)
            
            # Scale image to fit label while maintaining aspect ratio
            scaled_pixmap = QPixmap.fromImage(q_image).scaled(
                self.camera_label.size(),
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation
            )
            
            self.camera_label.setPixmap(scaled_pixmap)
            
        except Exception as e:
            print(f"Display update error: {e}")
    
    def toggle_time_in_out(self):
        """Handle Time In/Out button click"""
        self.time_in_active = not self.time_in_active
        
        if self.time_in_active:
            self.time_in_out_btn.setObjectName("activeButton")
            self.status_label.setText("✅ TIME IN RECORDED")
            print("Time In recorded")
        else:
            self.time_in_out_btn.setObjectName("timeInOut")
            self.status_label.setText("✅ TIME OUT RECORDED")
            print("Time Out recorded")
        
        # Refresh stylesheet
        self.time_in_out_btn.style().unpolish(self.time_in_out_btn)
        self.time_in_out_btn.style().polish(self.time_in_out_btn)
        self.time_in_out_btn.update()
    
    def toggle_break(self):
        """Handle Break On/Off button click"""
        self.break_active = not self.break_active
        
        if self.break_active:
            self.break_btn.setObjectName("activeButton")
            self.status_label.setText("☕ BREAK STARTED")
            print("Break started")
        else:
            self.break_btn.setObjectName("breakButton")
            self.status_label.setText("☕ BREAK ENDED")
            print("Break ended")
        
        # Refresh stylesheet
        self.break_btn.style().unpolish(self.break_btn)
        self.break_btn.style().polish(self.break_btn)
        self.break_btn.update()
    
    def toggle_job(self):
        """Handle Job In/Out button click"""
        self.job_active = not self.job_active
        
        if self.job_active:
            self.job_btn.setObjectName("activeButton")
            self.status_label.setText("💼 JOB IN PROGRESS")
            print("Job started")
        else:
            self.job_btn.setObjectName("jobButton")
            self.status_label.setText("💼 JOB COMPLETED")
            print("Job completed")
        
        # Refresh stylesheet
        self.job_btn.style().unpolish(self.job_btn)
        self.job_btn.style().polish(self.job_btn)
        self.job_btn.update()
    
    def keyPressEvent(self, event):
        """Handle keyboard events (ESC to exit kiosk mode)"""
        if event.key() == Qt.Key_Escape:
            self.close_app()
    
    def close_app(self):
        """Clean up and close application"""
        if self.camera_thread:
            self.camera_thread.stop()
        QApplication.restoreOverrideCursor()
        self.close()
    
    def closeEvent(self, event):
        """Handle window close event"""
        if self.camera_thread:
            self.camera_thread.stop()
        QApplication.restoreOverrideCursor()
        event.accept()


def main():
    app = QApplication(sys.argv)
    
    # Set application-wide font
    font = QFont("Ubuntu", 12)
    app.setFont(font)
    
    window = AttendanceKioskGUI()
    window.show()
    
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
