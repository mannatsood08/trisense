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
        self.facial_movement_history = deque(maxlen=30)
        self.mfcc_history = deque(maxlen=10)
        self.pitch_history = deque(maxlen=10)
        
        # Per-modality smoothing
        self.face_score_history = deque(maxlen=15)
        self.voice_score_history = deque(maxlen=5) # Slower update rate
        self.pose_score_history = deque(maxlen=15)
        
        # Scoring components (0-100 for UI)
        self.last_face_score = 0
        self.last_voice_score = 0
        self.last_pose_score = 0
        
        self.score_history = deque(maxlen=15) # Final fused smoothing
        self.last_explanation = "Initializing multimodal assessment..."

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
                # Silent fail for audio if device busy
                time.sleep(5)

    def calculate_mar(self, landmarks, img_w, img_h):
        """Mouth Aspect Ratio: vertical / horizontal"""
        # Upper and lower lip centers
        p13 = np.array([landmarks[13].x * img_w, landmarks[13].y * img_h])
        p14 = np.array([landmarks[14].x * img_w, landmarks[14].y * img_h])
        # Mouth corners
        p61 = np.array([landmarks[61].x * img_w, landmarks[61].y * img_h])
        p291 = np.array([landmarks[291].x * img_w, landmarks[291].y * img_h])
        
        vertical_dist = np.linalg.norm(p13 - p14)
        horizontal_dist = np.linalg.norm(p61 - p291)
        return vertical_dist / (horizontal_dist + 1e-6)

    def calculate_ear(self, landmarks, img_w, img_h):
        """Eye Aspect Ratio: vertical / horizontal"""
        def get_ear(indices):
            # Vertical
            p_top = np.array([landmarks[indices[1]].x * img_w, landmarks[indices[1]].y * img_h])
            p_bot = np.array([landmarks[indices[5]].x * img_w, landmarks[indices[5]].y * img_h])
            # Horizontal
            p_left = np.array([landmarks[indices[0]].x * img_w, landmarks[indices[0]].y * img_h])
            p_right = np.array([landmarks[indices[3]].x * img_w, landmarks[indices[3]].y * img_h])
            
            v = np.linalg.norm(p_top - p_bot)
            h = np.linalg.norm(p_left - p_right)
            return v / (h + 1e-6)

        # Landmarks for eyes (approximate vertical/horizontal pairs)
        left_eye = [33, 159, 158, 133, 153, 145]
        right_eye = [362, 386, 385, 263, 373, 374]
        
        return (get_ear(left_eye) + get_ear(right_eye)) / 2.0

    def process_face(self, frame):
        h, w = frame.shape[:2]
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        results = self.face_mesh.process(rgb_frame)
        
        if results.multi_face_landmarks:
            landmarks = results.multi_face_landmarks[0].landmark
            
            # 1. Feature Extraction
            mar = self.calculate_mar(landmarks, w, h)
            ear = self.calculate_ear(landmarks, w, h)
            
            # Face size for normalization
            face_w = (max(l.x for l in landmarks) - min(l.x for l in landmarks)) * w
            
            # 2. Movement Tracking
            movement = 0
            if self.last_face_landmarks:
                # Compare a subset of landmarks for stability
                subset = [0, 13, 33, 61, 133, 159, 263, 291, 362, 386]
                diffs = []
                for i in subset:
                    d = np.linalg.norm(np.array([landmarks[i].x - self.last_face_landmarks[i].x, 
                                                landmarks[i].y - self.last_face_landmarks[i].y]))
                    diffs.append(d)
                movement = np.mean(diffs)
            
            self.last_face_landmarks = landmarks
            self.facial_movement_history.append(movement)
            avg_movement = np.mean(self.facial_movement_history)

            # 3. Interpretability Mapping (0 to 1 Distress Score)
            # High MAR (>0.3) -> Tension/Agitation
            mar_distress = np.clip((mar - 0.2) * 3, 0, 1)
            # Low EAR (<0.2) -> Drowsiness/Withdrawal
            ear_distress = np.clip((0.25 - ear) * 5, 0, 1)
            # Low movement -> Flat affect / Distress
            # Movement is typically ~0.002-0.01. < 0.0015 is very low.
            mov_distress = np.clip((0.002 - avg_movement) * 500, 0, 1)

            # Weighted Face Score
            raw_face_score = (mar_distress * 0.35) + (ear_distress * 0.35) + (mov_distress * 0.30)
            self.face_score_history.append(raw_face_score)
            self.last_face_score = np.mean(self.face_score_history) * 100

            # Draw visual feedback (interpretable bounding box)
            color = (0, 255, 0) if raw_face_score < 0.4 else (0, 165, 255) if raw_face_score < 0.7 else (0, 0, 255)
            x_coords = [l.x * w for l in landmarks]
            y_coords = [l.y * h for l in landmarks]
            cv2.rectangle(frame, (int(min(x_coords)), int(min(y_coords))), 
                          (int(max(x_coords)), int(max(y_coords))), color, 2)
        else:
            # Gradually decay score if face lost
            if len(self.face_score_history) > 0:
                self.face_score_history.append(self.face_score_history[-1] * 0.9)
            self.last_face_score = np.mean(self.face_score_history) * 100 if self.face_score_history else 0

        # Process Pose
        self.process_pose(frame)
        
        return frame, self.last_face_score, ""

    def process_pose(self, frame):
        h, w = frame.shape[:2]
        results = self.pose.process(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
        
        if results.pose_landmarks:
            landmarks = results.pose_landmarks.landmark
            
            # 1. Posture: Shoulder-Hip Alignment
            # We measure vertical distance and normalize by shoulder width for distance-invariance
            shoulder_mid_y = (landmarks[11].y + landmarks[12].y) / 2
            hip_mid_y = (landmarks[23].y + landmarks[24].y) / 2
            shoulder_width = abs(landmarks[11].x - landmarks[12].x)
            
            torso_height = hip_mid_y - shoulder_mid_y
            # Ratio of vertical height to width. 
            # Slouching reduces vertical height while width stays relatively stable.
            posture_ratio = torso_height / (shoulder_width + 1e-6)
            
            # Normal upright ratio is typically > 1.2. 
            # We lower this to 0.7 to avoid false positives from leaning back in chairs.
            slouch_distress = np.clip((0.8 - posture_ratio) * 2, 0, 1)
            
            # 2. Head Position: Nose relative to shoulders
            nose_y = landmarks[0].y
            head_tilt = nose_y - shoulder_mid_y
            # Downward tilt (nose closer to or below shoulder line)
            tilt_distress = np.clip((head_tilt + 0.1) * 4, 0, 1)
            
            raw_pose_score = (slouch_distress * 0.6) + (tilt_distress * 0.4)
            self.pose_score_history.append(raw_pose_score)
            self.last_pose_score = np.mean(self.pose_score_history) * 100
        else:
            if len(self.pose_score_history) > 0:
                self.pose_score_history.append(self.pose_score_history[-1] * 0.9)
            self.last_pose_score = np.mean(self.pose_score_history) * 100 if self.pose_score_history else 0

    def extract_voice_features(self, audio_data, sr=22050):
        if audio_data is None or len(audio_data) < 500:
            return
            
        try:
            # Energy
            rms = librosa.feature.rms(y=audio_data)
            energy = np.mean(rms)
            
            # Pitch variability
            pitches, magnitudes = librosa.piptrack(y=audio_data, sr=sr)
            pitch_vals = [pitches[magnitudes[:, t].argmax(), t] for t in range(pitches.shape[1]) if magnitudes[:, t].max() > 0.1]
            pitch_var = np.std(pitch_vals) if len(pitch_vals) > 5 else 0
            
            # Scoring
            energy_distress = np.clip((0.02 - energy) * 50, 0, 1)
            pitch_distress = np.clip((40 - pitch_var) / 40, 0, 1)
            
            raw_voice_score = (energy_distress * 0.5) + (pitch_distress * 0.5)
            self.voice_score_history.append(raw_voice_score)
            self.last_voice_score = np.mean(self.voice_score_history) * 100
        except:
            pass

    def get_fused_distress(self):
        # 40% Face, 40% Voice, 20% Pose
        fused_score = (self.last_face_score * 0.4) + (self.last_voice_score * 0.4) + (self.last_pose_score * 0.2)
        
        self.score_history.append(fused_score)
        smoothed_score = np.mean(self.score_history)
        
        level = "NORMAL"
        if smoothed_score > 75: level = "HIGH"
        elif smoothed_score > 50: level = "MODERATE"
        elif smoothed_score > 25: level = "MILD"
        
        # Explainable Reasoning
        reasons = []
        if self.last_face_score > 40:
            reasons.append("reduced facial expression or tension")
        if self.last_voice_score > 40:
            reasons.append("low vocal energy/monotone")
        if self.last_pose_score > 40:
            reasons.append("slouched posture detected")
            
        if not reasons:
            self.last_explanation = "Multimodal signals are within normal operational range."
        else:
            self.last_explanation = f"{level} distress indicated by " + ", ".join(reasons) + "."
            
        return smoothed_score, level

    def get_explanation(self):
        return self.last_explanation
