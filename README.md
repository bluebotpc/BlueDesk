# GoobyDesk

Simple, Lightweight, Databaseless Service Desk for Home Labbers, Families, and One Man MSPs.

**Current Version:**  v0.4.1

[GoobyDesk Repo Wiki](https://github.com/GoobyFRS/GoobyDesk/wiki) & [Production Deployment Guide](https://github.com/GoobyFRS/GoobyDesk/wiki/Production-Deployment-Guide) you can find information on my code standards, my variables, and other data I think is important for an open source project to be successful after the creator moves on.

## What is GoobyDesk

GoobyDesk is a Python3, Flask-based web application.

- By default, the Flask app will run at ```http://127.0.0.1:5000``` during local development.
- Production instances should be ran behind a Python3 WSGI server such as [Gunicorn](https://gunicorn.org/).
- Production Gunicorn instances should be ran behind a Reverse Proxy such as [Caddy](https://caddyserver.com/).

Mobile-friendly landing page with lightweight ticket submission.

- Requestor Name
- Requestor Contact Email
- Ticket Subject/Title
- Ticket Impact
  - Low
  - Medium
  - High
- Ticket Urgency
  - Planning
  - Low
  - Medium
  - High
- Ticket Message
- Ticket Category
  - Request
  - Incident
  - Maintenance
  - Change
  - Access

New Ticket Created confirmation emails are sent from an inbox defined in a DOTENV file.

New Ticket Created confirmation emails are based on a clean HTML5 Jinja template that can be easily customized.

User email replies are appended to the ticket notes.

Technician Dashboard where logged in users can view Open Tickets and manage them.

Support for multiple technicians.

Closed Tickets are hidden from the Dashboard by default.

## Goals and Roadmap to Production v1.0

- Implement "Logged In Technician" and Closed_By status.
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

**Technically Broken, no longer supported.**

1. Comment out ```import fcntl```
2. Comment out ```load_tickets``` lines 44-60.
3. Uncomment top ```load_tickets```. lines 35 - 42.
4. Enable Debugging at EOF.

```shell
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
python app.py
```

CTRL+C to break. ```deactivate``` to clean up.

### Screenshots

#### Landing Page

![Index-GHWiki](https://github.com/user-attachments/assets/6dfde191-1c8f-4c15-8c72-5544f06d17a9)

#### Login

![Login-GHWiki](https://github.com/user-attachments/assets/0d538988-e36a-4cdb-9126-bd93c1f9aa53)

#### Dashboard

![Dashboard-GHWiki](https://github.com/user-attachments/assets/b72367bd-b2f5-47bf-8b18-6e56f0a7bbe3)

#### Confirmation Email Template

![FirstEmail-GHWiki](https://github.com/user-attachments/assets/9fa30684-ab70-49b9-b897-1fb106802c06)

#### Ticket Commander

![TktCommander-GHWiki](https://github.com/user-attachments/assets/2d08aa6d-35b7-44f3-8381-3d4983aee59b)
