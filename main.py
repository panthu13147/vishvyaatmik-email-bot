"""
Vishvyaatmik AI Email Manager -- main loop.

Pipeline per unread email:
  1. Idempotency check (storage) -- skip if we've already handled this
     Message-ID (protects against duplicate posts if \\Seen ever fails).
  2. Rule-based pre-classification (classifier.pre_classify) -- instant,
     free, and guarantees security/IMPORTANT senders are never silently
     junked.
  3. If pre-classified JUNK -> mark read, log, done. No AI call spent.
  4. Otherwise -> AI brain produces a real summary + category.
  5. reconcile() merges the rule-based floor with the AI's verdict.
  6. If the final category isn't JUNK -> post a color-coded embed to
     Discord.
  7. Mark as read, record in the local DB.
"""

import time

import config
import email_service
import storage
from ai_brain import analyze_email
from classifier import pre_classify, reconcile
from discord_notifier import send_status_message, send_to_discord


def process_email(mail, item):
    sender, subject, body = item["sender"], item["subject"], item["body"]
    message_id = item["message_id"]

    if storage.already_processed(message_id):
        email_service.mark_as_read(mail, item["id"])
        return

    pre_category = pre_classify(sender, subject)
    print(f"🔎 [{pre_category}] {subject[:60]!r} <- {sender}")

    if pre_category == "JUNK":
        verdict = {
            "category": "JUNK", "summary": "", "action_required": "None",
            "key_details": "None", "provider": "rules",
        }
        storage.record_email(message_id, sender, subject, verdict)
        email_service.mark_as_read(mail, item["id"])
        return

    verdict = analyze_email(sender, subject, body, pre_category)
    verdict["category"] = reconcile(pre_category, verdict.get("category", "INFO"))

    storage.record_email(message_id, sender, subject, verdict)
    email_service.mark_as_read(mail, item["id"])

    if verdict["category"] != "JUNK":
        print(f"   -> {verdict['category']}: {verdict['summary'][:80]!r}")
        send_to_discord(sender, subject, verdict)
        time.sleep(config.DISCORD_POST_DELAY)
    else:
        print("   -> AI reclassified as JUNK, not posted.")

    # Pace AI calls relative to Groq's free-tier rate limit.
    time.sleep(config.AI_CALL_DELAY)


def run_cycle() -> bool:
    """Returns False on a connection-level failure, True otherwise
    (even if there was simply nothing new)."""
    mail = None
    try:
        mail = email_service.connect()
    except Exception as e:
        print(f"❌ Could not connect to mailbox: {e}")
        return False

    try:
        items = email_service.fetch_unread(mail)
        if items:
            print(f"📥 {len(items)} new email(s) to triage")
        for item in items:
            try:
                process_email(mail, item)
            except Exception as e:
                print(f"⚠️ Failed on one email ({item.get('subject', '')!r}): {e}")
    finally:
        try:
            mail.logout()
        except Exception:
            pass

    return True


def main():
    print("🚀 VISHVYAATMIK AI EMAIL MANAGER -- v2")
    print(f"   Groq:   {'configured' if config.GROQ_API_KEY else 'NOT SET'}")
    print(f"   Gemini: {'configured (fallback)' if config.GEMINI_API_KEY else 'not set (optional)'}")
    print(f"   Discord webhook: {'configured' if config.DISCORD_WEBHOOK_URL else 'NOT SET'}")
    print("Monitoring inbox... (Ctrl+C to stop)\n")

    storage.init_db()
    send_status_message("✅ Vishvyaatmik AI Email Manager is online and monitoring your inbox.")

    while True:
        ok = run_cycle()
        time.sleep(config.POLL_INTERVAL_IDLE if ok else config.POLL_INTERVAL_ERROR)


if __name__ == "__main__":
    main()
