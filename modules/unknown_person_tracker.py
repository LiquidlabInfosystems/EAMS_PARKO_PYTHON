#!/usr/bin/env python3
"""
Unknown Person Tracker Module
Tracks unknown persons by face embeddings to differentiate between individuals
Each unknown person gets a unique ID (foreign_1, foreign_2, etc.)
"""

import json
import os
import time
from datetime import datetime
from typing import Dict, Tuple, Optional
import numpy as np


class UnknownPerson:
    """Represents an unknown person detected by the system"""
    
    def __init__(self, person_id: str, embedding: np.ndarray, first_seen: float):
        self.person_id = person_id
        self.embedding = embedding
        self.first_seen = first_seen
        self.last_seen = first_seen
        self.last_incident_time = None
        self.incident_count = 0
    
    def to_dict(self):
        return {
            "person_id": self.person_id,
            "embedding": self.embedding.tolist(),
            "first_seen": self.first_seen,
            "last_seen": self.last_seen,
            "last_incident_time": self.last_incident_time,
            "incident_count": self.incident_count
        }
    
    @classmethod
    def from_dict(cls, data: dict):
        person = cls(
            person_id=data["person_id"],
            embedding=np.array(data["embedding"]),
            first_seen=data["first_seen"]
        )
        person.last_seen = data["last_seen"]
        person.last_incident_time = data.get("last_incident_time")
        person.incident_count = data.get("incident_count", 0)
        return person


class UnknownPersonTracker:
    """
    Tracks unknown persons using face embeddings
    Differentiates between individuals to apply appropriate cooldowns
    """
    
    def __init__(self, 
                 similarity_threshold: float = 0.4,
                 storage_file: str = "unknown_persons.json",
                 cooldown_seconds: float = 300.0):
        """
        Initialize tracker
        
        Args:
            similarity_threshold: Cosine similarity threshold to match same person
            storage_file: JSON file to persist unknown person data
            cooldown_seconds: Cooldown period for same person (seconds)
        """
        self.similarity_threshold = similarity_threshold
        self.storage_file = storage_file
        self.cooldown_seconds = cooldown_seconds
        
        self.unknown_persons: Dict[str, UnknownPerson] = {}
        self.next_id_number = 1
        
        self.load_from_file()
    
    def compute_similarity(self, embedding1: np.ndarray, embedding2: np.ndarray) -> float:
        """Compute cosine similarity between two embeddings"""
        embedding1 = embedding1.flatten()
        embedding2 = embedding2.flatten()
        
        dot_product = np.dot(embedding1, embedding2)
        norm1 = np.linalg.norm(embedding1)
        norm2 = np.linalg.norm(embedding2)
        
        if norm1 == 0 or norm2 == 0:
            return 0.0
        
        return dot_product / (norm1 * norm2)
    
    def find_matching_unknown(self, embedding: np.ndarray) -> Optional[str]:
        """
        Find if this embedding matches any known unknown person
        
        Args:
            embedding: Face embedding to match
        
        Returns:
            person_id if match found, None otherwise
        """
        best_match_id = None
        best_similarity = -1.0
        
        for person_id, person in self.unknown_persons.items():
            similarity = self.compute_similarity(embedding, person.embedding)
            
            if similarity > best_similarity:
                best_similarity = similarity
                best_match_id = person_id
        
        # Check if best match exceeds threshold
        if best_similarity >= self.similarity_threshold:
            return best_match_id
        
        return None
    
    def add_new_unknown(self, embedding: np.ndarray) -> str:
        """
        Add a new unknown person
        
        Args:
            embedding: Face embedding of the new unknown person
        
        Returns:
            person_id assigned to this unknown person
        """
        person_id = f"foreign_{self.next_id_number}"
        current_time = time.time()
        
        self.unknown_persons[person_id] = UnknownPerson(
            person_id=person_id,
            embedding=embedding,
            first_seen=current_time
        )
        
        self.next_id_number += 1
        self.save_to_file()
        
        print(f"✓ New unknown person registered: {person_id}")
        return person_id
    
    def update_last_seen(self, person_id: str):
        """Update the last seen timestamp for a person"""
        if person_id in self.unknown_persons:
            self.unknown_persons[person_id].last_seen = time.time()
            self.save_to_file()
    
    def can_send_incident(self, person_id: str) -> Tuple[bool, str]:
        """
        Check if incident can be sent for this person (respects cooldown)
        
        Args:
            person_id: The unknown person ID
        
        Returns:
            (can_send, reason) tuple
        """
        if person_id not in self.unknown_persons:
            return True, "New unknown person"
        
        person = self.unknown_persons[person_id]
        
        if person.last_incident_time is None:
            return True, "First incident for this person"
        
        current_time = time.time()
        time_since_last = current_time - person.last_incident_time
        
        if time_since_last >= self.cooldown_seconds:
            return True, f"Cooldown expired ({time_since_last:.0f}s elapsed)"
        
        remaining = self.cooldown_seconds - time_since_last
        return False, f"Cooldown active ({remaining:.0f}s remaining)"
    
    def record_incident(self, person_id: str):
        """Record that an incident was sent for this person"""
        if person_id in self.unknown_persons:
            person = self.unknown_persons[person_id]
            person.last_incident_time = time.time()
            person.incident_count += 1
            self.save_to_file()
            print(f"✓ Incident recorded for {person_id} (total: {person.incident_count})")
    
    def get_or_create_unknown(self, embedding: np.ndarray) -> Tuple[str, bool]:
        """
        Get existing unknown person ID or create new one
        
        Args:
            embedding: Face embedding
        
        Returns:
            (person_id, is_new) tuple
        """
        # Try to find match
        person_id = self.find_matching_unknown(embedding)
        
        if person_id:
            # Found existing unknown person
            self.update_last_seen(person_id)
            return person_id, False
        else:
            # New unknown person
            person_id = self.add_new_unknown(embedding)
            return person_id, True
    
    def get_person_info(self, person_id: str) -> Optional[Dict]:
        """Get information about an unknown person"""
        if person_id in self.unknown_persons:
            person = self.unknown_persons[person_id]
            return {
                "person_id": person.person_id,
                "first_seen": datetime.fromtimestamp(person.first_seen).isoformat(),
                "last_seen": datetime.fromtimestamp(person.last_seen).isoformat(),
                "incident_count": person.incident_count,
                "last_incident": datetime.fromtimestamp(person.last_incident_time).isoformat() if person.last_incident_time else None
            }
        return None
    
    def cleanup_old_entries(self, max_age_days: int = 30):
        """Remove entries older than max_age_days"""
        current_time = time.time()
        cutoff_time = current_time - (max_age_days * 24 * 3600)
        
        to_remove = []
        for person_id, person in self.unknown_persons.items():
            if person.last_seen < cutoff_time:
                to_remove.append(person_id)
        
        for person_id in to_remove:
            del self.unknown_persons[person_id]
            print(f"Cleaned up old entry: {person_id}")
        
        if to_remove:
            self.save_to_file()
    
    def save_to_file(self):
        """Save unknown persons to JSON file"""
        try:
            data = {
                "next_id_number": self.next_id_number,
                "persons": [person.to_dict() for person in self.unknown_persons.values()]
            }
            with open(self.storage_file, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            print(f"⚠️ Error saving unknown persons: {e}")
    
    def load_from_file(self):
        """Load unknown persons from JSON file"""
        if os.path.exists(self.storage_file):
            try:
                with open(self.storage_file, 'r') as f:
                    data = json.load(f)
                
                self.next_id_number = data.get("next_id_number", 1)
                
                for person_data in data.get("persons", []):
                    person = UnknownPerson.from_dict(person_data)
                    self.unknown_persons[person.person_id] = person
                
                print(f"✓ Loaded {len(self.unknown_persons)} unknown person records")
                
                # Update next ID number to avoid conflicts
                if self.unknown_persons:
                    max_id = max([int(p.person_id.split('_')[1]) for p in self.unknown_persons.values()])
                    self.next_id_number = max_id + 1
                
            except Exception as e:
                print(f"⚠️ Error loading unknown persons: {e}")
                self.unknown_persons = {}
                self.next_id_number = 1
        else:
            print("○ No existing unknown person records found")
    
    def get_statistics(self) -> Dict:
        """Get statistics about tracked unknown persons"""
        total_persons = len(self.unknown_persons)
        total_incidents = sum(p.incident_count for p in self.unknown_persons.values())
        
        active_persons = []
        current_time = time.time()
        for person in self.unknown_persons.values():
            if current_time - person.last_seen < 3600:  # Seen in last hour
                active_persons.append(person.person_id)
        
        return {
            "total_unknown_persons": total_persons,
            "total_incidents": total_incidents,
            "active_in_last_hour": len(active_persons),
            "active_persons": active_persons
        }


# Example usage
if __name__ == "__main__":
    # Test the tracker
    tracker = UnknownPersonTracker()
    
    # Create dummy embeddings
    embedding1 = np.random.rand(512)
    embedding2 = np.random.rand(512)
    embedding3 = embedding1 + np.random.rand(512) * 0.01  # Similar to embedding1
    
    # Test 1: New person
    person_id1, is_new1 = tracker.get_or_create_unknown(embedding1)
    print(f"Person 1: {person_id1}, New: {is_new1}")
    
    # Test 2: Different person
    person_id2, is_new2 = tracker.get_or_create_unknown(embedding2)
    print(f"Person 2: {person_id2}, New: {is_new2}")
    
    # Test 3: Same as person 1
    person_id3, is_new3 = tracker.get_or_create_unknown(embedding3)
    print(f"Person 3: {person_id3}, New: {is_new3}")
    
    # Test cooldown
    can_send, reason = tracker.can_send_incident(person_id1)
    print(f"Can send for {person_id1}: {can_send}, Reason: {reason}")
    
    # Record incident
    tracker.record_incident(person_id1)
    
    # Check cooldown again
    can_send, reason = tracker.can_send_incident(person_id1)
    print(f"Can send for {person_id1}: {can_send}, Reason: {reason}")
    
    # Stats
    print(f"\nStatistics: {tracker.get_statistics()}")
