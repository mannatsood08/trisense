import os

# Base Directory path
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Safety Keywords for Voice Emergency
EMERGENCY_KEYWORDS = [
    "help", "emergency", "call doctor", "call ambulance",
    "i need help", "help me", "save me", "sos"
]

# Pose Detection Settings
POSE_MIN_CONFIDENCE = 0.5
FALL_DURATION_THRESHOLD = 2.0  # seconds horizontally to be considered a fall

# Audio Detection Settings
AUDIO_ENERGY_THRESHOLD = 250
MIN_TRANSCRIPT_LENGTH = 3

# Face Monitor Settings
# Path to authorized users' face database
FACES_DB_PATH = os.path.join(BASE_DIR, "authorized_faces")

# UI Settings
STREAM_WIDTH = 360
STREAM_HEIGHT = 480

# --- Emergency Verification & SMS ---
VERIFICATION_WINDOW = 10  # Seconds to wait for user response
ESCALATION_COOLDOWN = 20  # Seconds between alert SMS

# Twilio Configuration (Fill these for SMS to work)
TWILIO_ACCOUNT_SID = "ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
TWILIO_AUTH_TOKEN = "xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
TWILIO_PHONE_NUMBER = "+1234567890"
CAREGIVER_PHONE_NUMBER = "+1234567890"

# Audio Files
ALARM_SOUND_PATH = os.path.join(BASE_DIR, "static", "alarm.wav")
