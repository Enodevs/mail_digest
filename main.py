import datetime
import json
import os
import time

import litellm
import requests
from dotenv import load_dotenv
from imap_tools import AND, MailBox
from litellm import completion

load_dotenv()

EMAIL = os.getenv("EMAIL_ADDRESS")
PASSWORD = os.getenv("EMAIL_PASSWORD")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

IMPORTANCE_ORDER = {"High": 3, "Medium": 2, "Low": 1}


def fetch_unread_emails(limit=5):
    if not EMAIL or not PASSWORD:
        print("EMAIL and PASSWORD environment variables must be set.")
        return []

    messages = []
    try:
        with MailBox("imap.gmail.com").login(EMAIL, PASSWORD, "INBOX") as mailbox:
            for msg in mailbox.fetch(AND(seen=False), limit=limit, reverse=True):
                mail_body = msg.text or (msg.html or "")[:4000]
                messages.append(
                    {
                        "subject": msg.subject or "(no subject)",
                        "from": msg.from_,
                        "date": str(msg.date),  # make string for safety
                        "body": mail_body.strip(),
                    }
                )
        print(f"Fetched {len(messages)} unread emails.")
    except Exception as e:
        print(f"Failed to fetch emails: {e}")
    return messages


def analyze_email(email_data):
    if not GEMINI_API_KEY:
        print("GEMINI_API_KEY missing.")
        return {"summary": "N/A", "importance": "Low", "reason": "No API key"}

    prompt = f"""You are an expert personal assistant. Analyze this email and respond ONLY with valid JSON.
Subject: {email_data["subject"]}
From: {email_data["from"]}
Date: {email_data["date"]}
Body: {email_data["body"]}

JSON format:
{{
  "summary": "1-2 sentence summary",
  "importance": "High" or "Medium" or "Low",
  "reason": "short reason (e.g. 'Boss asking for report', 'Newsletter', 'Invoice attached')"
}}
Rules for importance:
- High: urgent action, money, boss, meeting, deadline, personal/family
- Medium: needs reply but not urgent
- Low: promotions, newsletters, FYI
"""

    for attempt in range(3):  # simple retry up to 3 times
        try:
            response = completion(
                model="gemini/gemini-2.5-flash",
                messages=[{"role": "user", "content": prompt}],
                api_key=GEMINI_API_KEY,
                temperature=0.3,
                response_format={"type": "json_object"},
                max_tokens=400,
                stream=False,
            )

            content = response.choices[0].message.content.strip()
            if not content:
                print(f"Empty content for '{email_data['subject']}'")
                return {"summary": "No summary", "importance": "Low", "reason": "Empty"}

            parsed = json.loads(content)
            return parsed

        except litellm.RateLimitError as e:
            print(f"Rate limit hit for '{email_data['subject']}': {e}")
            if attempt < 2:
                wait = 60  # seconds – increase if needed
                print(f"Retrying after {wait}s...")
                time.sleep(wait)
            else:
                return {
                    "summary": "Rate limited",
                    "importance": "Low",
                    "reason": "Quota exceeded – try later or paid tier",
                }

        except Exception as e:
            print(
                f"Analysis failed for '{email_data['subject']}': {type(e).__name__} - {e}"
            )
            return {"summary": "Error", "importance": "Low", "reason": str(e)}


def send_to_telegram(summary_text):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("Telegram not configured – skipping send.")
        return

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": summary_text,
        "parse_mode": "Markdown",  # optional: for bold/italics
        "disable_notification": False,
    }

    try:
        resp = requests.post(url, json=payload)
        if resp.status_code == 200:
            print("Digest sent to Telegram! 🚀")
        else:
            print(f"Telegram send failed: {resp.text}")
    except Exception as e:
        print(f"Telegram error: {e}")


def main():
    print("Fetching inbox data...")
    messages = fetch_unread_emails(limit=10)  # increase if you get more unread

    if not messages:
        print("No unread emails.")
        return

    analyses = []
    for email in messages:
        analysis = analyze_email(email)
        analyses.append(
            {
                "subject": email["subject"],
                "from": email["from"],
                "importance": analysis.get("importance", "Low"),
                "summary": analysis.get("summary", "N/A"),
                "reason": analysis.get("reason", "N/A"),
            }
        )

    # Build pretty Markdown digest
    digest = (
        "📬 *Daily Email Digest* – "
        + datetime.date.today().strftime("%B %d, %Y")
        + "\n\n"
    )
    for item in sorted(
        analyses, key=lambda x: IMPORTANCE_ORDER.get(x["importance"], 0), reverse=True
    ):
        emoji = (
            "🔥"
            if item["importance"] == "High"
            else "📌"
            if item["importance"] == "Medium"
            else "📬"
        )
        digest += f"{emoji} **{item['importance']}** – {item['subject']}\n"
        digest += f"   From: {item['from']}\n"
        digest += f"   {item['summary']}\n"
        digest += f"   Why: {item['reason']}\n\n"

    print("Sending digest to Telegram...")
    send_to_telegram(digest)


if __name__ == "__main__":
    main()
