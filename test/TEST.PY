#!/usr/bin/env python3
"""
Debug color display in PySide6
"""

import sys
from PySide6.QtWidgets import QApplication, QMainWindow, QLabel, QVBoxLayout, QWidget
from PySide6.QtCore import QThread, Signal, Qt
from PySide6.QtGui import QImage, QPixmap
from picamera2 import Picamera2
import numpy as np
import time
import cv2

class CameraThread(QThread):
    frame_ready = Signal(np.ndarray)
    
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
            time.sleep(0.033)
        
        picam2.stop()
    
    def stop(self):
        self.running = False
        self.quit()
        self.wait()


class TestWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Color Test - Picamera2 vs Qt")
        self.setGeometry(100, 100, 1400, 500)
        
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        
        # OpenCV window label
        self.label_qt = QLabel("Qt Display")
        self.label_qt.setAlignment(Qt.AlignCenter)
        self.label_qt.setMinimumSize(1280, 960)
        layout.addWidget(self.label_qt)
        
        self.camera_thread = CameraThread()
        self.camera_thread.frame_ready.connect(self.update_frame)
        self.camera_thread.start()
    
    def update_frame(self, frame):
        # Show in OpenCV window for comparison
        cv2.imshow("OpenCV Display (Correct Colors)", frame)
        cv2.waitKey(1)
        
        # Method 1: Direct QImage (what we're currently using)
        h, w, ch = frame.shape
        
        print(f"Frame info: shape={frame.shape}, dtype={frame.dtype}, contiguous={frame.flags['C_CONTIGUOUS']}")
        
        # Ensure contiguous
        if not frame.flags['C_CONTIGUOUS']:
            frame = np.ascontiguousarray(frame)
        
        bytes_per_line = ch * w
        # q_img = QImage(frame.data, w, h, bytes_per_line, QImage.Format_RGB888)
        q_image = QImage(frame.data, width, height, bytes_per_line, QImage.Format_BGR888)
        
        pixmap = QPixmap.fromImage(q_img)
        self.label_qt.setPixmap(pixmap.scaled(self.label_qt.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation))
    
    def closeEvent(self, event):
        self.camera_thread.stop()
        cv2.destroyAllWindows()
        event.accept()


def main():
    app = QApplication(sys.argv)
    window = TestWindow()
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
