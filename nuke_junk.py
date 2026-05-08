import imaplib
import email
import os
from dotenv import load_dotenv

load_dotenv()
EMAIL_USER = os.getenv('EMAIL_USER')
EMAIL_PASS = os.getenv('EMAIL_PASS')

# 🗑️ THE MEGA TRASH LIST (Add more words if you want)
JUNK_KEYWORDS = ['swiggy', 'zomato', 'uber', 'tentabs', 'marketing', 'newsletter', 'promotions', 'noreply', 'no-reply', 'offers', 'linkedin', 'spam', 'updates@', 'info@']

def run_nuke():
    print("☢️ NUKE SEQUENCE INITIATED: Bypassing AI, targeting only junk...")
    try:
        mail = imaplib.IMAP4_SSL("imap.gmail.com")
        mail.login(EMAIL_USER, EMAIL_PASS)
        mail.select("inbox")

        status, messages = mail.search(None, "UNSEEN")
        email_ids = messages[0].split()

        if not email_ids:
            print("📭 Inbox is already clear of unread emails.")
            return

        print(f"🎯 Found {len(email_ids)} unread emails. Scanning for trash...")
        
        nuked = 0
        for e_id in email_ids:
            # PEEK.HEADER sirf title/sender uthata hai, poora mail nahi, isliye ultra-fast hai
            status, msg_data = mail.fetch(e_id, "(RFC822.HEADER)")
            for response_part in msg_data:
                if isinstance(response_part, tuple):
                    msg = email.message_from_bytes(response_part[1])
                    
                    sender = str(msg.get("From")).lower()
                    subject = str(msg.get("Subject")).lower()
                    
                    # Agar sender ya subject mein junk word hai, toh uda do
                    is_junk = any(junk in sender or junk in subject for junk in JUNK_KEYWORDS)
                    
                    if is_junk:
                        mail.store(e_id, '+FLAGS', '\\Seen')
                        nuked += 1
                        print(f"💥 NUKED: {sender[:30]}...")

        mail.logout()
        print(f"\n✅ NUKE COMPLETE: {nuked} junk emails destroyed without using API!")
        print("Ab tu 'main.py' run karke bache hue important emails ko summarize karwa sakta hai.")
        
    except Exception as e:
        print(f"❌ Nuke Error: {e}")

if __name__ == "__main__":
    run_nuke()