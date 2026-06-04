#!/usr/bin/env python3
"""Debug script to catch GUI errors"""
import sys
import traceback

def main():
    try:
        print("=" * 60)
        print("STARTING ATTENDANCE GUI DEBUG")
        print("=" * 60)
        
        # Import after printing so we see any import errors
        print("\n[1/5] Importing PySide6...")
        from PySide6.QtWidgets import QApplication
        print("✓ PySide6 imported")
        
        print("\n[2/5] Setting up QApplication...")
        app = QApplication(sys.argv)
        print("✓ QApplication created")
        
        print("\n[3/5] Importing attendance_gui module...")
        from attendance_gui import AttendanceKioskGUI
        print("✓ AttendanceKioskGUI imported")
        
        print("\n[4/5] Creating GUI window...")
        window = AttendanceKioskGUI()
        print("✓ AttendanceKioskGUI instance created")
        
        print("\n[5/5] Showing window...")
        window.show()
        print("✓ Window.show() called")
        
        print("\n" + "=" * 60)
        print("STARTING EVENT LOOP")
        print("=" * 60 + "\n")
        
        sys.exit(app.exec())
        
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        print("\nFull traceback:")
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
