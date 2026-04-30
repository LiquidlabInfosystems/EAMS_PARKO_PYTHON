#!/usr/bin/env python3
"""
Attendance State Manager Module
Manages business logic for each person's attendance state
Enforces proper sequence:
- TIME IN -> TIME OUT -> TIME IN (repeat)
- BREAK START -> BREAK END -> BREAK START (repeat) [Must be TIMED IN]
- JOB START -> JOB END -> JOB START (repeat) [INDEPENDENT of TIME IN/OUT]
"""

import json
import os
from datetime import datetime, timezone
from enum import Enum
from typing import Dict, Optional, Tuple


def _make_naive(dt: Optional[datetime]) -> Optional[datetime]:
    """Convert timezone-aware datetime to naive (remove timezone info)"""
    if dt is None:
        return None
    if dt.tzinfo is not None:
        return dt.replace(tzinfo=None)
    return dt


class AttendanceState(Enum):
    """Attendance states for tracking"""
    TIMED_OUT = "timed_out"
    TIMED_IN = "timed_in"
    ON_BREAK = "on_break"


class PersonState:
    """Represents the current state of a person"""
    
    def __init__(self, name: str):
        self.name = name
        self.attendance_state = AttendanceState.TIMED_OUT
        self.on_job = False  # Separate flag - INDEPENDENT of time in/out
        self.last_time_in = None
        self.last_time_out = None
        self.last_break_start = None
        self.last_break_end = None
        self.last_job_start = None
        self.last_job_end = None
    
    def to_dict(self):
        return {
            "name": self.name,
            "attendance_state": self.attendance_state.value,
            "on_job": self.on_job,
            "last_time_in": self.last_time_in.isoformat() if self.last_time_in else None,
            "last_time_out": self.last_time_out.isoformat() if self.last_time_out else None,
            "last_break_start": self.last_break_start.isoformat() if self.last_break_start else None,
            "last_break_end": self.last_break_end.isoformat() if self.last_break_end else None,
            "last_job_start": self.last_job_start.isoformat() if self.last_job_start else None,
            "last_job_end": self.last_job_end.isoformat() if self.last_job_end else None
        }
    
    @classmethod
    def from_dict(cls, data: dict):
        person = cls(data["name"])
        person.attendance_state = AttendanceState(data["attendance_state"])
        person.on_job = data.get("on_job", False)
        person.last_time_in = datetime.fromisoformat(data["last_time_in"]) if data["last_time_in"] else None
        person.last_time_out = datetime.fromisoformat(data["last_time_out"]) if data["last_time_out"] else None
        person.last_break_start = datetime.fromisoformat(data["last_break_start"]) if data["last_break_start"] else None
        person.last_break_end = datetime.fromisoformat(data["last_break_end"]) if data.get("last_break_end") else None
        person.last_job_start = datetime.fromisoformat(data["last_job_start"]) if data.get("last_job_start") else None
        person.last_job_end = datetime.fromisoformat(data["last_job_end"]) if data.get("last_job_end") else None
        return person


class AttendanceStateManager:
    """Manages attendance states for all people"""
    
    def __init__(self, state_file: str = "attendance_states.json"):
        self.state_file = state_file
        self.people: Dict[str, PersonState] = {}
        self.load_states()
    
    def load_states(self):
        if os.path.exists(self.state_file):
            try:
                with open(self.state_file, 'r') as f:
                    data = json.load(f)
                    for person_data in data:
                        person = PersonState.from_dict(person_data)
                        self.people[person.name] = person
                print(f"✓ Loaded {len(self.people)} person states")
            except Exception as e:
                print(f"⚠️ Error loading states: {e}")
                self.people = {}
    
    def save_states(self):
        try:
            data = [person.to_dict() for person in self.people.values()]
            with open(self.state_file, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            print(f"⚠️ Error saving states: {e}")
    
    def get_person(self, name: str) -> PersonState:
        if name not in self.people:
            self.people[name] = PersonState(name)
        return self.people[name]
    
    def sync_from_server(self, name: str, api_response: dict) -> Tuple[bool, str, bool]:
        """
        Sync local state from server API response
        
        Args:
            name: Person's name
            api_response: Response from get_attendance_status API
            
        Returns:
            Tuple of (success, message, is_blocked)
            - success: True if sync succeeded
            - message: Info/error message to display
            - is_blocked: True if user should be blocked from actions
        """
        if not api_response:
            # API offline - use local state
            return True, "Using offline mode", False
        
        # Check for blocking conditions
        if not api_response.get('success', False):
            message = api_response.get('message', 'Unknown error')
            
            # Task is running - block attendance
            if api_response.get('isTaskRunning', False):
                return False, "Task already running. Please pause or complete the task.", True
            
            # Previous day not timed out - approval required
            if 'Previous day' in message or 'approval' in message.lower():
                return False, message, True
            
            # Employee not found
            if 'not found' in message.lower():
                return False, "Employee not found on server", True
            
            # Other errors
            return False, message, True
        
        # Success - update local state from server
        person = self.get_person(name)
        
        # Parse ISO timestamps from server
        def parse_iso(iso_str):
            if iso_str:
                try:
                    # Handle ISO format with Z suffix
                    if iso_str.endswith('Z'):
                        iso_str = iso_str[:-1] + '+00:00'
                    return datetime.fromisoformat(iso_str)
                except:
                    return None
            return None
        
        person.last_time_in = parse_iso(api_response.get('last_time_in'))
        person.last_time_out = parse_iso(api_response.get('last_time_out'))
        person.last_break_start = parse_iso(api_response.get('last_break_start'))
        person.last_break_end = parse_iso(api_response.get('last_break_end'))
        person.last_job_start = parse_iso(api_response.get('last_job_start'))
        person.last_job_end = parse_iso(api_response.get('last_job_end'))
        
        # Determine attendance state from timestamps
        if person.last_break_start and (not person.last_break_end or person.last_break_start > person.last_break_end):
            person.attendance_state = AttendanceState.ON_BREAK
        elif person.last_time_in and (not person.last_time_out or person.last_time_in > person.last_time_out):
            person.attendance_state = AttendanceState.TIMED_IN
        else:
            person.attendance_state = AttendanceState.TIMED_OUT
        
        # Determine job state
        if person.last_job_start and (not person.last_job_end or person.last_job_start > person.last_job_end):
            person.on_job = True
        else:
            person.on_job = False
        
        # Save synced state locally
        self.save_states()
        
        return True, "Status synced from server", False
    
    def can_time_in(self, name: str) -> Tuple[bool, str]:
        person = self.get_person(name)
        if person.attendance_state == AttendanceState.TIMED_IN:
            return False, f"{name} is already TIMED IN.\n\nPlease TIME OUT first."
        if person.attendance_state == AttendanceState.ON_BREAK:
            return False, f"{name} is ON BREAK.\n\nPlease END BREAK first."
        return True, f"OK"
    
    def can_time_out(self, name: str) -> Tuple[bool, str]:
        person = self.get_person(name)
        if person.attendance_state == AttendanceState.TIMED_OUT:
            return False, f"{name} is already TIMED OUT.\n\nPlease TIME IN first."
        if person.attendance_state == AttendanceState.ON_BREAK:
            return False, f"{name} is ON BREAK.\n\nPlease END BREAK first."
        return True, f"OK"
    
    def can_break_start(self, name: str) -> Tuple[bool, str]:
        person = self.get_person(name)
        if person.attendance_state == AttendanceState.ON_BREAK:
            return False, f"{name} is already ON BREAK.\n\nPlease END current break first."
        if person.attendance_state != AttendanceState.TIMED_IN:
            return False, f"{name} must be TIMED IN.\nPlease TIME IN first."
        return True, f"OK"
    
    def can_break_end(self, name: str) -> Tuple[bool, str]:
        person = self.get_person(name)
        if person.attendance_state != AttendanceState.ON_BREAK:
            return False, f"{name} is not on break.\n\nPlease START BREAK first."
        return True, f"OK"
    
    def can_job_start(self, name: str) -> Tuple[bool, str]:
        person = self.get_person(name)
        if person.on_job:
            return False, f"{name} is already ON A JOB.\n\nPlease END current job first."
        if person.attendance_state != AttendanceState.TIMED_IN:
            return False, f"{name} must be TIMED IN.\nPlease TIME IN first."
        return True, f"OK"
    
    def can_job_end(self, name: str) -> Tuple[bool, str]:
        person = self.get_person(name)
        if not person.on_job:
            return False, f"{name} is not on a job.\n\nPlease START JOB first."
        return True, f"OK"
    
    def time_in(self, name: str) -> Tuple[bool, str]:
        can_do, msg = self.can_time_in(name)
        if not can_do:
            return False, msg
        person = self.get_person(name)
        person.last_time_in = datetime.now()
        person.attendance_state = AttendanceState.TIMED_IN
        self.save_states()
        return True, f"✓ {name} TIMED IN"
    
    def time_out(self, name: str) -> Tuple[bool, str]:
        can_do, msg = self.can_time_out(name)
        if not can_do:
            return False, msg
        person = self.get_person(name)
        person.last_time_out = datetime.now()
        person.attendance_state = AttendanceState.TIMED_OUT
        self.save_states()
        return True, f"✓ {name} TIMED OUT"
    
    def break_start(self, name: str) -> Tuple[bool, str]:
        can_do, msg = self.can_break_start(name)
        if not can_do:
            return False, msg
        person = self.get_person(name)
        person.last_break_start = datetime.now()
        person.attendance_state = AttendanceState.ON_BREAK
        self.save_states()
        return True, f"✓ {name} BREAK STARTED"
    
    def break_end(self, name: str) -> Tuple[bool, str]:
        can_do, msg = self.can_break_end(name)
        if not can_do:
            return False, msg
        person = self.get_person(name)
        person.last_break_end = datetime.now()
        person.attendance_state = AttendanceState.TIMED_IN
        self.save_states()
        return True, f"✓ {name} BREAK ENDED"
    
    def job_start(self, name: str) -> Tuple[bool, str]:
        can_do, msg = self.can_job_start(name)
        if not can_do:
            return False, msg
        person = self.get_person(name)
        person.last_job_start = datetime.now()
        person.on_job = True
        self.save_states()
        return True, f"✓ {name} JOB STARTED"
    
    def job_end(self, name: str) -> Tuple[bool, str]:
        can_do, msg = self.can_job_end(name)
        if not can_do:
            return False, msg
        person = self.get_person(name)
        person.last_job_end = datetime.now()
        person.on_job = False
        self.save_states()
        return True, f"✓ {name} JOB ENDED"
    
    def get_state_display(self, name: str) -> str:
        person = self.get_person(name)
        states = []
        if person.attendance_state == AttendanceState.TIMED_OUT:
            states.append("🔴 TIMED OUT")
        elif person.attendance_state == AttendanceState.TIMED_IN:
            states.append("🟢 TIMED IN")
        elif person.attendance_state == AttendanceState.ON_BREAK:
            states.append("🟡 ON BREAK")
        if person.on_job:
            states.append("🔵 ON JOB")
        return " | ".join(states) if states else "⚪ UNKNOWN"
