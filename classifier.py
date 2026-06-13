"""
Rule-based pre-classification.

Runs BEFORE any AI call. Three jobs:
  1. Catch the obvious cases for free and instantly (saves API quota).
  2. Guarantee security-critical mail (OTPs, fraud alerts) is NEVER
     silently dropped, no matter what the AI or any junk rule says.
  3. Set a "floor" for known-important senders (banks, job boards, dev
     platforms) so the AI can refine but not bury them.

pre_classify() returns one of: "URGENT", "IMPORTANT", "JUNK", "UNKNOWN".
"UNKNOWN" means "let the AI decide" -- it's the only category the AI is
fully free to set on its own.
"""

import re

import config


def _domain_of(sender: str) -> str:
    match = re.search(r"@([\w.\-]+)", sender or "")
    return match.group(1).lower() if match else ""


def pre_classify(sender: str, subject: str) -> str:
    sender_l = (sender or "").lower()
    subject_l = (subject or "").lower()
    domain = _domain_of(sender_l)

    # 1. Security / OTP language ALWAYS wins. Never let a "security alert"
    #    get auto-junked just because it came from a domain on the junk
    #    list (e.g. a spoofed or unusual sender).
    if any(kw in subject_l for kw in config.URGENT_SUBJECT_KEYWORDS):
        return "URGENT"

    # 2. Known junk senders (promo platforms, social recommendation digests).
    if any(domain == d or domain.endswith("." + d) for d in config.JUNK_SENDER_DOMAINS):
        return "JUNK"

    # 3. Known important senders (banks, job boards, dev platforms, gov/edu).
    if any(domain == d or domain.endswith("." + d) for d in config.IMPORTANT_SENDER_DOMAINS):
        return "IMPORTANT"

    if any(kw in subject_l for kw in config.IMPORTANT_SUBJECT_KEYWORDS):
        return "IMPORTANT"

    # 4. Generic marketing patterns -- only reached if the domain wasn't
    #    recognised as important above, so e.g. notifications@github.com
    #    is safe even though "notifications" can look noreply-ish.
    if any(p in sender_l for p in config.JUNK_SENDER_PATTERNS):
        return "JUNK"

    if any(kw in subject_l for kw in config.JUNK_SUBJECT_KEYWORDS):
        return "JUNK"

    return "UNKNOWN"


# Used by reconcile() to compare severity.
_CATEGORY_RANK = {"JUNK": 0, "INFO": 1, "IMPORTANT": 2, "URGENT": 3}


def reconcile(pre_category: str, ai_category: str) -> str:
    """
    Combine the rule-based pre-classification with the AI's verdict.

    - A pre-classification of IMPORTANT/URGENT sets a FLOOR of INFO: the AI
      can upgrade it (e.g. IMPORTANT -> URGENT) or agree, but it can never
      push a known-important sender all the way down to JUNK and have it
      go completely unseen.
    - A pre-classification of UNKNOWN gives the AI full authority, including
      the ability to call something JUNK (e.g. a promotional email from a
      sender we don't have rules for yet).
    - If the AI's category is missing/invalid, default to INFO so something
      is always shown rather than nothing.
    """
    if ai_category not in config.VALID_CATEGORIES:
        ai_category = "INFO"

    if pre_category in ("IMPORTANT", "URGENT"):
        if _CATEGORY_RANK[ai_category] < _CATEGORY_RANK["INFO"]:
            return "INFO"
        return ai_category

    return ai_category
