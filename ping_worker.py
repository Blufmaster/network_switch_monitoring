from ping3 import ping
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from database import get_devices, get_device_id_by_ip, log_ping_result
from notifier import send_alert_email
from notification import send_whatsapp_alert
from telegram_notifier import send_telegram_alert


device_status = {}
failure_count = {}
alert_sent = set()

def handle_ping(dev):
    name, ip, email = dev[1], dev[2], dev[4]

    response = ping(ip, timeout=1)
    status = "UP" if response else "DOWN"
    response_time = round(response * 1000, 2) if response else None  # ms

    prev_status = device_status.get(ip, {}).get("status", "UNKNOWN")

    if status == "DOWN":
        failure_count[ip] = failure_count.get(ip, 0) + 1
    else:
        failure_count[ip] = 0

    if failure_count[ip] >= 5 and ip not in alert_sent:  # 5 consecutive failures then only the mail will be sent 
        print(f"[ALERT] Device down: {name} has been down for 3 cycles ({ip}). Notifying {email}")
        send_alert_email(name, ip, email, issue="Device Down")
        send_whatsapp_alert(name, ip)
        send_telegram_alert(name, ip)


        alert_sent.add(ip)

    if status == "UP":
        alert_sent.discard(ip)

    # Save live status
    device_status[ip] = {
        "status": status,
        "response_time": response_time if response_time is not None else "N/A"
    }

    print(f"[PING] {name} ({ip}) → {status} ({response_time} ms)")

    # Log to DB
    device_id = get_device_id_by_ip(ip)
    if device_id:
        log_ping_result(device_id, response_time or 0.0, status)

def ping_devices(interval=2, batch_size=50):
    while True:
        devices = get_devices()
        print("[INFO] Starting batch ping...")

        seen_ips = set()
        unique_devices = []

        for dev in devices:
            ip = dev[2]
            if ip not in seen_ips:
                seen_ips.add(ip)
                unique_devices.append(dev)

        for i in range(0, len(unique_devices), batch_size):
            batch = unique_devices[i:i + batch_size]
            with ThreadPoolExecutor(max_workers=batch_size) as executor:
                executor.map(handle_ping, batch)

            print(f"[INFO] Batch {i // batch_size + 1} complete. Waiting 2s...")
            time.sleep(2)

        print(f"[INFO] Full cycle complete. Sleeping for {interval} seconds...\n")
        time.sleep(interval)

def start_background_thread():
    thread = threading.Thread(target=ping_devices, kwargs={"interval": 2, "batch_size": 50}, daemon=True)
    thread.start()
