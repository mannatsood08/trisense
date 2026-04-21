import time
from trisense.config import settings

last_alert_time = 0

def send_sms_alert(message_type, timestamp, reason):
    """
    Sends an SMS alert using Twilio SDK.
    Includes cooldown protection.
    """
    global last_alert_time
    current_time = time.time()
    
    if current_time - last_alert_time < settings.ESCALATION_COOLDOWN:
        print(f"[SMS] Cooldown active. Skipping alert.")
        return False

    alert_body = (
        f"🚨 TriSense Emergency alert\n"
        f"Type: {message_type}\n"
        f"Time: {time.ctime(timestamp)}\n"
        f"Reason: {reason}\n"
        f"User status: NO RESPONSE. Please check immediately."
    )

    try:
        # Check if Twilio ID is still placeholder
        if "xxxx" in settings.TWILIO_ACCOUNT_SID:
            print("\n" + "="*40)
            print("SIMULATED SMS ALERT (Twilio credentials missing)")
            print(f"To: {settings.CAREGIVER_PHONE_NUMBER}")
            print(f"Message: {alert_body}")
            print("="*40 + "\n")
            last_alert_time = current_time
            return True

        from twilio.rest import Client
        client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
        
        client.messages.create(
            body=alert_body,
            from_=settings.TWILIO_PHONE_NUMBER,
            to=settings.CAREGIVER_PHONE_NUMBER
        )
        
        print("[SMS] Alert sent successfully via Twilio.")
        last_alert_time = current_time
        return True
        
    except Exception as e:
        print(f"[SMS] Failed to send alert: {e}")
        return False
