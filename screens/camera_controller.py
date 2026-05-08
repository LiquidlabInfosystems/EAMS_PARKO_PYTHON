#!/usr/bin/env python3
"""
Camera Controller Module
Handles camera thread (Raspberry Pi Picamera2) and frame drawing utilities.
"""

from PySide6.QtCore import QThread, Signal, Qt
from PySide6.QtGui import QImage, QPixmap
from picamera2 import Picamera2
import libcamera
import numpy as np
import time
import cv2
import config


class CameraThread(QThread):
    """Camera thread - optimized for Raspberry Pi 4"""
    frame_ready = Signal(np.ndarray)
    status_update = Signal(str)

    def __init__(self, mirror=True):
        super().__init__()
        self._running = False
        self.picam2 = None
        self.mirror = mirror


    def run(self):
        """Capture frames in RGB888."""
        try:
            self.picam2 = Picamera2()

            # libcamera.Transform handles mirror only (vc4 pipeline does not
            # support rotation here). Rotation is done per-frame via cv2.rotate.
            transform = libcamera.Transform(hflip=1 if self.mirror else 0, vflip=0)

            preview_config = self.picam2.create_preview_configuration(
                main={"size": config.CAMERA_RESOLUTION, "format": "RGB888"},
                buffer_count=2,
                transform=transform
            )

            self.picam2.configure(preview_config)
            self.picam2.set_controls({
                "AwbEnable": True,
                "AeEnable": True,
                "AwbMode": libcamera.controls.AwbModeEnum.Auto,
            })

            self.picam2.start()
            time.sleep(0.5)  # slightly longer warm-up helps Pi 4 AE settle

            self._running = True
            self.status_update.emit("✅ Camera Ready")

            frame_interval = 1.0 / max(config.CAMERA_FPS, 1)

            rotation = getattr(config, 'CAMERA_ROTATION', 0)
            _rotate_map = {
                90:  cv2.ROTATE_90_CLOCKWISE,
                180: cv2.ROTATE_180,
                270: cv2.ROTATE_90_COUNTERCLOCKWISE,
            }

            while self._running:
                try:
                    frame_rgb = self.picam2.capture_array()

                    if rotation in _rotate_map:
                        frame_rgb = cv2.rotate(frame_rgb, _rotate_map[rotation])

                    self.frame_ready.emit(frame_rgb)

                    time.sleep(frame_interval)

                except Exception as e:
                    print(f"Capture error: {e}")
                    time.sleep(0.05)

        except Exception as e:
            self.status_update.emit(f"❌ Camera Error")
            print(f"Camera init error: {e}")

    def stop(self):
        """Stop camera"""
        self._running = False
        if self.picam2:
            try:
                self.picam2.stop()
                self.picam2.close()
            except:
                pass
        self.quit()
        self.wait()


# ── Frame drawing helpers ────────────────────────────────────────────────────

def display_frame(frame_rgb, camera_label):
    """Display frame on a QLabel"""
    try:
        frame_bgr = frame_rgb[:, :, ::-1].copy()

        height, width, channel = frame_bgr.shape
        bytes_per_line = 3 * width

        q_image = QImage(frame_bgr.data, width, height, bytes_per_line, QImage.Format_RGB888)

        # Use KeepAspectRatio with current label size to allow layout to handle shrinking
        scaled_pixmap = QPixmap.fromImage(q_image).scaled(
            camera_label.width(),
            camera_label.height(),
            Qt.KeepAspectRatio,
            Qt.SmoothTransformation
        )

        camera_label.setPixmap(scaled_pixmap)
    except Exception as e:
        print(f"Display error: {e}")


def draw_box_rgb(frame, x1, y1, x2, y2, color_rgb, thickness=4):
    """Draw rectangle"""
    h, w = frame.shape[:2]
    x1, y1 = max(0, x1), max(0, y1)
    x2, y2 = min(w, x2), min(h, y2)

    for t in range(thickness):
        if y1+t < h:
            frame[y1+t, x1:x2] = color_rgb
        if y2-t-1 >= 0:
            frame[y2-t-1, x1:x2] = color_rgb
        if x1+t < w:
            frame[y1:y2, x1+t] = color_rgb
        if x2-t-1 >= 0:
            frame[y1:y2, x2-t-1] = color_rgb


def draw_filled_box_rgb(frame, x1, y1, x2, y2, color_rgb):
    """Draw filled rectangle"""
    h, w = frame.shape[:2]
    x1, y1 = max(0, x1), max(0, y1)
    x2, y2 = min(w, x2), min(h, y2)
    frame[y1:y2, x1:x2] = color_rgb


def put_text_rgb(frame, text, x, y, color_rgb, scale=1.0, thickness=2):
    """Put text"""
    frame_bgr = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
    color_bgr = (color_rgb[2], color_rgb[1], color_rgb[0])
    cv2.putText(frame_bgr, text, (x, y), cv2.FONT_HERSHEY_SIMPLEX, scale, color_bgr, thickness)
    frame[:] = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
