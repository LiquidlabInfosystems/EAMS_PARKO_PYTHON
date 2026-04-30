"""
API Client Module for Attendance Events
Enhanced with health check monitoring, automatic retry, and persistent storage
Reads configuration from config.py
"""

import requests
import json
from datetime import datetime
from typing import Optional, Dict, Tuple
import threading
from queue import Queue
import time
import os

import config


class AttendanceAPIClient:
    """
    Enhanced API client that handles sending attendance events to remote API

    New Features:
    - Health check endpoint monitoring (/health)
    - Automatic retry when server comes back online
    - Persistent local storage for failed requests
    - Survives app restarts

    Configuration loaded from config.py
    """

    def __init__(self, server_ip: Optional[str] = None, server_port: Optional[int] = None, 
                 endpoint: Optional[str] = None, timeout: Optional[int] = None, health_endpoint: Optional[str] = None,
                 health_check_interval: Optional[int] = None, storage_file: Optional[str] = None):
        """
        Initialize API client with enhanced features

        Args:
            server_ip: Server IP address (defaults to config.API_SERVER_IP)
            server_port: Server port (defaults to config.API_SERVER_PORT)
            endpoint: API endpoint path (defaults to config.API_ENDPOINT)
            timeout: Request timeout in seconds (defaults to config.API_TIMEOUT)
        """
        # Use config values as defaults
        self.server_ip = server_ip if server_ip is not None else config.API_SERVER_IP
        self.server_port = server_port if server_port is not None else config.API_SERVER_PORT
        self.endpoint = endpoint if endpoint is not None else config.API_ENDPOINT
        self.timeout = timeout if timeout is not None else config.API_TIMEOUT

        # Health check endpoint
        self.health_endpoint = health_endpoint if health_endpoint is not None else config.API_HEALTH_ENDPOINT
        self.storage_file = storage_file if storage_file is not None else config.API_STORAGE_FILE
        self.health_check_interval = health_check_interval if health_check_interval is not None else config.API_HEALTH_CHECK_INTERVAL

        # Build URLs
        self.base_url = f"http://{self.server_ip}:{self.server_port}{self.endpoint}"
        self.health_url = f"http://{self.server_ip}:{self.server_port}{self.health_endpoint}"

        # Queues
        self.event_queue = Queue()  # For new events
        self.failed_queue = []  # For failed events (persistent)
        self.is_running = True

        # Server status
        self.server_online = False
        self.last_health_check = 0  # seconds

        # Statistics
        self.total_sent = 0
        self.total_failed = 0
        self.total_retried = 0

        # Load failed requests from disk
        self._load_failed_requests()

        # Start background threads
        self.sender_thread = threading.Thread(target=self._send_worker, daemon=True)
        self.sender_thread.start()

        self.retry_thread = threading.Thread(target=self._retry_worker, daemon=True)
        self.retry_thread.start()

        print(f"✓ API Client initialized")
        print(f"  └─ Server: {self.server_ip}:{self.server_port}")
        print(f"  └─ Endpoint: {self.endpoint}")
        print(f"  └─ Health: {self.health_endpoint}")
        print(f"  └─ Full URL: {self.base_url}")
        if self.failed_queue:
            print(f"  └─ 💾 Loaded {len(self.failed_queue)} failed requests from disk")

    def _load_failed_requests(self):
        """Load failed requests from persistent storage"""
        try:
            if os.path.exists(self.storage_file):
                with open(self.storage_file, 'r') as f:
                    data = json.load(f)
                    self.failed_queue = data.get('failed_requests', [])
        except Exception as e:
            print(f"⚠️ Error loading failed requests: {e}")
            self.failed_queue = []

    def _save_failed_requests(self):
        """Save failed requests to persistent storage"""
        try:
            data = {
                'failed_requests': self.failed_queue,
                'last_updated': datetime.now().isoformat()
            }
            with open(self.storage_file, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            print(f"⚠️ Error saving failed requests: {e}")

    def _check_server_health(self) -> bool:
        """
        Check if server is online via health endpoint
        Returns True if server responds with 200
        """
        try:
            response = requests.get(self.health_url, timeout=3)

            if response.status_code == 200:
                if not self.server_online:
                    print(f"✅ Server is ONLINE (health check passed)")
                self.server_online = True
                return True
            else:
                if self.server_online:
                    print(f"⚠️ Server health check returned {response.status_code}")
                self.server_online = False
                return False

        except (requests.exceptions.Timeout, requests.exceptions.ConnectionError):
            if self.server_online:
                print(f"🔌 Server is OFFLINE")
            self.server_online = False
            return False
        except Exception as e:
            if self.server_online:
                print(f"❌ Health check error: {e}")
            self.server_online = False
            return False

    def _map_action_to_condition(self, action: str) -> str:
        """
        Map action to API condition format (lowercase with spaces)

        Args:
            action: Original action (e.g., "TIME IN", "BREAK START")

        Returns:
            Condition string for API ("time in", "time out", "break start", etc.)
        """
        action_mapping = {
            "TIME IN": "time in",
            "TIME OUT": "time out",
            "BREAK START": "break start",
            "BREAK END": "break end",
            "JOB START": "job start",
            "JOB END": "job end"
        }

        # Return mapped value or convert to lowercase with spaces
        return action_mapping.get(action.upper(), action.lower())

    def get_attendance_status(self, employee_id: str, timestamp: Optional[int] = None) -> Optional[Dict]:
        """
        Get attendance status from server API
        
        Args:
            employee_id: Employee ID to query
            timestamp: Unix timestamp (defaults to current time)
            
        Returns:
            Dict with status info or None if request fails
            
        Response structure:
        {
            "success": true/false,
            "isTaskRunning": true/false,
            "employee": {...},
            "last_time_in": "ISO string or null",
            "last_time_out": "ISO string or null",
            "last_break_start": "ISO string or null",
            "last_break_end": "ISO string or null",
            "last_job_start": "ISO string or null",
            "last_job_end": "ISO string or null",
            "message": "..."
        }
        """
        if timestamp is None:
            timestamp = int(datetime.now().timestamp())
        
        status_url = f"http://{self.server_ip}:{self.server_port}/api/attendance/status"
        
        try:
            response = requests.get(
                status_url,
                params={"employeeId": employee_id, "timestamp": timestamp},
                timeout=self.timeout
            )
            
            if response.status_code == 200:
                data = response.json()
                return data
            else:
                # Try to parse error response
                try:
                    data = response.json()
                    return data
                except:
                    return {
                        "success": False,
                        "message": f"Server error: {response.status_code}"
                    }
                    
        except requests.exceptions.Timeout:
            print(f"⏱️ Attendance status request timeout")
            return None
        except requests.exceptions.ConnectionError:
            print(f"🔌 Server offline - cannot fetch attendance status")
            return None
        except Exception as e:
            print(f"❌ Error fetching attendance status: {e}")
            return None

    def validate_and_send_event(self, name: str, action: str, timestamp: datetime, employee_id: Optional[str] = None) -> Tuple[bool, Optional[str]]:
        """
        Synchronously validate and send attendance event to API.
        Returns (success, error_message) - if success is False, error_message contains the server error.
        Use this to validate with API before updating local state.
        """
        try:
            condition = self._map_action_to_condition(action)
            timestamp_epoch = int(timestamp.timestamp())
            
            payload = {
                "name": name,
                "timestamp": timestamp_epoch,
                "condition": condition,
                "employee_id": employee_id if employee_id else "none"
            }
            
            print(f"📤 Validating with API: {name} - {condition}")
            
            response = requests.post(
                self.base_url,
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=self.timeout
            )
            
            if response.status_code in [200, 201]:
                print(f"✅ API Validated: {name} - {condition}")
                return True, None
            else:
                # Parse error message from response
                try:
                    error_data = response.json()
                    error_msg = error_data.get('message', f'API Error: Status {response.status_code}')
                except:
                    error_msg = f'API Error: Status {response.status_code}'
                print(f"❌ API Rejected: {error_msg}")
                return False, error_msg
                
        except requests.exceptions.Timeout:
            # On timeout, allow local update (queue for retry)
            print(f"⏱️ API Timeout - will queue for retry")
            return True, None  # Allow local update
        except requests.exceptions.ConnectionError:
            # On connection error, allow local update (queue for retry)
            print(f"🔌 API Offline - will queue for retry")
            return True, None  # Allow local update
        except Exception as e:
            print(f"❌ API Error: {e}")
            return True, None  # Allow local update on unknown errors

    def send_attendance_event(self, name: str, action: str, timestamp: Optional[datetime] = None, employee_id: Optional[str] = None) -> bool:
        """
        Queue attendance event for sending to API

        Args:
            name: Person's name
            action: Action performed (e.g., "TIME IN")
            timestamp: Event timestamp (uses current time if None)
            employee_id: Optional employee ID (sends None if not provided)

        Returns:
            True if queued successfully
        """
        if timestamp is None:
            timestamp = datetime.now()

        # Create event data
        event = {
            'name': name,
            'action': action,
            'timestamp': timestamp.isoformat(),  # Store as ISO string for JSON
            'attempts': 0,
            'first_attempt': datetime.now().isoformat(),
            'employee_id': employee_id
        }

        # Add to queue
        self.event_queue.put(event)

        return True

    def _send_worker(self):
        """
        Background worker thread that sends queued events
        """
        print("✓ API sender thread started")

        while self.is_running:
            try:
                # Get event from queue (with timeout to check is_running)
                try:
                    event = self.event_queue.get(timeout=1.0)
                except:
                    continue  # Queue empty, check again

                # Send event
                success = self._send_event_sync(event)

                if success:
                    self.total_sent += 1
                else:
                    self.total_failed += 1
                    # Add to failed queue for retry
                    event['attempts'] += 1
                    event['last_failed'] = datetime.now().isoformat()
                    self.failed_queue.append(event)
                    self._save_failed_requests()
                    print(f"📥 Added to retry queue (total: {len(self.failed_queue)} failed)")

                # Mark task as done
                self.event_queue.task_done()

            except Exception as e:
                print(f"API sender thread error: {e}")
                time.sleep(1)

    def _retry_worker(self):
        """
        Background worker thread for retrying failed events
        """
        print("✓ API retry thread started")

        while self.is_running:
            try:
                # Check health periodically
                current_time = time.time()
                if current_time - self.last_health_check > self.health_check_interval:
                    self._check_server_health()
                    self.last_health_check = current_time

                # Process failed queue if server is online
                if self.server_online and self.failed_queue:
                    print(f"\n🔄 Retrying {len(self.failed_queue)} failed requests...")

                    retry_batch = self.failed_queue.copy()
                    successful = []

                    for event in retry_batch:
                        event['attempts'] += 1

                        if self._send_event_sync(event, is_retry=True):
                            successful.append(event)
                            self.total_retried += 1
                        else:
                            if not self._check_server_health():
                                print(f"⚠️ Server offline, stopping retry batch")
                                break

                        time.sleep(0.5)

                    # Remove successful events
                    if successful:
                        for event in successful:
                            if event in self.failed_queue:
                                self.failed_queue.remove(event)

                        self._save_failed_requests()
                        print(f"✅ Retried {len(successful)} requests successfully")
                        print(f"📊 Remaining: {len(self.failed_queue)}")

                time.sleep(10)  # Check every 10 seconds

            except Exception as e:
                print(f"Retry thread error: {e}")
                time.sleep(10)

    def _send_event_sync(self, event: Dict, is_retry: bool = False) -> bool:
        """
        Synchronously send event to API

        Args:
            event: Event dictionary with name, action, timestamp
            is_retry: Whether this is a retry attempt

        Returns:
            True if sent successfully
        """
        try:
            name = event['name']
            action = event['action']
            timestamp_str = event['timestamp']
            employee_id = event.get('employee_id', None)

            # Parse timestamp
            timestamp = datetime.fromisoformat(timestamp_str)

            # Map action to condition
            condition = self._map_action_to_condition(action)

            # Format timestamp as epoch
            timestamp_epoch = int(timestamp.timestamp())

            # Create payload - always send employee_id (use "none" if not set)
            payload = {
                "name": name,
                "timestamp": timestamp_epoch,  # Epoch as integer
                "condition": condition,
                "employee_id": employee_id if employee_id else "none"
            }

            # Send POST request
            retry_tag = f"[RETRY #{event['attempts']}] " if is_retry else ""
            print(f"📤 {retry_tag}Sending to API: {name} - {condition} (epoch: {timestamp_epoch})")

            response = requests.post(
                self.base_url,
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=self.timeout
            )

            # Check response
            if response.status_code in [200, 201]:
                print(f"✅ API Success: {name} - {condition} (Status: {response.status_code})")
                return True
            else:
                print(f"❌ API Error: Status {response.status_code} - {response.text}")
                self._check_server_health()  # Check health on error
                return False

        except requests.exceptions.Timeout:
            print(f"⏱️ API Timeout: {self.base_url}")
            self._check_server_health()
            return False
        except requests.exceptions.ConnectionError:
            print(f"🔌 API Connection Error: Cannot reach {self.server_ip}:{self.server_port}")
            self._check_server_health()
            return False
        except Exception as e:
            print(f"❌ API Send Error: {e}")
            return False

    def get_stats(self) -> Dict:
        """Get API client statistics"""
        return {
            'server_online': self.server_online,
            'total_sent': self.total_sent,
            'total_failed': self.total_failed,
            'total_retried': self.total_retried,
            'queued': self.event_queue.qsize(),
            'failed_pending': len(self.failed_queue),
            'server_url': self.base_url
        }

    def stop(self):
        """Stop the API client"""
        print("\nStopping API client...")
        self.is_running = False

        # Wait for queue to empty
        if not self.event_queue.empty():
            print(f"Waiting for {self.event_queue.qsize()} pending events...")
            self.event_queue.join()

        # Save failed requests
        if self.failed_queue:
            self._save_failed_requests()
            print(f"💾 {len(self.failed_queue)} failed requests saved for next session")

        # Stop threads
        if self.sender_thread.is_alive():
            self.sender_thread.join(timeout=3)
        if self.retry_thread.is_alive():
            self.retry_thread.join(timeout=3)

        # Show final stats
        stats = self.get_stats()
        print(f"📊 Final API Stats:")
        print(f"   ✅ Sent: {stats['total_sent']}")
        print(f"   ❌ Failed: {stats['total_failed']}")
        print(f"   🔄 Retried: {stats['total_retried']}")
        print(f"   📥 Remaining: {stats['failed_pending']}")

        print("✓ API client stopped")
