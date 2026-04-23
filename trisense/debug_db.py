import sqlite3
import os

DB_PATH = 'trisense/users.db'
if not os.path.exists(DB_PATH):
    print(f"DB not found at {DB_PATH}")
else:
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    print("--- MESSAGES ---")
    cursor.execute("SELECT * FROM messages")
    for row in cursor.fetchall():
        print(row)
        
    print("\n--- USERS ---")
    cursor.execute("SELECT username, role FROM users")
    for row in cursor.fetchall():
        print(row)
        
    conn.close()
