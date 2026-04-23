import time
import cv2
import os
import mediapipe as mp
try:
    from deepface import DeepFace
    HAS_DEEPFACE = True
except ImportError:
    HAS_DEEPFACE = False

class FaceMonitor:
    def __init__(self, db_path):
        self.db_path = db_path
        self.mp_face_detection = mp.solutions.face_detection
        self.face_detection = self.mp_face_detection.FaceDetection(
            model_selection=0, min_detection_confidence=0.6) # Increased confidence
        
        self.last_recognition_time = 0
        self.recognition_interval = 4.0  # Recognition every 4s for stability
        self.current_state = "NORMAL"
        self.last_face_count = 0
        
        if not os.path.exists(self.db_path):
            os.makedirs(self.db_path)

        if HAS_DEEPFACE:
            print("[FaceMonitor] Initializing DeepFace engine...")
            try:
                # Pre-build model to avoid context/threading issues during lazy-load
                DeepFace.build_model("VGG-Face")
                print("[FaceMonitor] Recognition engine ready.")
            except Exception as e:
                print(f"[FaceMonitor] Warm-up warning: {e}")

    def process_frame(self, frame):
        """
        Returns (annotated_frame, face_state)
        face_state: NORMAL, AUTHORIZED_USER, UNKNOWN_PERSON, VERIFYING
        """
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        results = self.face_detection.process(rgb_frame)
        
        face_count = len(results.detections) if results.detections else 0
        state = self.current_state
        
        # 1. Force immediate recognition if a new face enters
        if face_count > self.last_face_count:
            print(f"[FaceMonitor] New face detected! Count: {face_count}. Forcing immediate check.")
            self.last_recognition_time = 0 
            state = "VERIFYING"
        
        self.last_face_count = face_count

        if results.detections:
            # Drawing and processing
            for detection in results.detections:
                bboxC = detection.location_data.relative_bounding_box
                ih, iw, _ = frame.shape
                x, y, w, h = int(bboxC.xmin * iw), int(bboxC.ymin * ih), \
                             int(bboxC.width * iw), int(bboxC.height * ih)
                
                # Draw bounding box
                color = (0, 255, 0) if state == "AUTHORIZED_USER" else (0, 165, 255) # Orange for unknown/verifying
                if state == "UNKNOWN_PERSON": color = (0, 0, 255) # Red
                cv2.rectangle(frame, (x, y), (x+w, y+h), color, 2)
            
            # 2. Recognition Logic
            if HAS_DEEPFACE and (time.time() - self.last_recognition_time) > self.recognition_interval:
                self.last_recognition_time = time.time()
                
                new_state = "AUTHORIZED_USER" # Assume authorized, prove otherwise
                found_unknown = False
                
                for detection in results.detections:
                    bboxC = detection.location_data.relative_bounding_box
                    ih, iw, _ = frame.shape
                    x, y, w, h = int(bboxC.xmin * iw), int(bboxC.ymin * ih), \
                                 int(bboxC.width * iw), int(bboxC.height * ih)
                                 
                    face_crop = frame[max(0, y):min(ih, y+h), max(0, x):min(iw, x+w)]
                    if face_crop.shape[0] > 10 and face_crop.shape[1] > 10:
                        try:
                            if len(os.listdir(self.db_path)) > 0:
                                dfs = DeepFace.find(img_path=face_crop, db_path=self.db_path, enforce_detection=False, silent=True)
                                if not (len(dfs) > 0 and len(dfs[0]) > 0):
                                    found_unknown = True
                                    break # Priority: if one is unknown, the whole state is unknown
                            else:
                                found_unknown = True
                                break
                        except Exception as e:
                            print(f"[FaceMonitor] Recognition Error: {e}")
                            continue

                if found_unknown:
                    state = "UNKNOWN_PERSON"
                else:
                    state = "AUTHORIZED_USER"
                
                self.current_state = state
            else:
                # Maintain state during polling interval
                state = self.current_state
        else:
            state = "NORMAL"
            self.current_state = state
            
        return frame, state
