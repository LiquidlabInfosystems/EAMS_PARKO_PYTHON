import time
import cv2
import numpy as np
from PySide6.QtCore import QThread, Signal
from picamera2 import Picamera2
import libcamera
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
