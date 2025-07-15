import os
from twilio.rest import Client
from dotenv import load_dotenv

load_dotenv()

print("TWILIO_ACCOUNT_SID =", repr(os.getenv("TWILIO_ACCOUNT_SID")))
print("TWILIO_WHATSAPP_FROM =", repr(os.getenv("TWILIO_WHATSAPP_FROM")))


account_sid = os.getenv("TWILIO_ACCOUNT_SID")
auth_token = os.getenv("TWILIO_AUTH_TOKEN")
from_whatsapp = os.getenv("TWILIO_WHATSAPP_FROM")
to_whatsapp = os.getenv("ALERT_WHATSAPP_TO")

client = Client(account_sid, auth_token)

def send_whatsapp_alert(device_name, ip, issue="DOWN"):
    message = client.messages.create(
        body=f"🚨 Alert: Device '{device_name}' ({ip}) is {issue}!\n - The Intern",
        from_=from_whatsapp,
        to=to_whatsapp
    )
    print(f"[TWILIO] Sent WhatsApp alert: SID {message.sid}")
