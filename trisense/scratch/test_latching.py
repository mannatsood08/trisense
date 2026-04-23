from trisense.modules.event_engine import EventEngine
import time

def test_latching():
    engine = EventEngine()
    
    print("--- Testing Emergency Latching ---")
    
    # 1. Trigger Emergency
    print("Triggering FALL_DETECTED...")
    engine.trigger_event("pose", "FALL_DETECTED", reason="Test Fall")
    print(f"System State: {engine.current_state}, Locked: {engine.locked}")
    
    # 2. Trigger Normal (should be ignored by state machine)
    print("\nTriggering NORMAL pose (sensor says person is up)...")
    engine.trigger_event("pose", "NORMAL")
    print(f"System State: {engine.current_state}, Locked: {engine.locked}")
    
    if engine.current_state == "EMERGENCY" and engine.locked:
        print("SUCCESS: State remained EMERGENCY despite NORMAL input.")
    else:
        print("FAILURE: State reset automatically.")

    # 3. Trigger Safe Confirmed
    print("\nTriggering SAFE_CONFIRMED...")
    engine.trigger_event("system", "SAFE_CONFIRMED")
    print(f"System State: {engine.current_state}, Locked: {engine.locked}")
    
    if engine.current_state == "NORMAL" and not engine.locked:
        print("SUCCESS: System unlocked and reset to NORMAL.")
    else:
        print("FAILURE: System failed to unlock.")

if __name__ == "__main__":
    test_latching()
