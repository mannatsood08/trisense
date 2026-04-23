import threading
import cv2
import time
from trisense.models.pose_detection import PoseDetector
from trisense.models.face_monitor import FaceMonitor

class CameraStream(threading.Thread):
    def __init__(self, event_engine, faces_db_path, width=640, height=480):
        super().__init__(daemon=True)
        self.event_engine = event_engine
        self.pose_detector = PoseDetector()
        self.face_monitor = FaceMonitor(db_path=faces_db_path)
        self.context_engine = None # Will be set by main.py call setup_context
        
        self.cap = cv2.VideoCapture(0)
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
        
        self.current_frame = None
        self.lock = threading.Lock()

    def run(self):
        print("[CameraStream] Started parsing video frames...")
        # State tracking to only emit events on change
        last_pose_state = "NORMAL"
        last_face_state = "NORMAL"
        
        while True:
            ret, frame = self.cap.read()
            if not ret:
                time.sleep(0.1)
                continue

            # --- Portrait Crop Mode (360x480) ---
            # Capture is 640, target is 360. Margin is (640-360)/2 = 140
            h, w = frame.shape[:2]
            target_w = 360
            if w > target_w:
                start_x = (w - target_w) // 2
                frame = frame[:, start_x:start_x+target_w]

            # 1. Pose Detection
            frame, pose_state, pose_reason = self.pose_detector.process_frame(frame)
            if pose_state != last_pose_state:
                self.event_engine.trigger_event("pose", pose_state, reason=pose_reason)
                last_pose_state = pose_state
            
            # 1.5 Context Engine Landmark Processing
            if self.context_engine and self.pose_detector.last_landmarks:
                self.context_engine.process_landmarks(self.pose_detector.last_landmarks)

            # 2. Face Monitoring
            frame, face_state = self.face_monitor.process_frame(frame)
            if face_state != last_face_state:
                reason = "Face recognized" if face_state == "AUTHORIZED_USER" else "Unknown face detected"
                if face_state == "NORMAL": reason = "No face in view"
                self.event_engine.trigger_event("face", face_state, reason=reason)
                last_face_state = face_state

            # Encode frame for UI Streaming
            ret, buffer = cv2.imencode('.jpg', frame)
            if ret:
                with self.lock:
                    self.current_frame = buffer.tobytes()

    def get_frame(self):
        with self.lock:
            return self.current_frame
