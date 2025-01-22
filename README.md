# GoobyDesk

Simple, Lightweight, Databaseless Service Desk for Home Labbers, Families, and One Man MSPs.

**Current Version:**  v0.1.10

## How GoobyDesk works

- GoobyDesk is a python3.12 Flask project that by default runs at ```http://127.0.0.1:5000```.
- Landing page is a basic Service Desk form.
- User provided _email_ and _subject_ are used to generate a _Notification_ email sent to the user.
- The script will monitor the configured inbox every 5 minutes for replies. When found, the contents will be append to the Ticket Notes.

## Linux Project Setup

```shell
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python3 ./app.py
```

CTRL+C to break. ```deactivate``` to clean up.

## Windows Project Setup

```shell
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
python app.py
```

CTRL+C to break. ```deactivate``` to clean up.

### Goals and Roadmap

- OAuth2.0 Support for Email Authentication.
- Fine tune email reply handling.
- HTML Form validation.
- File locking and retry support.
- Mutli-user (Technician) support
- Standardized logging
