from flask import Flask, render_template, Response, request, redirect, url_for, session, flash
import json
import time
import os
import threading
import queue
from functools import wraps
import numpy as np
import cv2

from trisense.models.database import init_db, add_user, verify_user

app = Flask(__name__)
app.secret_key = 'trisense_super_secret_key'

# Initialize Database
init_db()

# Global instances (will be injected by main.py)
camera_stream = None
event_engine = None
context_engine = None
camera_paused = False # Global privacy toggle

def save_snapshot(event_data):
    """Saves a frame when an emergency occurs"""
    data = json.loads(event_data)
    if data['event'] in ["EMERGENCY", "FALL_DETECTED", "CRITICAL"]:
        if camera_stream:
            frame_bytes = camera_stream.get_frame()
            if frame_bytes:
                import os
                static_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static', 'snapshots')
                filename = f"snapshot_{int(time.time())}.jpg"
                path = os.path.join(static_dir, filename)
                with open(path, 'wb') as f:
                    f.write(frame_bytes)
                # Store the last snapshot filename globally or in engine
                global last_snapshot_info
                last_snapshot_info = {
                    "url": f"/static/snapshots/{filename}",
                    "time": time.strftime('%H:%M:%S'),
                    "event": data['event']
                }
                print(f"[Dashboard] Emergency Snapshot saved: {filename}")

last_snapshot_info = None

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

@app.route('/')
@login_required
def index():
    return render_template('index.html', user=session['user'])

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        user_data = verify_user(username, password)
        if user_data:
            session['user'] = user_data['username']
            session['role'] = user_data['role']
            if user_data['role'] == 'doctor':
                return redirect(url_for('doctor_dashboard'))
            return redirect(url_for('index'))
        else:
            flash('Invalid username or password')
            
    return render_template('login.html')

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        role = request.form.get('role', 'user') # Default to user

        if password != confirm_password:
            flash('Passwords do not match')
        elif add_user(username, password, role):
            flash('Account created! Please login.')
            return redirect(url_for('login'))
        else:
            flash('Username already exists')

    return render_template('signup.html')

@app.route('/logout')
def logout():
    session.pop('user', None)
    return redirect(url_for('login'))

def gen_frames():
    # Pre-generate privacy placeholder once
    try:
        privacy_placeholder = np.zeros((480, 360, 3), dtype=np.uint8)
        cv2.putText(privacy_placeholder, "PRIVACY MODE", (40, 240), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (255, 255, 255), 2)
        _, privacy_buffer = cv2.imencode('.jpg', privacy_placeholder)
        privacy_bytes = privacy_buffer.tobytes()
    except:
        privacy_bytes = b''

    while True:
        try:
            if camera_paused:
                yield (b'--frame\r\n'
                       b'Content-Type: image/jpeg\r\n\r\n' + privacy_bytes + b'\r\n')
                time.sleep(1.0)
                continue
                
            if camera_stream is None:
                time.sleep(0.5)
                continue
            
            frame = camera_stream.get_frame()
            if frame is not None:
                # Direct yield of the pre-encoded bytes from CameraStream
                yield (b'--frame\r\n'
                       b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')
                time.sleep(0.04) # Stable 25 FPS
            else:
                time.sleep(0.1)
        except Exception as e:
            print(f"[Dashboard] Stream Error: {e}")
            time.sleep(1.0)

@app.route('/video_feed')
@login_required
def video_feed():
    return Response(gen_frames(),
                    mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/events')
@login_required
def events():
    def event_stream():
        import queue
        q = queue.Queue()
        
        def listener(data):
            q.put(data)
            
        event_engine.subscribe(listener)
        
        try:
            last_context_time = 0
            while True:
                # 1. Wait for data from queue with timeout so we can also send context pulses
                try:
                    data = q.get(timeout=1.0)
                    yield f"data: {data}\n\n"
                except queue.Empty:
                    pass
                
                # 2. Periodically pulse context data (every 2 seconds)
                if context_engine and (time.time() - last_context_time) > 2.0:
                    context_data = context_engine.get_status()
                    pulse = json.dumps({
                        "event": "CONTEXT_UPDATE",
                        "source": "context",
                        "timestamp": time.time(),
                        "details": context_data,
                        "system_state": event_engine.current_state # required by script.js updateUI
                    })
                    yield f"data: {pulse}\n\n"
                    last_context_time = time.time()
        except GeneratorExit:
            # Client disconnected
            event_engine.listeners.remove(listener)

    return Response(event_stream(), content_type='text/event-stream')

# --- Doctor Portal ---
@app.route('/doctor/dashboard')
@login_required
def doctor_dashboard():
    if session.get('role') != 'doctor':
        return redirect(url_for('index'))
    return render_template('doctor_dashboard.html', user=session['user'], camera_paused=camera_paused)

@app.route('/api/camera/toggle', methods=['POST'])
@login_required
def toggle_camera():
    global camera_paused
    camera_paused = not camera_paused
    return {"status": "ok", "paused": camera_paused}

@app.route('/api/patient/notes')
@login_required
def patient_notes():
    from trisense.models.database import get_patient_notes
    notes = get_patient_notes(session['user'])
    return {"notes": notes}

# --- Emergency Endpoints ---
@app.route('/sos', methods=['POST'])
@login_required
def trigger_sos():
    if event_engine:
        event_engine.push_event("CRITICAL_SOS", "Emergency SOS button pressed", source="USER_INTERFACE")
    return {"status": "success", "message": "SOS triggered"}

@app.route('/call_doctor', methods=['POST'])
@login_required
def call_doctor():
    event_engine.trigger_event("manual", "EMERGENCY", "User requested emergency doctor call.", reason="Manual Trigger")
    return {"status": "success", "message": "Doctor notified"}

@app.route('/send_alert', methods=['POST'])
@login_required
def send_alert():
    event_engine.trigger_event("manual", "EMERGENCY", "User sent a high-priority alert.", reason="Manual Trigger")
    return {"status": "success", "message": "Alert sent"}

@app.route('/mark_safe', methods=['POST'])
@login_required
def mark_safe():
    # Reset states
    event_engine.trigger_event("manual", "NORMAL", "User marked themselves as SAFE.", reason="Manual Reset")
    return {"status": "success", "message": "System marked as safe"}

@app.route('/api/speak', methods=['POST'])
@login_required
def api_speak():
    from trisense.utils.voice_service import voice_service
    if not request.is_json:
        return {"status": "error", "message": "JSON required"}, 400
        
    text = request.json.get('text', '')
    if text:
        voice_service.speak(text)
    return {"status": "ok"}

# --- Emotional Wellbeing Routes ---
from trisense.models.wellbeing_model import WellbeingModel
wellbeing_model = WellbeingModel()

@app.route('/wellbeing')
@login_required
def wellbeing_page():
    return render_template('wellbeing.html', user=session['user'])

def gen_wellbeing_frames():
    while True:
        if camera_stream is None:
            time.sleep(0.1)
            continue
        
        # Get raw frame from camera stream
        raw_frame_bytes = camera_stream.get_frame()
        if raw_frame_bytes is not None:
            # Decode to CV2
            nparr = np.frombuffer(raw_frame_bytes, np.uint8)
            frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            
            # Process Wellbeing (Mesh + Analysis)
            processed_frame, score, explanation = wellbeing_model.process_face(frame)
            
            # Encode back
            ret, buffer = cv2.imencode('.jpg', processed_frame)
            if ret:
                yield (b'--frame\r\n'
                       b'Content-Type: image/jpeg\r\n\r\n' + buffer.tobytes() + b'\r\n')
        else:
            time.sleep(0.01)

@app.route('/wellbeing_feed')
@login_required
def wellbeing_feed():
    return Response(gen_wellbeing_frames(),
                    mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/wellbeing_stats')
@login_required
def wellbeing_stats():
    def stats_stream():
        while True:
            score, status = wellbeing_model.get_fused_distress()
            data = {
                "score": round(score, 1),
                "status": status,
                "face_score": round(wellbeing_model.last_face_score, 1),
                "voice_score": round(wellbeing_model.last_voice_score, 1),
                "pose_score": round(wellbeing_model.last_pose_score, 1),
                "explanation": wellbeing_model.get_explanation()
            }
            yield f"data: {json.dumps(data)}\n\n"
            time.sleep(1) # Emit stats every second
            
    return Response(stats_stream(), content_type='text/event-stream')

# --- Care Features Routes ---
@app.route('/api/add_prescription', methods=['POST'])
@login_required
def api_add_prescription():
    if session.get('role') != 'doctor':
        return {"status": "error", "message": "Unauthorized"}, 403
    
    data = request.json
    patient = data.get('patient')
    med = data.get('medicine')
    time_str = data.get('time')
    
    from trisense.models.database import add_prescription
    if add_prescription(patient, session['user'], med, time_str):
        return {"status": "success"}
    return {"status": "error"}

@app.route('/api/get_prescriptions')
@login_required
def api_get_prescriptions():
    from trisense.models.database import get_prescriptions, get_all_prescriptions
    # Doctors can filter by patient via query param
    target_patient = request.args.get('patient')
    
    if session.get('role') == 'doctor':
        if target_patient:
            return {"prescriptions": get_prescriptions(target_patient)}
        return {"prescriptions": get_all_prescriptions()}
    else:
        return {"prescriptions": get_prescriptions(session['user'])}

@app.route('/api/doctor/patient_history')
@login_required
def api_patient_history():
    if session.get('role') != 'doctor':
        return {"status": "error"}, 403
    # For now, return all events from engine. Real app would filter by patient_id in DB.
    # We will simulate patient filtering by returning events as is, but UI will handle selection.
    return {"events": event_engine.last_events if event_engine else []}

@app.route('/api/doctor/notes', methods=['GET', 'POST'])
@login_required
def api_doctor_notes():
    if session.get('role') != 'doctor':
        return {"status": "error"}, 403
    
    from trisense.models.database import add_patient_note, get_patient_notes
    if request.method == 'POST':
        data = request.json
        patient = data.get('patient')
        note = data.get('note')
        add_patient_note(patient, session['user'], note)
        return {"status": "success"}
    else:
        patient = request.args.get('patient')
        if not patient:
            return {"status": "error", "message": "Missing patient param"}, 400
        return {"notes": get_patient_notes(patient)}

@app.route('/api/doctor/last_snapshot')
@login_required
def api_last_snapshot():
    # In a real app, you'd filter by patient. Here we return the global last alert.
    if last_snapshot_info:
        return last_snapshot_info
    return {"url": None, "message": "No snapshots yet"}

@app.route('/api/get_patients')
@login_required
def api_get_patients():
    if session.get('role') != 'doctor':
        return {"status": "error"}, 403
    from trisense.models.database import get_all_patients
    return {"patients": get_all_patients()}

@app.route('/api/messages', methods=['GET', 'POST'])
@login_required
def api_messages():
    from trisense.models.database import add_message, get_messages, get_all_patient_messages
    if request.method == 'POST':
        data = request.json
        receiver = data.get('receiver')
        msg = data.get('message')
        add_message(session['user'], receiver, msg)
        return {"status": "success"}
    else:
        other_user = request.args.get('with')
        if session.get('role') == 'doctor':
            if not other_user:
                return {"status": "error", "message": "Doctor must specify a patient"}, 400
            msgs = get_messages(session['user'], other_user)
        else:
            # Patient: Get all messages with doctors to ensure they don't miss anything
            msgs = get_all_patient_messages(session['user'])
            
        return {"messages": msgs}

@app.route('/api/doctor/analytics')
@login_required
def api_wellbeing_analytics():
    if session.get('role') != 'doctor':
        return {"status": "error"}, 403
    
    patient = request.args.get('patient')
    if not patient:
        return {"status": "error", "message": "Missing patient"}, 400
        
    from trisense.models.database import get_wellbeing_history
    history = get_wellbeing_history(patient)
    
    # Early Warning System (Feature Implementation)
    at_risk = False
    warning_reason = ""
    
    if len(history) >= 5:
        # Check distress trend
        recent_distress = [h['distress'] for h in history[-5:]]
        distress_slope = recent_distress[-1] - recent_distress[0]
        
        # Check activity trend
        recent_activity = [h['activity'] for h in history[-5:]]
        activity_slope = recent_activity[-1] - recent_activity[0]
        
        if distress_slope > 10 and activity_slope < 0:
            at_risk = True
            warning_reason = "Rising distress coupled with declining activity levels."
        elif distress_slope > 20:
            at_risk = True
            warning_reason = "Significant sudden increase in emotional distress."

    return {
        "history": history,
        "at_risk": at_risk,
        "warning_reason": warning_reason
    }

@app.route('/api/my_doctor')
@login_required
def api_get_my_doctor():
    from trisense.models.database import get_doctor_for_patient
    doctor = get_doctor_for_patient(session['user'])
    return {"doctor": doctor}

@app.route('/api/chatbot', methods=['POST'])
@login_required
def api_chatbot():
    from trisense.utils.chatbot_service import chatbot_service
    from trisense.models.database import get_prescriptions
    
    data = request.json
    user_input = data.get('message', '')
    
    # Prepare Context
    context = {
        "username": session['user'],
        "role": session.get('role', 'user'),
        "system_state": event_engine.current_state if event_engine else "UNKNOWN",
        "prescriptions": get_prescriptions(session['user'])
    }
    
    response = chatbot_service.get_response(user_input, context)
    return {"response": response}

def start_ui(_camera_stream, _event_engine, _context_engine=None):
    global camera_stream, event_engine, context_engine
    camera_stream = _camera_stream
    event_engine = _event_engine
    context_engine = _context_engine
    
    # Start wellbeing background logger
    def wellbeing_logger():
        from trisense.models.database import log_wellbeing_score, get_all_patients
        while True:
            time.sleep(30) # Log every 30s for demo purposes
            if context_engine:
                status = context_engine.get_status()
                distress = status.get('risk_score', 0)
                activity = status.get('inactivity_score', 0)
                # In a real app, you'd log for the specific patient being monitored.
                # Here we log for 'mannat' as a primary demo patient.
                log_wellbeing_score('mannat', distress, activity)
    
    threading.Thread(target=wellbeing_logger, daemon=True).start()
    
    # Register snapshot listener
    event_engine.subscribe(save_snapshot)
    
    # Run server
    app.run(host='0.0.0.0', port=5000, debug=False, use_reloader=False)
