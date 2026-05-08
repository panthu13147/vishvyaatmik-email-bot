import time
from email_service import fetch_and_clean_emails, mark_as_read
from ai_brain import analyze_email
from discord_notifier import send_to_discord

def run_ai_agent():
    print(f"[{time.strftime('%H:%M:%S')}] 🔍 Scanning for new high-stakes updates...")
    
    # Batch size chota rakhenge kyunki ab naye emails kam hi aayenge
    emails_list, mail_connection = fetch_and_clean_emails(batch_size=5)
    
    if not emails_list:
        return

    print(f"🧠 AI Brain (Groq) is analyzing {len(emails_list)} new incoming signals...")
    
    for mail in emails_list:
        analysis = analyze_email(mail['body'])
        
        if "IGNORE" in analysis.upper():
            mark_as_read(mail_connection, mail['id'])
            continue

        # 📡 Sending the Signal to Discord
        send_to_discord(mail['sender'], mail['subject'], analysis)
        
        # Mark as read so we don't process it again
        mark_as_read(mail_connection, mail['id'])
        time.sleep(2) # Safety delay
        
    try:
        mail_connection.logout()
    except:
        pass

if __name__ == "__main__":
    print("🚀 VISHVYAATMIK AI BOT IS LIVE! 🚀")
    print("System is now monitoring your inbox 24/7...")
    
    while True:
        try:
            run_ai_agent()
        except Exception as e:
            print(f"⚠️ Runtime Glitch: {e}. Retrying in 60s...")
        
        # Har 5 minute (300 seconds) mein check karega
        # Tu isko 60 (1 min) bhi kar sakta hai agar bohot fast chahiye
        time.sleep(30)