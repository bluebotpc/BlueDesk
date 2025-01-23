# GoobyDesk

Simple, Lightweight, Databaseless Service Desk for Home Labbers, Families, and One Man MSPs.

**Current Version:**  v0.1.12

[GoobyDesk Repo Wiki](https://github.com/GoobyFRS/GoobyDesk/wiki) & [Production Deployment Guide](https://github.com/GoobyFRS/GoobyDesk/wiki/Production-Deployment-Guide) you can find information on my code standards, my variables, and other data I think is important for an open source project to be successful after the creator moves on.

## What is GoobyDesk

- GoobyDesk is a Python3, Flask-based web application.
  - By default, the Flask app will run at ```http://127.0.0.1:5000``` during local development.
  - Production instances should be ran behind a Python3 WSGI server such as [Gunicorn](https://gunicorn.org/).
  - Production instances should be ran behind a Reverse Proxy such as [Caddy](https://caddyserver.com/).
- Mobile-friendly landing page with lightweight ticket submission.
  - Requestor Name
  - Requestor Contact Email
  - Ticket Subject/Title
  - Ticket Message
  - Ticket Category
    - Request
    - Incident
    - Maintenance
    - Change
    - Access
- New Ticket Created confirmation emails are sent from an inbox defined in a DOTENV file.
- New Ticket Created confirmation emails are based on a clean HTML5 Jinja template that can be easily customized.
- User email replies are appended to the ticket notes.
- Technician Dashboard where logged in users can view Open Tickets and Close them.
  - Support for multiple technicians.
  - Closed Tickets are hidden by default.

## Goals and Roadmap to Production v1.0

- Ability to set In-Progress status.
- Individual Ticket html page rendering with controls. (Change Status, Read Notes)
- User-Input validation and sanitation on public facing HTML forms.
- File locking and retry support.
- Ensure proper HTTP codes are sent to the user/client.
- Implement standardized ```/var/log/goobydesk``` logging.

### Linux Project Setup

```shell
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python3 ./app.py
```

CTRL+C to break. ```deactivate``` to clean up.

### Windows Project Setup

```shell
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
python app.py
```

CTRL+C to break. ```deactivate``` to clean up.

### Screenshots

#### Landing Page

![LandingPage-GHWiki](https://github.com/user-attachments/assets/66267c63-5d02-4802-ac4b-32c67c8735cd)

#### Login

![Login-GHWiki](https://github.com/user-attachments/assets/a9c86ea6-710c-468a-bd8d-6ab7020cdcb5)

#### Dashboard

![Dashboard-GHWiki](https://github.com/user-attachments/assets/30b21d8f-e5cd-4713-a2b2-26f958db29e5)

#### Confirmation Email Template
