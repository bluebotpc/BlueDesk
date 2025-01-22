#!/usr/bin/env python3
from flask import Flask, render_template, request, redirect, url_for, session, jsonify
import json # My preffered method of "database" replacements.
import smtplib # Outgoing Email
import imaplib # Incoming Email
import email # Reading Replies
import threading # Background processes
import time
import re # Regex Support for Email Replies
import os # Dotenv requirement
from dotenv import load_dotenv
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart # Required for new-ticket-email.html
from email.header import decode_header
from datetime import datetime

app = Flask(__name__)
app.secret_key = "secretdemokey"
# I attempted to leverage the dotenv file but had trouble.

# Load environment variables from .env in the local folder.
load_dotenv(dotenv_path=".env")
TICKETS_FILE = os.getenv("TICKETS_FILE")
EMPLOYEE_FILE = os.getenv("EMPLOYEE_FILE")
IMAP_SERVER = os.getenv("IMAP_SERVER") # Provider IMAP Server Address
EMAIL_ACCOUNT = os.getenv("EMAIL_ACCOUNT") # SEND FROM Email Address/Username
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD") # App Password - No OAuth or OAuth2 support yet.
SMTP_SERVER = os.getenv("SMTP_SERVER") # Provider SMTP Server Address.
SMTP_PORT = os.getenv("SMTP_PORT") # Provider SMTP Server Port. Default is TCP/587.

# Read/Loads the ticket file into memory.
def load_tickets():
    try:
        with open(TICKETS_FILE, "r") as f:
            return json.load(f)
    except FileNotFoundError:
        return [] # represents an empty list.

# Writes to the ticket file database.
def save_tickets(tickets):
    with open(TICKETS_FILE, "w") as f:
        json.dump(tickets, f, indent=4)

# Read/Loads the employee file.
def load_employees():
    try:
        with open(EMPLOYEE_FILE, "r") as f:
            return json.load(f)
    except FileNotFoundError:
        return {} # represents an empty dictionary.

# Generate a new ticket number
def generate_ticket_number():
    tickets = load_tickets() # Read/Load the tickets-db into memory.
    current_year = datetime.now().year  # Get the current year dynamically
    ticket_count = str(len(tickets) + 1).zfill(4)  # Zero-padded ticket count
    return f"TKT-{current_year}-{ticket_count}"  # Format: TKT-YYYY-XXXX

# Send a confirmation email
def send_email(to_email, subject, body, html=True):
    msg = MIMEMultipart()
    msg["Subject"] = subject
    msg["From"] = EMAIL_ACCOUNT
    msg["To"] = to_email
    
    # Attach body as plain text and/or HTML
    if html:
        msg.attach(MIMEText(body, "html"))
    else:
        msg.attach(MIMEText(body, "plain"))
    
    try:
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()
            server.login(EMAIL_ACCOUNT, EMAIL_PASSWORD)
            server.sendmail(EMAIL_ACCOUNT, to_email, msg.as_string())
    except Exception as e:
        print(f"ERROR - Email sending failed: {e}")

# extract_email_body is attempting to scrape the content of the "valid" TKT email replies. It skips attachments. I do not currently need this feature. 
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

# fetch_email_replies logically occurs before extract_email_body which is above this comment in the code.
def fetch_email_replies():
    try:
        mail = imaplib.IMAP4_SSL(IMAP_SERVER)
        mail.login(EMAIL_ACCOUNT, EMAIL_PASSWORD) # Graceful Email system login.
        mail.select("inbox") # Select the inbox for reading/monitoring.

        messages = mail.search(None, "UNSEEN") # UNSEEN or ALL -- Only reading UNSEEN currently.
        email_ids = messages[0].split()

        tickets = load_tickets() # Read the tickets file into memory.
        
        for email_id in email_ids:
            msg_data = mail.fetch(email_id, "(RFC822)")
            for response_part in msg_data:
                if isinstance(response_part, tuple):
                    msg = email.message_from_bytes(response_part[1])
                    subject, encoding = decode_header(msg["Subject"])[0]
                    if isinstance(subject, bytes):
                        subject = subject.decode(encoding or "utf-8")
                    
                    from_email = msg.get("From")
                    match_ticket_reply = re.search(r"(?i)\bTKT-\d{4}-\d+\b", subject)  # Match "TKT-YYYY-XXXX" with no case sensitivity and should accept RE: re: and whitespace.
                    ticket_id = match_ticket_reply.group(0) if match_ticket_reply else None # Cleans up the extracted ticket number so it doesn"t include "RE:".
                    #print(f"DEBUG - Extracted ticket ID: {ticket_id} from subject: {subject}")

                    if not ticket_id:
                        continue  # Skip and do nothing if no valid ticket-id is found.

                    body = extract_email_body(msg)

                    # Find the corresponding ticket
                    for ticket in tickets:
                        if ticket["ticket_number"] == ticket_id:
                            ticket["notes"].append({"message": body})
                            save_tickets(tickets)  # Save changes to the ticket-db
                            print(f"INFO - Updated ticket {ticket_id} with reply from {from_email}")
                            break
                        
        #save_tickets(tickets)
        mail.logout() # Graceful logout.
        #print("INFO - Email fetch job completed.")
    except Exception as e:
        print(f"Error fetching emails: {e}")

# Background email monitoring
def background_email_monitor():
    while True:
        fetch_email_replies()
        time.sleep(300)  # Wait for  emails every 5 minutes.

threading.Thread(target=background_email_monitor, daemon=True).start()

# BELOW THIS LINE IS RESERVED FOR FLASK APP ROUTES
# This is the "default" route for the home/index/landing page. This is where users submit a ticket.
@app.route("/", methods=["GET", "POST"])
def home():
    if request.method == "POST":
        name = request.form["name"]
        email = request.form["email"]
        subject = request.form["subject"]
        message = request.form["message"]
        request_type = request.form["type"]
        ticket_number = generate_ticket_number()
        
        new_ticket = {
            "ticket_number": ticket_number,
            "requestor_name": name,
            "requestor_email": email,
            "subject": subject,
            "message": message,
            "request_type": request_type,
            "status": "Open",
            "submission_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "notes": []
        }
        
        tickets = load_tickets()
        tickets.append(new_ticket)
        save_tickets(tickets)
        
        # Render the HTML email template
        email_body = render_template("/new-ticket-email.html", ticket=new_ticket)

        # Send the email with HTML format
        send_email(email, f"{ticket_number} - {subject}", email_body, html=True)
        
        return redirect(url_for("home"))
    
    return render_template("index.html")

# 
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        employees = load_employees()  # Load list of technicians

        # Iterate through the list of employees to check for a match
        for defined_technician in employees:
            if username == defined_technician["tech_username"] and password == defined_technician["tech_authcode"]:
                session["technician"] = username  # Store the technician's username in the session
                return redirect(url_for("dashboard"))
        
    return render_template("login.html")

@app.route("/dashboard")
def dashboard():
    if not session.get("technician"): # If the local machine does not have a session token/cookie containing the 'technician' tag.
        return redirect(url_for("login")) # Redirect them to the login page.
    
    tickets = load_tickets()
    # Filtering out tickets with the Closed Status.
    open_tickets = [ticket for ticket in tickets if ticket["status"].lower() != "closed"]
    return render_template("dashboard.html", tickets=open_tickets)

# Opens a ticket in raw json. This should be tweaked eventually.
@app.route("/ticket/<ticket_number>")
def ticket_detail(ticket_number):

    if "technician" not in session: # Validate logged in user.
        return "Forbidden: Unauthorized Access", 403 # Return a 403 page.
    
    tickets = load_tickets() 
    ticket = next((t for t in tickets if t["ticket_number"] == ticket_number), None)
    if ticket:
        return jsonify(ticket)
    
    return "Ticket Number in the URL was not found.", 404

# Routine to close a ticket. This invloves a write operation to the tickets.json file.
@app.route("/close_ticket/<ticket_number>", methods=["POST"])
def close_ticket(ticket_number):
    if not session.get("technician"):  # Ensure only logged-in techs can close tickets.
        return jsonify({"message": "Unauthorized"}), 403
    
    tickets = load_tickets() # Loads tickets.json into memory.
    for ticket in tickets:
        if ticket["ticket_number"] == ticket_number: # Basic input validation.
            ticket["status"] = "Closed"
            save_tickets(tickets)
            return jsonify({"message": f"Ticket {ticket_number} has been closed."})
        
    # If the ticket was not found....
    return jsonify({"message": "Ticket not found"}), 404

# Removes the session cookie from the user browser, sending the Technician/user back to the login page.
@app.route("/logout")
def logout():
    session.pop("technician", None)
    return redirect(url_for("login")) # Send a logged out user back to the login page. This can be customized.

if __name__ == "__main__":
    app.run(debug=True) #debug=True
