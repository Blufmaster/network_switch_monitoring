import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import MinMaxScaler
from database import get_connection
import logging
import argparse
from notification import send_whatsapp_alert

# Setup logging
logging.basicConfig(
    format='[%(asctime)s] %(levelname)s: %(message)s',
    level=logging.INFO
)

def get_recent_logs(minutes=5):
    """Fetch ping logs for the last N minutes."""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        time_threshold = datetime.utcnow() - timedelta(minutes=minutes)
        cursor.execute("""
            SELECT device_id, timestamp, response_time, status
            FROM ping_logs
            WHERE timestamp >= %s
            ORDER BY device_id, timestamp
        """, (time_threshold,))
        rows = cursor.fetchall()
        df = pd.DataFrame(rows, columns=["device_id", "timestamp", "response_time", "status"])
        return df
    finally:
        cursor.close()
        conn.close()

def get_device_baselines():
    """Fetch baseline response time and std deviation for each device."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT device_id, avg_response_time, std_dev_response_time
        FROM device_baselines
    """)
    rows = cursor.fetchall()
    conn.close()
    return {row[0]: {"avg": row[1], "std": row[2]} for row in rows}

def update_device_baselines(features_df):
    """Insert or update baseline values for devices."""
    conn = get_connection()
    cursor = conn.cursor()
    for _, row in features_df.iterrows():
        cursor.execute("""
            INSERT INTO device_baselines (device_id, avg_response_time, std_dev_response_time, updated_at)
            VALUES (%s, %s, %s, CURRENT_TIMESTAMP)
            ON CONFLICT (device_id)
            DO UPDATE SET 
                avg_response_time = EXCLUDED.avg_response_time,
                std_dev_response_time = EXCLUDED.std_dev_response_time,
                updated_at = EXCLUDED.updated_at
        """, (int(row['device_id']), float(row['avg_response_time']), float(row['std_dev_response_time'])))
    conn.commit()
    cursor.close()
    conn.close()

def update_risk_scores(df_scores):
    """Write or update risk scores in the database using UPSERT."""
    conn = get_connection()
    cursor = conn.cursor()
    for _, row in df_scores.iterrows():
        cursor.execute("""
            INSERT INTO device_risk_scores (device_id, risk_score, updated_at)
            VALUES (%s, %s, CURRENT_TIMESTAMP)
            ON CONFLICT (device_id)
            DO UPDATE SET risk_score = EXCLUDED.risk_score, updated_at = EXCLUDED.updated_at
        """, (int(row['device_id']), float(row['risk_score'])))
    conn.commit()
    cursor.close()
    conn.close()
    logging.info(f"✅ Updated risk scores for {len(df_scores)} devices.")

def extract_features(df):
    """Extract statistical features from recent ping logs."""
    features = []
    for device_id, group in df.groupby("device_id"):
        response_times = group["response_time"].replace(0.0, np.nan)
        valid_rts = response_times.dropna()

        uptime_count = (group["status"] == "UP").sum()
        total_count = len(group)

        features.append({
            "device_id": device_id,
            "avg_response_time": valid_rts.mean() if not valid_rts.empty else 0,
            "std_dev_response_time": valid_rts.std() if len(valid_rts) > 1 else 0,
            "uptime_ratio": uptime_count / total_count if total_count else 0
        })

    feature_df = pd.DataFrame(features)
    update_device_baselines(feature_df)
    return feature_df

def compute_risk_scores(minutes=5, verbose=False, export_features=False):
    logging.info(f"🧑‍🧐 Computing risk scores using Isolation Forest (last {minutes} mins)...")

    logs_df = get_recent_logs(minutes=minutes)
    if logs_df.empty:
        logging.warning("No recent logs found.")
        return

    features_df = extract_features(logs_df)
    if features_df.empty:
        logging.warning("No valid feature data.")
        return

    if export_features:
        features_df.to_csv("features_snapshot.csv", index=False)
        logging.info("📁 Exported features to features_snapshot.csv")

    # Step 1: Detect devices that are DOWN for 5 consecutive pings
    critical_device_ids = set()
    for device_id, group in logs_df.groupby("device_id"):
        last_logs = group.sort_values("timestamp", ascending=False).head(5)
        if len(last_logs) == 5 and all(last_logs["status"] == "DOWN"):
            critical_device_ids.add(device_id)
            logging.critical(f"🚨 Device {device_id} is DOWN 5x consecutively → Marked as CRITICAL")

    if verbose and critical_device_ids:
        logging.warning(f"🔥 Total devices DOWN 5x in a row: {list(critical_device_ids)}")

    # Step 1.5: Detect very unstable latency (spikes above 15ms)
    conn = get_connection()
    cursor = conn.cursor()
    for device_id, group in logs_df.groupby("device_id"):
        sorted_group = group.sort_values("timestamp", ascending=False)
        recent_rts = sorted_group["response_time"].replace(0.0, np.nan).head(5).tolist()

        if len(recent_rts) == 5 and all(pd.notna(rt) and rt > 15 for rt in recent_rts):


            earlier_rts = sorted_group["response_time"].iloc[5:15].replace(0.0, np.nan).dropna()
            if len(earlier_rts) >= 5:
                baseline_avg = earlier_rts.mean()
                if 3 <= baseline_avg <= 6:
                    cursor.execute("SELECT name, ip FROM devices WHERE id = %s", (device_id,))
                    result = cursor.fetchone()
                    if result:
                        name, ip = result
                        msg = f"⚠️ Very unstable device detected: {name} ({ip}) – High latency spike."
                        logging.critical(msg)
                        send_whatsapp_alert(name, ip, issue="High Latency Spike") # 5 spikes in a row issuee
    cursor.close()
    conn.close()

    # Step 2: Isolation Forest on all devices
    X = features_df[["avg_response_time", "std_dev_response_time", "uptime_ratio"]].fillna(0)

    model = IsolationForest(contamination=0.15,n_jobs=1, random_state=42)
    model.fit(X)
    scores = -model.decision_function(X)  # higher = more anomalous

    # Normalize scores between 0–1
    scaler = MinMaxScaler()
    normalized_scores = scaler.fit_transform(scores.reshape(-1, 1)).flatten()

    # Step 3: Apply CRITICAL tag or model score
    final_scores = []
    for i, row in features_df.iterrows():
        device_id = row["device_id"]
        if device_id in critical_device_ids:
            final_scores.append(1.0)
        else:
            final_scores.append(normalized_scores[i])

    features_df["risk_score"] = final_scores

    # Step 4: Verbose Logging
    if verbose:
        for i, row in features_df.iterrows():
            device_id = row["device_id"]
            label = "CRITICAL (5x DOWN)" if device_id in critical_device_ids else "Normal"
            logging.info(
                f"[Device {device_id}] Risk = {row['risk_score']:.4f} ({label}), "
                f"avg={row['avg_response_time']:.2f}, std={row['std_dev_response_time']:.2f}, uptime={row['uptime_ratio']:.2f}"
            )

    # Step 5: Update DB
    update_risk_scores(features_df[["device_id", "risk_score"]])
    logging.info("✅ Risk score computation completed.")

def refresh_device_baselines(minutes=60):
    logging.info(f"🔄 Updating device baselines using last {minutes} minutes of logs...")
    logs_df = get_recent_logs(minutes=minutes)
    if logs_df.empty:
        logging.warning("No recent logs for baseline update.")
        return
    features_df = extract_features(logs_df)
    update_device_baselines(features_df)
    logging.info("✅ Device baselines updated.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run Isolation Forest-based risk scoring.")
    parser.add_argument("--minutes", type=int, default=5, help="Lookback window in minutes")
    parser.add_argument("--verbose", action="store_true", help="Verbose logging")
    parser.add_argument("--export-features", action="store_true", help="Export features to CSV")

    args = parser.parse_args()
    compute_risk_scores(minutes=args.minutes, verbose=args.verbose, export_features=args.export_features)

# python -m ai_model.risk_model
# python -m ai_model.risk_model --verbose
# python -m ai_model.risk_model --export-features
# python -m ai_model.risk_model --minutes 60
# python -m ai_model.risk_model --minutes 60 --verbose --export-features
# python -m ai_model.risk_model --minutes 60 --verbose
# python -m ai_model.risk_model --minutes 30 --verbose
