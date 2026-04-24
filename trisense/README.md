# TriSense Monitoring System

TriSense is a multimodal, context-aware safety monitoring system designed for elderly and vulnerable individuals. It leverages Computer Vision, Audio Analysis, and Behavioral Learning to provide a real-time safety net, ensuring rapid response to emergencies like falls while minimizing false alarms through intelligent verification.

---

## 🚀 Key Features

- **🛡️ Advanced Vision Analytics**: 
    - Real-time **Fall Detection** using Mediapipe Pose.
    - **Inactivity Monitoring** to detect prolonged lack of movement.
    - **Face Recognition** to identify authorized residents vs. unknown individuals.
- **🎙️ Voice Emergency System**:
    - Keyword detection for phrases like "Help" or "SOS".
    - **Two-Step Verification**: The system verbally asks "Are you okay?" after a fall and waits for a response before escalating.
- **🧠 Context-Aware Engine**:
    - **Zone Monitoring**: Alerts for entries into restricted areas (e.g., Kitchen Stove).
    - **Routine Learning**: Learns daily patterns and detects anomalies (e.g., waking up much later than usual).
    - **Weighted Risk Scoring**: Fuses multiple sensor inputs into a single risk metric.
- **📱 Responsive Dashboard**:
    - Real-time video stream with pose overlays.
    - Clinical messaging system for patient-doctor communication.
    - Medicine reminders and wellbeing history tracking.
- **🚨 Automated Escalation**:
    - Instant SMS alerts via Twilio.
    - Audible local alarms.

---

## 🛠️ Tech Stack

- **Language**: Python 3.10+
- **Vision**: OpenCV, Mediapipe, DeepFace
- **Audio**: SpeechRecognition, PyAudio, Pyttsx3 (TTS)
- **Web**: Flask, HTML5, CSS3, JavaScript
- **Database**: SQLite3
- **Infrastructure**: Twilio API (SMS)

---

## 📦 Installation

1. **Clone the repository**:
   ```bash
   git clone <repository-url>
   cd trisense
   ```

2. **Create a Virtual Environment** (Recommended):
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install Dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

   *Note: On Windows, you may need to install `PyAudio` via a wheel if `pip install` fails.*

4. **Initialize Database**:
   The database is automatically initialized on the first run, but you can run:
   ```bash
   python -c "from trisense.models.database import init_db; init_db()"
   ```

---

## ⚙️ Configuration

Open `trisense/config/settings.py` to configure:
- **Twilio Credentials**: `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `TWILIO_PHONE_NUMBER`.
- **Caregiver Number**: `CAREGIVER_PHONE_NUMBER`.
- **Thresholds**: Adjust `FALL_DURATION_THRESHOLD` or `AUDIO_ENERGY_THRESHOLD` as needed.

---

## 🏃 Running the Application

To start the full system (Camera, Audio, and Web UI):

```bash
python main.py
```

Once started, open your browser and navigate to:
`http://localhost:5000`

---

## 📂 Project Structure

- `main.py`: Main entry point initializing all modules.
- `trisense/modules/`: Core logic (Camera, Audio, Context Engine).
- `trisense/models/`: Database schemas and ML models.
- `trisense/ui/`: Flask app, templates, and static assets.
- `trisense/config/`: System settings and constants.

---

## 📝 License

This project is for educational/clinical research purposes. Use at your own risk.
