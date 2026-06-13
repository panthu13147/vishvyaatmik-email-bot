[README.md](https://github.com/user-attachments/files/28907748/README.md)
# Vishvyaatmik AI Email Manager — v2

## What was actually going wrong

Looking at your code and the screenshot, three separate bugs were stacking
on top of each other:

1. **The "Server Error: 429" spam.** The old `ai_brain.py` sent the *entire*
   email body straight into the prompt with no length limit. Marketing
   emails (Pinterest, Unidays) are often 15–20k characters of HTML-derived
   text once decoded. Groq's free tier caps you at **6,000 tokens/minute**
   — one or two of those emails and you're over the limit, and the raw
   `429` error text got forwarded straight to Discord as the "summary".

2. **The junk filter was inverted.** `nuke_junk.py` had `'linkedin'` in the
   *junk* keyword list (the opposite of what you want), while Pinterest and
   Unidays — actual junk — weren't in any junk list at all, so they went
   all the way to the AI and triggered the 429s above.

3. **HTML-only emails were silently dropped.** `get_text_from_email` only
   looked at `text/plain` parts. Many bank/security emails are HTML-only —
   the old code would extract an empty body, the AI would return `IGNORE`,
   and the email vanished with no summary and no Discord post at all.

## The new architecture

```
IMAP fetch ──▶ classifier.pre_classify() ──▶ JUNK? ──yes──▶ mark read, log, STOP
                       │                                    (zero AI calls)
                       │ no
                       ▼
              ai_brain.analyze_email()
              Groq (primary) → Gemini (fallback) → rules-only (last resort)
                       │
                       ▼
              classifier.reconcile(pre_category, ai_category)
                       │
                       ▼
              discord_notifier ──▶ color-coded embed
                       │
                       ▼
              storage.py (SQLite log, for idempotency + future stats)
```

**Four categories** instead of the old binary IGNORE/not-IGNORE:

| Category  | Color  | Meaning                                                        |
|-----------|--------|-----------------------------------------------------------------|
| 🚨 URGENT    | red    | OTPs, security alerts, fraud warnings, <24h deadlines         |
| ⭐ IMPORTANT | gold   | Bank transactions, job/interview mail, bills, GitHub/LeetCode, gov/edu |
| ℹ️ INFO      | blue   | Routine updates worth a glance                                |
| 🗑️ JUNK      | —      | Marketing/promo — never posted to Discord                     |

### Why it's "bulletproof" now

- **Rule-based pre-filter runs first**, for free. Pinterest/Unidays-style
  mail is marked JUNK and skipped *before* any AI call — that alone removes
  most of the load that was causing 429s.
- **Security mail can never be silenced.** OTP/fraud/security-alert subjects
  are flagged `URGENT` regardless of sender, even if the sender domain is
  also on the junk list.
- **Known-important senders (banks, LinkedIn, GitHub, etc.) have a floor.**
  The AI can upgrade them but can't demote them to JUNK and make them
  disappear — at worst they show as `INFO`.
- **Email bodies are truncated to 2000 chars** before hitting the AI —
  enough for a real summary, far below the TPM ceiling.
- **Groq 429s trigger a backoff + retry**, not a crash.
- **Gemini 2.5 Flash is an optional second opinion** if Groq is exhausted
  (only used if you set `GEMINI_API_KEY`).
- **If every AI provider fails**, you get a clearly-labeled rule-based
  notice instead of a raw error string — you're never left wondering if
  the bot is alive.
- **HTML-only emails now get summarized too** (HTML is stripped to text as
  a fallback), so important bank/security mail can't vanish.
- **SQLite log (`vishvyaatmik.db`)** records every triaged email by
  Message-ID, so a missed `\Seen` flag can't cause duplicate posts or
  duplicate AI calls — and it's the foundation for the digest/voice
  features below.

## Files

| File                  | Status   | Purpose |
|-----------------------|----------|---------|
| `config.py`           | **new**  | All tunable settings + the importance/junk rule lists |
| `classifier.py`       | **new**  | Rule-based pre-classification + reconciliation logic |
| `storage.py`          | **new**  | SQLite log for idempotency + stats |
| `email_service.py`    | rewritten | IMAP fetch, robust MIME/HTML parsing, multi-encoding subjects |
| `ai_brain.py`         | rewritten | Groq → Gemini → rules-only chain, JSON-structured output |
| `discord_notifier.py` | rewritten | Rich color-coded embeds, 429-aware retries |
| `main.py`             | rewritten | Orchestration loop, startup status ping |
| `nuke_junk.py`        | rewritten | Same logic as the main bot, just skips the AI step |
| `requirements.txt`    | updated  | Added `beautifulsoup4`, `google-genai`; removed deprecated `google-generativeai` |
| `.env.example`        | **new**  | Documents every required/optional env var |

## Setup & Deployment

**Yes — this is a drop-in replacement.** Same env var names you already
have, same entry point (`main.py`), same Discord webhook.

1. **Replace the files in your repo** with all the files in this package
   (overwrite the old `main.py`, `email_service.py`, `ai_brain.py`,
   `discord_notifier.py`, `nuke_junk.py`, `requirements.txt`, `.gitignore`,
   and add the new `config.py`, `classifier.py`, `storage.py`).

2. **Your existing `.env` keeps working as-is.** The only *optional* addition is:
   ```
   GEMINI_API_KEY=your_key_here   # leave blank to skip — Groq + rules still work fine
   ```
   Get a free key at https://aistudio.google.com/apikey if you want the
   fallback brain.

3. **Commit and push to GitHub:**
   ```bash
   git add .
   git commit -m "v2: smart triage, fix 429s, fix junk filter"
   git push
   ```

4. **Install the updated dependencies and restart the bot.** How you do
   this depends on where it's running:
   - **Local machine / VPS:** `pip install -r requirements.txt --break-system-packages`
     (or inside your venv), then re-run `python main.py`.
   - **Replit / Railway / Render / PythonAnywhere etc.:** these normally
     auto-install from `requirements.txt` on deploy, but you'll likely need
     to manually **stop and restart** the running process — pushing to
     GitHub alone doesn't kill an already-running loop.
   - Tell me which platform you're using and I can give you exact restart
     steps.

5. **Watch for the startup message.** On boot, the bot now posts
   *"✅ Vishvyaatmik AI Email Manager is online and monitoring your inbox."*
   to your `#email-alerts` channel. If you don't see it, the process didn't
   actually restart (or `DISCORD_WEBHOOK_URL` is missing).

6. **Optional one-time cleanup:** run `python nuke_junk.py` once to clear
   out any backlog of obvious junk (Pinterest/Unidays/etc.) sitting unread
   in your inbox, using the *new* rules — instant, no AI cost.

## Customizing the rules

Everything importance-related lives in `config.py`:

- `IMPORTANT_SENDER_DOMAINS` — add your specific bank's domain if it's not
  there (check the `From:` address on a real email from them — domains vary
  by bank).
- `JUNK_SENDER_DOMAINS` / `JUNK_SENDER_PATTERNS` / `JUNK_SUBJECT_KEYWORDS` —
  add any recurring senders you want auto-silenced.
- `URGENT_SUBJECT_KEYWORDS` / `IMPORTANT_SUBJECT_KEYWORDS` — phrase-based
  triggers that work regardless of sender.

No code changes needed for any of this — just edit the lists.

## Roadmap: towards "Jarvis"

This rewrite is structured so the voice-assistant phase has something to
build on rather than starting from zero:

- `storage.py` already has every triaged email, categorized and
  summarized, in a local SQLite DB. A voice assistant can query it
  directly — *"any important emails today?"* becomes
  `storage.stats_since(start_of_day)` plus a `SELECT` for the IMPORTANT/URGENT
  rows.
- `ai_brain.analyze_email()` is provider-agnostic and already returns
  structured JSON — the same function can power a voice assistant's
  "read me my emails" skill.
- A natural next step *before* full voice control: a daily digest message
  (e.g. "Yesterday: 2 urgent, 5 important, 31 junk filtered") posted once a
  day using `storage.stats_since()` — this is a small addition whenever
  you're ready, and a good stepping stone toward the assistant style
  interaction you're after.

The voice layer itself (wake word, speech-to-text, text-to-speech) is a
separate, larger project — happy to scope that out whenever you want to
start on it.
