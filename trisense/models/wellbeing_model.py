import cv2
import mediapipe as mp
import numpy as np
import time
import threading
import librosa
import sounddevice as sd
import os
import csv
from datetime import datetime
from collections import deque

class WellbeingModel:
    def __init__(self):
        # MediaPipe Setup
        self.mp_face_mesh = mp.solutions.face_mesh
        self.face_mesh = self.mp_face_mesh.FaceMesh(refine_landmarks=True)
        self.mp_pose = mp.solutions.pose
        self.pose = self.mp_pose.Pose()

        # State Management
        self.state = "CALIBRATING"
        self.calibration_duration = 30 # Seconds
        self.start_time = time.time()
        
        # Baselines
        self.baselines = {
            "face_movement": [],
            "voice_energy": [],
            "posture_ratio": [],
            "voice_mfcc": []
        }
        self.calibrated_baselines = {}

        # Feature tracking
        self.last_face_landmarks = None
        self.facial_movement_history = deque(maxlen=30)
        self.voice_score_history = deque(maxlen=15)
        self.last_pose_landmarks = None
        self.inactivity_start_time = time.time()
        
        # Modality smoothing
        self.face_score_history = deque(maxlen=30)
        self.voice_score_history = deque(maxlen=30)
        self.pose_score_history = deque(maxlen=30)
        self.inactivity_score_history = deque(maxlen=30)
        
        # Dynamic Weights
        self.default_weights = {"face": 0.4, "voice": 0.3, "pose": 0.2, "inact": 0.1}
        self.active_modalities = {"face": False, "voice": False, "pose": False, "inact": True}
        
        self.score_history = deque(maxlen=30)
        self.last_explanation = "Initializing system..."
        self.confidence_score = 0
        
        # Logging Setup
        self.log_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "logs")
        if not os.path.exists(self.log_dir): os.makedirs(self.log_dir)
        self.log_file = os.path.join(self.log_dir, "wellbeing_research_log.csv")
        self._init_log()

        # Audio Thread
        threading.Thread(target=self._audio_capture_loop, daemon=True).start()

    def _init_log(self):
        if not os.path.exists(self.log_file):
            with open(self.log_file, "w", newline="") as f:
                writer = csv.writer(f)
                writer.writerow(["timestamp", "state", "face_score", "voice_score", "pose_score", "inact_score", "final_distress", "confidence"])

    def log_data(self, f_s, v_s, p_s, i_s, final, conf):
        with open(self.log_file, "a", newline="") as f:
            writer = csv.writer(f)
            writer.writerow([datetime.now().isoformat(), self.state, f_s, v_s, p_s, i_s, final, conf])

    def _audio_capture_loop(self):
        while True:
            try:
                duration, fs = 2, 22050
                recording = sd.rec(int(duration * fs), samplerate=fs, channels=1)
                sd.wait()
                self.extract_voice_features(recording.flatten(), sr=fs)
            except: time.sleep(5)

    def calculate_mar_ear(self, landmarks, w, h):
        # Mouth
        p13, p14 = np.array([landmarks[13].x*w, landmarks[13].y*h]), np.array([landmarks[14].x*w, landmarks[14].y*h])
        p61, p291 = np.array([landmarks[61].x*w, landmarks[61].y*h]), np.array([landmarks[291].x*w, landmarks[291].y*h])
        mar = np.linalg.norm(p13 - p14) / (np.linalg.norm(p61 - p291) + 1e-6)
        # Eyes
        def get_e(idx):
            top, bot = np.array([landmarks[idx[1]].x*w, landmarks[idx[1]].y*h]), np.array([landmarks[idx[5]].x*w, landmarks[idx[5]].y*h])
            l, r = np.array([landmarks[idx[0]].x*w, landmarks[idx[0]].y*h]), np.array([landmarks[idx[3]].x*w, landmarks[idx[3]].y*h])
            return np.linalg.norm(top - bot) / (np.linalg.norm(l - r) + 1e-6)
        ear = (get_e([33, 159, 158, 133, 153, 145]) + get_e([362, 386, 385, 263, 373, 374])) / 2.0
        return mar, ear

    def process_face(self, frame):
        h, w = frame.shape[:2]
        results = self.face_mesh.process(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
        
        if results.multi_face_landmarks:
            self.active_modalities["face"] = True
            landmarks = results.multi_face_landmarks[0].landmark
            mar, ear = self.calculate_mar_ear(landmarks, w, h)
            
            movement = 0
            if self.last_face_landmarks:
                subset = [1, 33, 61, 133, 159, 263, 291, 362, 386]
                movement = np.mean([np.linalg.norm(np.array([landmarks[i].x - self.last_face_landmarks[i].x, 
                                                            landmarks[i].y - self.last_face_landmarks[i].y])) for i in subset])
            self.last_face_landmarks = landmarks

            if self.state == "CALIBRATING":
                self.baselines["face_movement"].append(movement)
                score = 0
            else:
                # Deviation-based score
                base_mov = self.calibrated_baselines.get("face_movement", 0.002)
                mov_dev = np.clip((base_mov - movement) * 500, 0, 1) # Movement reduction
                mar_dev = np.clip((mar - 0.2) * 5, 0, 1)
                ear_dev = np.clip((0.25 - ear) * 10, 0, 1)
                score = (mov_dev * 0.4 + mar_dev * 0.3 + ear_dev * 0.3)
            
            self.face_score_history.append(score)
        else:
            self.active_modalities["face"] = False
            if self.face_score_history: self.face_score_history.append(self.face_score_history[-1] * 0.9)

        self.process_pose(frame)
        self.update_state()
        return frame, np.mean(self.face_score_history)*100 if self.face_score_history else 0, ""

    def process_pose(self, frame):
        results = self.pose.process(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
        if results.pose_landmarks:
            self.active_modalities["pose"] = True
            lm = results.pose_landmarks.landmark
            shoulder_y = (lm[11].y + lm[12].y) / 2
            hip_y = (lm[23].y + lm[24].y) / 2
            ratio = (hip_y - shoulder_y) / (abs(lm[11].x - lm[12].x) + 1e-6)
            
            if self.state == "CALIBRATING":
                self.baselines["posture_ratio"].append(ratio)
                score = 0
            else:
                base_ratio = self.calibrated_baselines.get("posture_ratio", 0.9)
                slouch = np.clip((base_ratio - 0.1 - ratio) * 5, 0, 1)
                tilt = np.clip((lm[0].y - shoulder_y + 0.05) * 5, 0, 1)
                score = (slouch * 0.6 + tilt * 0.4)
            self.pose_score_history.append(score)

            # Inactivity
            mv = 0
            if self.last_pose_landmarks:
                mv = np.mean([np.linalg.norm(np.array([lm[i].x - self.last_pose_landmarks[i].x, lm[i].y - self.last_pose_landmarks[i].y])) for i in [11,12,23,24]])
            self.last_pose_landmarks = lm
            if mv > 0.005: self.inactivity_start_time = time.time()
            idle = time.time() - self.inactivity_start_time
            inact_score = np.clip((idle - 30) / 120, 0, 1) if self.state == "MONITORING" else 0
            self.inactivity_score_history.append(inact_score)
        else:
            self.active_modalities["pose"] = False
            if self.pose_score_history: self.pose_score_history.append(self.pose_score_history[-1] * 0.9)
            if self.inactivity_score_history: self.inactivity_score_history.append(0)

    def extract_voice_features(self, data, sr=22050):
        if data is None or len(data) < 500: 
            self.active_modalities["voice"] = False
            return
        self.active_modalities["voice"] = True
        energy = np.mean(librosa.feature.rms(y=data))
        mfcc_var = np.mean(np.std(librosa.feature.mfcc(y=data, sr=sr), axis=1))
        
        if self.state == "CALIBRATING":
            self.baselines["voice_energy"].append(energy)
            self.baselines["voice_mfcc"].append(mfcc_var)
            score = 0
        else:
            b_e = self.calibrated_baselines.get("voice_energy", 0.02)
            b_m = self.calibrated_baselines.get("voice_mfcc", 20)
            score = (np.clip((b_e*0.8 - energy)*50, 0, 1) * 0.6 + np.clip((b_m*0.8 - mfcc_var)/b_m, 0, 1) * 0.4)
        self.voice_score_history.append(score)

    def update_state(self):
        elapsed = time.time() - self.start_time
        if self.state == "CALIBRATING" and elapsed > self.calibration_duration:
            for k, v in self.baselines.items():
                if v: self.calibrated_baselines[k] = np.mean(v)
            self.state = "MONITORING"
            print(f"[Wellbeing] Calibration Complete: {self.calibrated_baselines}")

    def get_fused_distress(self):
        if self.state == "CALIBRATING":
            progress = int((time.time() - self.start_time) / self.calibration_duration * 100)
            self.last_explanation = f"Calibrating baseline... {progress}%"
            return 0, "CALIBRATING"

        # Active Modalites & Weights
        active_list = [k for k, v in self.active_modalities.items() if v]
        self.confidence_score = len(active_list) / len(self.active_modalities)
        
        # Weight Redistribution
        current_weights = self.default_weights.copy()
        missing = [k for k, v in self.active_modalities.items() if not v]
        if missing:
            missing_sum = sum(current_weights[m] for m in missing)
            active_sum = sum(current_weights[a] for a in active_list)
            if active_sum > 0:
                for a in active_list: current_weights[a] += (current_weights[a] / active_sum) * missing_sum
        
        f_s = np.mean(self.face_score_history) if self.active_modalities["face"] else 0
        v_s = np.mean(self.voice_score_history) if self.active_modalities["voice"] else 0
        p_s = np.mean(self.pose_score_history) if self.active_modalities["pose"] else 0
        i_s = np.mean(self.inactivity_score_history)
        
        fused = (f_s * current_weights["face"] + v_s * current_weights["voice"] + p_s * current_weights["pose"] + i_s * current_weights["inact"]) * 100
        self.score_history.append(fused)
        smoothed = np.mean(self.score_history)
        
        level = "NORMAL"
        if smoothed > 70: level = "HIGH"
        elif smoothed > 40: level = "MODERATE"
        elif smoothed > 15: level = "MILD"
        
        # Explanation
        reasons = []
        if f_s > 0.4: reasons.append("facial deviation")
        if v_s > 0.4: reasons.append("vocal flatness")
        if p_s > 0.4: reasons.append("posture shift")
        if i_s > 0.4: reasons.append("behavioral stillness")
        
        self.last_explanation = f"{level} distress via " + (", ".join(reasons) if reasons else "baseline signals") + "."
        self.last_explanation += "\n\n*NOTICE: Behavioral monitoring, not medical diagnosis.*"
        
        # Logging
        if int(time.time()) % 5 == 0: # Log every 5 seconds
            self.log_data(f_s, v_s, p_s, i_s, smoothed, self.confidence_score)
            
        return smoothed, level

    def get_explanation(self): return self.last_explanation
