import time
import math
import mediapipe as mp
import cv2

class PoseDetector:
    def __init__(self, min_confidence=0.5, fall_duration_threshold=1.5):
        self.mp_pose = mp.solutions.pose
        self.pose = self.mp_pose.Pose(
            static_image_mode=False,
            min_detection_confidence=min_confidence,
            min_tracking_confidence=min_confidence
        )
        self.mp_drawing = mp.solutions.drawing_utils
        self.fall_duration_threshold = fall_duration_threshold
        
        self.fall_start_time = None
        self.last_seen_time = 0
        self.tracking_loss_grace = 1.0 # 1 second of lost tracking allowed before resetting
        self.current_state = "NORMAL"
        self.last_landmarks = None

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
            self.last_seen_time = time.time()
            self.mp_drawing.draw_landmarks(
                frame, results.pose_landmarks, self.mp_pose.POSE_CONNECTIONS)
            
            self.last_landmarks = results.pose_landmarks.landmark
            landmarks = self.last_landmarks
            
            # Using key points for orientation
            shoulder = [landmarks[self.mp_pose.PoseLandmark.LEFT_SHOULDER.value].x,
                        landmarks[self.mp_pose.PoseLandmark.LEFT_SHOULDER.value].y]
            ankle = [landmarks[self.mp_pose.PoseLandmark.LEFT_ANKLE.value].x,
                     landmarks[self.mp_pose.PoseLandmark.LEFT_ANKLE.value].y]
            hip = [landmarks[self.mp_pose.PoseLandmark.LEFT_HIP.value].x,
                   landmarks[self.mp_pose.PoseLandmark.LEFT_HIP.value].y]
            knee = [landmarks[self.mp_pose.PoseLandmark.LEFT_KNEE.value].x,
                    landmarks[self.mp_pose.PoseLandmark.LEFT_KNEE.value].y]
            
            vertical_diff = abs(shoulder[1] - ankle[1])
            horizontal_diff = abs(shoulder[0] - ankle[0])
            
            # Portrait mode assumption: Fall means horizontal_diff becomes significant relative to vertical
            # Broaden check: vertical_diff < 0.25 (squashed) OR horizontal posture
            is_horizontal = horizontal_diff > (vertical_diff * 1.2)
            hip_angle = self.calculate_angle(shoulder, hip, knee)
            
            # Broadened thresholds: anything remotely horizontal or extremely squashed
            if is_horizontal or vertical_diff < 0.15:
                state = "POTENTIAL_FALL"
                reason = "Horizontal/Low-angle posture detected"
                if self.fall_start_time is None:
                    self.fall_start_time = time.time()
                elif (time.time() - self.fall_start_time) >= self.fall_duration_threshold:
                    state = "FALL_DETECTED"
                    duration = round(time.time() - self.fall_start_time, 1)
                    reason = f"Fall confirmed: position held for {duration}s"
            else:
                self.fall_start_time = None
                state = "NORMAL"
                reason = "Upright"

        else:
            # Handle tracking loss
            if self.fall_start_time is not None:
                if (time.time() - self.last_seen_time) > self.tracking_loss_grace:
                    # Grace period expired, person likely walked away
                    self.fall_start_time = None
                    state = "NORMAL"
                    reason = "Tracking lost (Grace expired)"
                else:
                    # Within grace period, maintain previous potential state
                    state = "POTENTIAL_FALL"
                    reason = "Tracking lost (Maintaining state...)"
            else:
                state = "NORMAL"
                reason = "No person detected"
            self.last_landmarks = None

        self.current_state = state
        return frame, state, reason

        self.current_state = state
        return frame, state, reason
