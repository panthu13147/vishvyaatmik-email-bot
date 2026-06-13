"""
Central configuration for the Vishvyaatmik AI Email Manager.

Everything you'd want to tune lives here -- pacing, AI models, Discord
styling, and (most importantly) the rule-based importance/junk lists.
Edit this file freely; the rest of the code reads from it.
"""

import os
from dotenv import load_dotenv

load_dotenv()

# ============================================================
# SECRETS / ENV VARS  (set these in your .env file)
# ============================================================
EMAIL_USER = os.getenv("EMAIL_USER")
EMAIL_PASS = os.getenv("EMAIL_PASS")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")  # optional -- fallback brain
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")


# ============================================================
# POLLING & PACING
# ============================================================
# How long to sleep between inbox checks when nothing went wrong.
POLL_INTERVAL_IDLE = 30

# How long to sleep after a connection-level error (don't hammer Gmail).
POLL_INTERVAL_ERROR = 60

# Seconds between AI calls. Groq's free tier is 30 requests/minute, so
# anything >= 2.5s per call keeps us comfortably under that even with
# retries.
AI_CALL_DELAY = 3

# Seconds between Discord posts (Discord webhooks rate-limit too).
DISCORD_POST_DELAY = 1.2

# Max unread emails pulled per cycle. Keep this modest -- it's the upper
# bound on AI calls (and therefore tokens-per-minute) in a single pass.
BATCH_SIZE = 8


# ============================================================
# AI BRAIN
# ============================================================
# llama-3.3-70b-versatile and llama-3.1-8b-instant share the same free-tier
# limits on Groq (30 RPM / 6,000 TPM / 1,000 RPD as of mid-2026), so we use
# the smarter 70B model by default for better classification quality. Swap
# to "llama-3.1-8b-instant" if you want lower latency.
GROQ_MODEL = "llama-3.3-70b-versatile"

# Optional second-opinion / fallback brain if Groq is rate-limited or down.
# Only used if GEMINI_API_KEY is set. Gemini 2.5 Flash is the stable free
# model as of mid-2026 (2.0 Flash was retired June 1, 2026).
GEMINI_MODEL = "gemini-2.5-flash"

# Truncate the email body before it ever reaches the AI. This is the single
# biggest fix for TPM-based 429s -- a "Pinterest recommendations" email can
# easily be 20,000+ characters of HTML-derived text. 2000 chars (~500
# tokens) is plenty of context for a summary.
MAX_BODY_CHARS = 2000

AI_MAX_OUTPUT_TOKENS = 400

# If Groq returns a 429, wait this many seconds * (attempt number) before
# retrying, up to GROQ_MAX_RETRIES times.
GROQ_MAX_RETRIES = 2
GROQ_RETRY_BASE_SECONDS = 20


# ============================================================
# CATEGORIES & DISCORD STYLING
# ============================================================
CATEGORY_STYLE = {
    "URGENT":    {"emoji": "🚨", "color": 0xE74C3C},  # red
    "IMPORTANT": {"emoji": "⭐", "color": 0xF1C40F},  # gold
    "INFO":      {"emoji": "ℹ️", "color": 0x3498DB},  # blue
    "JUNK":      {"emoji": "🗑️", "color": 0x95A5A6},  # grey (never posted)
}
VALID_CATEGORIES = set(CATEGORY_STYLE)

DISCORD_USERNAME = "Vishvyaatmik AI Assistant"
DISCORD_AVATAR_URL = "https://i.imgur.com/7v5vSGi.png"


# ============================================================
# RULE-BASED PRE-CLASSIFICATION
# ============================================================
# These run BEFORE any AI call. They're free, instant, and -- for the
# URGENT/IMPORTANT cases -- they set a FLOOR that the AI cannot override
# downward (see classifier.reconcile). Add/remove entries freely.

# Subject phrases that mean "drop everything" regardless of sender.
# Matching these ALWAYS pre-flags URGENT, even if the sender domain is
# also in JUNK_SENDER_DOMAINS below -- security mail must never be silenced.
URGENT_SUBJECT_KEYWORDS = [
    "otp", "one time password", "one-time password", "verification code",
    "security alert", "unusual activity", "unauthorized", "unauthorised",
    "suspicious login", "new sign-in", "password reset", "account suspended",
    "account locked", "fraud alert", "fraud detected",
]

# Senders matching these domains are pre-flagged IMPORTANT. The AI still
# writes the summary, but reconcile() won't let it demote these to JUNK.
IMPORTANT_SENDER_DOMAINS = [
    # --- Banks & financial institutions (India) -- edit to match YOUR bank's
    #     actual sending domain; check a real email's "From" address.
    "hdfcbank.com", "icicibank.com", "sbi.co.in", "onlinesbi.com",
    "axisbank.com", "kotak.com", "idfcfirstbank.com", "yesbank.in",
    "bankofbaroda.in", "pnbindia.in", "canarabank.com", "indusind.com",
    "federalbank.co.in", "rblbank.com", "unionbankofindia.co.in",
    # --- Payments / fintech / cards ---
    "paytm.com", "phonepe.com", "paypal.com", "razorpay.com",
    "cred.club", "americanexpress.com", "sbicard.com",
    # --- Jobs & career ---
    "linkedin.com", "naukri.com", "indeed.com", "internshala.com",
    "unstop.com", "hackerearth.com", "glassdoor.com", "wellfound.com",
    "instahyre.com", "cutshort.io", "foundit.in", "angel.co",
    # --- Dev / coding platforms ---
    "github.com", "leetcode.com", "hackerrank.com", "codeforces.com",
    "gitlab.com",
    # --- Education ---
    "classroom.google.com",
    # --- Government / official (India) ---
    "gov.in", "nic.in", "uidai.gov.in", "incometax.gov.in", "epfindia.gov.in",
]

# Subject phrases that mean "worth a look", regardless of sender.
IMPORTANT_SUBJECT_KEYWORDS = [
    "kyc", "debited", "credited", "transaction alert", "payment due",
    "payment failed", "invoice", "interview", "shortlisted", "offer letter",
    "application received", "application status", "admit card",
    "results declared", "exam", "deadline",
]

# Senders matching these domains are instant JUNK -- skipped before any AI
# call. (Subject to the URGENT override above.)
JUNK_SENDER_DOMAINS = [
    "swiggy.com", "zomato.com", "ubereats.com", "dunzo.com", "blinkit.com",
    "pinterest.com", "myunidays.com", "groupon.com", "nykaa.com",
    "myntra.com", "ajio.com", "facebookmail.com", "instagram.com",
    "twitter.com", "x.com",
]

# Generic local-part patterns. Only checked if the domain wasn't recognised
# as IMPORTANT above -- so notifications@github.com still gets through.
JUNK_SENDER_PATTERNS = [
    "newsletter", "marketing", "mailer", "campaign", "promo", "noreply",
    "no-reply", "donotreply", "do-not-reply",
]

# Subject phrases that strongly suggest promotional content.
JUNK_SUBJECT_KEYWORDS = [
    "% off", "sale", "discount", "deal of the day", "flash sale",
    "limited time", "free shipping", "new arrivals", "win a", "giveaway",
    "just for you", "don't miss out", "exclusive offer", "best deals",
]
