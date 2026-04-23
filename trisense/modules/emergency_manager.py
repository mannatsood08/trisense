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
        self.last_warning_time = 0
        self.warning_cooldown = 30 # Seconds between warning beeps
        # Non-blocking registration
        self.event_engine.subscribe(self.on_event_received)
        print("[EmergencyManager] Initialized and monitoring for events.")

    def on_event_received(self, event_json):
        import json
        data = json.loads(event_json)
        
        # Handle immediate SOS (Feature 7)
        if data.get("system_state") == "CRITICAL" and data.get("source") == "USER_INTERFACE":
            print("[EmergencyManager] CRITICAL SOS RECEIVED. Escalating immediately.")
            self.escalate_emergency("SOS_BUTTON", data.get("timestamp"), "Manual SOS triggered", "User pressed SOS button")
            return

        # Handle Potential Falls/Emergencies (Feature 6)
        if data.get("system_state") in ["EMERGENCY", "CRITICAL"] and not self.is_verifying:
            # We don't want to re-trigger if it's already an escalated or system type event
            if data.get("source") not in ["system", "manual"]:
                trigger_source = data.get("source")
                trigger_timestamp = data.get("timestamp")
                trigger_reason = data.get("reason")
                
                threading.Thread(target=self.run_verification_workflow, 
                                 args=(trigger_source, trigger_timestamp, trigger_reason),
                                 daemon=True).start()
        
        elif data.get("system_state") == "WARNING":
            # Play a short "notice" beep for warnings with a cooldown to prevent ear fatigue
            current_time = time.time()
            if not self.is_verifying and (current_time - self.last_warning_time) > self.warning_cooldown:
                self.last_warning_time = current_time
                print(f"[EmergencyManager] Warning alert: {data.get('reason', 'Unknown reason')}. Playing notice.")
                threading.Thread(target=self.play_notice_beep, daemon=True).start()

    def play_notice_beep(self):
        """Short beep to alert user the system sees something suspicious"""
        winsound.Beep(800, 150)
        time.sleep(0.1)
        winsound.Beep(800, 150)

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
            for _ in range(duration_sec * 2):
                if not self.event_engine.locked:
                    print("[EmergencyManager] Reset detected during beep. Stopping alarm.")
                    break
                try:
                    winsound.Beep(1000, 300)
                except:
                    pass
                time.sleep(0.3)

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

            # 3. Check if we should abort (user might have clicked Mark Safe already)
            if not self.event_engine.locked:
                print("[EmergencyManager] Manual reset detected. Aborting verification.")
                return

            # 4. Speak Verification Message (Personalized Feature 6)
            self.speak("I detected a possible fall. Are you okay? Please say 'I am fine' to cancel this alert.")

            # 4. Listen for Response
            recognizer = sr.Recognizer()
            microphone = sr.Microphone()
            
            try:
                with microphone as mic:
                    recognizer.adjust_for_ambient_noise(mic, duration=1)
                    print(f"[EmergencyManager] Listening for 10 seconds...")
                    try:
                        audio = recognizer.listen(mic, timeout=5, phrase_time_limit=5)
                        
                        # Re-check abort before processing speech
                        if not self.event_engine.locked:
                            print("[EmergencyManager] Manual reset detected during listening. Aborting.")
                            return
                            
                        response = recognizer.recognize_google(audio).lower()
                        print(f"[EmergencyManager] User responded: {response}")
                        
                        safe_keywords = [
                            "i am okay", "i'm fine", "cancel", "no problem", "stop", "safe",
                            "i am ok", "i'm ok", "everything is fine", "yes", "i am good", "ok"
                        ]
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
            except Exception as e:
                print(f"[EmergencyManager] Microphone Access Error: {e}")
                print("[EmergencyManager] Falling back to automatic escalation for safety.")
                self.escalate_emergency(source, timestamp, reason, f"Mic Error: {e}")
        
        finally:
            self.is_verifying = False

    def escalate_emergency(self, type, timestamp, reason, user_resp):
        # FINAL CHECK: If user marked safe while we were preparing escalation, DO NOT ESCALATE
        if not self.event_engine.locked:
            print("[EmergencyManager] Abortion: System already marked safe. Skipping escalation.")
            return

        self.event_engine.trigger_event("system", "ESCALATED_EMERGENCY", 
                                        details=f"User Response: {user_resp}",
                                        reason="Escalation due to lack of safe confirmation")
        
        # Send SMS alert
        send_sms_alert(type, timestamp, reason)

