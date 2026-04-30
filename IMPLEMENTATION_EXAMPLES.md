# Implementation Examples - Face Recognition Optimization

## Quick Start: Apply These Changes First

### 1. Update config.py (Immediate Impact)

```python
# config.py - OPTIMIZED SETTINGS

# ★★★ CAMERA SETTINGS ★★★
CAMERA_RESOLUTION = (640, 480)  # Changed from (960, 720)
CAMERA_FPS = 30  # Changed from 25

# ★★★ RECOGNITION SETTINGS ★★★
DETECTION_CONFIDENCE = 0.6  # Changed from 0.5
RECOGNITION_THRESHOLD = 0.60  # Changed from 0.55

# ★★★ PREPROCESSING ★★★
PREPROCESSING_METHOD = 'histogram'  # Changed from 'clahe'

# ★★★ LIVENESS CONFIGURATION ★★★
ENABLE_LIVENESS = False  # Changed from True (for speed)

# ★★★ NEW: PERFORMANCE SETTINGS ★★★
PROCESS_EVERY_N_FRAMES = 2  # Process every 2nd frame
RECOGNIZE_EVERY_N_FRAMES = 3  # Recognize every 3rd processed frame
USE_FACE_TRACKING = True  # Enable face tracking
TRACKING_REDETECT_INTERVAL = 5  # Re-detect every 5 frames
```

### 2. Add Frame Skipping to attendance_gui.py

Add these lines to the `__init__` method:
```python
# In AttendanceKioskGUI.__init__()
self.frame_skip_counter = 0
self.recognition_counter = 0
```

Modify `process_frame()` method:
```python
def process_frame(self):
    if self.latest_frame is None or self.processing:
        return
    
    # Always display for smooth video
    if self.display_stack.currentIndex() == 1:
        self.display_frame(self.latest_frame)
    
    # Frame skipping for processing
    self.frame_skip_counter += 1
    if self.frame_skip_counter % config.PROCESS_EVERY_N_FRAMES != 0:
        return
    
    self.processing = True
    # ... rest of processing code
```


### 3. Add Face Tracking Module

Create new file `modules/face_tracker.py`:
```python
#!/usr/bin/env python3
"""
Face Tracker Module - Reduces detection overhead
"""

class FaceTracker:
    def __init__(self, redetect_interval=5):
        self.last_bbox = None
        self.frames_since_detection = 0
        self.redetect_interval = redetect_interval
        self.tracking_active = False
    
    def should_detect(self):
        """Check if we should run full detection"""
        if not self.tracking_active or self.last_bbox is None:
            return True
        
        self.frames_since_detection += 1
        return self.frames_since_detection >= self.redetect_interval
    
    def update(self, bbox):
        """Update tracker with new detection"""
        self.last_bbox = bbox
        self.frames_since_detection = 0
        self.tracking_active = True
    
    def reset(self):
        """Reset tracker"""
        self.last_bbox = None
        self.frames_since_detection = 0
        self.tracking_active = False
    
    def get_search_roi(self, frame_shape, expansion=0.5):
        """Get region of interest for next frame"""
        if self.last_bbox is None:
            return None
        
        h, w = frame_shape[:2]
        x, y, bw, bh = self.last_bbox
        
        # Expand search area
        margin = int(max(bw, bh) * expansion)
        x1 = max(0, x - margin)
        y1 = max(0, y - margin)
        x2 = min(w, x + bw + margin)
        y2 = min(h, y + bh + margin)
        
        return (x1, y1, x2, y2)
```

### 4. Integrate Face Tracker in face_recognizer.py

Add to `FaceRecognizer.__init__()`:
```python
from modules.face_tracker import FaceTracker

# In __init__
if config.USE_FACE_TRACKING:
    self.face_tracker = FaceTracker(
        redetect_interval=config.TRACKING_REDETECT_INTERVAL
    )
else:
    self.face_tracker = None
```

Modify `process_frame()`:
```python
def process_frame(self, image_rgb, preprocess=True):
    # Optional preprocessing
    if preprocess:
        processed = self.preprocess_image(image_rgb)
    else:
        processed = image_rgb
    
    # Use tracking to reduce detection calls
    if self.face_tracker and not self.face_tracker.should_detect():
        # Use ROI from last detection
        roi = self.face_tracker.get_search_roi(processed.shape)
        if roi:
            x1, y1, x2, y2 = roi
            roi_frame = processed[y1:y2, x1:x2]
            detected_faces = self.detect_faces(roi_frame)
            
            # Adjust coordinates back to full frame
            for face in detected_faces:
                bx, by, bw, bh = face['bbox']
                face['bbox'] = (bx + x1, by + y1, bw, bh)
        else:
            detected_faces = self.detect_faces(processed)
    else:
        # Full detection
        detected_faces = self.detect_faces(processed)
        
        # Update tracker
        if self.face_tracker and detected_faces:
            self.face_tracker.update(detected_faces[0]['bbox'])
    
    # ... rest of processing
```


### 5. Add Embedding Cache

Create new file `modules/embedding_cache.py`:
```python
#!/usr/bin/env python3
"""
Embedding Cache - Reduces redundant computations
"""
import time
import numpy as np

class EmbeddingCache:
    def __init__(self, max_age_seconds=2.0, max_size=50):
        self.cache = {}  # {key: (embedding, timestamp)}
        self.max_age = max_age_seconds
        self.max_size = max_size
    
    def get(self, key):
        """Get cached embedding if still valid"""
        if key in self.cache:
            embedding, timestamp = self.cache[key]
            if time.time() - timestamp < self.max_age:
                return embedding
            else:
                # Expired
                del self.cache[key]
        return None
    
    def set(self, key, embedding):
        """Cache an embedding"""
        # Cleanup if too large
        if len(self.cache) >= self.max_size:
            self._cleanup_oldest()
        
        self.cache[key] = (embedding.copy(), time.time())
    
    def _cleanup_oldest(self):
        """Remove oldest entries"""
        if not self.cache:
            return
        
        # Sort by timestamp
        sorted_items = sorted(
            self.cache.items(),
            key=lambda x: x[1][1]
        )
        
        # Remove oldest 20%
        remove_count = max(1, len(sorted_items) // 5)
        for key, _ in sorted_items[:remove_count]:
            del self.cache[key]
    
    def clear(self):
        """Clear all cache"""
        self.cache.clear()
```

Integrate in `face_recognizer.py`:
```python
from modules.embedding_cache import EmbeddingCache

# In __init__
self.embedding_cache = EmbeddingCache(max_age_seconds=2.0)

# In process_frame, before extracting embedding:
cache_key = f"{x}_{y}_{w}_{h}"
embedding = self.embedding_cache.get(cache_key)

if embedding is None:
    embedding = self.extract_embedding(face_img)
    if embedding is not None:
        self.embedding_cache.set(cache_key, embedding)
```

### 6. Optimize Database Loading

Add to `face_recognizer.py`:
```python
def optimize_database(self):
    """Pre-compute averaged embeddings for faster matching"""
    print("🔧 Optimizing database...")
    
    for name, data in self.known_faces.items():
        if isinstance(data, list):
            # Old format - convert to new format
            embeddings = data
            averaged = np.mean(embeddings, axis=0)
            averaged = averaged / (np.linalg.norm(averaged) + 1e-10)
            
            self.known_faces[name] = {
                'individual': embeddings,
                'averaged': averaged
            }
        elif isinstance(data, dict):
            # New format - ensure averaged exists
            if 'averaged' not in data:
                embeddings = data['individual']
                averaged = np.mean(embeddings, axis=0)
                averaged = averaged / (np.linalg.norm(averaged) + 1e-10)
                data['averaged'] = averaged
    
    self.save_database()
    print("✓ Database optimized")

# Call in __init__ after loading database
self.optimize_database()
```


### 7. Add Performance Monitor

Create new file `modules/performance_monitor.py`:
```python
#!/usr/bin/env python3
"""
Performance Monitoring Module
"""
import time
import numpy as np
from collections import deque

class PerformanceMonitor:
    def __init__(self, window_size=100):
        self.frame_times = deque(maxlen=window_size)
        self.detection_times = deque(maxlen=window_size)
        self.recognition_times = deque(maxlen=window_size)
        self.last_frame_time = time.time()
    
    def start_frame(self):
        """Mark start of frame processing"""
        self.frame_start = time.time()
    
    def end_frame(self):
        """Mark end of frame processing"""
        duration = time.time() - self.frame_start
        self.frame_times.append(duration)
    
    def log_detection(self, duration):
        """Log detection time"""
        self.detection_times.append(duration)
    
    def log_recognition(self, duration):
        """Log recognition time"""
        self.recognition_times.append(duration)
    
    def get_fps(self):
        """Calculate current FPS"""
        if not self.frame_times:
            return 0.0
        avg_time = np.mean(self.frame_times)
        return 1.0 / avg_time if avg_time > 0 else 0.0
    
    def get_stats(self):
        """Get performance statistics"""
        return {
            'fps': round(self.get_fps(), 1),
            'avg_frame_ms': round(np.mean(self.frame_times) * 1000, 1) if self.frame_times else 0,
            'avg_detection_ms': round(np.mean(self.detection_times) * 1000, 1) if self.detection_times else 0,
            'avg_recognition_ms': round(np.mean(self.recognition_times) * 1000, 1) if self.recognition_times else 0,
            'frame_count': len(self.frame_times)
        }
    
    def print_stats(self):
        """Print statistics to console"""
        stats = self.get_stats()
        print(f"\n📊 Performance Stats:")
        print(f"   FPS: {stats['fps']}")
        print(f"   Frame: {stats['avg_frame_ms']}ms")
        print(f"   Detection: {stats['avg_detection_ms']}ms")
        print(f"   Recognition: {stats['avg_recognition_ms']}ms")
```

Integrate in `attendance_gui.py`:
```python
from modules.performance_monitor import PerformanceMonitor

# In __init__
self.perf_monitor = PerformanceMonitor()

# Add timer to print stats every 10 seconds
self.stats_timer = QTimer()
self.stats_timer.timeout.connect(self.print_performance_stats)
self.stats_timer.start(10000)  # 10 seconds

def print_performance_stats(self):
    """Print performance statistics"""
    self.perf_monitor.print_stats()

# In process_frame
def process_frame(self):
    self.perf_monitor.start_frame()
    
    # ... processing code ...
    
    self.perf_monitor.end_frame()
```

### 8. Temporal Consistency Filter

Create new file `modules/temporal_filter.py`:
```python
#!/usr/bin/env python3
"""
Temporal Consistency Filter - Stabilize recognition results
"""
from collections import deque
import numpy as np

class TemporalFilter:
    def __init__(self, window_size=5, confidence_threshold=0.6):
        self.window_size = window_size
        self.confidence_threshold = confidence_threshold
        self.history = deque(maxlen=window_size)
        self.last_stable_result = None
    
    def add_result(self, name, confidence):
        """Add recognition result"""
        self.history.append((name, confidence))
    
    def get_stable_result(self):
        """Get stable recognition result"""
        if len(self.history) < 3:
            return self.last_stable_result, 0.0
        
        # Count occurrences
        name_counts = {}
        for name, conf in self.history:
            if name not in name_counts:
                name_counts[name] = []
            name_counts[name].append(conf)
        
        # Find most common with high confidence
        best_name = None
        best_score = 0.0
        
        for name, confs in name_counts.items():
            occurrence_ratio = len(confs) / len(self.history)
            
            if occurrence_ratio >= self.confidence_threshold:
                avg_conf = np.mean(confs)
     