import threading
import time
import speech_recognition as sr
import winsound
import os
from trisense.config import settings
from trisense.utils.sms_service import send_sms_alert
from trisense.utils.voice_service import voice_service

class EmergencyManager:
    def __init__(self, event_engine):
        self.event_engine = event_engine
        self.is_verifying = False
        # Non-blocking registration
        self.event_engine.subscribe(self.on_event_received)
        print("[EmergencyManager] Initialized and monitoring for events.")

    def on_event_received(self, event_json):
        import json
        data = json.loads(event_json)
        
        # Only trigger verification if system enters EMERGENCY state and we aren't already verifying
        if data.get("system_state") in ["EMERGENCY", "CRITICAL"] and not self.is_verifying:
            # We don't want to re-trigger if it's already an escalated or system type event
            if data.get("source") not in ["system", "manual"]:
                trigger_source = data.get("source")
                trigger_timestamp = data.get("timestamp")
                trigger_reason = data.get("reason")
                
                threading.Thread(target=self.run_verification_workflow, 
                                 args=(trigger_source, trigger_timestamp, trigger_reason),
                                 daemon=True).start()

    def play_alarm(self, duration_sec=3):
        """Plays a warning sound"""
        if os.path.exists(settings.ALARM_SOUND_PATH):
            try:
                # Basic windows sound player approach
                winsound.PlaySound(settings.ALARM_SOUND_PATH, winsound.SND_FILENAME | winsound.SND_ASYNC)
            except:
                winsound.Beep(1000, 1000)
        else:
            # Fallback to beep
            print("[EmergencyManager] Alarm file missing, using system beep.")
            for _ in range(duration_sec):
                try:
                    winsound.Beep(1000, 500)
                except:
                    pass
                time.sleep(0.5)

    def speak(self, text):
        voice_service.speak(text)

    def run_verification_workflow(self, source, timestamp, reason):
        self.is_verifying = True
        print(f"\n[EmergencyManager] STARTING VERIFICATION for {source} emergency...")
        
        try:
            # 1. Sound Alarm
            self.play_alarm()
            
            # 2. Update Dashboard status via system event
            self.event_engine.trigger_event("system", "VERIFYING", 
                                            details="System is verifying user safety via voice.",
                                            reason="Waiting for user response...")

            # 3. Speak Verification Message
            self.speak("An emergency has been detected. Are you okay? Please respond.")

            # 4. Listen for Response
            recognizer = sr.Recognizer()
            microphone = sr.Microphone()
            
            with microphone as mic:
                recognizer.adjust_for_ambient_noise(mic, duration=1)
                print(f"[EmergencyManager] Listening for 10 seconds...")
                try:
                    audio = recognizer.listen(mic, timeout=5, phrase_time_limit=5)
                    response = recognizer.recognize_google(audio).lower()
                    print(f"[EmergencyManager] User responded: {response}")
                    
                    safe_keywords = ["i am okay", "i'm fine", "cancel", "no problem", "stop", "safe"]
                    is_safe = any(kw in response for kw in safe_keywords)
                    
                    if is_safe:
                        print("[EmergencyManager] User confirmed SAFE.")
                        self.event_engine.trigger_event("system", "SAFE_CONFIRMED", 
                                                        details=f"User verbally confirmed safety: {response}",
                                                        reason="Safe response received")
                    else:
                        print("[EmergencyManager] Response detected but not safe. ESCALATING.")
                        self.escalate_emergency(source, timestamp, reason, response)
                        
                except (sr.WaitTimeoutError, sr.UnknownValueError):
                    print("[EmergencyManager] No intelligible response detected. ESCALATING.")
                    self.escalate_emergency(source, timestamp, reason, "No response")
        
        finally:
            self.is_verifying = False

    def escalate_emergency(self, type, timestamp, reason, user_resp):
        self.event_engine.trigger_event("system", "ESCALATED_EMERGENCY", 
                                        details=f"User Response: {user_resp}",
                                        reason="Escalation due to lack of safe confirmation")
        
        # Send SMS alert
        send_sms_alert(type, timestamp, reason)

