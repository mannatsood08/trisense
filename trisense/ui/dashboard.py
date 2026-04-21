from flask import Flask, render_template, Response, request, redirect, url_for, session, flash
import json
import time
from functools import wraps

from trisense.models.database import init_db, add_user, verify_user

app = Flask(__name__)
app.secret_key = 'trisense_super_secret_key'

# Initialize Database
init_db()

# Global instances (will be injected by main.py)
camera_stream = None
event_engine = None

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
    while True:
        if camera_stream is None:
            time.sleep(0.1)
            continue
        
        frame = camera_stream.get_frame()
        if frame is not None:
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')
        else:
            time.sleep(0.01)

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
            while True:
                # Wait for data from queue
                data = q.get()
                yield f"data: {data}\n\n"
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
    return render_template('doctor_dashboard.html', user=session['user'])

# --- Emergency Endpoints ---
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
    text = request.json.get('text', '')
    if text:
        voice_service.speak(text)
    return {"status": "ok"}

def start_ui(_camera_stream, _event_engine):
    global camera_stream, event_engine
    camera_stream = _camera_stream
    event_engine = _event_engine
    
    # Run server
    app.run(host='0.0.0.0', port=5000, debug=False, use_reloader=False)
