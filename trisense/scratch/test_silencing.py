from trisense.modules.event_engine import EventEngine
import time

def test_sensor_silencing():
    engine = EventEngine()
    
    print("--- Testing Sensor Silencing (Re-lock Prevention) ---")
    
    # 1. Trigger Pose Emergency
    print("Pose detects FALL...")
    engine.trigger_event("pose", "FALL_DETECTED")
    print(f"System State: {engine.current_state}, Locked: {engine.locked}")
    
    # 2. Mark Safe (Manual)
    print("\nUser marks SAFE...")
    engine.trigger_event("manual", "SAFE_CONFIRMED")
    print(f"System State: {engine.current_state}, Locked: {engine.locked}")
    print(f"Silenced Modules: {engine.silenced_modules}")

    # 3. Simulate sensor still seeing fall after cooldown (e.g., 11 seconds later)
    # The module 'pose' is silenced because it was active during reset.
    print("\nSimulating 11 seconds passing... Sensor 'pose' still detects FALL...")
    engine.last_safe_time = time.time() - 11 # Trick the cooldown
    engine.trigger_event("pose", "FALL_DETECTED")
    print(f"System State: {engine.current_state}, Locked: {engine.locked}")
    
    if engine.current_state == "NORMAL":
        print("SUCCESS: System ignored the persistent fall. Silencing worked.")
    else:
        print("FAILURE: System re-locked immediately.")

    # 4. Sensor finally sees person stand up (NORMAL)
    print("\nSensor 'pose' returns to NORMAL...")
    engine.trigger_event("pose", "NORMAL")
    print(f"Silenced Modules: {engine.silenced_modules}")
    
    # 5. Sensor detects a NEW fall
    print("\nSensor 'pose' detects NEW fall...")
    engine.trigger_event("pose", "FALL_DETECTED")
    print(f"System State: {engine.current_state}, Locked: {engine.locked}")
    
    if engine.current_state == "EMERGENCY":
        print("SUCCESS: System re-locked for a NEW event after returning to NORMAL.")
    else:
        print("FAILURE: System is still silenced.")

if __name__ == "__main__":
    test_sensor_silencing()
