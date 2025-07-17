from flask import Flask, render_template, request, redirect, url_for
from ai_model.risk_model import compute_risk_scores
import threading
import time
import os
from ai_model.risk_model import refresh_device_baselines
from datetime import datetime, timedelta
import pandas as pd
from database import get_device_stats


from database import (
    init_db,
    get_devices,
    add_device,
    delete_device,
    delete_all_devices,
    get_device_id_by_ip,
    log_ping_result,
    get_ping_logs_for_device,
    #get_all_risk_score,
    delete_old_ping_logs
)
from ping_worker import start_background_thread, device_status

app = Flask(__name__)

# ✅ Initialize database
init_db()

from database import get_all_risk_scores, get_all_device_baselines
@app.route("/", methods=["GET"])
def dashboard():
    search_ip = request.args.get("search_ip", "").strip()
    search_name = request.args.get("search_name", "").strip()
    time_range = request.args.get("range", "6h")

    range_map = {
        "3h": 3,
        "6h": 6,
        "12h": 12,
        "1d": 24,
        "3d": 72,
        "all": None
    }

    hours = range_map.get(time_range, 6)
    since = datetime.utcnow() - timedelta(hours=hours) if hours else None

    devices = get_devices()
    risk_scores = get_all_risk_scores()
    baselines = get_all_device_baselines()

    statuses = []
    current_5x_down = []
    historical_5x_down = []

    for d in devices:
        dev_id, name, ip = d[0], d[1], d[2]

        if search_ip and search_ip.lower() not in ip.lower():
            continue
        if search_name and search_name.lower() not in name.lower():
            continue

        stat = device_status.get(ip, {})
        status = stat.get("status", "UNKNOWN")
        response_time = stat.get("response_time", "N/A")
        risk_score = risk_scores.get(dev_id, None)

        if status == "DOWN":
            risk_score = 1.0  # Force critical risk if currently down

        baseline = baselines.get(dev_id, {})
        avg_baseline = round(baseline.get("avg", 0), 2)
        std_baseline = round(baseline.get("std", 0), 2)

        # Historical 5× DOWN streak detection
        logs_df = get_ping_logs_for_device(dev_id, since=since)
        streak = 0
        historical_found = False

        for _, row in logs_df.iterrows():
            if row["status"] == "DOWN":
                streak += 1
                if streak >= 5:
                    historical_found = True
                    break
            else:
                streak = 0

        if historical_found:
            historical_5x_down.append(name)

        # Current 5× DOWN streak detection
        current_streak = 0
        recent_logs = logs_df.tail(5)
        if not recent_logs.empty and len(recent_logs) >= 5:
            for _, row in recent_logs.iterrows():
                if row["status"] == "DOWN":
                    current_streak += 1

            if current_streak >= 5 and status == "DOWN":
                current_5x_down.append(name)

        statuses.append((
            dev_id,
            name,
            ip,
            status,
            response_time,
            risk_score,
            avg_baseline,
            std_baseline
        ))

    # ✅ Sort by risk_score descending (None becomes -1 to go at bottom)
    statuses.sort(key=lambda x: x[5] if x[5] is not None else -1, reverse=True)

    return render_template(
        "dashboard.html",
        devices=statuses,
        current_down_streak_devices=current_5x_down,
        historical_down_streak_devices=historical_5x_down,
        selected_range=time_range,
        search_ip=search_ip,
        search_name=search_name
    )





@app.route("/manage", methods=["GET", "POST"])
def manage():
    if request.method == "POST":
        name = request.form["name"]
        ip = request.form["ip"]
        type = request.form["type"]
        email = request.form["email"]
        add_device(name, ip, type, email)
        return redirect("/manage")

    search_ip = request.args.get("search_ip", "").strip()
    search_name = request.args.get("search_name", "").strip()

    all_devices = get_devices()
    devices = []

    for d in all_devices:
        if search_ip and search_ip.lower() not in d[2].lower():
            continue
        if search_name and search_name.lower() not in d[1].lower():
            continue
        devices.append(d)

    return render_template(
        "manage.html",
        devices=devices,
        search_ip=search_ip,
        search_name=search_name
    )


@app.route("/delete/<int:device_id>", methods=["GET", "POST"])
def delete(device_id):
    delete_device(device_id)
    return redirect(url_for("manage"))


@app.route("/delete_all")
def delete_all():
    delete_all_devices()
    return redirect(url_for("manage"))

@app.route("/logs/<int:device_id>")
def show_logs(device_id):
    logs_df = get_ping_logs_for_device(device_id)
    
    if logs_df.empty:
        logs = []
    else:
        logs = list(logs_df.itertuples(index=False, name=None))  # returns list of (timestamp, status, response_time)

    return render_template("logs.html", logs=logs)


# ✅ Background thread for periodic AI-based risk score calculation
def run_risk_score_updater():
    while True:
        print("[AI] Computing risk scores...")
        compute_risk_scores(minutes=10)  # Uses last 60 minutes of data
        time.sleep(60)  # Run every 5 minutes (change to 300s from 60s)
        # final update every 5 minutes using the last 60 minutes of logs


def run_baseline_updater():
    while True:
        refresh_device_baselines(minutes=10)
        print("[AI] Updated device baselines.", flush=True)
        time.sleep(300)  # 5 minutes (for testing; later switch to 24*3600 for 24 hours)  # Once every 24 hours change it later to 24hrs currently set to 5 mins for testing
        # calculate baseline every 3 hours

        """| Task                   | Interval     | Data Used     |
| ---------------------- | ------------ | ------------- |
| **Ping every device**  | Every 60 sec | Real-time     |
| **Compute Risk Score** | Every 5 min  | Last 60 mins  |
| **Update Baselines**   | Every 3 hrs  | Last 3 hrs    |
| **Send Email Alerts**  | On 3 fails   | Last 3 checks |
"""



@app.route("/device/<ip>")
def device_detail(ip):
    stats = get_device_stats(ip)
    if not stats:
        return f"No device found with IP {ip}", 404

    # Parse ?range=3h, 6h, 12h, 1d, 3d, all
    range_param = request.args.get("range", "6h")

    hours_map = {
        "3h": 3,
        "6h": 6,
        "12h": 12,
        "1d": 24,
        "3d": 72,
        "all": None
    }

    hours = hours_map.get(range_param, 6)
    since = datetime.now() - timedelta(hours=hours) if hours else None

    logs_df = get_ping_logs_for_device(stats["device_id"], since=since)

    # Add derived field
    stats["uptime_percent"] = round(stats["uptime_ratio"] * 100, 2)
    stats["timestamps"] = logs_df["timestamp"].dt.strftime("%Y-%m-%d %H:%M:%S").tolist()
    stats["response_times"] = logs_df["response_time"].tolist()
    stats["selected_range"] = range_param

    return render_template("device_detail.html", **stats)




def run_log_cleanup():
    while True:
        delete_old_ping_logs(days=15)
        print("[Cleanup] Deleted old ping logs")
        time.sleep(86400)  # Run once every 24 hours

# Start cleanup in background
cleanup_thread = threading.Thread(target=run_log_cleanup, daemon=True)
cleanup_thread.start()







# ✅ Entry point
if __name__ == "__main__":
    # Avoid running threads twice in debug mode (Flask's auto-reload spawns two processes)
    if os.environ.get("WERKZEUG_RUN_MAIN") == "true":
        start_background_thread()  # ✅ Starts the pinger thread
        threading.Thread(target=run_risk_score_updater, daemon=True).start()  # ✅ Risk score updater
        threading.Thread(target=run_baseline_updater, daemon=True).start()    # ✅ Baseline updater

    app.run(host="127.0.0.1", port=8000, debug=True)
