
import ast
import os
import sys

def check_file(filepath):
    with open(filepath, 'r') as f:
        tree = ast.parse(f.read())
    
    defined_names = set()
    used_names = set()
    
    # Simple visitor to find definitions and usages
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                defined_names.add(alias.asname or alias.name)
        elif isinstance(node, ast.ImportFrom):
            for alias in node.names:
                defined_names.add(alias.asname or alias.name)
        elif isinstance(node, ast.ClassDef):
            defined_names.add(node.name)
        elif isinstance(node, ast.FunctionDef):
            defined_names.add(node.name)
        elif isinstance(node, ast.Name):
            if isinstance(node.ctx, ast.Load):
                used_names.add(node.id)
            elif isinstance(node.ctx, ast.Store):
                defined_names.add(node.id)

    # Builtins and common Qt modules that might be imported via 'from PySide6 import ...'
    common_builtins = set(dir(__builtins__)) | {"__file__", "__name__", "self", "args", "kwargs"}
    
    # Classes we expect to be defined via imports in this project
    qt_widgets = {"QWidget", "QLabel", "QPushButton", "QVBoxLayout", "QHBoxLayout", "QGridLayout", 
                  "QFrame", "QMessageBox", "QDialog", "QLineEdit", "QStackedWidget", "QApplication", 
                  "QMainWindow", "QProgressBar", "QSizePolicy", "QListWidget", "QListWidgetItem", "QInputDialog", "QImage", "QPixmap", "QPainter", "QColor", "QFont", "QPen", "QBrush"}
    qt_core = {"Qt", "Signal", "Slot", "QPropertyAnimation", "QEasingCurve", "QTimer", "Property", "QDateTime"}
    
    missing = []
    for name in used_names:
        if name not in defined_names and name not in common_builtins:
            if name in qt_widgets or name in qt_core:
                missing.append(name)
    
    return missing

files_to_check = [
    "attendance_gui.py",
    "screens/face_list_screen.py",
    "screens/welcome_screen.py",
    "screens/admin_screen.py",
    "screens/registration_screen.py",
    "screens/attendance_screen.py",
    "modules/ui_utils.py"
]

for f in files_to_check:
    if os.path.exists(f):
        missing = check_file(f)
        if missing:
            print(f"File: {f} - Missing imports: {', '.join(missing)}")
        else:
            print(f"File: {f} - OK")
