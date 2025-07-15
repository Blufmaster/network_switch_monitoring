import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns

LOG_FILE = "risk_score_log.csv"  # Rename your uploaded file to this or change path here
DEVICE_ID = 9  # Device to analyze

def load_data(log_file):
    df = pd.read_csv(log_file)
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    return df

def filter_device(df, device_id):
    return df[df['device_id'] == device_id].sort_values(by='timestamp')

def plot_risk_trend(df, device_id):
    plt.figure(figsize=(12, 5))
    sns.lineplot(data=df, x='timestamp', y='risk_score', marker='o')
    plt.title(f'Risk Score Over Time – Device {device_id}')
    plt.xlabel('Timestamp')
    plt.ylabel('Risk Score')
    plt.xticks(rotation=45)
    plt.tight_layout()
    plt.grid(True)
    plt.savefig(f'device_{device_id}_risk_trend.png')
    plt.show()

def compute_stats(df, device_id):
    std = df['risk_score'].std()
    mean = df['risk_score'].mean()
    print(f"\n📊 Stability Report for Device {device_id}")
    print(f"➤ Total Samples      : {len(df)}")
    print(f"➤ Mean Risk Score    : {mean:.4f}")
    print(f"➤ Std. Deviation     : {std:.4f}")
    if std < 0.05:
        print("✅ Status            : Very Stable")
    elif std < 0.15:
        print("⚠️  Status           : Moderately Stable")
    else:
        print("❌ Status            : Unstable")

def main():
    df = load_data(LOG_FILE)
    df_device = filter_device(df, DEVICE_ID)
    
    if df_device.empty:
        print(f"No data found for device {DEVICE_ID}")
        return
    
    compute_stats(df_device, DEVICE_ID)
    plot_risk_trend(df_device, DEVICE_ID)

if __name__ == "__main__":
    main()
