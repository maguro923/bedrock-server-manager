import requests
import json
from os import environ

WEBHOOK_URL = environ.get("DISCORD_WEBHOOK_URL","")

def send(message):
    if not WEBHOOK_URL:
        print("DISCORD_WEBHOOK_URL is not set. skipping notification.")
        return False
    data = {
        "content": message
    }
    headers = {
        "Content-Type": "application/json"
    }
    try:
        response = requests.post(WEBHOOK_URL, data=json.dumps(data), headers=headers, timeout=10)
    except requests.RequestException as e:
        print(f"Failed to send message: {e}")
        return False
    if response.status_code != 204:
        print(f"Failed to send message: {response.status_code} - {response.text}")
        return False
    return True