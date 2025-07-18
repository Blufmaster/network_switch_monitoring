# five_down_report.py

import pandas as pd
import matplotlib.pyplot as plt
from database import get_connection
import logging
from datetime import datetime, timedelta


logging.basicConfig(level=logging.INFO, format='[%(asctime)s] %(levelname)s: %(message)s')

def fetch_five_down_sequences(days=1):
    """Find all devices that had 5 or more consecutive DOWNs in the last N days and count them."""
    conn = get_connection()
    cursor = conn.cursor()

    time_threshold = datetime.utcnow() - timedelta(days=days)

    logging.info(f"📥 Fetching ping logs for the last {days} days...")

    cursor.execute("""
        SELECT d.id, d.name, d.ip, p.timestamp, p.status
        FROM ping_logs p
        JOIN devices d ON p.device_id = d.id
        WHERE p.timestamp >= %s
        ORDER BY p.device_id, p.timestamp
    """, (time_threshold,))
    
    rows = cursor.fetchall()
    cursor.close()
    conn.close()

    if not rows:
        logging.warning("No ping logs found.")
        return pd.DataFrame()

    df = pd.DataFrame(rows, columns=["device_id", "name", "ip", "timestamp", "status"])

    logging.info("🔍 Scanning for 5x DOWN sequences...")
    report = []

    for device_id, group in df.groupby("device_id"):
        group = group.sort_values("timestamp")
        down_count = 0
        streaks = 0

        for _, row in group.iterrows():
            if row["status"] == "DOWN":
                down_count += 1
                if down_count == 5:
                    streaks += 1
            else:
                down_count = 0

        if streaks > 0:
            report.append({
                "device_id": device_id,
                "name": group["name"].iloc[0],
                "ip": group["ip"].iloc[0],
                "5x_down_sequences": streaks
            })

    report_df = pd.DataFrame(report)
    return report_df


def save_report_and_plot(df):
    if df.empty:
        logging.info(" No 5x DOWN sequences found.")
        return

    # Save to CSV
    csv_path = "reportrequested.csv"
    df.to_csv(csv_path, index=False)
    logging.info(f"📁 Report saved to {csv_path}")

    # Plotting
    plt.figure(figsize=(12, 6))
    plt.barh(df["name"], df["5x_down_sequences"], color='crimson')
    plt.xlabel("Number of 5x DOWN Sequences")
    plt.ylabel("Device Name")
    plt.title("Devices with 5 Consecutive DOWNs")
    plt.tight_layout()
    plt.grid(axis='x', linestyle='--', alpha=0.7)

    plot_path = "five_down_summary.png"
    plt.savefig(plot_path)
    logging.info(f" Plot saved to {plot_path}")
    plt.show()


def plot_device_downtime(ip, days=7):
    """Plot UP/DOWN status of a specific device over the past N days."""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT d.name, d.id FROM devices d WHERE d.ip = %s
    """, (ip,))
    result = cursor.fetchone()
    if not result:
        logging.error(f"❌ Device with IP {ip} not found.")
        return

    device_name, device_id = result
    time_threshold = datetime.utcnow() - timedelta(days=days)

    cursor.execute("""
        SELECT timestamp, status FROM ping_logs
        WHERE device_id = %s AND timestamp >= %s
        ORDER BY timestamp ASC
    """, (device_id, time_threshold))
    rows = cursor.fetchall()
    cursor.close()
    conn.close()

    if not rows:
        logging.warning(f"No ping logs found for device {ip} in the last {days} days.")
        return

    df = pd.DataFrame(rows, columns=["timestamp", "status"])
    df["status_numeric"] = df["status"].apply(lambda s: 1 if s == "UP" else 0)

    # Plot
    plt.figure(figsize=(14, 5))
    plt.plot(df["timestamp"], df["status_numeric"], drawstyle="steps-post", color='blue', label='Status (UP=1, DOWN=0)')
    plt.fill_between(df["timestamp"], 0, df["status_numeric"], step="post", alpha=0.2, color='red', where=(df["status_numeric"] == 0))

    plt.ylim(-0.1, 1.1)
    plt.title(f"Device Status Over Last {days} Days\n{device_name} ({ip})")
    plt.xlabel("Time")
    plt.ylabel("Status")
    plt.yticks([0, 1], ["DOWN", "UP"])
    plt.grid(True, linestyle='--', alpha=0.6)
    plt.tight_layout()

    filename = f"downtime_plot_{ip.replace('.', '_')}.png"
    plt.savefig(filename)
    logging.info(f"📊 Downtime graph saved as {filename}")
    plt.show()

if __name__ == "__main__":
    summary_df = fetch_five_down_sequences()
    save_report_and_plot(summary_df)
    plot_device_downtime("8.8.8.8", days=1)

