import requests
import json

WEBHOOK_URL = ""

def send(message):
    data = {
        "content": message
    }
    headers = {
        "Content-Type": "application/json"
    }
    response = requests.post(WEBHOOK_URL, data=json.dumps(data), headers=headers)
    if response.status_code != 204:
        print(f"Failed to send message: {response.status_code} - {response.text}")