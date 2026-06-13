"""
Stand-alone utility: mark obviously-junk unread emails as read WITHOUT
calling any AI. Uses the exact same rules as the main bot (config.py /
classifier.py), so "junk" is defined in exactly one place.

Handy for clearing a backlog fast before letting main.py's AI work
through what's left.
"""

import email_service
from classifier import pre_classify


def run_nuke():
    print("☢️  NUKE: scanning unread mail for obvious junk (no AI calls)...")
    mail = email_service.connect()
    try:
        items = email_service.fetch_unread_headers(mail, batch_size=500)
        if not items:
            print("📭 Inbox already clear of unread mail.")
            return

        nuked = 0
        for item in items:
            category = pre_classify(item["sender"], item["subject"])
            if category == "JUNK":
                email_service.mark_as_read(mail, item["id"])
                nuked += 1
                print(f"💥 NUKED: {item['sender'][:60]}")

        print(f"\n✅ Done: {nuked}/{len(items)} unread emails marked as junk and cleared.")
        print("Run main.py to let the AI triage what's left.")
    finally:
        mail.logout()


if __name__ == "__main__":
    run_nuke()
