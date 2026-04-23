import time
import json
import os
import math
from datetime import datetime

class ContextEngine:
    def __init__(self, event_engine, data_dir=None):
        self.event_engine = event_engine
        if data_dir is None:
            # Default to logs directory
            self.data_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'logs')
        else:
            self.data_dir = data_dir
            
        if not os.path.exists(self.data_dir):
            os.makedirs(self.data_dir)
            
        self.routine_file = os.path.join(self.data_dir, 'routine_data.json')
        self.routine_data = self._load_routine_data()
        
        # State tracking
        self.last_landmarks = None
        self.last_movement_time = time.time()
        self.inactivity_start_time = None
        self.inactivity_status = "NORMAL"
        
        # Routine tracking
        self.first_move_recorded_today = False
        self.today_first_move_time = None
        
        # Zones definition (relative 0-1)
        self.zones = {
            "RESTRICTED": {"x": [0.0, 0.3], "y": [0.0, 0.4], "label": "Kitchen Stove Area"},
            "DOOR": {"x": [0.8, 1.0], "y": [0.0, 1.0], "label": "Main Exit"},
            "BED": {"x": [0.3, 0.7], "y": [0.6, 1.0], "label": "Bed Area"}
        }
        self.current_zone = "NONE"
        
        # Fusion scores
        self.risk_score = 0
        self.fused_state = "NORMAL"
        self.score_history = [] # For temporal smoothing
        
        # Subscribe to event engine for state updates
        self.event_engine.subscribe(self.on_event)

    def _load_routine_data(self):
        if os.path.exists(self.routine_file):
            try:
                with open(self.routine_file, 'r') as f:
                    return json.load(f)
            except:
                pass
        return {"history": [], "average_wakeup": "08:00"}

    def _save_routine_data(self):
        with open(self.routine_file, 'w') as f:
            json.dump(self.routine_data, f)

    def on_event(self, event_json):
        # We don't need to do specific heavy lifting here, 
        # as we pull stats during process_cycle.
        pass

    def process_landmarks(self, landmarks):
        """Called by CameraStream with current pose landmarks"""
        if landmarks is None:
            return

        now = time.time()
        
        # 1. Inactivity Detection
        movement = 0
        if self.last_landmarks:
            # Check a few key points: shoulders and hips
            indices = [11, 12, 23, 24] # LEFT_SHOULDER, RIGHT_SHOULDER, LEFT_HIP, RIGHT_HIP
            for i in indices:
                p1 = landmarks[i]
                p2 = self.last_landmarks[i]
                dist = math.sqrt((p1.x - p2.x)**2 + (p1.y - p2.y)**2)
                movement += dist
        
        self.last_landmarks = landmarks
        
        if movement > 0.02: # Movement threshold
            self.last_movement_time = now
            self.inactivity_start_time = None
            if self.inactivity_status != "NORMAL":
                self.inactivity_status = "NORMAL"
                self.event_engine.trigger_event("context", "NORMAL", "Movement detected. Ending inactivity period.")
        else:
            if self.inactivity_start_time is None:
                self.inactivity_start_time = now
            
            idle_duration = now - self.inactivity_start_time
            if idle_duration > 300 and self.inactivity_status == "NORMAL": # 5 minutes of no movement
                self.inactivity_status = "INACTIVITY_WARNING"
                self.event_engine.trigger_event("context", "INACTIVITY_WARNING", f"No movement for {int(idle_duration/60)} minutes.")

        # 2. Zone Monitoring
        # Use center of hips (avg of 23, 24) as 'person location'
        lx = (landmarks[23].x + landmarks[24].x) / 2
        ly = (landmarks[23].y + landmarks[24].y) / 2
        
        detected_zone = "NONE"
        for zone_id, bounds in self.zones.items():
            if bounds["x"][0] <= lx <= bounds["x"][1] and bounds["y"][0] <= ly <= bounds["y"][1]:
                detected_zone = zone_id
                break
        
        if detected_zone != self.current_zone:
            if detected_zone == "RESTRICTED":
                self.event_engine.trigger_event("context", "ZONE_ALERT", f"User entered restricted area: {self.zones[detected_zone]['label']}")
            self.current_zone = detected_zone

        # 3. Routine Learning
        dt = datetime.now()
        current_date = dt.strftime("%Y-%m-%d")
        
        # Reset daily flag
        if "last_date" not in self.routine_data or self.routine_data["last_date"] != current_date:
            self.routine_data["last_date"] = current_date
            self.first_move_recorded_today = False
            self._save_routine_data()

        if not self.first_move_recorded_today and dt.hour >= 4:
            # First significant movement of the day detected after 4 AM
            if movement > 0.05:
                self.first_move_recorded_today = True
                self.today_first_move_time = dt.strftime("%H:%M")
                
                # Update history and calculate new average
                self.routine_data["history"].append({"date": current_date, "time": self.today_first_move_time})
                if len(self.routine_data["history"]) > 30:
                    self.routine_data["history"].pop(0)
                
                # Simple average calc (minutes from midnight)
                total_mins = 0
                for entry in self.routine_data["history"]:
                    h, m = map(int, entry["time"].split(":"))
                    total_mins += (h * 60 + m)
                avg_mins = total_mins / len(self.routine_data["history"])
                avg_h, avg_m = divmod(int(avg_mins), 60)
                self.routine_data["average_wakeup"] = f"{avg_h:02d}:{avg_m:02d}"
                self._save_routine_data()
                
                # Check for anomaly
                h, m = map(int, self.today_first_move_time.split(":"))
                diff = abs((h * 60 + m) - avg_mins)
                if diff > 60: # Over 1 hour deviation
                    self.event_engine.trigger_event("context", "ROUTINE_ANOMALY", 
                        f"Wake-up time ({self.today_first_move_time}) significantly deviates from average ({self.routine_data['average_wakeup']}).")

        # 4. Multi-Signal Fusion
        self.update_fusion()

    def update_fusion(self):
        # Weights
        # W_POSE = 0.4, W_VOICE = 0.3, W_FACE = 0.2, W_INACT = 0.1
        
        # Get source states from EventEngine
        p_state = self.event_engine.sub_states.get("pose", "NORMAL")
        v_state = self.event_engine.sub_states.get("voice", "NORMAL")
        f_state = self.event_engine.sub_states.get("face", "NORMAL")
        
        p_score = 100 if p_state == "FALL_DETECTED" else (40 if p_state == "POTENTIAL_FALL" else 0)
        v_score = 100 if v_state == "EMERGENCY" else 0
        f_score = 70 if f_state == "UNKNOWN_PERSON" else (0 if f_state == "AUTHORIZED_USER" else 10)
        i_score = 50 if self.inactivity_status == "INACTIVITY_WARNING" else 0
        
        raw_risk = (p_score * 0.4) + (v_score * 0.3) + (f_score * 0.2) + (i_score * 0.1)
        
        # Temporal smoothing (sliding window of 10 samples)
        self.score_history.append(raw_risk)
        if len(self.score_history) > 10:
            self.score_history.pop(0)
        
        self.risk_score = sum(self.score_history) / len(self.score_history)
        
        new_state = "NORMAL"
        if self.risk_score > 85: new_state = "CRITICAL"
        elif self.risk_score > 60: new_state = "HIGH"
        elif self.risk_score > 30: new_state = "WARNING"
        
        self.fused_state = new_state

    def get_status(self):
        """Returns context data for UI"""
        avg_wakeup = self.routine_data.get("average_wakeup", "--:--")
        today_wakeup = self.today_first_move_time if self.today_first_move_time else "Sleeping/Not detected"
        
        inact_mins = 0
        if self.inactivity_start_time:
            inact_mins = int((time.time() - self.inactivity_start_time) / 60)

        return {
            "risk_score": round(self.risk_score, 1),
            "fused_state": self.fused_state,
            "inactivity_mins": inact_mins,
            "inactivity_status": self.inactivity_status,
            "current_zone": self.zones.get(self.current_zone, {"label": "Free Area"})["label"],
            "avg_wakeup": avg_wakeup,
            "today_wakeup": today_wakeup
        }
