#!/usr/bin/env python3
"""
Face Database Manager - Rename and Delete Registered Faces
Simple tool to manage your face database
"""

import os
os.environ['GLOG_minloglevel'] = '2'
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'

import pickle
import sys
from pathlib import Path


def load_database(db_path="simple_faces.pkl"):
    """Load face database"""
    if not os.path.exists(db_path):
        print("❌ No face database found!")
        print(f"   Looking for: {db_path}")
        return None

    try:
        with open(db_path, 'rb') as f:
            faces = pickle.load(f)
        return faces
    except Exception as e:
        print(f"❌ Error loading database: {e}")
        return None


def save_database(faces, db_path="simple_faces.pkl"):
    """Save face database"""
    try:
        # Create backup first
        if os.path.exists(db_path):
            backup_path = db_path + ".backup"
            os.system(f"cp {db_path} {backup_path}")
            print(f"💾 Backup created: {backup_path}")

        with open(db_path, 'wb') as f:
            pickle.dump(faces, f)
        return True
    except Exception as e:
        print(f"❌ Error saving database: {e}")
        return False


def list_registered_faces(db_path="simple_faces.pkl"):
    """List all registered faces with details"""
    faces = load_database(db_path)

    if faces is None:
        return None

    if not faces:
        print("\n📂 Database is empty - no faces registered yet")
        return faces

    print(f"\n{'='*90}")
    print(f"👥 REGISTERED FACES ({len(faces)} total)")
    print(f"{'='*90}")
    print(f"{'No.':<5} {'Name':<25} {'Employee ID':<15} {'Samples':<10} {'Status'}")
    print(f"{'-'*90}")

    for i, (name, data) in enumerate(faces.items(), 1):
        # Get sample count and employee ID
        if isinstance(data, dict):
            count = len(data.get('individual', []))
            emp_id = data.get('employee_id', '-') or '-'
        else:
            count = len(data)
            emp_id = '-'

        # Status indicator
        if count >= 8:
            status = "✅ Excellent"
        elif count >= 5:
            status = "👍 Good"
        elif count >= 3:
            status = "⚠️  Minimum"
        else:
            status = "❌ Poor"

        print(f"{i:<5} {name:<25} {emp_id:<15} {count:<10} {status}")

    print(f"{'='*90}")
    return faces


def rename_person(db_path="simple_faces.pkl"):
    """Rename a registered person"""
    print(f"\n{'='*70}")
    print("✏️  RENAME PERSON")
    print(f"{'='*70}")

    faces = list_registered_faces(db_path)

    if faces is None or not faces:
        return

    print("\n📝 Enter the current name to rename")
    old_name = input("   Current name: ").strip()

    if not old_name:
        print("❌ Cancelled - no name entered")
        return

    if old_name not in faces:
        print(f"❌ '{old_name}' not found in database")
        print(f"   Available names: {', '.join(faces.keys())}")
        return

    new_name = input("   New name: ").strip()

    if not new_name:
        print("❌ Cancelled - no new name entered")
        return

    if new_name in faces:
        print(f"❌ '{new_name}' already exists in database!")
        return

    # Confirmation
    print(f"\n⚠️  Confirm rename:")
    print(f"   '{old_name}' → '{new_name}'")
    confirm = input("   Type 'yes' to confirm: ").strip().lower()

    if confirm != 'yes':
        print("❌ Cancelled")
        return

    # Perform rename
    faces[new_name] = faces.pop(old_name)

    if save_database(faces, db_path):
        print(f"\n✅ Successfully renamed '{old_name}' to '{new_name}'!")
    else:
        print(f"\n❌ Failed to save changes")


def delete_person(db_path="simple_faces.pkl"):
    """Delete a person from database"""
    print(f"\n{'='*70}")
    print("🗑️  DELETE PERSON")
    print(f"{'='*70}")

    faces = list_registered_faces(db_path)

    if faces is None or not faces:
        return

    print("\n⚠️  Enter the name to DELETE (this cannot be undone!)")
    name_to_delete = input("   Name: ").strip()

    if not name_to_delete:
        print("❌ Cancelled - no name entered")
        return

    if name_to_delete not in faces:
        print(f"❌ '{name_to_delete}' not found in database")
        print(f"   Available names: {', '.join(faces.keys())}")
        return

    # Get sample count for confirmation
    if isinstance(faces[name_to_delete], dict):
        count = len(faces[name_to_delete].get('individual', []))
    else:
        count = len(faces[name_to_delete])

    # Confirmation
    print(f"\n⚠️  WARNING: You are about to DELETE:")
    print(f"   Name: {name_to_delete}")
    print(f"   Samples: {count}")
    print(f"   This action CANNOT be undone!")
    confirm = input("\n   Type 'DELETE' to confirm: ").strip()

    if confirm != 'DELETE':
        print("❌ Cancelled - deletion not confirmed")
        return

    # Perform deletion
    del faces[name_to_delete]

    if save_database(faces, db_path):
        print(f"\n✅ Successfully deleted '{name_to_delete}' from database")
        print(f"   {len(faces)} person(s) remaining")
    else:
        print(f"\n❌ Failed to save changes")


def show_statistics(db_path="simple_faces.pkl"):
    """Show detailed statistics about the database"""
    print(f"\n{'='*70}")
    print("📊 DATABASE STATISTICS")
    print(f"{'='*70}")

    faces = load_database(db_path)

    if faces is None:
        return

    if not faces:
        print("\n📂 Database is empty")
        return

    total_persons = len(faces)
    total_samples = 0
    sample_counts = []

    for name, data in faces.items():
        if isinstance(data, dict):
            count = len(data.get('individual', []))
        else:
            count = len(data)

        total_samples += count
        sample_counts.append(count)

    avg_samples = total_samples / total_persons if total_persons > 0 else 0
    min_samples = min(sample_counts) if sample_counts else 0
    max_samples = max(sample_counts) if sample_counts else 0

    print(f"\n📈 Overall Statistics:")
    print(f"   Total persons: {total_persons}")
    print(f"   Total samples: {total_samples}")
    print(f"   Average samples per person: {avg_samples:.1f}")
    print(f"   Minimum samples: {min_samples}")
    print(f"   Maximum samples: {max_samples}")

    # Quality distribution
    excellent = sum(1 for c in sample_counts if c >= 8)
    good = sum(1 for c in sample_counts if 5 <= c < 8)
    minimum = sum(1 for c in sample_counts if 3 <= c < 5)
    poor = sum(1 for c in sample_counts if c < 3)

    print(f"\n🏆 Quality Distribution:")
    print(f"   ✅ Excellent (8+ samples): {excellent} persons")
    print(f"   👍 Good (5-7 samples): {good} persons")
    print(f"   ⚠️  Minimum (3-4 samples): {minimum} persons")
    print(f"   ❌ Poor (< 3 samples): {poor} persons")

    # Database file size
    if os.path.exists(db_path):
        file_size = os.path.getsize(db_path)
        print(f"\n💾 Database File:")
        print(f"   Path: {db_path}")
        print(f"   Size: {file_size:,} bytes ({file_size/1024:.1f} KB)")

def update_employee_id(db_path="simple_faces.pkl"):
    """Update employee ID for a person without deleting face data"""
    print(f"\n{'='*70}")
    print("🆔 UPDATE EMPLOYEE ID")
    print(f"{'='*70}")

    faces = list_registered_faces(db_path)

    if faces is None or not faces:
        return

    print("\n📝 Enter the name to update employee ID for")
    name = input("   Name: ").strip()

    if not name:
        print("❌ Cancelled - no name entered")
        return

    if name not in faces:
        print(f"❌ '{name}' not found in database")
        print(f"   Available names: {', '.join(faces.keys())}")
        return

    # Show current employee ID if exists
    data = faces[name]
    current_id = data.get('employee_id') if isinstance(data, dict) else None
    if current_id:
        print(f"   Current employee ID: {current_id}")
    else:
        print(f"   Current employee ID: (not set)")

    new_id = input("   Enter new employee ID: ").strip()

    if not new_id:
        print("❌ Cancelled - no employee ID entered")
        return

    # Confirmation
    print(f"\n⚠️  Confirm update:")
    print(f"   Name: {name}")
    print(f"   New Employee ID: {new_id}")
    confirm = input("   Type 'yes' to confirm: ").strip().lower()

    if confirm != 'yes':
        print("❌ Cancelled")
        return

    # Perform update - preserve all other data
    if isinstance(data, dict):
        faces[name]['employee_id'] = new_id
    else:
        # Convert legacy format to new format
        import numpy as np
        averaged = np.mean(data, axis=0)
        averaged = averaged / (np.linalg.norm(averaged) + 1e-10)
        faces[name] = {
            'individual': data,
            'averaged': averaged,
            'employee_id': new_id
        }

    if save_database(faces, db_path):
        print(f"\n✅ Successfully updated employee ID for '{name}' to '{new_id}'!")
    else:
        print(f"\n❌ Failed to save changes")


def main():
    """Main menu"""
    db_path = "simple_faces.pkl"

    # Print header
    print("\n" + "="*70)
    print("          FACE DATABASE MANAGER")
    print("          Rename & Delete Registered Faces")
    print("="*70)

    # Check if database exists
    if not os.path.exists(db_path):
        print(f"\n❌ ERROR: Face database not found!")
        print(f"   Looking for: {db_path}")
        print(f"   Current directory: {os.getcwd()}")
        print("\n💡 Tip: Make sure you run this script from the same directory")
        print("         where your attendance system is located.")
        sys.exit(1)

    while True:
        print(f"\n{'='*70}")
        print("MENU OPTIONS")
        print(f"{'='*70}")
        print("  1. 📋 List all registered faces")
        print("  2. ✏️  Rename a person")
        print("  3. 🗑️  Delete a person")
        print("  4. 📊 Show statistics")
        print("  5. 🆔 Update employee ID")
        print("  6. 🚪 Exit")
        print(f"{'='*70}")

        choice = input("\nEnter choice (1-6): ").strip()

        if choice == '1':
            list_registered_faces(db_path)

        elif choice == '2':
            rename_person(db_path)

        elif choice == '3':
            delete_person(db_path)

        elif choice == '4':
            show_statistics(db_path)

        elif choice == '5':
            update_employee_id(db_path)

        elif choice == '6':
            print("\n👋 Goodbye!")
            break

        else:
            print("\n❌ Invalid choice - please enter 1-6")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n👋 Goodbye!")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
