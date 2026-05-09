# Mail Digest

AI-powered email digest that fetches unread emails, classifies them by importance using Groq LLM, and sends a daily summary to Telegram.

## How It Works

```
Gmail (IMAP) → Fetch unread → LLM analysis (Groq) → Sorted digest → Telegram
```

1. **Fetch** — Connects to Gmail via IMAP and grabs unread emails
2. **Analyze** — Sends each email to Groq's LLM (`llama-3.3-70b-versatile`) which returns a JSON summary + importance rating (High/Medium/Low) + reason
3. **Digest** — Builds a sorted digest (High → Medium → Low) and sends it to a Telegram chat

## Setup

### Prerequisites

- Python 3.12+
- [uv](https://docs.astral.sh/uv/) (recommended) or pip

### Installation

```bash
git clone <repo-url>
cd gmail-automation
uv sync
```

Or with pip:

```bash
pip install -r requirements.txt
```

### Configuration

Copy `.env.example` to `.env` and fill in your credentials:

```env
EMAIL_ADDRESS="your.email@gmail.com"
EMAIL_PASSWORD="your-gmail-app-password"
GROQ_API_KEY="gsk_your-groq-api-key"
TELEGRAM_BOT_TOKEN="your-bot-token"
TELEGRAM_CHAT_ID="your-chat-id"
IMAP_HOST="imap.gmail.com"       # optional, defaults to imap.gmail.com
```

| Variable | Description |
|---|---|
| `EMAIL_ADDRESS` | Your Gmail address |
| `EMAIL_PASSWORD` | [Gmail App Password](https://support.google.com/accounts/answer/185833) (not your regular password) |
| `GROQ_API_KEY` | API key from [Groq](https://console.groq.com) |
| `TELEGRAM_BOT_TOKEN` | Token from [@BotFather](https://t.me/BotFather) |
| `TELEGRAM_CHAT_ID` | Your Telegram chat ID (get it from [@userinfobot](https://t.me/userinfobot)) |
| `IMAP_HOST` | IMAP server host (defaults to `imap.gmail.com`) |

### Gmail App Password

1. Enable [2-Step Verification](https://myaccount.google.com/security) on your Google account
2. Go to [App Passwords](https://myaccount.google.com/apppasswords)
3. Generate a new app password for "Mail"
4. Use that password in `EMAIL_PASSWORD`

## Usage

```bash
python main.py
```

Run it manually, or automate it with any scheduler:

**Cron (Linux/macOS):**
```bash
# Run every day at 8 AM
0 8 * * * cd /path/to/gmail-automation && /path/to/.venv/bin/python main.py
```

**GitHub Actions (`.github/workflows/digest.yml`):**
```yaml
name: Daily Email Digest
on:
  schedule:
    - cron: "0 8 * * *"
  workflow_dispatch:

jobs:
  digest:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - run: pip install -r requirements.txt
      - run: python main.py
        env:
          EMAIL_ADDRESS: ${{ secrets.EMAIL_ADDRESS }}
          EMAIL_PASSWORD: ${{ secrets.EMAIL_PASSWORD }}
          GROQ_API_KEY: ${{ secrets.GROQ_API_KEY }}
          TELEGRAM_BOT_TOKEN: ${{ secrets.TELEGRAM_BOT_TOKEN }}
          TELEGRAM_CHAT_ID: ${{ secrets.TELEGRAM_CHAT_ID }}
```

Store your secrets in the repo's **Settings → Secrets and variables → Actions**.

**Other options:** systemd timers, Windows Task Scheduler, [Koyeb](https://www.koyeb.com), [Render Cron Jobs](https://render.com), or any serverless cron service.

## Architecture

```
main.py
├── fetch_unread_emails()   — IMAP fetch via imap-tools
├── extract_body()          — Strips HTML, returns clean text
├── analyze_email()         — LLM classification via litellm (Groq)
│   ├── PRIMARY_MODEL       — llama-3.3-70b-versatile
│   └── FALLBACK_MODEL      — llama-3.1-8b-instant (on rate limit)
├── send_to_telegram()      — HTTP POST with retry logic
└── main()                  — Orchestrator (parallel via ThreadPoolExecutor)
```

Key design choices:
- **Parallel analysis** — Emails are analyzed concurrently (up to 4 at once)
- **Graceful degradation** — Falls back to a smaller model on rate limits, retries on failure
- **Telegram retry** — 3 attempts with exponential backoff
- **Configurable IMAP** — Works with any IMAP server, not just Gmail

## Tech Stack

- [imap-tools](https://github.com/ikvk/imap-tools) — IMAP email fetching
- [litellm](https://github.com/BerriAI/litellm) — LLM API calls (Groq)
- [rich](https://github.com/Textualize/rich) — Beautiful console output
- python-dotenv, requests — Config and HTTP

---

Made by [Isiaq Abdullah](https://abdullahdevs.vercel.app) · [X (Twitter)](https://x.com/abdullahdevs_) · [GitHub](https://github.com/abdullahdevs)

> If you build a product based on this, I'd appreciate a shoutout — [@abdullahdevs_](https://x.com/abdullahdevs_)
