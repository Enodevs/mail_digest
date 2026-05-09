import datetime
import json
import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

import litellm
import requests
from dotenv import load_dotenv
from imap_tools import AND, MailBox
from litellm import completion
from rich.console import Console

load_dotenv()

EMAIL = os.getenv("EMAIL_ADDRESS")
PASSWORD = os.getenv("EMAIL_PASSWORD")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

PRIMARY_MODEL = "groq/llama-3.3-70b-versatile"
FALLBACK_MODEL = "groq/llama-3.1-8b-instant"

IMPORTANCE_ORDER = {"High": 3, "Medium": 2, "Low": 1}

console = Console()


def fetch_unread_emails(limit=6) -> list[dict]:
    if not EMAIL or not PASSWORD:
        console.log("[red]EMAIL and PASSWORD environment variables must be set.[/red]")
        return []

    messages = []
    try:
        with MailBox("imap.gmail.com", timeout=30).login(
            EMAIL, PASSWORD, "INBOX"
        ) as mailbox:
            for msg in mailbox.fetch(AND(seen=False), limit=limit, reverse=True):
                mail_body = msg.text or (msg.html or "")[:4000]
                messages.append(
                    {
                        "subject": msg.subject or "(no subject)",
                        "from": msg.from_,
                        "date": str(msg.date),
                        "body": mail_body.strip(),
                    }
                )
        console.log(f"[green]Fetched {len(messages)} unread emails.[/green]")
    except Exception as e:
        console.log(f"[red]Failed to fetch emails: {e}[/red]")
    return messages


def analyze_email(email_data: dict) -> dict:
    if not GROQ_API_KEY:
        console.log("[red]GROQ_API_KEY missing.[/red]")
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

Rules:
- High: urgent action, money, boss, meeting, deadline, personal/family
- Medium: needs reply but not urgent
- Low: promotions, newsletters, FYI
"""

    models_to_try = [PRIMARY_MODEL, FALLBACK_MODEL]

    for model in models_to_try:
        for attempt in range(3):
            try:
                response = completion(
                    model=model,
                    messages=[{"role": "user", "content": prompt}],
                    api_key=GROQ_API_KEY,
                    temperature=0.3,
                    response_format={"type": "json_object"},
                    max_tokens=500,
                )

                content = response.choices[0].message.content.strip()
                parsed = json.loads(content)
                console.log(
                    f"[green]Analyzed with[/green] [cyan]{model}[/cyan]: {email_data['subject'][:60]}..."
                )
                return parsed

            except litellm.RateLimitError:
                console.log(f"[yellow]Rate limit on {model}. Switching...[/yellow]")
                break
            except json.JSONDecodeError:
                console.log("[yellow]JSON parse failed. Retrying...[/yellow]")
                time.sleep(2)
                continue
            except Exception as e:
                console.log(f"[red]Error with {model}: {e}[/red]")
                if attempt < 2:
                    time.sleep(3)
                    continue
                break

    return {"summary": "Analysis failed", "importance": "Low", "reason": "API error"}


def send_to_telegram(summary_text: str) -> None:
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        console.log("[yellow]Telegram not configured.[/yellow]")
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": summary_text,
        "parse_mode": "Markdown",
    }
    try:
        resp = requests.post(url, json=payload)
        if resp.status_code == 200:
            console.log("[green]Digest sent to Telegram![/green]")
        else:
            console.log(f"[red]Telegram failed: {resp.text}[/red]")
    except Exception as e:
        console.log(f"[red]Telegram error: {e}[/red]")


def main() -> None:
    console.rule("[bold blue]Daily Email Digest")
    console.log("[blue]Starting Email Digest...[/blue]")
    messages = fetch_unread_emails()

    if not messages:
        console.log("[yellow]No unread emails.[/yellow]")
        return

    analyses = []
    with ThreadPoolExecutor(max_workers=4) as executor:
        future_map = {executor.submit(analyze_email, email): email for email in messages}
        for future in as_completed(future_map):
            email = future_map[future]
            analysis = future.result()
            analyses.append(
                {
                    "subject": email["subject"],
                    "from": email["from"],
                    "importance": analysis.get("importance", "Low"),
                    "summary": analysis.get("summary", "N/A"),
                    "reason": analysis.get("reason", "N/A"),
                }
            )

    digest = (
        f"📬 *Daily Email Digest* – {datetime.date.today().strftime('%B %d, %Y')}\n\n"
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
        digest += f"From: {item['from']}\n"
        digest += f"{item['summary']}\n"
        digest += f"Why: {item['reason']}\n\n"

    send_to_telegram(digest)
    console.rule("[bold green]Done")


if __name__ == "__main__":
    main()
