"""
IMAP layer: connect, fetch unread mail, extract clean text, mark as read.

This module is pure I/O + parsing -- no importance/junk decisions live
here (see classifier.py and ai_brain.py for that).
"""

import email
import imaplib
import re
from email.header import decode_header, make_header

import config

try:
    from bs4 import BeautifulSoup
    _HAS_BS4 = True
except ImportError:  # pragma: no cover - bs4 is in requirements.txt
    _HAS_BS4 = False


def connect():
    mail = imaplib.IMAP4_SSL("imap.gmail.com")
    mail.login(config.EMAIL_USER, config.EMAIL_PASS)
    mail.select("inbox")
    return mail


def _decode_subject(raw_subject) -> str:
    """Decode a possibly multi-part, multi-encoding Subject header."""
    if not raw_subject:
        return "(no subject)"
    try:
        decoded = str(make_header(decode_header(raw_subject)))
        return decoded if decoded.strip() else "(no subject)"
    except Exception:
        return str(raw_subject)


def _html_to_text(html: str) -> str:
    if _HAS_BS4:
        soup = BeautifulSoup(html, "html.parser")
        for tag in soup(["script", "style"]):
            tag.decompose()
        text = soup.get_text(separator=" ")
    else:  # crude fallback if bs4 isn't installed
        text = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", html,
                       flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"&nbsp;|&#160;", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def get_text_from_email(msg) -> str:
    """
    Extract readable text from an email.message.Message.

    Prefers text/plain parts. If none exist (HTML-only marketing emails
    AND some HTML-only bank/security emails), falls back to stripping the
    text/html part so the email is never silently treated as empty.
    """
    plain_parts = []
    html_parts = []

    if msg.is_multipart():
        for part in msg.walk():
            content_type = part.get_content_type()
            disposition = str(part.get("Content-Disposition") or "")
            if "attachment" in disposition.lower():
                continue
            try:
                payload = part.get_payload(decode=True)
                if payload is None:
                    continue
                charset = part.get_content_charset() or "utf-8"
                decoded = payload.decode(charset, errors="ignore")
            except Exception:
                continue

            if content_type == "text/plain":
                plain_parts.append(decoded)
            elif content_type == "text/html":
                html_parts.append(decoded)
    else:
        try:
            payload = msg.get_payload(decode=True)
            charset = msg.get_content_charset() or "utf-8"
            decoded = payload.decode(charset, errors="ignore") if payload else ""
        except Exception:
            decoded = ""

        if msg.get_content_type() == "text/html":
            html_parts.append(decoded)
        else:
            plain_parts.append(decoded)

    body = "\n".join(p.strip() for p in plain_parts if p and p.strip())
    if body:
        return body

    # No usable text/plain -- fall back to the HTML part rather than
    # returning empty (empty body used to mean "AI says IGNORE", which
    # silently dropped HTML-only bank/security emails).
    html_body = "\n".join(_html_to_text(h) for h in html_parts if h and h.strip())
    return html_body


def fetch_unread(mail, batch_size=None):
    """
    Fetch up to `batch_size` unread emails (full RFC822, body truncated to
    config.MAX_BODY_CHARS). Returns a list of dicts:
        id, message_id, sender, subject, body
    """
    batch_size = batch_size or config.BATCH_SIZE

    status, messages = mail.search(None, "UNSEEN")
    if status != "OK":
        return []

    email_ids = messages[0].split()
    if not email_ids:
        return []

    email_ids = email_ids[-batch_size:]
    emails = []

    for e_id in email_ids:
        status, msg_data = mail.fetch(e_id, "(RFC822)")
        if status != "OK":
            continue
        for response_part in msg_data:
            if not isinstance(response_part, tuple):
                continue
            msg = email.message_from_bytes(response_part[1])

            sender = msg.get("From", "") or ""
            subject = _decode_subject(msg.get("Subject"))
            message_id = (msg.get("Message-ID", "") or "").strip()
            if not message_id:
                # Fallback key for malformed emails without a Message-ID.
                message_id = f"{sender}|{subject}|{msg.get('Date', '')}"

            body = get_text_from_email(msg)

            emails.append({
                "id": e_id,
                "message_id": message_id,
                "sender": sender,
                "subject": subject,
                "body": body[:config.MAX_BODY_CHARS],
            })

    return emails


def fetch_unread_headers(mail, batch_size=500):
    """
    Lightweight fetch: sender + subject only (RFC822.HEADER, no body).
    Used by nuke_junk.py for fast bulk scanning.
    """
    status, messages = mail.search(None, "UNSEEN")
    if status != "OK":
        return []

    email_ids = messages[0].split()
    if not email_ids:
        return []

    email_ids = email_ids[-batch_size:]
    emails = []

    for e_id in email_ids:
        status, msg_data = mail.fetch(e_id, "(RFC822.HEADER)")
        if status != "OK":
            continue
        for response_part in msg_data:
            if not isinstance(response_part, tuple):
                continue
            msg = email.message_from_bytes(response_part[1])
            emails.append({
                "id": e_id,
                "sender": msg.get("From", "") or "",
                "subject": _decode_subject(msg.get("Subject")),
            })

    return emails


def mark_as_read(mail, email_id):
    mail.store(email_id, "+FLAGS", "\\Seen")
