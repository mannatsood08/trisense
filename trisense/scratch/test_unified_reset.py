from trisense.modules.event_engine import EventEngine
from trisense.modules.emergency_manager import EmergencyManager
import time
import threading

def test_unified_reset():
    engine = EventEngine()
    manager = EmergencyManager(engine)
    
    print("--- Testing Unified Reset (Manual Override) ---")
    
    # 1. Trigger Emergency (starts background manager thread)
    print("User says 'HELP'...")
    engine.trigger_event("voice", "EMERGENCY", reason="HELP keyword")
    print(f"System State: {engine.current_state}, Locked: {engine.locked}")
    
    # Wait 2 seconds for manager to start its work
    time.sleep(2)
    
    # 2. Manual Reset (clicks button)
    print("\nUser clicks 'Mark System Safe' button...")
    engine.trigger_event("manual", "SAFE_CONFIRMED")
    print(f"System State: {engine.current_state}, Locked: {engine.locked}")
    
    # 3. Wait for manager's window (should have aborted)
    print("\nWaiting for potential escalation (should be aborted)...")
    time.sleep(15) 
    
    print(f"\nFinal State: {engine.current_state}, Locked: {engine.locked}")
    if engine.current_state == "NORMAL":
        print("SUCCESS: System remained NORMAL. Abortion worked.")
    else:
        print("FAILURE: System re-locked by background escalation.")

if __name__ == "__main__":
    test_unified_reset()
