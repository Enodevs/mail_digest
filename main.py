import asyncio
import datetime
import json
import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

import discord
import groq
from dotenv import load_dotenv
from groq import Groq
from imap_tools import AND, MailBox
from rich.console import Console

from lib.helpers import extract_body

load_dotenv()

EMAIL = os.getenv("EMAIL_ADDRESS")
PASSWORD = os.getenv("EMAIL_PASSWORD")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

DISCORD_BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN")
DISCORD_CHANNEL_ID = os.getenv("DISCORD_CHANNEL_ID")

IMAP_HOST = os.getenv("IMAP_HOST", "imap.gmail.com")

PRIMARY_MODEL = "openai/gpt-oss-20b"
FALLBACK_MODEL = "qwen/qwen3.6-27b"

IMPORTANCE_ORDER = {"High": 3, "Medium": 2, "Low": 1}

console = Console()

client = Groq(api_key=GROQ_API_KEY)

discord_client = discord.Client(
    intents=discord.Intents.none()
)


def fetch_unread_emails(limit=6) -> list[dict]:
    if not EMAIL or not PASSWORD:
        console.log("[red]EMAIL and PASSWORD environment variables must be set.[/red]")
        return []

    messages = []

    try:
        with MailBox(IMAP_HOST, timeout=30).login(
            EMAIL,
            PASSWORD,
            "INBOX"
        ) as mailbox:

            for msg in mailbox.fetch(
                AND(seen=False),
                limit=limit,
                reverse=True
            ):
                messages.append(
                    {
                        "subject": msg.subject or "(no subject)",
                        "from": msg.from_,
                        "date": str(msg.date),
                        "body": extract_body(msg),
                    }
                )

        console.log(
            f"[green]Fetched {len(messages)} unread emails.[/green]"
        )

    except (ConnectionError, TimeoutError, OSError) as e:
        console.log(
            f"[red]Network error fetching emails: {e}[/red]"
        )

    except Exception as e:
        console.log(
            f"[red]Failed to fetch emails: {e}[/red]"
        )

    return messages


def analyze_email(email_data: dict) -> dict:
    if not GROQ_API_KEY:
        console.log("[red]GROQ_API_KEY missing.[/red]")
        return {
            "summary": "N/A",
            "importance": "Low",
            "reason": "No API key",
        }

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
                    messages=[
                        {
                            "role": "user",
                            "content": prompt,
                        }
                    ],
                    temperature=0.3,
                    response_format={"type": "json_object"},
                    max_tokens=500,
                )

                if response.choices[0].message.content:
                    content = (
                        response.choices[0]
                        .message
                        .content
                        .strip()
                    )

                parsed = json.loads(content)

                console.log(
                    f"[green]Analyzed with[/green] "
                    f"[cyan]{model}[/cyan]: "
                    f"{email_data['subject'][:60]}..."
                )

                return parsed

            except groq.RateLimitError:
                console.log(
                    f"[yellow]Rate limit on {model}. Switching...[/yellow]"
                )
                break

            except groq.NotFoundError:
                console.log(
                    f"[yellow]Model provided '{model}' not found. "
                    f"Switching...[/yellow]"
                )
                break

            except json.JSONDecodeError:
                console.log(
                    "[yellow]JSON parse failed. Retrying...[/yellow]"
                )
                time.sleep(2)

            except Exception as e:
                console.log(
                    f"[yellow]Error with {model} "
                    f"(attempt {attempt + 1}): {e}[/yellow]"
                )

                if attempt < 2:
                    time.sleep(3)
                    continue

                break

    return {
        "summary": "Analysis failed",
        "importance": "Low",
        "reason": "API error",
    }


def build_digest(analyses: list[dict]) -> str:
    digest = (
        f"📬 **Daily Email Digest** · "
        f"{datetime.date.today().strftime('%B %d, %Y')}\n\n"
    )

    for item in sorted(
        analyses,
        key=lambda x: IMPORTANCE_ORDER.get(
            x["importance"],
            0
        ),
        reverse=True,
    ):
        emoji = (
            "🔥"
            if item["importance"] == "High"
            else "📌"
            if item["importance"] == "Medium"
            else "📬"
        )

        digest += (
            f"{emoji} **{item['importance']}** · "
            f"{item['subject']}\n"
        )
        digest += f"From: {item['from']}\n"
        digest += f"{item['summary']}\n"
        digest += f"Why: {item['reason']}\n\n"

    return digest


async def send_to_discord(summary_text: str) -> None:
    if not DISCORD_BOT_TOKEN or not DISCORD_CHANNEL_ID:
        console.log(
            "[yellow]Discord is not configured.[/yellow]"
        )
        return

    try:
        channel_id = int(DISCORD_CHANNEL_ID)

    except ValueError:
        console.log(
            "[red]DISCORD_CHANNEL_ID must be a number.[/red]"
        )
        return

    try:
        await discord_client.login(DISCORD_BOT_TOKEN)

        channel = discord_client.get_channel(channel_id)

        if channel is None:
            channel = await discord_client.fetch_channel(channel_id)

        # Discord messages have a 2000-character limit.
        chunks = [
            summary_text[i:i + 1900]
            for i in range(0, len(summary_text), 1900)
        ]

        for chunk in chunks:
            await channel.send(chunk)

        console.log(
            "[green]Digest sent to Discord![/green]"
        )

    except discord.Forbidden:
        console.log(
            "[red]Discord denied access to the channel. "
            "Check the bot's permissions.[/red]"
        )

    except discord.NotFound:
        console.log(
            "[red]Discord channel was not found. "
            "Check DISCORD_CHANNEL_ID.[/red]"
        )

    except discord.HTTPException as e:
        console.log(
            f"[red]Discord API error: {e}[/red]"
        )

    except Exception as e:
        console.log(
            f"[red]Failed to send Discord digest: {e}[/red]"
        )

    finally:
        await discord_client.close()


def main() -> None:
    console.rule("[bold blue]Daily Email Digest")

    messages = fetch_unread_emails()

    if not messages:
        console.log("[yellow]No unread emails.[/yellow]")
        return

    analyses = []

    with ThreadPoolExecutor(max_workers=4) as executor:
        future_map = {
            executor.submit(
                analyze_email,
                email
            ): email
            for email in messages
        }

        for future in as_completed(future_map):
            email = future_map[future]
            analysis = future.result()

            analyses.append(
                {
                    "subject": email["subject"],
                    "from": email["from"],
                    "importance": analysis.get(
                        "importance",
                        "Low"
                    ),
                    "summary": analysis.get(
                        "summary",
                        "N/A"
                    ),
                    "reason": analysis.get(
                        "reason",
                        "N/A"
                    ),
                }
            )

    digest = build_digest(analyses)

    asyncio.run(
        send_to_discord(digest)
    )

    console.rule("[bold green]Done")


if __name__ == "__main__":
    main()
