import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime, timedelta
import pandas as pd

DB_CONFIG = {
    "dbname": "network_monitor",
    "user": "monitor_user",
    "password": "password",
    "host": "localhost",
    "port": 5432
}

def get_connection():
    return psycopg2.connect(**DB_CONFIG)

def init_db():
    conn = get_connection()
    cursor = conn.cursor()

    # Table for device information
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS devices (
            id SERIAL PRIMARY KEY,
            name TEXT NOT NULL,
            ip TEXT NOT NULL,
            type TEXT,
            email TEXT
        )
    """)

    # Table for ping logs
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS ping_logs (
            id SERIAL PRIMARY KEY,
            device_id INTEGER REFERENCES devices(id),
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            response_time REAL,
            status TEXT CHECK(status IN ('UP', 'DOWN')) NOT NULL
        )
    """)

    # Table for risk scores
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS device_risk_scores (
            device_id INTEGER PRIMARY KEY REFERENCES devices(id) ON DELETE CASCADE,
            risk_score REAL,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Table for device baselines 
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS device_baselines (
            device_id INT PRIMARY KEY,
            avg_response_time FLOAT,
            std_dev_response_time FLOAT,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Indexes
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_ping_logs_device_id 
        ON ping_logs(device_id)
    """)
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_ping_logs_device_id_timestamp 
        ON ping_logs(device_id, timestamp DESC)
    """)

    # Commit and close
    conn.commit()
    cursor.close()
    conn.close()




def get_recent_logs(minutes=5):
    conn = psycopg2.connect(**DB_CONFIG)
    cursor = conn.cursor()
    try:
        time_threshold = datetime.utcnow() - timedelta(minutes=minutes)
        cursor.execute("""
            SELECT device_id, timestamp, response_time, status
            FROM ping_logs
            WHERE timestamp >= %s
            ORDER BY device_id, timestamp""",
            (time_threshold,))
    
        rows = cursor.fetchall()
        df = pd.DataFrame(rows, columns=["device_id", "timestamp", "response_time", "status"])
        return df
    finally:
        cursor.close()
        conn.close()
    
    


def get_devices():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM devices")
    devices = cursor.fetchall()
    conn.close()
    return devices

def add_device(name, ip, type, email):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO devices (name, ip, type, email) VALUES (%s, %s, %s, %s)",
        (name, ip, type, email)
    )
    conn.commit()
    conn.close()

def log_ping_result(device_id, response_time, status):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO ping_logs (device_id, response_time, status) VALUES (%s, %s, %s)",
        (device_id, response_time, status)
    )
    conn.commit()
    conn.close()

def delete_device(device_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM devices WHERE id = %s", (device_id,))
    conn.commit()
    conn.close()

def delete_all_devices():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM devices")
    conn.commit()
    conn.close()

def get_device_id_by_ip(ip):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM devices WHERE ip = %s", (ip,))
    result = cursor.fetchone()
    conn.close()
    return result[0] if result else None

def get_all_risk_scores():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT device_id, risk_score FROM device_risk_scores")
    results = cursor.fetchall()
    conn.close()
    return {row[0]: row[1] for row in results}

def get_all_device_baselines():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT device_id, avg_response_time, std_dev_response_time
        FROM device_baselines
    """)
    rows = cursor.fetchall()
    cursor.close()
    conn.close()
    return {row[0]: {"avg": row[1], "std": row[2]} for row in rows}

def get_device_ip_map():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, ip FROM devices")
    result = dict(cursor.fetchall())
    cursor.close()
    conn.close()
    return result

def get_device_info_by_id(device_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT name, ip FROM devices WHERE id = %s", (device_id,))
    row = cursor.fetchone()
    cursor.close()
    conn.close()
    if row:
        return row  # (name, ip)
    return ("Unknown", "Unknown")


  # or wherever get_connection is defined

def get_device_by_ip(ip):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, name FROM devices WHERE ip = %s", (ip,))
    result = cursor.fetchone()
    cursor.close()
    conn.close()
    return result  # (device_id, name)

def get_ping_logs_for_device(device_id, since=None, limit=None):
    conn = get_connection()
    cursor = conn.cursor()

    query = """
        SELECT timestamp, response_time, status
        FROM ping_logs
        WHERE device_id = %s
    """
    params = [device_id]

    if since is not None:
        query += " AND timestamp >= %s"
        params.append(since)

    query += " ORDER BY timestamp ASC"

    if limit is not None:
        query += " LIMIT %s"
        params.append(limit)

    cursor.execute(query, tuple(params))
    rows = cursor.fetchall()
    cursor.close()
    conn.close()

    return pd.DataFrame(rows, columns=["timestamp", "response_time", "status"])




def get_device_stats(ip):
    device = get_device_by_ip(ip)
    if not device:
        return None
    device_id, name = device
    df = get_ping_logs_for_device(device_id)

    if df.empty:
        return {"name": name, "ip": ip, "uptime_ratio": 0, "avg_response": 0, "std_response": 0, "down_streaks": 0}

    total = len(df)
    up_count = (df["status"] == "UP").sum()
    down_count = (df["status"] == "DOWN").sum()
    uptime_ratio = round(up_count / total, 3) if total else 0

    avg_response = round(df["response_time"].replace(0.0, pd.NA).dropna().mean(), 2)
    std_response = round(df["response_time"].replace(0.0, pd.NA).dropna().std(), 2)

    # Detect 5x DOWN streaks
    down_streaks = 0
    streak = 0
    for status in df["status"]:
        if status == "DOWN":
            streak += 1
            if streak == 5:
                down_streaks += 1
        else:
            streak = 0

    return {
        "device_id": device_id,
        "name": name,
        "ip": ip,
        "uptime_ratio": uptime_ratio,
        "up_count": up_count,
        "down_count": down_count,
        "avg_response": avg_response,
        "std_response": std_response,
        "down_streaks": down_streaks
    }



def delete_old_ping_logs(days=15):
    cutoff_date = datetime.now() - timedelta(days=days)
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                DELETE FROM ping_logs
                WHERE timestamp < %s
            """, (cutoff_date,))
        conn.commit()



def get_down_streaks_in_timeframe(hours=None):
    """
    Returns devices that have at least one 5× DOWN streak in the given timeframe.
    If hours is None, it checks all available logs.
    """
    if hours is not None:
        time_threshold = datetime.utcnow() - timedelta(hours=hours)
    else:
        time_threshold = None

    conn = get_connection()
    cursor = conn.cursor()

    # Get all device IDs and names
    cursor.execute("SELECT id, name, ip FROM devices")
    devices = cursor.fetchall()

    results = []

    for device_id, name, ip in devices:
        df = get_ping_logs_for_device(device_id, since=time_threshold)

        if df.empty or "status" not in df.columns:
            continue

        streak = 0
        count = 0
        last_streak_time = None
        i = 0

        while i < len(df):
            if df.iloc[i]["status"] == "DOWN":
                streak += 1
                if streak == 5:
                    count += 1
                    last_streak_time = df.iloc[i]["timestamp"]
                    # Skip all consecutive DOWNs beyond the 5th to avoid counting overlap
                    while i < len(df) and df.iloc[i]["status"] == "DOWN":
                        i += 1
                    streak = 0
                    continue
            else:
                streak = 0
            i += 1

        if count > 0:
            results.append({
                "device_name": name,
                "ip": ip,
                "occurrences": count,
                "last_occurred": last_streak_time
            })

    cursor.close()
    conn.close()
    return results




#run this file directly to initialize the database
"""if __name__ == "__main__":
    init_db()
    print("✅ Database initialized.")"""



