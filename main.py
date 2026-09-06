import datetime
import json
import os
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

import groq
import requests
from dotenv import load_dotenv
from imap_tools import AND, MailBox
from rich.console import Console
from groq import Groq

load_dotenv()

EMAIL = os.getenv("EMAIL_ADDRESS")
PASSWORD = os.getenv("EMAIL_PASSWORD")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
IMAP_HOST = os.getenv("IMAP_HOST", "imap.gmail.com")

PRIMARY_MODEL = "openai/gpt-oss-20b"
FALLBACK_MODEL = "qwen/qwen3.6-27b"

IMPORTANCE_ORDER = {"High": 3, "Medium": 2, "Low": 1}

console = Console()

client = Groq(
    api_key=GROQ_API_KEY
)

def extract_body(msg) -> str:
    text = msg.text
    if text:
        return text.strip()
    html = msg.html
    if html:
        clean = re.sub(r"<[^>]+>", " ", html)
        clean = re.sub(r"\s+", " ", clean).strip()
        return clean[:4000]
    return ""


def fetch_unread_emails(limit=6) -> list[dict]:
    if not EMAIL or not PASSWORD:
        console.log("[red]EMAIL and PASSWORD environment variables must be set.[/red]")
        return []

    messages = []
    try:
        with MailBox(IMAP_HOST, timeout=30).login(EMAIL, PASSWORD, "INBOX") as mailbox:
            for msg in mailbox.fetch(AND(seen=False), limit=limit, reverse=True):
                messages.append(
                    {
                        "subject": msg.subject or "(no subject)",
                        "from": msg.from_,
                        "date": str(msg.date),
                        "body": extract_body(msg),
                    }
                )
        console.log(f"[green]Fetched {len(messages)} unread emails.[/green]")
    except (ConnectionError, TimeoutError, OSError) as e:
        console.log(f"[red]Network error fetching emails: {e}[/red]")
    except Exception as e:
        console.log(f"[red]Failed to fetch emails: {e}[/red]")
    return messages


def analyze_email(email_data: dict) -> dict:
    if not GROQ_API_KEY:
        console.log("[red]GROQ_API_KEY missing.[/red]")
        return {"summary": "N/A", "importance": "Low", "reason": "No API key"}

    content = ""

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
                response = client.chat.completions.create(
                    model=model,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.3,
                    response_format={"type": "json_object"},
                    max_tokens=500,
                )

                if response.choices[0].message.content:
                    content = response.choices[0].message.content.strip()

                parsed = json.loads(content)
                console.log(
                    f"[green]Analyzed with[/green] [cyan]{model}[/cyan]: {email_data['subject'][:60]}..."
                )
                return parsed

            except groq.RateLimitError:
                console.log(f"[yellow]Rate limit on {model}. Switching...[/yellow]")
                break
            except groq.NotFoundError:
                console.log(f"[yellow]Model provided '{model}' not found. Switching...[/yellow]")
                break
            except json.JSONDecodeError:
                console.log("[yellow]JSON parse failed. Retrying...[/yellow]")
                time.sleep(2)
                continue
            except Exception as e:
                console.log(
                    f"[yellow]Error with {model} (attempt {attempt + 1}): {e}[/yellow]"
                )
                if attempt < 2:
                    time.sleep(3)
                    continue
                break

    return {"summary": "Analysis failed", "importance": "Low", "reason": "API error"}


def escape_md(text) -> str:
    """Escape special characters for Telegram's legacy Markdown parse mode.

    Legacy 'Markdown' (as opposed to 'MarkdownV2') only requires escaping
    _ * [ ] and ` — but any of these appearing unbalanced in email subjects,
    sender names, or LLM-generated summaries will break Telegram's parser
    with 'can't find end of the entity' errors.
    """
    if not text:
        return ""
    text = str(text)
    return re.sub(r"([_*\[\]`])", r"\\\1", text)


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

    for attempt in range(3):
        try:
            resp = requests.post(url, json=payload, timeout=15)
            if resp.status_code == 200:
                console.log("[green]Digest sent to Telegram![/green]")
                return
            console.log(
                f"[yellow]Telegram attempt {attempt + 1} failed "
                f"(HTTP {resp.status_code}): {resp.text}[/yellow]"
            )
        except requests.Timeout:
            console.log(f"[yellow]Telegram attempt {attempt + 1} timed out.[/yellow]")
        except requests.RequestException as e:
            console.log(f"[yellow]Telegram attempt {attempt + 1} error: {e}[/yellow]")

        if attempt < 2:
            time.sleep(2**attempt)

    console.log("[red]Telegram send failed after 3 attempts.[/red]")


def main() -> None:
    console.rule("[bold blue]Daily Email Digest")
    messages = fetch_unread_emails()

    if not messages:
        console.log("[yellow]No unread emails.[/yellow]")
        return

    analyses = []
    with ThreadPoolExecutor(max_workers=4) as executor:
        future_map = {
            executor.submit(analyze_email, email): email for email in messages
        }
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
        digest += f"{emoji} **{item['importance']}** – {escape_md(item['subject'])}\n"
        digest += f"From: {escape_md(item['from'])}\n"
        digest += f"{escape_md(item['summary'])}\n"
        digest += f"Why: {escape_md(item['reason'])}\n\n"

    send_to_telegram(digest)
    console.rule("[bold green]Done")


if __name__ == "__main__":
    main()
