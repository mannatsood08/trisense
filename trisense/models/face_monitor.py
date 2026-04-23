import time
import cv2
import os
import mediapipe as mp

# Force legacy Keras to avoid "layer sequential has never been called" errors in Keras 3
os.environ["TF_USE_LEGACY_KERAS"] = "1"
os.environ["TF_ENABLE_ONEDNN_OPTS"] = "0"

try:
    from deepface import DeepFace
    import tensorflow as tf
    HAS_DEEPFACE = True
except ImportError:
    HAS_DEEPFACE = False

class FaceMonitor:
    def __init__(self, db_path):
        self.db_path = db_path
        self.mp_face_detection = mp.solutions.face_detection
        self.face_detection = self.mp_face_detection.FaceDetection(
            model_selection=0, min_detection_confidence=0.6)
        
        self.last_recognition_time = 0
        self.recognition_interval = 4.0 
        self.current_state = "NORMAL"
        self.last_face_count = 0
        
        # Facenet512 is more robust for Keras 2/3 compatibility and more accurate
        self.model_name = "Facenet512" 
        
        if not os.path.exists(self.db_path):
            os.makedirs(self.db_path)
            print(f"[FaceMonitor] Created faces database at {self.db_path}")

        if HAS_DEEPFACE:
            print(f"[FaceMonitor] Initializing DeepFace engine with {self.model_name}...")
            try:
                # Pre-build model
                DeepFace.build_model(self.model_name)
                print("[FaceMonitor] Recognition engine ready.")
            except Exception as e:
                print(f"[FaceMonitor] Initialization warning: {e}")

    def process_frame(self, frame):
        """
        Returns (annotated_frame, face_state)
        face_state: NORMAL, AUTHORIZED_USER, UNKNOWN_PERSON, VERIFYING
        """
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        results = self.face_detection.process(rgb_frame)
        
        face_count = len(results.detections) if results.detections else 0
        state = self.current_state
        
        # Force immediate recognition if a new face enters
        if face_count > self.last_face_count:
            print(f"[FaceMonitor] New face detected! Count: {face_count}. Forcing immediate check.")
            self.last_recognition_time = 0 
            state = "VERIFYING"
        
        self.last_face_count = face_count

        if results.detections:
            for detection in results.detections:
                bboxC = detection.location_data.relative_bounding_box
                ih, iw, _ = frame.shape
                x, y, w, h = int(bboxC.xmin * iw), int(bboxC.ymin * ih), \
                             int(bboxC.width * iw), int(bboxC.height * ih)
                
                color = (0, 255, 0) if state == "AUTHORIZED_USER" else (0, 165, 255)
                if state == "UNKNOWN_PERSON": color = (0, 0, 255)
                cv2.rectangle(frame, (x, y), (x+w, y+h), color, 2)
            
            # Recognition Logic
            if HAS_DEEPFACE and (time.time() - self.last_recognition_time) > self.recognition_interval:
                self.last_recognition_time = time.time()
                
                found_unknown = False
                
                # Check if there are any files in the database
                db_files = [f for f in os.listdir(self.db_path) if f.endswith(('.jpg', '.jpeg', '.png'))]
                
                if len(db_files) == 0:
                    # If no faces registered, everyone is unknown
                    found_unknown = True
                    print("[FaceMonitor] Database empty. No authorized faces found.")
                else:
                    for detection in results.detections:
                        bboxC = detection.location_data.relative_bounding_box
                        ih, iw, _ = frame.shape
                        x, y, w, h = int(bboxC.xmin * iw), int(bboxC.ymin * ih), \
                                     int(bboxC.width * iw), int(bboxC.height * ih)
                                     
                        face_crop = frame[max(0, y):min(ih, y+h), max(0, x):min(iw, x+w)]
                        if face_crop.shape[0] > 20 and face_crop.shape[1] > 20: # Slightly larger for better accuracy
                            try:
                                # Switch to verify loop for higher stability in Keras 3/Legacy mixed environments
                                match_found = False
                                for db_file in db_files:
                                    img_path = os.path.join(self.db_path, db_file)
                                    try:
                                        # VGG-Face is the most compatible with verify across versions
                                        result = DeepFace.verify(
                                            img1_path=face_crop,
                                            img2_path=img_path,
                                            model_name="VGG-Face",
                                            enforce_detection=False,
                                            silent=True
                                        )
                                        if result.get("verified", False):
                                            match_found = True
                                            print(f"[FaceMonitor] Match found: {db_file} (Confidence: {result.get('distance')})")
                                            break
                                    except Exception as ve:
                                        continue
                                
                                if not match_found:
                                    found_unknown = True
                            except Exception as e:
                                print(f"[FaceMonitor] Recognition Error: {e}")
                                continue

                state = "UNKNOWN_PERSON" if found_unknown else "AUTHORIZED_USER"
                self.current_state = state
            else:
                state = self.current_state
        else:
            state = "NORMAL"
            self.current_state = state
            
        return frame, state
