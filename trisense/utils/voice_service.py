import pyttsx3
import threading
import queue
import time

class VoiceService:
    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(VoiceService, cls).__new__(cls)
                cls._instance._init_service()
            return cls._instance

    def _init_service(self):
        self.speak_queue = queue.Queue()
        self.stop_event = threading.Event()
        self.thread = threading.Thread(target=self._run_loop, daemon=True)
        self.thread.start()

    def _run_loop(self):
        # Initialize engine inside the dedicated thread
        engine = pyttsx3.init()
        # Set property: slower speech for better clarity
        engine.setProperty('rate', 160)
        
        while not self.stop_event.is_set():
            try:
                # Wait for message to speak
                text = self.speak_queue.get(timeout=1)
                print(f"[VoiceService] Speaking: {text}")
                engine.say(text)
                engine.runAndWait()
                self.speak_queue.task_done()
            except queue.Empty:
                continue
            except Exception as e:
                print(f"[VoiceService] Error: {e}")
                # Re-initialize if engine crashes
                try:
                    engine = pyttsx3.init()
                    engine.setProperty('rate', 160)
                except:
                    pass

    def speak(self, text):
        """Adds text to the speech queue (Non-blocking)"""
        if text:
            self.speak_queue.put(text)

# Global singleton
voice_service = VoiceService()
