import time
import logging
import json

# Setup logging
import os
log_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'logs')
if not os.path.exists(log_dir):
    os.makedirs(log_dir)

logging.basicConfig(
    filename=os.path.join(log_dir, 'events.log'),
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
class EventEngine:
    def __init__(self):
        self.current_state = "NORMAL"
        self.sub_states = {
            "pose": "NORMAL",
            "voice": "NORMAL",
            "face": "NORMAL"
        }
        self.last_events = []
        self.listeners = []

    def subscribe(self, listener_func):
        """Allow UI/SSE stream to subscribe to events"""
        self.listeners.append(listener_func)

    def _broadcast(self, event_data):
        payload = json.dumps(event_data)
        for listener in self.listeners:
            listener(payload)

    def update_system_state(self):
        # Multi-modal fusion logic
        pose_state = self.sub_states.get('pose', 'NORMAL')
        voice_state = self.sub_states.get('voice', 'NORMAL')
        face_state = self.sub_states.get('face', 'NORMAL')
        manual_state = self.sub_states.get('manual', 'NORMAL')

        if (pose_state == "FALL_DETECTED" and voice_state == "EMERGENCY") or manual_state == "EMERGENCY":
            self.current_state = "CRITICAL"
        elif pose_state == "FALL_DETECTED" or voice_state == "EMERGENCY":
            self.current_state = "EMERGENCY"
        elif face_state == "UNKNOWN_PERSON" or pose_state == "POTENTIAL_FALL":
            self.current_state = "WARNING"
        else:
            self.current_state = "NORMAL"

    def trigger_event(self, source, event_type, details="", reason=""):
        """
        source: 'pose', 'voice', 'face', 'manual', 'system'
        event_type: e.g. 'FALL_DETECTED', 'UNKNOWN_PERSON', 'EMERGENCY', 'NORMAL', 'SAFE_CONFIRMED'
        """
        if event_type == "SAFE_CONFIRMED":
            # Reset all states to NORMAL
            for key in self.sub_states:
                self.sub_states[key] = "NORMAL"
            self.current_state = "NORMAL"
        else:
            self.sub_states[source] = event_type
            self.update_system_state()
        
        severity = "LOW"
        if self.current_state == "CRITICAL":
            severity = "CRITICAL"
        elif self.current_state == "EMERGENCY":
            severity = "HIGH"
        elif self.current_state == "WARNING":
            severity = "MEDIUM"

        event_data = {
            "timestamp": time.time(),
            "source": source,
            "event": event_type,
            "details": details,
            "reason": reason,
            "severity": severity,
            "system_state": self.current_state
        }
        
        # Log critical/high events
        if severity in ["CRITICAL", "HIGH"] or event_type != "NORMAL":
            logging.info(f"Event Triggered: {json.dumps(event_data)}")
        
        self.last_events.append(event_data)
        if len(self.last_events) > 50:
            self.last_events.pop(0)

        self._broadcast(event_data)
