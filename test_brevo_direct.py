import smtplib
from email.mime.text import MIMEText

HOST = "smtp-relay.brevo.com"
PORT = 587
USER = "a7380e001@smtp-brevo.com"
PASSWORD = "xsmtpsib-1f13a1b811fb973594e6696fb9101fbb39ad69ca4cfb45ef1822eec4bbda3a39-I7zPvwgzky8DxXnm"

msg = MIMEText("Direct SMTP test from Python")
msg["Subject"] = "Brevo Direct Test"
msg["From"] = "info@vibemall.in"
msg["To"] = "info.vibemall@gmail.com"

try:
    server = smtplib.SMTP(HOST, PORT)
    server.ehlo()
    server.starttls()
    server.ehlo()
    print("Logging in...")
    server.login(USER, PASSWORD)
    print("Login successful!")
    server.sendmail("info@vibemall.in", ["info.vibemall@gmail.com"], msg.as_string())
    print("Email sent successfully!")
    server.quit()
except Exception as e:
    print(f"Error: {e}")
