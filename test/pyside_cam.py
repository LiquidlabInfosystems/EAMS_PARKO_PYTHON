#!/usr/bin/env python3
"""
Simple Picamera2 Feed with PySide6
"""

import sys
from PySide6.QtWidgets import QApplication, QMainWindow, QLabel
from PySide6.QtCore import QThread, Signal, Qt
from PySide6.QtGui import QImage, QPixmap
from picamera2 import Picamera2
import time

class CameraThread(QThread):
    frame_ready = Signal(object)
    
    def __init__(self):
        super().__init__()
        self.running = False
        
    def run(self):
        picam2 = Picamera2()
        config = picam2.create_preview_configuration(
            main={"size": (1280, 960), "format": "RGB888"}
        )
        picam2.configure(config)
        picam2.start()
        time.sleep(0.5)
        
        self.running = True
        
        while self.running:
            frame = picam2.capture_array()
            self.frame_ready.emit(frame)
            time.sleep(0.033)  # ~30 FPS
        
        picam2.stop()
    
    def stop(self):
        self.running = False
        self.quit()
        self.wait()


class CameraWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Simple Picamera2 Feed")
        self.setGeometry(100, 100, 1280, 960)
        
        self.label = QLabel(self)
        self.label.setAlignment(Qt.AlignCenter)
        self.setCentralWidget(self.label)
        
        self.camera_thread = CameraThread()
        self.camera_thread.frame_ready.connect(self.update_frame)
        self.camera_thread.start()
    
    def update_frame(self, frame):
        h, w, ch = frame.shape
        bytes_per_line = ch * w
        q_img = QImage(frame.data, w, h, bytes_per_line, QImage.Format_RGB888)
        pixmap = QPixmap.fromImage(q_img)
        self.label.setPixmap(pixmap.scaled(self.label.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation))
    
    def closeEvent(self, event):
        self.camera_thread.stop()
        event.accept()


def main():
    app = QApplication(sys.argv)
    window = CameraWindow()
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
