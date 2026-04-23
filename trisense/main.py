import time
import os
import sys

# Add the parent directory of trisense to Python Path 
# so we can import trisense modules cleanly
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from trisense.config import settings
from trisense.modules.event_engine import EventEngine
from trisense.modules.audio_listener import AudioListener
from trisense.modules.camera_stream import CameraStream
from trisense.modules.emergency_manager import EmergencyManager
from trisense.modules.reminder_engine import ReminderEngine
from trisense.modules.context_engine import ContextEngine
from trisense.ui.dashboard import start_ui
import threading

def main():
    print("====================================")
    print("Starting TriSense Monitoring System")
    print("====================================")
    
    # 1. Initialize Event Engine
    event_engine = EventEngine()
    print("[INIT] Event Engine Initialized.")
    
    # 1.5 Initialize Context Engine
    context_engine = ContextEngine(event_engine)
    print("[INIT] Context-Aware Behavior Module started.")
    
    # 2. Start Camera Processing Thread
    camera_stream = CameraStream(
        event_engine=event_engine, 
        faces_db_path=settings.FACES_DB_PATH,
        width=settings.STREAM_WIDTH,
        height=settings.STREAM_HEIGHT
    )
    camera_stream.context_engine = context_engine
    camera_stream.start()
    print("[INIT] Camera stream & Vision models started.")
    
    # 3. Start Audio Processing Thread
    audio_listener = AudioListener(
        event_engine=event_engine,
        keywords=settings.EMERGENCY_KEYWORDS,
        energy_threshold=settings.AUDIO_ENERGY_THRESHOLD
    )
    audio_listener.start()
    print("[INIT] Voice emergency listener started.")
    
    # 3.5 Start Medicine Reminder Engine
    reminder_engine = ReminderEngine(event_engine)
    reminder_engine.start()
    print("[INIT] Medicine reminder engine started.")
    
    # 4. Start Emergency Manager (Monitoring state engine)
    emergency_manager = EmergencyManager(event_engine)
    
    # 5. Start Flask UI in main thread (blocking until exit)
    print("\n[INIT] Starting Web Dashboard. Open http://localhost:5000 in your browser.\n")
    start_ui(camera_stream, event_engine, context_engine)

if __name__ == "__main__":
    main()
