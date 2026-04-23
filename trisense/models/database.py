import sqlite3
import os
from werkzeug.security import generate_password_hash, check_password_hash

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'users.db')

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'user'
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS prescriptions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            patient_username TEXT NOT NULL,
            doctor_username TEXT NOT NULL,
            medicine_name TEXT NOT NULL,
            time TEXT NOT NULL,
            FOREIGN KEY (patient_username) REFERENCES users (username)
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sender TEXT NOT NULL,
            receiver TEXT NOT NULL,
            message TEXT NOT NULL,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (sender) REFERENCES users (username),
            FOREIGN KEY (receiver) REFERENCES users (username)
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS patient_notes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            patient_username TEXT NOT NULL,
            doctor_username TEXT NOT NULL,
            note_text TEXT NOT NULL,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (patient_username) REFERENCES users (username),
            FOREIGN KEY (doctor_username) REFERENCES users (username)
        )
    ''')
    
    # Add default admin if not exists
    cursor.execute("SELECT * FROM users WHERE username='admin'")
    if not cursor.fetchone():
        hashed_pw = generate_password_hash("admin123")
        cursor.execute("INSERT INTO users (username, password, role) VALUES (?, ?, ?)", 
                       ("admin", hashed_pw, "doctor"))
    
    conn.commit()
    conn.close()

def add_user(username, password, role='user'):
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        hashed_pw = generate_password_hash(password)
        cursor.execute("INSERT INTO users (username, password, role) VALUES (?, ?, ?)", 
                       (username, hashed_pw, role))
        conn.commit()
        conn.close()
        return True
    except sqlite3.IntegrityError:
        return False

def verify_user(username, password):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT password, role FROM users WHERE username=?", (username,))
    result = cursor.fetchone()
    conn.close()
    
    if result and check_password_hash(result[0], password):
        return {"username": username, "role": result[1]}
    return None

def get_all_patients():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT username FROM users WHERE role='patient' OR role='user'")
    patients = [row[0] for row in cursor.fetchall()]
    conn.close()
    return patients

def add_prescription(patient, doctor, medicine, time):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("INSERT INTO prescriptions (patient_username, doctor_username, medicine_name, time) VALUES (?, ?, ?, ?)",
                   (patient, doctor, medicine, time))
    conn.commit()
    conn.close()
    return True

def get_prescriptions(username):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT medicine_name, time, doctor_username FROM prescriptions WHERE patient_username=?", (username,))
    res = cursor.fetchall()
    conn.close()
    return [{"medicine": r[0], "time": r[1], "doctor": r[2]} for r in res]

def get_all_prescriptions():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT patient_username, medicine_name, time FROM prescriptions")
    res = cursor.fetchall()
    conn.close()
    return [{"patient": r[0], "medicine": r[1], "time": r[2]} for r in res]

def add_message(sender, receiver, msg):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("INSERT INTO messages (sender, receiver, message) VALUES (?, ?, ?)",
                   (sender, receiver, msg))
    conn.commit()
    conn.close()

def get_messages(u1, u2):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT sender, receiver, message, timestamp FROM messages WHERE (sender=? AND receiver=?) OR (sender=? AND receiver=?) ORDER BY timestamp ASC",
                   (u1, u2, u2, u1))
    res = cursor.fetchall()
    conn.close()
    return [{"sender": r[0], "receiver": r[1], "message": r[2], "time": r[3]} for r in res]

def add_patient_note(patient, doctor, note):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("INSERT INTO patient_notes (patient_username, doctor_username, note_text) VALUES (?, ?, ?)",
                   (patient, doctor, note))
    conn.commit()
    conn.close()
    return True

def get_patient_notes(patient):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT note_text, timestamp, doctor_username FROM patient_notes WHERE patient_username=? ORDER BY timestamp DESC", (patient,))
    res = cursor.fetchall()
    conn.close()
    return [{"text": r[0], "time": r[1], "doctor": r[2]} for r in res]

def get_doctor_for_patient(patient):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    # 1. Try to find doctor from prescriptions
    cursor.execute("SELECT doctor_username FROM prescriptions WHERE patient_username=? LIMIT 1", (patient,))
    res = cursor.fetchone()
    if res:
        conn.close()
        return res[0]
    
    # 2. Try to find any doctor who has messaged the patient
    cursor.execute("""
        SELECT sender FROM messages 
        JOIN users ON messages.sender = users.username
        WHERE receiver=? AND users.role='doctor' 
        ORDER BY timestamp DESC LIMIT 1
    """, (patient,))
    res = cursor.fetchone()
    if res:
        conn.close()
        return res[0]
        
    # 3. Default fallback to the system admin doctor
    conn.close()
    return "admin"
