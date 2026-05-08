
import subprocess
from PySide6.QtWidgets import QLineEdit
from PySide6.QtCore import Qt, QTimer

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
        # Cancel any pending hide
        if VKLineEdit._hide_timer and VKLineEdit._hide_timer.isActive():
            VKLineEdit._hide_timer.stop()
        self._show_keyboard()

    def focusOutEvent(self, event):
        super().focusOutEvent(event)
        # Delay hiding to see if another VKLineEdit gets focus (e.g. tabbing)
        if VKLineEdit._hide_timer is None:
            VKLineEdit._hide_timer = QTimer()
            VKLineEdit._hide_timer.setSingleShot(True)
            VKLineEdit._hide_timer.timeout.connect(self._hide_keyboard)
        
        VKLineEdit._hide_timer.start(200) # 200ms delay

    @classmethod
    def _show_keyboard(cls):
        # 1. Default device virtual keyboard (squeekboard via dbus)
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

        # 2. X11 default keyboards
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
        # 1. Hide squeekboard
        try:
            subprocess.run(
                ['dbus-send', '--session', '--type=method_call',
                 '--dest=sm.puri.OSK0', '/sm/puri/OSK0',
                 'sm.puri.OSK0.SetVisible', 'boolean:false'],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
            )
        except Exception:
            pass

        # 2. Hide X11 keyboards
        if cls._kb_proc is not None and cls._kb_proc.poll() is None:
            cls._kb_proc.terminate()
            cls._kb_proc = None
