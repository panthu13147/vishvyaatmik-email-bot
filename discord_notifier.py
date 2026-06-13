"""
Posts a structured email verdict to Discord as a rich, color-coded embed.
Handles Discord's own rate limits (429 + Retry-After header) gracefully.
"""

import time

import requests

import config


def _truncate(text, limit):
    text = "" if text is None else str(text)
    return text if len(text) <= limit else text[: limit - 1] + "…"


def _post(payload):
    if not config.DISCORD_WEBHOOK_URL:
        print("❌ DISCORD_WEBHOOK_URL is not set -- cannot notify Discord.")
        return False

    for _ in range(3):
        try:
            resp = requests.post(config.DISCORD_WEBHOOK_URL, json=payload, timeout=15)
        except Exception as e:
            print(f"❌ Discord connection failed: {e}")
            return False

        if resp.status_code == 204:
            return True

        if resp.status_code == 429:
            retry_after = 1.0
            try:
                retry_after = float(resp.headers.get("Retry-After", "1"))
            except ValueError:
                pass
            print(f"⏳ Discord rate-limited. Waiting {retry_after:.1f}s...")
            time.sleep(retry_after + 0.1)
            continue

        print(f"⚠️ Discord API error {resp.status_code}: {resp.text[:200]}")
        return False

    return False


def send_to_discord(sender, subject, verdict):
    category = verdict.get("category", "INFO")
    style = config.CATEGORY_STYLE.get(category, config.CATEGORY_STYLE["INFO"])

    embed = {
        "author": {"name": f"{style['emoji']} {category}"},
        "title": _truncate(subject or "(no subject)", 256),
        "description": _truncate(verdict.get("summary", ""), 4096),
        "color": style["color"],
        "fields": [
            {"name": "📩 From", "value": _truncate(sender, 1024), "inline": False},
            {"name": "✅ Action Needed", "value": _truncate(verdict.get("action_required", "None"), 256), "inline": True},
            {"name": "🔑 Key Details", "value": _truncate(verdict.get("key_details", "None"), 256), "inline": True},
        ],
        "footer": {"text": f"Vishvyaatmik AI • via {verdict.get('provider', 'unknown')}"},
    }

    payload = {
        "username": config.DISCORD_USERNAME,
        "avatar_url": config.DISCORD_AVATAR_URL,
        "embeds": [embed],
    }
    return _post(payload)


def send_status_message(text):
    """Plain-text status ping (e.g. 'bot is online'). Useful for spotting
    silent crashes -- if you stop seeing these, the bot probably died."""
    payload = {
        "username": config.DISCORD_USERNAME,
        "avatar_url": config.DISCORD_AVATAR_URL,
        "content": text,
    }
    return _post(payload)
