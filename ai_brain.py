import os
from groq import Groq
from dotenv import load_dotenv

# Load the Secret Vault
load_dotenv()
GROQ_API_KEY = os.getenv('GROQ_API_KEY')

# Initialize Groq Client
client = Groq(api_key=GROQ_API_KEY)

def analyze_email(email_text):
    if not email_text:
        return "IGNORE"
    
    # 🧠 THE VISHVYAATMIK DEVELOPER PROMPT (Groq Edition)
    prompt = f"""
    You are an elite AI Assistant for a "Vishvyaatmik Student Developer". 
    Read the following email and follow these strict rules:

    🚨 THE TRASH RULE:
    If it's just a general notification, generic newsletter, promotional offer, or social media request, output EXACTLY ONE WORD: "IGNORE".

    💎 THE ANOMALY RULE (High Alert):
    If this email is highly unusual or extremely beneficial (e.g., received Bitcoin, massive bank transfer, a job/freelance offer, or an urgent account warning), you MUST output a DETAILED EXPLANATION of exactly what happened.

    ⏩ THE ONE-LINER RULE (For everything else):
    For all other valid but normal emails (e.g., regular college updates, normal bank statements), provide ONLY a simple 1-line summary. No long bullet points.

    Output format for valid emails:
    1. 🏷️ PRIORITY: [Anomaly/Alert] OR [General Info]
    2. 📝 SUMMARY: (Detailed explanation for anomalies, or a crisp 1-liner for normal stuff)

    Email Content:
    {email_text}
    """
    
    try:
        chat_completion = client.chat.completions.create(
            messages=[
                {
                    "role": "system",
                    "content": "You are a highly efficient, strict email parser. Obey the rules exactly."
                },
                {
                    "role": "user",
                    "content": prompt,
                }
            ],
            # llama3-8b-8192 is blazing fast and has massive daily limits
            model="llama-3.1-8b-instant",
            temperature=0.2, # Low temp so it doesn't hallucinate
        )
        return chat_completion.choices[0].message.content
    except Exception as e:
        return f"❌ Groq Engine Crash: {e}"