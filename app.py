#!/usr/bin/env python3
from flask import Flask, render_template, request, redirect, url_for, session, jsonify
import json
import smtplib
import imaplib
import email
import threading
import time
import re
import os
from dotenv import load_dotenv
from email.mime.text import MIMEText
from email.header import decode_header
from datetime import datetime

app = Flask(__name__)
app.secret_key = 'supersecretkey'

TICKETS_FILE = 'tickets.json'
EMPLOYEE_FILE = 'employee.json'

# Load environment variables from .env
load_dotenv(dotenv_path=".env")

IMAP_SERVER = os.getenv("IMAP_SERVER")
EMAIL_ACCOUNT = os.getenv("EMAIL_ACCOUNT")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")
SMTP_SERVER = os.getenv("SMTP_SERVER")
SMTP_PORT = os.getenv("SMTP_PORT")

# Load Tickets
def load_tickets():
    try:
        with open(TICKETS_FILE, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        return []

def save_tickets(tickets):
    with open(TICKETS_FILE, 'w') as f:
        json.dump(tickets, f, indent=4)
        print("INFO - ticket-db has been updated.") # This should only be a log line. Once replies are handled properly it will likely be removed.

# Read the Employees Database
def load_employees():
    try:
        with open(EMPLOYEE_FILE, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        return {}

# Generate new ticket number
def generate_ticket_number():
    tickets = load_tickets()
    return f"TKT-{str(len(tickets) + 1).zfill(4)}" # TKT-2025-count  -- Plan to add year, but not yet.

# Send confirmation email
def send_email(to_email, subject, body):
    msg = MIMEText(body)
    msg['Subject'] = subject # Subject provided by user input.
    msg['From'] = EMAIL_ACCOUNT # Email Account referenced at the top.
    msg['To'] = to_email # Email provided by user input.
    
    try:
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()
            server.login(EMAIL_ACCOUNT, EMAIL_PASSWORD)
            server.sendmail(EMAIL_ACCOUNT, to_email, msg.as_string())
            print("INFO - Confirmation email was successfully sent.")
    except Exception as e:
        print(f"Email sending failed: {e}")

# extract_email_body is attempting to remove whitespace and ignore html in favor of plaintext. I think it is working.
def extract_email_body(msg):
    body = ""
    
    if msg.is_multipart():
        for part in msg.walk():
            content_type = part.get_content_type()
            content_disposition = str(part.get("Content-Disposition"))

            if "attachment" in content_disposition:
                continue  # Skip attachments

            if content_type == "text/plain":  # Prefer plaintext over HTML
                try:
                    body = part.get_payload(decode=True).decode(errors="ignore").strip()
                except Exception as e:
                    print(f"Error decoding email part: {e}")
                    continue
            elif content_type == "text/html" and not body:
                try:
                    body = part.get_payload(decode=True).decode(errors="ignore").strip()
                except Exception as e:
                    print(f"Error decoding HTML part: {e}")
                    continue
    else:
        try:
            body = msg.get_payload(decode=True).decode(errors="ignore").strip()
        except Exception as e:
            print(f"Error decoding single-part email: {e}")

    return body

def fetch_email_replies():
    try:
        mail = imaplib.IMAP4_SSL(IMAP_SERVER)
        mail.login(EMAIL_ACCOUNT, EMAIL_PASSWORD) # Graceful email login.
        mail.select("inbox") # Select the inbox for reading/monitoring.

        _, messages = mail.search(None, 'UNSEEN') # UNSEEN or ALL
        email_ids = messages[0].split()

        tickets = load_tickets()
        
        for email_id in email_ids:
            _, msg_data = mail.fetch(email_id, '(RFC822)')
            for response_part in msg_data:
                if isinstance(response_part, tuple):
                    msg = email.message_from_bytes(response_part[1])
                    subject, encoding = decode_header(msg["Subject"])[0]
                    if isinstance(subject, bytes):
                        subject = subject.decode(encoding or "utf-8")
                    
                    from_email = msg.get("From")
                    ticket_match = re.search(r'RE:TKT-\d+', subject) # Searching for RE: assuming most replies will contain this. It works so far!
                    ticket_id = ticket_match.group(0) if ticket_match else None

                    if not ticket_id:
                        continue  # Skip if no valid ticket ID is found

                    body = extract_email_body(msg)

                    # Find the corresponding ticket
                    for ticket in tickets:
                        if ticket["ticket_number"] == ticket_id:
                            ticket["notes"].append({"message": body})
                            save_tickets(tickets)  # Save changes to the ticket-db
                            print(f"Updated ticket {ticket_id} with reply from {from_email}")
                            break
        #save_tickets(tickets) # Commenting this out to prevent constant writing to the json file.
        mail.logout()
        print("INFO - Email fetch job completed.")
    except Exception as e:
        print(f"Error fetching emails: {e}")

# Background email monitoring
def background_email_monitor():
    while True:
        fetch_email_replies()
        time.sleep(120)  # Check emails every 2 minutes.

threading.Thread(target=background_email_monitor, daemon=True).start()

# Routes
@app.route('/', methods=['GET', 'POST'])
def home():
    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        subject = request.form['subject']
        message = request.form['message']
        request_type = request.form['type']
        ticket_number = generate_ticket_number()
        
        new_ticket = {
            "ticket_number": ticket_number,
            "requestor_name": name,
            "requestor_email": email,
            "subject": subject,
            "message": message,
            "request_type": request_type,
            "status": "Open",
            "submission_date": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            "notes": []
        }
        
        tickets = load_tickets()
        tickets.append(new_ticket)
        save_tickets(tickets)
        
        send_email(email, f"{ticket_number} - {subject}", f"Thank you for your request. Your new Ticket ID is {ticket_number}. You have provided the following details... {message}")
        
        return redirect(url_for('home'))
    
    return render_template('index.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        employees = load_employees()
        
        if username == employees.get("tech_username") and password == employees.get("tech_authcode"):
            session['technician'] = True
            return redirect(url_for('dashboard'))
        
    return render_template('login.html')

@app.route('/dashboard')
def dashboard():
    if not session.get('technician'):
        return redirect(url_for('login'))
    
    tickets = load_tickets()
    return render_template('dashboard.html', tickets=tickets)

@app.route('/ticket/<ticket_number>')
def ticket_detail(ticket_number):
    tickets = load_tickets()
    ticket = next((t for t in tickets if t['ticket_number'] == ticket_number), None)
    if ticket:
        return jsonify(ticket)
    return "Ticket not found", 404

@app.route('/logout')
def logout():
    session.pop('technician', None)
    return redirect(url_for('login'))

if __name__ == '__main__':
    app.run(debug=True)
