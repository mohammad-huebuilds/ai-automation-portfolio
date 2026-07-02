import os
import sys
import json
import requests
from dotenv import load_dotenv

# Load environment variables from the .env file
load_dotenv()

# Fetch the webhook URL from your environment
WEBHOOK_URL = os.getenv("Make_webhook_url")

def trigger_scenario(topic):
    if not WEBHOOK_URL:
        print("Error: Make_webhook_url not found in environment. Did you set up your .env file?")
        return

    payload = {
        "topic": topic
    }
    
    print(f"Sending topic '{topic}' to Make.com webhook...")
    
    try:
        response = requests.post(
            WEBHOOK_URL,
            headers={"Content-Type": "application/json"},
            data=json.dumps(payload),
            timeout=10
        )
        
        if response.status_code == 200:
            print(f"Success. Make.com responded with: {response.text}")
        else:
            print(f"Unexpected status code: {response.status_code}")
            print(f"Response: {response.text}")
            
    except requests.exceptions.RequestException as e:
        print(f"Request failed: {e}")

if __name__ == "__main__":
    topic = sys.argv[1] if len(sys.argv) > 1 else "artificial intelligence trends"
    trigger_scenario(topic)