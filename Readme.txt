#  AI-Powered Network Switch Monitoring System

An intelligent real-time switch and network device monitoring system using Python (Flask), PostgreSQL, and AI models for risk analysis, anomaly detection, and predictive alerts.

---

## Features

###  Core Monitoring
- Pings 550+ devices in batches every **60 seconds**.
- Stores full ping history in PostgreSQL.
- Real-time dashboard with auto-refresh.
- Device detail pages with response-time graphs.
- Time-range filters: `3h`, `6h`, `12h`, `1d`, `3d`, `all`.

###  AI Capabilities
- **Risk scoring with Isolation Forest** (per device).
- **Baseline-based spike detection** (avg & std dev).
- **Smart alert system** for CRITICAL spikes (email/WhatsApp).
- **Downtime streak tracking** (5x DOWNs shown on detail page).
- **Risk refresh every 5 minutes** using last 60 minutes of data.
- **Baseline refresh every 3 hours** using last 3 hours of logs.

###  AI DataFrames
You can inspect, modify, or toggle the following:

| Purpose                | Variable / Table             | Where to Change / View              |
|------------------------|------------------------------|--------------------------------------|
| Risk Scores            | `device_risk_scores`         | Table in PostgreSQL (`risk_model.py`) |
| Device Baselines       | `device_baselines`           | Table in PostgreSQL (`refresh_device_baselines`) |
| Spike Detection        | `avg_baseline`, `std_baseline` | Dashboard view (passed from backend) |
| Raw Logs               | `ping_logs`                  | `/logs/<device_id>` route            |
| Model Parameters       | `contamination` (IForest)    | `risk_model.py`                      |
| Lookback Minutes       | `compute_risk_scores(minutes=10)` | `app.py > run_risk_score_updater()` |
| Baseline Window        | `refresh_device_baselines(minutes=180)` | `app.py > run_baseline_updater()`   |

---

## UI Features

-  **Dark mode-friendly design** (custom CSS)
- 🔍 IP & Name search on dashboard
- 📈 Charts via Chart.js
-  Device logs and stats with buttons for:
  - `View Stats`
  - `View Logs`
- 🛠️ `/manage` interface for:
  - Adding devices
  - Searching devices
  - Deleting devices
  - Bulk delete

---

##  File Structure

├── app.py # Main Flask app
├── database.py # DB schema + helper functions
├── ping_worker.py # Pinging + batch scheduling
├── ai_model/
│ └── risk_model.py # Isolation Forest + Baseline Logic
├── templates/ # HTML Jinja templates
│ ├── dashboard.html
│ ├── device_detail.html
│ ├── logs.html
│ └── manage.html
├── static/ # Optional: for future CSS/JS
└── requirements.txt

## ⚙️ Configuration

You can customize the following:

| Setting                     | Location               | Example                                  |
|-----------------------------|------------------------|------------------------------------------|
| **Ping interval**           | `ping_worker.py`       | `sleep(60)` per batch                    |
| **Batch size**              | `ping_worker.py`       | `BATCH_SIZE = 50`                        |
| **Risk refresh frequency**  | `app.py`               | `time.sleep(300)`                        |
| **Baseline refresh window** | `app.py`               | `refresh_device_baselines(180)`         |
| **Down Alert Streak**       | `ping_worker.py`       | After 3 fails                            |
| **Model tuning**            | `risk_model.py`        | Adjust IsolationForest parameters        |
| **Email settings**          | `email_utils.py` (if exists) | Set SMTP, from, to                     |

---

## 🧪 Setup Instructions

```bash
# Clone repo
git clone https://github.com/your-username/switch-monitoring-ai.git
cd switch-monitoring-ai

# Set up virtual env
python3 -m venv venv
source venv/bin/activate  # or venv\Scripts\activate on Windows

# Install dependencies
pip install -r requirements.txt

# Set up PostgreSQL (manual step, or docker)
# Create tables automatically:
python -c "from database import init_db; init_db()"

# Run the app
python app.py


Admin Notes
This app is intended to be used locally or on a private network.

Only one role: admin (no login screen required).

Alerting uses email or WhatsApp (optional feature).

No internet is required after setup.

Credits
Created by The Intern for Tata Steel as part of an AI-integrated real-time infrastructure monitoring solution.
