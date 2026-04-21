import time
import math
import mediapipe as mp
import cv2

class PoseDetector:
    def __init__(self, min_confidence=0.5, fall_duration_threshold=2.0):
        self.mp_pose = mp.solutions.pose
        self.pose = self.mp_pose.Pose(
            static_image_mode=False,
            min_detection_confidence=min_confidence,
            min_tracking_confidence=min_confidence
        )
        self.mp_drawing = mp.solutions.drawing_utils
        self.fall_duration_threshold = fall_duration_threshold
        
        self.fall_start_time = None
        self.current_state = "NORMAL"

    def calculate_angle(self, p1, p2, p3):
        """Calculate angle between 3 points (x, y)"""
        angle = math.degrees(
            math.atan2(p3[1]-p2[1], p3[0]-p2[0]) - 
            math.atan2(p1[1]-p2[1], p1[0]-p2[0])
        )
        if angle < 0:
            angle += 360
        return angle

    def process_frame(self, frame):
        """
        Processes a BGR frame from OpenCV.
        Returns (annotated_frame, pose_state, reason)
        """
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        results = self.pose.process(rgb_frame)
        
        state = "NORMAL"
        reason = ""
        
        if results.pose_landmarks:
            self.mp_drawing.draw_landmarks(
                frame, results.pose_landmarks, self.mp_pose.POSE_CONNECTIONS)
            
            landmarks = results.pose_landmarks.landmark
            
            shoulder = [landmarks[self.mp_pose.PoseLandmark.LEFT_SHOULDER.value].x,
                        landmarks[self.mp_pose.PoseLandmark.LEFT_SHOULDER.value].y]
            knee = [landmarks[self.mp_pose.PoseLandmark.LEFT_KNEE.value].x,
                    landmarks[self.mp_pose.PoseLandmark.LEFT_KNEE.value].y]
            ankle = [landmarks[self.mp_pose.PoseLandmark.LEFT_ANKLE.value].x,
                     landmarks[self.mp_pose.PoseLandmark.LEFT_ANKLE.value].y]
            hip = [landmarks[self.mp_pose.PoseLandmark.LEFT_HIP.value].x,
                   landmarks[self.mp_pose.PoseLandmark.LEFT_HIP.value].y]
            
            vertical_diff = shoulder[1] - ankle[1]
            horizontal_diff = abs(shoulder[0] - ankle[0])
            is_horizontal = horizontal_diff > abs(vertical_diff)
            hip_angle = self.calculate_angle(shoulder, hip, knee)
            
            if is_horizontal and (hip_angle > 140 or hip_angle < 40):
                state = "POTENTIAL_FALL"
                reason = "Horizontal posture detected"
                if self.fall_start_time is None:
                    self.fall_start_time = time.time()
                elif (time.time() - self.fall_start_time) >= self.fall_duration_threshold:
                    state = "FALL_DETECTED"
                    duration = round(time.time() - self.fall_start_time, 1)
                    reason = f"Fall detected: horizontal for {duration}s"
            else:
                self.fall_start_time = None
                state = "NORMAL"
                reason = "Upright/Normal posture"

        self.current_state = state
        return frame, state, reason
