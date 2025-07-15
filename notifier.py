import smtplib
from email.mime.text import MIMEText

def send_alert_email(device_name, ip, recipient_email, issue="Unknown"):
    subject = f"[ALERT] Device Down: {device_name}"
    body = f"Device: {device_name}\nIP Address: {ip}\nIssue: {issue} \n\n - The Intern"

    msg = MIMEText(body)
    msg['Subject'] = subject
    msg['From'] = "blufmaster2241@gmail.com"
    msg['To'] = recipient_email 
 

    try:
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login("blufmaster2241@gmail.com", "saem aply boqu ggbi")  # Replace with your actual password
        server.sendmail(msg['From'], [msg['To']], msg.as_string())
        server.quit()
        print(f"[EMAIL] Alert email sent to {recipient_email} for device {device_name}")
    except Exception as e:
        print(f"[ERROR] Failed to send email: {e}")