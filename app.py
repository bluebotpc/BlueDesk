#!/usr/bin/env python3
from flask import Flask, render_template, request, redirect, url_for, session, jsonify
import json # My preffered method of "database" replacements.
import smtplib # Required protocol for sending emails by code.
import imaplib # Required protocol for receiving/logging into email provider.
import re # Regex support for reading emails and subject lines.
import email # Required to read the content of the emails.
import threading # Background process.
import time # Used for script sleeping.
import os # Required to load DOTENV files.
import fcntl # Unix file locking support.
from dotenv import load_dotenv # Dependant on OS module
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart # Required for new-ticket-email.html
from email.header import decode_header
from datetime import datetime # Timestamps on tickets.
from local_webhook_handler import send_discord_notification # Webhook handler, local to this repo.
from local_webhook_handler import send_TktClosed_discord_notification # I need to find a better way to handle this import but I learned this new thing!

app = Flask(__name__)
app.secret_key = "secretdemokey"

# Load environment variables from .env in the local folder.
load_dotenv(dotenv_path=".env")
TICKETS_FILE = os.getenv("TICKETS_FILE")
EMPLOYEE_FILE = os.getenv("EMPLOYEE_FILE")
IMAP_SERVER = os.getenv("IMAP_SERVER") # Provider IMAP Server Address
EMAIL_ACCOUNT = os.getenv("EMAIL_ACCOUNT") # SEND FROM Email Address/Username
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD") # App Password
SMTP_SERVER = os.getenv("SMTP_SERVER") # Provider SMTP Server Address.
SMTP_PORT = os.getenv("SMTP_PORT") # Provider SMTP Server Port. Default is TCP/587.
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")

# Read/Loads the ticket file into memory. This is the original load_tickets function that works on Windows and Unix.
def load_tickets():
    try:
        with open(TICKETS_FILE, "r") as tkt_file:
            return json.load(tkt_file)
    except FileNotFoundError:
        return [] # represents an empty list.

# This load_tickets function contains the file locking mechanism for Linux.
 
def load_tickets(retries=5, delay=0.2):
   # Load tickets from JSON file with file locking and retry logic.
   for attempt in range(retries):
       try:
           with open(TICKETS_FILE, "r") as file:
               fcntl.flock(file, fcntl.LOCK_SH)  # Shared lock for reading
               tickets = json.load(file)
               fcntl.flock(file, fcntl.LOCK_UN)  # Unlock the file.
               return tickets
       except (json.JSONDecodeError, FileNotFoundError) as e:
           print(f"ERROR - Error loading tickets: {e}")
           return []
       except BlockingIOError:
           print(f"DEBUG - File is locked, retrying... ({attempt+1}/{retries})")
           time.sleep(delay)  # Wait before retrying
   raise Exception("ERROR - Failed to load tickets after multiple attempts.")

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

# Generate a new ticket number.
def generate_ticket_number():
    tickets = load_tickets() # Read/Load the tickets-db into memory.
    current_year = datetime.now().year  # Get the current year dynamically
    ticket_count = str(len(tickets) + 1).zfill(4)  # Zero-padded ticket count
    return f"TKT-{current_year}-{ticket_count}"  # Format: TKT-YYYY-XXXX

# Send a confirmation email.
def send_email(requestor_email, ticket_subject, ticket_message, html=True):
    msg = MIMEMultipart()
    msg["Subject"] = ticket_subject
    msg["From"] = EMAIL_ACCOUNT
    msg["To"] = requestor_email
    
    # Attach body as plain text and/or HTML
    if html:
        msg.attach(MIMEText(ticket_message, "html"))
    else:
        msg.attach(MIMEText(ticket_message, "plain"))
    
    try:
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()
            server.login(EMAIL_ACCOUNT, EMAIL_PASSWORD)
            server.sendmail(EMAIL_ACCOUNT, requestor_email, msg.as_string())
    except Exception as e:
        print(f"ERROR - Email sending failed: {e}")
    print(f"INFO - Confirmation Email sent to {requestor_email}")

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
                    print(f"ERROR - Error decoding email part: {e}")
                    continue
            elif content_type == "text/html" and not body:
                try:
                    body = part.get_payload(decode=True).decode(errors="ignore").strip()
                except Exception as e:
                    print(f"ERROR - Error decoding HTML part: {e}")
                    continue
    else:
        try:
            body = msg.get_payload(decode=True).decode(errors="ignore").strip()
        except Exception as e:
            print(f"ERROR - Error decoding single-part email: {e}")

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
        ticket_impact = request.form["ticket_impact"]
        ticket_urgency = request.form["ticket_urgency"]
        request_type = request.form["request_type"]
        ticket_number = generate_ticket_number()
        
        new_ticket = {
            "ticket_number": ticket_number,
            "requestor_name": requestor_name,
            "requestor_email": requestor_email,
            "ticket_subject": ticket_subject,
            "ticket_message": ticket_message,
            "request_type": request_type,
            "ticket_impact": ticket_impact,
            "ticket_urgency": ticket_urgency,
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
        send_email(requestor_email, f"{ticket_number} - {ticket_subject}", email_body, html=True)

        # Send a Discord webhook notification.
        send_discord_notification(ticket_number, ticket_message)
        
        return redirect(url_for("home"))
    
    return render_template("index.html")

# Route/routine for the technician login process.
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["tech_username_box"] # query from HTML form name.
        password = request.form["tech_password_box"]
        employees = load_employees() # Loads the employee data into memory.

        # Iterate through the list of employees to check for a match.
        # After adding this feature/function the simplified ability to only have one defined technician is broke. This should be resolved before production release.
        for defined_technician in employees:
            if username == defined_technician["tech_username"] and password == defined_technician["tech_authcode"]:
                session["technician"] = username  # Store the technician's username in the session cookie.
                return redirect(url_for("dashboard")) # On successful login, send to Dashboard.
            else:
                return render_template("404.html"), 404 # Failure sends to 404. This could be tweaked.
        
    return render_template("login.html")

# Route/routine for the technician login process.
@app.route("/dashboard")
def dashboard():
    if not session.get("technician"): # If the local machine does not have a session token/cookie containing the 'technician' tag.
        return redirect(url_for("login")) # Redirect them to the login page.
    
    tickets = load_tickets()
    # Filtering out tickets with the Closed Status on the main Dashboard.
    open_tickets = [ticket for ticket in tickets if ticket["ticket_status"].lower() != "closed"]
    return render_template("dashboard.html", tickets=open_tickets)

# Route/routine for viewing a ticket, loads into what I call Ticket Commander.
@app.route("/ticket/<ticket_number>")
def ticket_detail(ticket_number):
    if "technician" not in session:  # Validate the logged-in user cookie...
        return render_template("403.html"), 403  # Return a custom HTTP 403 page.

    tickets = load_tickets()
    ticket = next((t for t in tickets if t["ticket_number"] == ticket_number), None)
    
    if ticket:
        return render_template("ticket-commander.html", ticket=ticket)

    return render_template("404.html"), 404 # Return a custom HTTP 404 page.

# Route/routine for updating a ticket from Ticket Commander. Not called by the main technician dashboard.
@app.route("/ticket/<ticket_number>/update_status/<ticket_status>", methods=["POST"])
def update_ticket_status(ticket_number, ticket_status):
    if not session.get("technician"):  # Ensure only authenticated techs can update tickets.
        return render_template("403.html"), 403 # Otherwise, custom 403 error.
    
    valid_statuses = ["Open", "In-Progress", "Closed"]
    if ticket_status not in valid_statuses:
        return render_template("400.html"), 400 # Return HTTP 400 but this may change.

    tickets = load_tickets()  # Loads tickets into memory.
    for ticket in tickets:
        if ticket["ticket_number"] == ticket_number: 
            ticket["ticket_status"] = ticket_status  
            save_tickets(tickets)  # Save the changes to the tickets.
            send_TktClosed_discord_notification(ticket_number) # Discord notification for closing a ticket.
            return jsonify({"message": f"Ticket {ticket_number} updated to {ticket_status}."}) # Browser prompt on successful status update.
        
    return render_template("404.html"), 404

# Route/routine to close a ticket from the main technician dashboard. Not called from Ticket Commander.
@app.route("/close_ticket/<ticket_number>", methods=["POST"])
def close_ticket(ticket_number):
    if not session.get("technician"):  # Check the cookie for technician tag.
        return render_template("403.html"), 403
    
    tickets = load_tickets()
    for ticket in tickets:
        if ticket["ticket_number"] == ticket_number: # Basic input validation.
            ticket["ticket_status"] = "Closed"
            save_tickets(tickets)
            send_TktClosed_discord_notification(ticket_number) # Discord notification for closing a ticket.
            return jsonify({"message": f"Ticket {ticket_number} has been closed."}) # Browser Popup to confirm ticket closure.
        
    # If the ticket was not found....
    return render_template("404.html"), 404

# Removes the session cookie from the user browser, sending the Technician/user back to the login page.
@app.route("/logout")
def logout():
    session.pop("technician", None)
    return redirect(url_for("login"))

# BELOW THIS LINE IS RESERVED FOR FLASK ERROR ROUTES. PUT ALL CORE APP FUNCTIONS ABOVE THIS LINE!
# Handle 400 errors.
@app.errorhandler(400)
def bad_request(e):
    return render_template("400.html"), 400

# Handle 403 errors.
@app.errorhandler(403)
def forbidden(e):
    return render_template("403.html"), 403

# Handle 404 errors.
@app.errorhandler(404)
def page_not_found(e):
    return render_template("404.html"), 404

if __name__ == "__main__":
    app.run() #debug=True
