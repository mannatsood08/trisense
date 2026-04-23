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
            
            # Simple substring check (existing)
            for kw in self.keywords:
                if kw in transcript_lower:
                    return kw, transcript
            
            # Flexible word-based matching for phrases
            words = set(transcript_lower.split())
            for kw in self.keywords:
                kw_words = kw.split()
                if len(kw_words) > 1: # Only for phrases
                    # Check if all words of the keyword phrase exist in the transcript
                    if all(word in words for word in kw_words):
                        print(f"[VoiceDetector] Flexible Match Found: '{kw}'")
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
