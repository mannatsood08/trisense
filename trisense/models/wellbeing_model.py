import cv2
import mediapipe as mp
import numpy as np
import time
import threading
import librosa
import sounddevice as sd
from collections import deque

class WellbeingModel:
    def __init__(self):
        # Face Mesh Initialization
        self.mp_face_mesh = mp.solutions.face_mesh
        self.face_mesh = self.mp_face_mesh.FaceMesh(
            static_image_mode=False,
            max_num_faces=1,
            refine_landmarks=True,
            min_detection_confidence=0.5,
            min_tracking_confidence=0.5
        )
        
        # Pose Initialization (for body posture analysis)
        self.mp_pose = mp.solutions.pose
        self.pose = self.mp_pose.Pose(
            min_detection_confidence=0.5,
            min_tracking_confidence=0.5
        )

        self.mp_drawing = mp.solutions.drawing_utils

        # Feature tracking for movement & variability
        self.last_face_landmarks = None
        self.facial_movement_history = deque(maxlen=20)
        self.mfcc_history = deque(maxlen=10)
        self.pitch_history = deque(maxlen=10)
        
        # Scoring components
        self.last_face_score = 0
        self.last_voice_score = 0
        self.last_pose_score = 0
        self.score_history = deque(maxlen=10) # 10 seconds smoothing
        self.last_explanation = "Initializing system assessment..."

        # Audio Capture thread
        self.audio_thread = threading.Thread(target=self._audio_capture_loop, daemon=True)
        self.audio_thread.start()

    def _audio_capture_loop(self):
        """Captures small chunks of audio for real-time analysis"""
        while True:
            try:
                # Capture 2 seconds of audio
                duration = 2
                fs = 22050
                recording = sd.rec(int(duration * fs), samplerate=fs, channels=1)
                sd.wait()
                # Process features
                self.extract_voice_features(recording.flatten(), sr=fs)
            except Exception as e:
                print(f"[WellbeingAudio] Error: {e}")
                time.sleep(5)

    def calculate_mar(self, landmarks, img_w, img_h):
        """Mouth Aspect Ratio"""
        top_lip = np.array([landmarks[13].x * img_w, landmarks[13].y * img_h])
        bottom_lip = np.array([landmarks[14].x * img_w, landmarks[14].y * img_h])
        left_corner = np.array([landmarks[61].x * img_w, landmarks[61].y * img_h])
        right_corner = np.array([landmarks[291].x * img_w, landmarks[291].y * img_h])
        
        vertical_dist = np.linalg.norm(top_lip - bottom_lip)
        horizontal_dist = np.linalg.norm(left_corner - right_corner)
        return vertical_dist / (horizontal_dist + 1e-6)

    def calculate_ear(self, landmarks, img_w, img_h):
        """Eye Aspect Ratio (Openness)"""
        # Left Eye (Simplified set)
        l_top = np.array([landmarks[159].x * img_w, landmarks[159].y * img_h])
        l_bottom = np.array([landmarks[145].x * img_w, landmarks[145].y * img_h])
        l_left = np.array([landmarks[33].x * img_w, landmarks[33].y * img_h])
        l_right = np.array([landmarks[133].x * img_w, landmarks[133].y * img_h])
        
        # Right Eye
        r_top = np.array([landmarks[386].x * img_w, landmarks[386].y * img_h])
        r_bottom = np.array([landmarks[374].x * img_w, landmarks[374].y * img_h])
        r_left = np.array([landmarks[362].x * img_w, landmarks[362].y * img_h])
        r_right = np.array([landmarks[263].x * img_w, landmarks[263].y * img_h])
        
        def ear_single(top, bot, left, right):
            return np.linalg.norm(top - bot) / (np.linalg.norm(left - right) + 1e-6)
            
        return (ear_single(l_top, l_bottom, l_left, l_right) + ear_single(r_top, r_bottom, r_left, r_right)) / 2.0

    def process_face(self, frame):
        h, w = frame.shape[:2]
        results = self.face_mesh.process(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
        
        face_score = 0
        
        if results.multi_face_landmarks:
            landmarks = results.multi_face_landmarks[0].landmark
            
            # Simple bounding box instead of mesh
            coords = [(l.x * w, l.y * h) for l in landmarks]
            x_min = int(min(c[0] for c in coords))
            y_min = int(min(c[1] for c in coords))
            x_max = int(max(c[0] for c in coords))
            y_max = int(max(c[1] for c in coords))
            cv2.rectangle(frame, (x_min, y_min), (x_max, y_max), (0, 255, 0), 1)

            # Feature Calculation
            mar = self.calculate_mar(landmarks, w, h)
            ear = self.calculate_ear(landmarks, w, h)
            
            # Facial Movement (displacement from last frame)
            movement = 0
            if self.last_face_landmarks:
                movement = np.mean([np.linalg.norm(np.array([landmarks[i].x - self.last_face_landmarks[i].x, 
                                                              landmarks[i].y - self.last_face_landmarks[i].y])) 
                                     for i in range(0, 468, 50)]) # Sample 10 points
            self.last_face_landmarks = landmarks
            self.facial_movement_history.append(movement)
            avg_movement = np.mean(self.facial_movement_history)

            # --- Interpretable Scoring ---
            # Normal MAR: ~0.1-0.2. Distress: > 0.4 (mouth tension/yawning)
            mar_score = np.clip((mar - 0.15) * 4, 0, 1)
            
            # Normal EAR: ~0.25-0.35. Distress: < 0.2 (tiredness/drooping)
            ear_score = np.clip((0.28 - ear) * 5, 0, 1)
            
            # Normal movement: varied. Distress: < 0.001 (frozen/stony face)
            movement_score = np.clip((0.003 - avg_movement) * 300, 0, 1) if avg_movement > 0 else 0
            
            face_score = (mar_score * 0.4) + (ear_score * 0.4) + (movement_score * 0.2)
            self.last_face_score = face_score * 100
        
        # Process Pose alongside face
        self.process_pose(frame)
        
        return frame, self.last_face_score, ""

    def process_pose(self, frame):
        h, w = frame.shape[:2]
        results = self.pose.process(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
        
        if results.pose_landmarks:
            landmarks = results.pose_landmarks.landmark
            # Shoulder (11, 12) to Hip (23, 24) distance
            upper_body_y = (landmarks[11].y + landmarks[12].y) / 2
            lower_body_y = (landmarks[23].y + landmarks[24].y) / 2
            
            torso_height = lower_body_y - upper_body_y
            
            # Posture Score: Normalized torso height. 
            # Slouching reduces vertical distance between shoulders and hips
            # Assuming 0.4 as typical upright height in frame
            posture_score = np.clip((0.35 - torso_height) * 4, 0, 1)
            self.last_pose_score = posture_score * 100

    def extract_voice_features(self, audio_data, sr=22050):
        if audio_data is None or len(audio_data) < 100:
            return
            
        try:
            mfccs = librosa.feature.mfcc(y=audio_data, sr=sr, n_mfcc=13)
            mfcc_mean = np.mean(mfccs, axis=1)
            rms = librosa.feature.rms(y=audio_data)
            energy = np.mean(rms)
            
            # Pitch variation
            pitches, magnitudes = librosa.piptrack(y=audio_data, sr=sr)
            pitch_vals = []
            for t in range(pitches.shape[1]):
                index = magnitudes[:, t].argmax()
                pitch = pitches[index, t]
                if pitch > 0: pitch_vals.append(pitch)
            
            pitch_var = np.std(pitch_vals) if len(pitch_vals) > 5 else 0
            
            # MFCC Variation
            self.mfcc_history.append(mfcc_mean)
            mfcc_var = np.std(self.mfcc_history) if len(self.mfcc_history) > 2 else 0

            # --- Interpretable Scoring ---
            # Low energy (<0.02) -> Distress (withdrawn)
            energy_score = np.clip((0.03 - energy) * 20, 0, 1)
            
            # Low pitch variability (<20Hz) -> Distress (monotone)
            pitch_score = np.clip((50 - pitch_var) / 50, 0, 1)
            
            # Low MFCC variation -> Distress (unstated expression)
            mfcc_score = np.clip((2.0 - mfcc_var) / 2, 0, 1)
            
            self.last_voice_score = ((energy_score * 0.4) + (pitch_score * 0.3) + (mfcc_score * 0.3)) * 100
        except:
            pass

    def get_fused_distress(self):
        # Research aligned weights: 40% Face, 40% Voice, 20% Pose
        current_score = (self.last_face_score * 0.4) + (self.last_voice_score * 0.4) + (self.last_pose_score * 0.2)
        
        self.score_history.append(current_score)
        smoothed_score = np.mean(self.score_history) / 100.0 # 0.0 to 1.0
        
        level = "NORMAL"
        explanation_parts = []
        
        if smoothed_score > 0.8: level = "HIGH"
        elif smoothed_score > 0.6: level = "MODERATE"
        elif smoothed_score > 0.3: level = "MILD"
        
        if level != "NORMAL":
            if self.last_face_score > 50: explanation_parts.append("unusual facial tension or reduced expression")
            if self.last_voice_score > 50: explanation_parts.append("reduced vocal energy and variability")
            if self.last_pose_score > 50: explanation_parts.append("slouching posture")
            
            if not explanation_parts:
                self.last_explanation = f"{level} distress indicator detected based on subtle multimodal signals."
            else:
                self.last_explanation = f"{level} distress detected due to " + " and ".join(explanation_parts) + "."
        else:
            self.last_explanation = "Normal activity. All multimodal signals are within typical range."
            
        return smoothed_score * 100, level

    def get_explanation(self):
        return self.last_explanation
