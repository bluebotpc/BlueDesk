#!/usr/bin/env python3
from flask import Flask, render_template, request, redirect, url_for, session, jsonify
import json # My preffered method of "database" replacements.
import smtplib # Outgoing Email
import imaplib # Incoming Email
import email # Reading and Crafting the emails.
import threading # Background process.
import time # Only used to sleep the background thread.
import re # Regex Support for Email Replies
import os # Dotenv requirement
from dotenv import load_dotenv
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart # Required for new-ticket-email.html
from email.header import decode_header
from datetime import datetime

app = Flask(__name__)
app.secret_key = "secretdemokey"
# I attempted to leverage the dotenv file but had trouble. I experienced poor performance on an OCI E2.1.Micro using the secrets module.

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
        with open(TICKETS_FILE, "r") as tkt_file:
            return json.load(tkt_file)
    except FileNotFoundError:
        return [] # represents an empty list.

# Writes to the ticket file database.
def save_tickets(tickets):
    with open(TICKETS_FILE, "w") as tkt_file_write_op:
        json.dump(tickets, tkt_file_write_op, indent=4)

# Read/Loads the employee file into memory.
def load_employees():
    try:
        with open(EMPLOYEE_FILE, "r") as tech_file_read_op:
            return json.load(tech_file_read_op)
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
    print(f"INFO - Confirmation Email sent to {to_email}")

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
        mail.login(EMAIL_ACCOUNT, EMAIL_PASSWORD)  
        mail.select("inbox")  

        mail_server_response_status, messages = mail.search(None, "UNSEEN")  
        if mail_server_response_status != "OK":
            print("DEBUG - Reading Inbox via IMAP failed for an unknown reason.")
            return

        email_ids = messages[0].split()
        tickets = load_tickets()  

        for email_id in email_ids:
            email_id = email_id.decode()  # Ensure it's a string
            mail_server_response_status, msg_data = mail.fetch(email_id, "(RFC822)")
            if mail_server_response_status != "OK" or not msg_data:
                print(f"ERROR - Unable to fetch email {email_id}")
                continue  

            for response_part in msg_data:
                if isinstance(response_part, tuple):
                    msg = email.message_from_bytes(response_part[1])
                    subject, encoding = decode_header(msg["Subject"])[0]
                    if isinstance(subject, bytes):
                        subject = subject.decode(encoding or "utf-8")

                    from_email = msg.get("From")
                    match_ticket_reply = re.search(r"(?i)\bTKT-\d{4}-\d+\b", subject)
                    ticket_id = match_ticket_reply.group(0) if match_ticket_reply else None  
                    print(f"DEBUG - Extracted ticket ID: {ticket_id} from subject: {subject}")

                    if not ticket_id:
                        continue  

                    body = extract_email_body(msg)

                    for ticket in tickets:
                        if ticket["ticket_number"] == ticket_id:
                            ticket["ticket_notes"].append({"ticket_message": body})
                            save_tickets(tickets)  
                            print(f"DEBUG - Updated ticket {ticket_id} with reply from {from_email}")
                            break
                        
        mail.logout()  
        print("INFO - Email fetch job completed successfully.")
    except Exception as e:
        print(f"ERROR - Error fetching emails: {e}")

# Background email monitoring
def background_email_monitor():
    while True:
        fetch_email_replies()
        time.sleep(300)  # Wait for emails every 5 minutes.

threading.Thread(target=background_email_monitor, daemon=True).start()

# BELOW THIS LINE IS RESERVED FOR FLASK APP ROUTES
# This is the "default" route for the home/index/landing page. This is where users submit a ticket.
@app.route("/", methods=["GET", "POST"])
def home():
    if request.method == "POST":
        requestor_name = request.form["requestor_name"]
        requestor_email = request.form["requestor_email"]
        ticket_subject = request.form["ticket_subject"]
        ticket_message = request.form["ticket_message"]
        request_type = request.form["request_type"]
        ticket_number = generate_ticket_number()
        
        new_ticket = {
            "ticket_number": ticket_number,
            "requestor_name": requestor_name,
            "requestor_email": requestor_email,
            "ticket_subject": ticket_subject,
            "ticket_message": ticket_message,
            "request_type": request_type,
            "ticket_status": "Open",
            "submission_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "ticket_notes": []
        }
        
        tickets = load_tickets()
        tickets.append(new_ticket)
        print(f"INFO - a new {ticket_number} has been created")
        save_tickets(tickets)
        
        # Render the HTML email template
        email_body = render_template("/new-ticket-email.html", ticket=new_ticket)

        # Send the email with HTML format
        send_email(email, f"{ticket_number} - {ticket_subject}", email_body, html=True)
        
        return redirect(url_for("home"))
    
    return render_template("index.html")

# Route/routine for the technician login process.
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        employees = load_employees()  # Load list of technicians

        # Iterate through the list of employees to check for a match.
        # After adding this feature/function the simplified ability to only have one defined technician is broke. This should be resolved before production release.
        for defined_technician in employees:
            if username == defined_technician["tech_username"] and password == defined_technician["tech_authcode"]:
                session["technician"] = username  # Store the technician's username in the session cookie.
                return redirect(url_for("dashboard"))
            else:
                return jsonify({"message": f"Technician Authentication Failed."}), 404
        
    return render_template("login.html")

# Route/routine for the technician login process
@app.route("/dashboard")
def dashboard():
    if not session.get("technician"): # If the local machine does not have a session token/cookie containing the 'technician' tag.
        return redirect(url_for("login")) # Redirect them to the login page.
    
    tickets = load_tickets()
    # Filtering out tickets with the Closed Status.
    open_tickets = [ticket for ticket in tickets if ticket["ticket_status"].lower() != "closed"]
    return render_template("dashboard.html", tickets=open_tickets)

# Route/routine for viewing a ticket in raw json. This will work differently before production release v1.0.
@app.route("/ticket/<ticket_number>")
def ticket_detail(ticket_number):
    if "technician" not in session:  # Validate logged-in user
        return "Forbidden: Unauthorized Access", 403  # Return a 403 page

    tickets = load_tickets()
    ticket = next((t for t in tickets if t["ticket_number"] == ticket_number), None)
    
    if ticket:
        return render_template("ticket-commander.html", ticket=ticket)

    return "Ticket Number in the URL was not found.", 404

## Route/routine for updating a ticket. This is new and might get removed.
@app.route("/ticket/<ticket_number>/update_status/<status>", methods=["POST"])
def update_ticket_status(ticket_number, ticket_status):
    if not session.get("technician"):  # Ensure only logged-in techs can update tickets.
        return jsonify({"message": "Unauthorized"}), 403
    
    valid_statuses = ["Open", "In-Progress", "Closed"]
    if ticket_status not in valid_statuses:
        return jsonify({"message": "Invalid status provided"}), 400

    tickets = load_tickets()  # Load tickets.json
    for ticket in tickets:
        if ticket["ticket_number"] == ticket_number: 
            ticket["ticket_status"] = ticket_status  
            save_tickets(tickets)  # Save changes
            return jsonify({"message": f"Ticket {ticket_number} updated to {ticket_status}."})
        
    return jsonify({"message": "Ticket not found"}), 404

# Route/routine to close a ticket. This invloves a write operation to the tickets.json file.
@app.route("/close_ticket/<ticket_number>", methods=["POST"])
def close_ticket(ticket_number):
    if not session.get("technician"):  # Ensure only logged-in techs can close tickets.
        return jsonify({"message": "Unauthorized"}), 403
    
    tickets = load_tickets() # Loads tickets.json into memory.
    for ticket in tickets:
        if ticket["ticket_number"] == ticket_number: # Basic input validation.
            ticket["ticket_status"] = "Closed"
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
    app.run() #debug=True
