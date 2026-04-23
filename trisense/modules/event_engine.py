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
        self.locked = False
        self.last_emergency_time = None
        self.last_safe_time = 0
        self.silenced_modules = set() # Modules that must return to NORMAL before re-locking
        self.last_events = []
        self.listeners = []
        
        # New: Auto-escalation for persistent potential falls
        self.potential_fall_start_time = None
        self.last_unknown_face_time = 0

    def subscribe(self, listener_func):
        """Allow UI/SSE stream to subscribe to events"""
        self.listeners.append(listener_func)

    def _broadcast(self, event_data):
        payload = json.dumps(event_data)
        for listener in self.listeners:
            listener(payload)

    def update_system_state(self):
        # If the system is locked in an emergency, do not allow automatic downgrading
        if self.locked:
            return

        # Multi-modal fusion logic
        pose_state = self.sub_states.get('pose', 'NORMAL')
        voice_state = self.sub_states.get('voice', 'NORMAL')
        face_state = self.sub_states.get('face', 'NORMAL')
        manual_state = self.sub_states.get('manual', 'NORMAL')

        # Security Stickiness: Keep UNKNOWN_PERSON active for 5s
        if face_state == "UNKNOWN_PERSON":
            self.last_unknown_face_time = time.time()
        elif (time.time() - self.last_unknown_face_time) < 5.0:
            face_state = "UNKNOWN_PERSON"

        if (pose_state == "FALL_DETECTED" and voice_state == "EMERGENCY") or manual_state == "EMERGENCY":
            self.current_state = "CRITICAL"
        elif pose_state == "FALL_DETECTED" or voice_state == "EMERGENCY":
            self.current_state = "EMERGENCY"
            self.potential_fall_start_time = None # Reset if already emergency
        elif face_state == "UNKNOWN_PERSON" or pose_state == "POTENTIAL_FALL":
            # Auto-escalate if potential fall persists
            if pose_state == "POTENTIAL_FALL":
                if self.potential_fall_start_time is None:
                    self.potential_fall_start_time = time.time()
                elif (time.time() - self.potential_fall_start_time) > 4.0:
                    self.current_state = "EMERGENCY"
                    return # Skip standard warning assignment
            self.current_state = "WARNING"
        else:
            self.current_state = "NORMAL"
            self.potential_fall_start_time = None

    def trigger_event(self, source, event_type, details="", reason=""):
        """
        source: 'pose', 'voice', 'face', 'manual', 'system'
        event_type: e.g. 'FALL_DETECTED', 'UNKNOWN_PERSON', 'EMERGENCY', 'NORMAL', 'SAFE_CONFIRMED'
        """
        if event_type == "SAFE_CONFIRMED":
            # 1. Clear voice queue instantly
            from trisense.utils.voice_service import voice_service
            voice_service.flush()
            
            # 2. Reset all states and unlock
            self.locked = False
            self.last_safe_time = time.time()
            
            # 3. Silence modules that were active
            for key, val in self.sub_states.items():
                if val in ["EMERGENCY", "FALL_DETECTED", "CRITICAL"]:
                    self.silenced_modules.add(key)
            
            for key in self.sub_states:
                self.sub_states[key] = "NORMAL"
            self.current_state = "NORMAL"
            
            # 4. Filter out [ACTIVE] tags from history so UI clears them
            # This is optional but helps with the 'Initial State' feel
            
            # 5. Audible confirmation
            voice_service.speak("System reset. Monitoring standby.")
            
        elif event_type in ["FALL_DETECTED", "EMERGENCY"]:
            # 1. Cooldown check (increase to 10s)
            if time.time() - self.last_safe_time < 10:
                print(f"[EventEngine] Ignoring {event_type} during safety cooldown.")
                return 

            # 2. Check if this module is silenced (must go NORMAL first)
            if source in self.silenced_modules:
                print(f"[EventEngine] Ignoring {event_type} from {source} until it returns to NORMAL first.")
                return

            self.sub_states[source] = event_type
            self.current_state = "EMERGENCY"
            self.locked = True
            self.last_emergency_time = time.time()
            # Still call update to check for escalation to CRITICAL
            self.update_system_state()
        else:
            # If a silenced module sends a NORMAL event, un-silence it
            if event_type == "NORMAL" and source in self.silenced_modules:
                print(f"[EventEngine] Module {source} returned to NORMAL. Re-enabling safety triggers.")
                self.silenced_modules.remove(source)

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
            "system_state": self.current_state,
            "locked": self.locked
        }
        
        # Log critical/high events
        if severity in ["CRITICAL", "HIGH"] or event_type != "NORMAL":
            logging.info(f"Event Triggered: {json.dumps(event_data)}")
        
        self.last_events.append(event_data)
        if len(self.last_events) > 50:
            self.last_events.pop(0)

        self._broadcast(event_data)
