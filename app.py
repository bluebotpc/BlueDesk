from flask import Flask, render_template, request, redirect, url_for, session, jsonify
import json
import smtplib
from email.mime.text import MIMEText
from datetime import datetime

app = Flask(__name__)
app.secret_key = 'supersecretkey'

TICKETS_FILE = 'tickets.json'
EMPLOYEE_FILE = 'employee.json'

# Load tickets
def load_tickets():
    try:
        with open(TICKETS_FILE, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        return []

def save_tickets(tickets):
    with open(TICKETS_FILE, 'w') as f:
        json.dump(tickets, f, indent=4)

# Load employees
def load_employees():
    try:
        with open(EMPLOYEE_FILE, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        return {}

# Generate new ticket number
def generate_ticket_number():
    tickets = load_tickets()
    return f"TKT-{str(len(tickets) + 1).zfill(4)}"

# Send confirmation email
def send_email(to_email, subject, body):
    FROM_EMAIL = "GMAILACCOUNT"
    PASSWORD = "PASSWORD"
    
    msg = MIMEText(body)
    msg['Subject'] = subject
    msg['From'] = FROM_EMAIL
    msg['To'] = to_email
    
    try:
        with smtplib.SMTP('smtp.gmail.com', 587) as server:
            server.starttls()
            server.login(FROM_EMAIL, PASSWORD)
            server.sendmail(FROM_EMAIL, to_email, msg.as_string())
    except Exception as e:
        print(f"Email sending failed: {e}")

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
            "name": name,
            "email": email,
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
        
        send_email(email, f"{ticket_number} - {subject}", f"Thank you for your request. Your ticket ID is {ticket_number}.")
        
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