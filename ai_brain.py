"""
AI Brain: takes (sender, subject, body, pre_category) and returns a
structured verdict:

    {
        "category": "URGENT" | "IMPORTANT" | "INFO" | "JUNK",
        "summary": "...",
        "action_required": "...",
        "key_details": "...",
        "provider": "groq" | "gemini" | "rules-only",
    }

Resilience chain:
  1. Try Groq (primary). On a 429, back off and retry a couple of times.
  2. If Groq is unavailable/exhausted and GEMINI_API_KEY is set, try Gemini.
  3. If everything fails, return a rules-only result built from
     pre_category -- the user NEVER sees a raw "Server Error: 429" again.
"""

import json
import re
import time

import config

SYSTEM_PROMPT = (
    "You are Vishvyaatmik, a precise email-triage assistant for a student "
    "developer in India. You read one email at a time and respond with a "
    "single JSON object ONLY -- no markdown fences, no commentary, no "
    "text before or after the JSON."
)

CATEGORY_GUIDE = """Categories:
- URGENT: security alerts, OTPs/verification codes needed now, fraud or
  unauthorized-access warnings, account suspension, deadlines within 24h.
- IMPORTANT: bank/payment transactions, bills, job offers, interview
  invites, application status updates, official college/university or
  government mail, developer-platform activity (GitHub, LeetCode, etc.)
- INFO: routine updates, confirmations, low-stakes notifications worth a
  glance but no action.
- JUNK: marketing, promotions, newsletters, sales, social-media
  recommendation digests."""

JSON_SHAPE = """Respond with exactly this JSON shape (valid JSON, double quotes):
{
  "category": "URGENT" | "IMPORTANT" | "INFO" | "JUNK",
  "summary": "2-3 plain-English sentences describing what this email is and why it matters",
  "action_required": "what the user must do, in a few words, or \\"None\\"",
  "key_details": "amounts, dates, deadlines, codes, names worth highlighting, or \\"None\\""
}"""


def _build_prompt(sender, subject, body, pre_category):
    hint = ""
    if pre_category in ("IMPORTANT", "URGENT"):
        hint = (
            f"\nNote: a rule already flagged this as likely '{pre_category}' "
            f"based on the sender/subject. Confirm or refine the category, "
            f"but do not classify it as JUNK."
        )

    return (
        f"{CATEGORY_GUIDE}\n\n{JSON_SHAPE}{hint}\n\n"
        f"From: {sender}\nSubject: {subject}\n\nBody:\n{body}"
    )


def _extract_json(text):
    """Pull a JSON object out of `text`, tolerating markdown fences and
    stray commentary before/after the object."""
    if not text:
        return None
    cleaned = re.sub(r"```(?:json)?", "", text, flags=re.IGNORECASE)
    cleaned = cleaned.replace("```", "").strip()
    start, end = cleaned.find("{"), cleaned.rfind("}")
    if start == -1 or end == -1 or end < start:
        return None
    try:
        return json.loads(cleaned[start:end + 1])
    except json.JSONDecodeError:
        return None


def _is_rate_limit_error(e: Exception) -> bool:
    status = getattr(e, "status_code", None)
    if status is None:
        response = getattr(e, "response", None)
        status = getattr(response, "status_code", None)
    if status == 429:
        return True
    msg = str(e).lower()
    return "429" in msg or "rate limit" in msg or "rate_limit" in msg


def _call_groq(prompt):
    try:
        from groq import Groq
    except ImportError:
        print("⚠️ groq package not installed -- skipping Groq.")
        return None

    client = Groq(api_key=config.GROQ_API_KEY)

    for attempt in range(config.GROQ_MAX_RETRIES + 1):
        try:
            resp = client.chat.completions.create(
                model=config.GROQ_MODEL,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.2,
                max_tokens=config.AI_MAX_OUTPUT_TOKENS,
            )
            return resp.choices[0].message.content
        except Exception as e:
            if _is_rate_limit_error(e) and attempt < config.GROQ_MAX_RETRIES:
                wait = config.GROQ_RETRY_BASE_SECONDS * (attempt + 1)
                print(f"⏳ Groq rate-limited (429). Waiting {wait}s "
                      f"before retry {attempt + 1}/{config.GROQ_MAX_RETRIES}...")
                time.sleep(wait)
                continue
            print(f"⚠️ Groq call failed: {e}")
            return None
    return None


def _call_gemini(prompt):
    if not config.GEMINI_API_KEY:
        return None
    try:
        from google import genai
    except ImportError:
        print("⚠️ google-genai package not installed -- skipping Gemini fallback.")
        return None

    try:
        client = genai.Client(api_key=config.GEMINI_API_KEY)
        resp = client.models.generate_content(
            model=config.GEMINI_MODEL,
            contents=f"{SYSTEM_PROMPT}\n\n{prompt}",
        )
        return resp.text
    except Exception as e:
        print(f"⚠️ Gemini fallback failed: {e}")
        return None


def _rules_only_result(pre_category, subject):
    """Used when no AI provider is configured/available. The email is
    NEVER dropped -- it gets a basic flag based on the rule engine alone."""
    category = pre_category if pre_category in config.VALID_CATEGORIES else "INFO"
    needs_review = category in ("URGENT", "IMPORTANT")
    return {
        "category": category,
        "summary": (
            f"AI analysis is temporarily unavailable, so this is a "
            f"rule-based flag only (subject: \"{subject}\"). "
            f"Open the email to see the full details."
        ),
        "action_required": "Review manually" if needs_review else "None",
        "key_details": "None",
        "provider": "rules-only",
    }


def analyze_email(sender, subject, body, pre_category="UNKNOWN"):
    prompt = _build_prompt(sender, subject, body or "(empty body)", pre_category)

    raw, provider = None, None

    if config.GROQ_API_KEY:
        raw = _call_groq(prompt)
        provider = "groq"

    if raw is None and config.GEMINI_API_KEY:
        raw = _call_gemini(prompt)
        provider = "gemini"

    if raw is None:
        return _rules_only_result(pre_category, subject)

    parsed = _extract_json(raw)
    if parsed is None:
        # Model replied with prose instead of JSON -- still useful, just
        # treat the whole reply as the summary.
        return {
            "category": pre_category if pre_category in config.VALID_CATEGORIES else "INFO",
            "summary": raw.strip()[:600],
            "action_required": "None",
            "key_details": "None",
            "provider": provider,
        }

    parsed.setdefault("category", "INFO")
    parsed.setdefault("summary", "(no summary returned)")
    parsed.setdefault("action_required", "None")
    parsed.setdefault("key_details", "None")
    parsed["provider"] = provider
    return parsed
