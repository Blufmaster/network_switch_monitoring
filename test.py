import os
from dotenv import load_dotenv

load_dotenv()

print("TWILIO_ACCOUNT_SID =", repr(os.getenv("TWILIO_ACCOUNT_SID")))
print("TWILIO_WHATSAPP_FROM =", repr(os.getenv("TWILIO_WHATSAPP_FROM")))
