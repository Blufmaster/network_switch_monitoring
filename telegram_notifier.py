import requests

TELEGRAM_BOT_TOKEN = "7875785978:AAEpBaaWco33dvQZ2ipQvmqKSivXvvf3cyI"
TELEGRAM_CHAT_ID = "-1002849874511"  # Replace with your real chat ID

def send_telegram_alert(name, ip, issue="Device Down"):
    message = f"🚨 *Alert*: {issue}\nDevice: `{name}`\nIP: `{ip}`"
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"

    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "Markdown"
    }

    try:
        response = requests.post(url, json=payload)
        response.raise_for_status()
        print(f"[TELEGRAM] Sent alert to {TELEGRAM_CHAT_ID}")
    except Exception as e:
        print(f"[TELEGRAM] Failed to send alert: {e}")
