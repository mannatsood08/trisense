import threading
import speech_recognition as sr
from trisense.models.voice_detection import VoiceDetector

class AudioListener(threading.Thread):
    def __init__(self, event_engine, keywords, energy_threshold=300):
        super().__init__(daemon=True)
        self.event_engine = event_engine
        self.detector = VoiceDetector(keywords, energy_threshold)
        self.recognizer = sr.Recognizer()
        self.microphone = sr.Microphone()
        
        with self.microphone as source:
            self.recognizer.adjust_for_ambient_noise(source, duration=2)

    def run(self):
        print(f"[AudioListener] Started. Sensitivity: {self.detector.energy_threshold}")
        with self.microphone as source:
            while True:
                try:
                    # Listen for up to 5 seconds per chunk
                    audio_data = self.recognizer.listen(source, phrase_time_limit=5)
                    print("[AudioListener] Data captured, processing...")
                    
                    keyword, transcript = self.detector.detect_emergency(audio_data)
                    
                    if keyword:
                        print(f"[AudioListener] EMERGENCY: {keyword.upper()} identified.")
                        self.event_engine.trigger_event("voice", "EMERGENCY", 
                                                        details=f"Transcript: {transcript}", 
                                                        reason=f"Keyword identified: {keyword}")
                    elif transcript:
                        print(f"[AudioListener] Normal speech: {transcript[:30]}...")
                        self.event_engine.trigger_event("voice", "NORMAL", 
                                                        details=f"Transcript: {transcript}", 
                                                        reason="Observing speech")
                    else:
                        # Only clear state if it was high before, but don't spam empty logs
                        if self.event_engine.sub_states.get('voice') != "NORMAL":
                            self.event_engine.trigger_event("voice", "NORMAL")
                except sr.WaitTimeoutError:
                    pass
                except Exception as e:
                    print(f"[AudioListener] Error: {e}")
