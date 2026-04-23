import threading
import time
from datetime import datetime
from trisense.models.database import get_all_prescriptions
from trisense.utils.voice_service import voice_service

class ReminderEngine(threading.Thread):
    def __init__(self, event_engine):
        super().__init__(daemon=True)
        self.event_engine = event_engine
        self.last_checked_minute = ""

    def run(self):
        print("[ReminderEngine] Started. Monitoring medicine schedule...")
        while True:
            try:
                now = datetime.now()
                current_time = now.strftime("%H:%M") # HH:MM format
                
                # Only check once per minute
                if current_time != self.last_checked_minute:
                    self.check_reminders(current_time)
                    self.last_checked_minute = current_time
                    
                time.sleep(10) # Check every 10 seconds to avoid missing the minute
            except Exception as e:
                print(f"[ReminderEngine] Error: {e}")
                time.sleep(30)

    def check_reminders(self, time_str):
        prescriptions = get_all_prescriptions()
        for p in prescriptions:
            if p['time'] == time_str:
                patient = p['patient']
                med = p['medicine']
                
                print(f"[ReminderEngine] Match found! Sending reminder for {patient}: {med}")
                
                # 1. Trigger Event UI
                self.event_engine.trigger_event(
                    "system", 
                    "MEDICINE_REMINDER", 
                    details=f"Patient: {patient}, Medicine: {med}",
                    reason=f"Time for {med}"
                )
                
                # 2. Voice output
                msg = f"Attention {patient}, it is time to take your {med}."
                voice_service.speak(msg)
                
                # 3. Follow up question after a short delay
                threading.Timer(8.0, lambda: voice_service.speak("Did you take your medicine?")).start()

