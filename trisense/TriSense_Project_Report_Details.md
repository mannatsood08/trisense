# TriSense: A Multimodal AI-Powered Safety & Wellbeing Monitoring System

## 1. Project Overview
TriSense is an advanced monitoring system designed to enhance the safety and independence of elderly and vulnerable individuals. It integrates computer vision, audio analysis, and behavioral learning to provide a comprehensive, real-time safety net. Unlike traditional alert systems, TriSense is "context-aware," meaning it understands the difference between normal behavior and potential emergencies, significantly reducing false alarms while ensuring rapid response when actually needed.

---

## 2. Core Architecture
The system is built on a **Modular, Event-Driven Architecture**:
- **Event Engine**: The central nervous system of the project. It handles communication between all modules (Vision, Voice, Context, UI) using a pub-sub model.
- **Vision Module (Camera Stream)**: Processes live video to detect falls, recognized faces, and monitor physical activity.
- **Audio Module (Voice Listener)**: Monitors for emergency keywords and facilitates two-way voice verification.
- **Context Engine**: Fuses data from all sensors to calculate a "Risk Score" and identifies behavioral anomalies.
- **Emergency Manager**: Orchestrates the verification and escalation workflows (Alarms, TTS, SMS).
- **Web Dashboard**: A Flask-based interface for real-time monitoring, clinical messaging, and historical data visualization.

---

## 3. Key Features & Functionalities

### 3.1 Advanced Vision Analytics
- **Fall Detection**: Uses Mediapipe Pose to track 33 body landmarks. It detects falls based on rapid changes in vertical position and horizontal orientation.
- **Inactivity Monitoring**: Tracks specific landmarks (shoulders and hips) to detect prolonged periods of zero movement, which might indicate a medical issue.
- **Face Recognition**: Distinguishes between authorized residents and unknown individuals, providing a security layer.

### 3.2 Intelligent Voice Emergency System
- **Keyword Detection**: Listens for critical phrases like "Help", "SOS", "Call a Doctor", or "Emergency".
- **Voice Verification**: If a potential fall is detected, the system speaks to the user ("I detected a fall. Are you okay?") and listens for a response ("I am fine") to cancel the alert.
- **AI Safety Assistant**: An integrated assistant that uses Text-to-Speech (TTS) to provide reminders and safety status updates.

### 3.3 Context-Aware Behavior Module
- **Zone Monitoring**: Monitors activity in specific virtual zones like the "Kitchen Stove Area" (restricted) or "Bed Area".
- **Routine Learning**: Learns the user's daily patterns (e.g., average wake-up time) and triggers alerts if a significant deviation occurs (Routine Anomaly).
- **Weighted Risk Fusion**: Calculates a unified **Risk Score (0-100)** by combining inputs:
  - Pose State (40% weight)
  - Voice State (30% weight)
  - Face Identity (20% weight)
  - Inactivity Duration (10% weight)

### 3.4 Clinical Management & Communication
- **Multi-Doctor Messaging**: A secure chat system allowing patients to communicate with multiple clinicians for coordinated care.
- **Medicine Reminders**: Automated system that alerts users when it is time to take their prescribed medication.
- **Wellbeing History**: Logs distress scores and activity levels over time for clinical review.

---

## 4. Technology Stack
- **Programming Language**: Python 3.x
- **Computer Vision**: OpenCV (Frame processing), Mediapipe (Pose & Face tracking).
- **Audio Processing**: SpeechRecognition (Google API), PyAudio (Microphone access).
- **Web Backend**: Flask (Python), Werkzeug (Security/Hashing).
- **Database**: SQLite3 (User accounts, messages, prescriptions, history).
- **Frontend**: HTML5, CSS3 (Vanilla), JavaScript (Socket-like polling for real-time updates).
- **Communications**: Twilio API (SMS Alerts), Text-to-Speech (Pyttsx3/OS Native).

---

## 5. Security & Safety Mechanisms
- **Two-Step Verification**: Prevents false alarms by combining automated detection with human verbal confirmation.
- **SMS Escalation**: Automatically sends emergency details and timestamps to caregivers if the user does not respond or confirms an emergency.
- **Local Alarm System**: Plays an audible alert on the device to notify nearby individuals.
- **Secure Authentication**: Password hashing for all user roles (Doctor, Patient, Admin).

---

## 6. Implementation Highlights
- **Portrait Mode Optimization**: The dashboard UI is optimized for portrait-oriented displays, maximizing the vertical space for full-body pose detection.
- **Resilient Pipeline**: Background threads ensure that heavy ML processing does not lag the User Interface.
- **Explainable AI**: The system doesn't just trigger an alert; it provides a "Reason" (e.g., "No movement for 10 minutes" or "Unknown face in restricted zone").
