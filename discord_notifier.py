import requests
import os
from dotenv import load_dotenv

load_dotenv()
WEBHOOK_URL = os.getenv('DISCORD_WEBHOOK_URL')

def send_to_discord(sender, subject, summary):
    if not WEBHOOK_URL:
        print("❌ System Error: Discord Webhook URL is missing in the .env vault!")
        return

    # 🎨 Formatting the message for Discord
    discord_message = f"**📩 FROM:** `{sender}`\n**📌 SUBJECT:** {subject}\n{'-'*50}\n{summary}\n{'-'*50}"

    data = {
        "content": discord_message,
        "username": "Vishvyaatmik AI Assistant", # Bot ka naam
        "avatar_url": "https://i.imgur.com/7v5vSGi.png" # Ek cool AI avatar
    }

    try:
        response = requests.post(WEBHOOK_URL, json=data)
        if response.status_code == 204:
            print("✅ Successfully beamed analysis to Discord!")
        else:
            print(f"⚠️ Discord API Error: {response.status_code}")
    except Exception as e:
        print(f"❌ Discord Connection Failed: {e}")