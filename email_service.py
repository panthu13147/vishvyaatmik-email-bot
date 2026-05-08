import imaplib
import email
from email.header import decode_header
import os
from dotenv import load_dotenv

load_dotenv()
EMAIL_USER = os.getenv('EMAIL_USER')
EMAIL_PASS = os.getenv('EMAIL_PASS')

# 🛑 JUNK FILTERS (Lower case)
JUNK_KEYWORDS = ['swiggy', 'zomato', 'uber', 'tentabs', 'marketing', 'newsletter', 'promotions', 'noreply', 'no-reply']

def get_text_from_email(msg):
    body = ""
    if msg.is_multipart():
        for part in msg.walk():
            if part.get_content_type() == "text/plain":
                try:
                    body = part.get_payload(decode=True).decode('utf-8')
                    break
                except:
                    pass
    else:
        try:
            body = msg.get_payload(decode=True).decode('utf-8')
        except:
            pass
    return body

def fetch_and_clean_emails(batch_size=20):
    try:
        mail = imaplib.IMAP4_SSL("imap.gmail.com")
        mail.login(EMAIL_USER, EMAIL_PASS)
        mail.select("inbox")

        status, messages = mail.search(None, "UNSEEN")
        email_ids = messages[0].split()

        if not email_ids:
            return None, mail

        # Batched Processing: Sirf latest X emails uthao taaki crash na ho
        email_ids = email_ids[-batch_size:]
        print(f"📥 Found unread emails. Processing a batch of {len(email_ids)}...")
        
        emails_list = []
        
        for e_id in email_ids:
            status, msg_data = mail.fetch(e_id, "(RFC822)")
            for response_part in msg_data:
                if isinstance(response_part, tuple):
                    msg = email.message_from_bytes(response_part[1])
                    
                    sender = str(msg.get("From")).lower()
                    subject, encoding = decode_header(msg["Subject"])[0]
                    if isinstance(subject, bytes):
                        subject = subject.decode(encoding if encoding else "utf-8")
                        
                    # 🛡️ THE BOUNCER LOGIC
                    is_junk = any(junk in sender for junk in JUNK_KEYWORDS)
                    if is_junk:
                        print(f"🗑️ Bouncer Blocked Junk: {subject[:30]}... (Auto-marking as read)")
                        mark_as_read(mail, e_id)
                        continue # Skip to next email
                        
                    body = get_text_from_email(msg)
                    emails_list.append({
                        "id": e_id,
                        "subject": subject,
                        "sender": sender,
                        "body": body
                    })
        
        return emails_list, mail
        
    except Exception as e:
        print(f"❌ Mail Vault Error: {e}")
        return None, None

def mark_as_read(mail_connection, email_id):
    try:
        mail_connection.store(email_id, '+FLAGS', '\\Seen')
    except Exception as e:
        pass