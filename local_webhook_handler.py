#!/usr/bin/env python3
import os
import json
import requests
import logging
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv(dotenv_path=".env")
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")

# Sends a Discord webhook notification when a new ticket is created.
def send_discord_notification(ticket_number, ticket_subject, ticket_message):
    if not DISCORD_WEBHOOK_URL:
        logging.warning("WEBHOOK HANDLER - DISCORD_WEBHOOK_URL is not set. Check your .env file.")
        return
    
    data = {
        "username": "BlueDesk",
        
        "embeds": [
            {
                "title": f"New Ticket Created: {ticket_number} - {ticket_subject}",
                "description": f"**Details:** {ticket_message}",
                "color": 5814783,  # Light Blue # decimal representation of a hexadecimal color code
            }
        ]
    }

    headers = {"Content-Type": "application/json"}

    try:
        response = requests.post(DISCORD_WEBHOOK_URL, data=json.dumps(data), headers=headers)
        response.raise_for_status()  # Raise exception for HTTP errors
        
        if response.status_code == 204:
            logging.info(f"WEBHOOK HANDLER - New Ticket {ticket_number} notification sent to Discord.")
        else:
            logging.warning(f"WEBHOOK HANDLER - Unexpected response code: {response.status_code}")

    except requests.exceptions.ConnectionError:
        logging.error("WEBHOOK HANDLER - Failed to connect to Discord. Check internet and webhook URL.")
    except requests.exceptions.Timeout:
        logging.error("WEBHOOK HANDLER - Request to Discord timed out.")
    except requests.exceptions.RequestException as e:
        logging.error(f"WEBHOOK HANDLER - Unexpected error: {e}")

# send_TktUpdate_discord_notification will send a webhook when the status becomes In-Progress or Closed..
def send_TktUpdate_discord_notification(ticket_number, ticket_status):
    if not DISCORD_WEBHOOK_URL:
        logging.warning("WEBHOOK HANDLER - DISCORD_WEBHOOK_URL is not set. Check your .env file.")
        return
    
    data = {
        "username": "BlueDesk",
        
        "embeds": [
            {
                "title": f"Ticket {ticket_number} updated to {ticket_status}.",
                "color": 16776960,  # Yellow # decimal representation of a hexadecimal color code
            }
        ]
    }

    headers = {"Content-Type": "application/json"}

    try:
        response = requests.post(DISCORD_WEBHOOK_URL, data=json.dumps(data), headers=headers)
        response.raise_for_status()  # Raise exception for HTTP errors
        
        if response.status_code == 204:
            logging.info(f"WEBHOOK HANDLER - Ticket {ticket_number} status change notification sent to Discord.")
        else:
            logging.warning(f"WEBHOOK HANDLER - Unexpected response code: {response.status_code}")

    except requests.exceptions.ConnectionError:
        logging.error("WEBHOOK HANDLER - Failed to connect to Discord. Check internet and webhook URL.")
    except requests.exceptions.Timeout:
        logging.error("WEBHOOK HANDLER - Request to Discord timed out.")
    except requests.exceptions.RequestException as e:
        logging.error(f"WEBHOOK HANDLER - Unexpected error: {e}")