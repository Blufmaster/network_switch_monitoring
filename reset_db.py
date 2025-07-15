from database import get_connection

def clear_all_tables():
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("DELETE FROM ping_logs;")
    cur.execute("DELETE FROM device_risk_scores;")
    cur.execute("DELETE FROM device_baselines;")
    cur.execute("DELETE FROM devices;")

    conn.commit()
    cur.close()
    conn.close()
    print("✅ All tables cleared successfully.")

if __name__ == "__main__":
    clear_all_tables()
