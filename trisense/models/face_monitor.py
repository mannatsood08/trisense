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
            model_selection=0, min_detection_confidence=0.5)
        
        self.last_recognition_time = 0
        self.recognition_interval = 3.0  # run heavy recognition every 3s
        self.current_state = "NORMAL" # Assuming no faces means normal. If faces, check identity.
        
        if not os.path.exists(self.db_path):
            os.makedirs(self.db_path)

    def process_frame(self, frame):
        """
        Returns (annotated_frame, face_state)
        face_state: NORMAL, AUTHORIZED_USER, UNKNOWN_PERSON
        """
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        results = self.face_detection.process(rgb_frame)
        
        state = self.current_state
        
        if results.detections:
            for detection in results.detections:
                bboxC = detection.location_data.relative_bounding_box
                ih, iw, _ = frame.shape
                x, y, w, h = int(bboxC.xmin * iw), int(bboxC.ymin * ih), \
                             int(bboxC.width * iw), int(bboxC.height * ih)
                
                # Draw bounding box
                cv2.rectangle(frame, (x, y), (x+w, y+h), (255, 0, 0), 2)
                
                # Recognition step
                if HAS_DEEPFACE and (time.time() - self.last_recognition_time) > self.recognition_interval:
                    self.last_recognition_time = time.time()
                    # Crop face
                    face_crop = frame[max(0, y):min(ih, y+h), max(0, x):min(iw, x+w)]
                    if face_crop.shape[0] > 0 and face_crop.shape[1] > 0:
                        try:
                            # Verify against database 
                            # (find returns a list of dataframes of matches)
                            if len(os.listdir(self.db_path)) > 0:
                                dfs = DeepFace.find(img_path=face_crop, db_path=self.db_path, enforce_detection=False, silent=True)
                                if len(dfs) > 0 and len(dfs[0]) > 0:
                                    state = "AUTHORIZED_USER"
                                else:
                                    state = "UNKNOWN_PERSON"
                            else:
                                state = "UNKNOWN_PERSON" # No authorized users enrolled
                        except Exception as e:
                            # DeepFace failed
                            pass
                        self.current_state = state
                else:
                    state = self.current_state
        else:
            state = "NORMAL" # No face
            self.current_state = state
            
        return frame, state
