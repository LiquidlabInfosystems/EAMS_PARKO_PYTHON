"""
Temporal Recognition Buffer
Implements voting-based recognition for stability across multiple frames
"""

from collections import Counter
from typing import Optional, Tuple, Dict, List
import time


class TemporalRecognitionBuffer:
    """
    Buffer that maintains recognition results across multiple frames
    and provides consensus-based stable identity recognition.
    
    This helps prevent flickering/misidentification where the system
    briefly detects person A as person B due to frame-by-frame variability.
    """
    
    def __init__(self, buffer_size: int = 5, agreement_threshold: float = 0.6):
        """
        Initialize temporal recognition buffer.
        
        Args:
            buffer_size: Number of recent recognition results to maintain
            agreement_threshold: Fraction of buffer that must agree (0.0-1.0)
        """
        self.buffer_size = buffer_size
        self.agreement_threshold = agreement_threshold
        self.buffer: List[Dict] = []
        
        # Anti-flicker: Track last confirmed identity
        self.last_confirmed_identity: Optional[str] = None
        self.last_confirmed_time: float = 0.0
        self.identity_lock_time: float = 2.0  # Seconds
        
    def set_identity_lock_time(self, seconds: float):
        """Set the identity lock time for anti-flicker protection"""
        self.identity_lock_time = seconds
        
    def add_result(self, name: str, similarity: float):
        """
        Add a recognition result to the buffer.
        
        Args:
            name: Recognized person's name (or "Unknown")
            similarity: Similarity score (0.0-1.0)
        """
        self.buffer.append({
            'name': name,
            'similarity': similarity,
            'timestamp': time.time()
        })
        
        # Maintain buffer size
        if len(self.buffer) > self.buffer_size:
            self.buffer.pop(0)
    
    def get_consensus(self) -> Tuple[Optional[str], float, bool]:
        """
        Get consensus identity from buffer with anti-flicker protection.
        
        Returns:
            (name, agreement_score, is_stable)
            - name: Consensus identity or None if no consensus
            - agreement_score: Fraction of buffer agreeing on identity
            - is_stable: True if identity has been stable for required time
        """
        if len(self.buffer) < 2:
            return None, 0.0, False
        
        # Filter out "Unknown" for voting (we want to find actual identities)
        known_results = [r for r in self.buffer if r['name'] != 'Unknown']
        
        if not known_results:
            # All unknown - reset confirmed identity after lock time
            if time.time() - self.last_confirmed_time > self.identity_lock_time:
                self.last_confirmed_identity = None
            return None, 0.0, False
        
        # Count votes for each name
        votes = Counter([r['name'] for r in known_results])
        
        if not votes:
            return None, 0.0, False
        
        # Get most common identity
        most_common_name, most_common_count = votes.most_common(1)[0]
        
        # Calculate agreement as fraction of total buffer (including unknowns)
        agreement = most_common_count / len(self.buffer)
        
        # Check if consensus meets threshold
        if agreement >= self.agreement_threshold:
            current_time = time.time()
            
            # Anti-flicker: If switching to different identity, check lock time
            if self.last_confirmed_identity and self.last_confirmed_identity != most_common_name:
                time_since_confirm = current_time - self.last_confirmed_time
                
                if time_since_confirm < self.identity_lock_time:
                    # Still within lock period - keep previous identity
                    # But only if previous identity is still in the buffer
                    if any(r['name'] == self.last_confirmed_identity for r in known_results):
                        return self.last_confirmed_identity, agreement, True
            
            # Update confirmed identity
            self.last_confirmed_identity = most_common_name
            self.last_confirmed_time = current_time
            
            return most_common_name, agreement, True
        
        # No consensus - return last confirmed if within lock time
        if self.last_confirmed_identity and time.time() - self.last_confirmed_time < self.identity_lock_time:
            return self.last_confirmed_identity, agreement, False
        
        return None, agreement, False
    
    def get_average_similarity(self, name: str) -> float:
        """
        Get average similarity for a specific person from buffer.
        
        Args:
            name: Person's name
            
        Returns:
            Average similarity score
        """
        matching = [r['similarity'] for r in self.buffer if r['name'] == name]
        return sum(matching) / len(matching) if matching else 0.0
    
    def clear(self):
        """Clear the buffer and reset state"""
        self.buffer.clear()
        self.last_confirmed_identity = None
        self.last_confirmed_time = 0.0
    
    def reset_for_new_person(self):
        """Reset buffer when a confirmed different person appears"""
        self.buffer.clear()
        # Keep last_confirmed_identity for lock comparison
    
    def get_buffer_summary(self) -> Dict:
        """Get summary of current buffer state"""
        if not self.buffer:
            return {'empty': True}
        
        votes = Counter([r['name'] for r in self.buffer])
        
        return {
            'size': len(self.buffer),
            'votes': dict(votes),
            'last_confirmed': self.last_confirmed_identity,
            'buffer_contents': [r['name'] for r in self.buffer]
        }
