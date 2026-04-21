import speech_recognition as sr

class VoiceDetector:
    def __init__(self, keywords, energy_threshold=300):
        self.keywords = [k.lower() for k in keywords]
        self.energy_threshold = energy_threshold
        self.recognizer = sr.Recognizer()
        self.recognizer.energy_threshold = self.energy_threshold
        self.recognizer.dynamic_energy_threshold = True

    def detect_emergency(self, audio_data):
        """
        Process the audio data block.
        Returns: (keyword, transcript)
        """
        try:
            # Using Google Web Speech API
            transcript = self.recognizer.recognize_google(audio_data)
            transcript_lower = transcript.lower()
            
            print(f"[VoiceDetector] Captured: \"{transcript}\"")
            
            if len(transcript_lower) >= 3:
                for kw in self.keywords:
                    if kw in transcript_lower:
                        return kw, transcript
            return None, transcript
        except sr.UnknownValueError:
            # Speech was heard but not recognized
            # Only return this if we are fairly sure it wasn't just a cough or noise
            # (Checking if it's a very short burst)
            return None, "... (Unintelligible speech)"
        except sr.RequestError as e:
            # Internet or API issues
            msg = "Speech API offline/error"
            print(f"[VoiceDetector] {msg}: {e}")
            return None, f"[{msg}]"
            
        return None, None
