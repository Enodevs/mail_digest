
import json
import os
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

BASE_DIR = Path(__file__).resolve().parent.parent
CREDENTIALS_FILE = BASE_DIR / "credentials.json"
TOKEN_FILE = BASE_DIR / "token.json"

GMAIL_SCOPES = [
    "https://www.googleapis.com/auth/gmail.modify",
]

CALENDAR_SCOPES = [
    "https://www.googleapis.com/auth/calendar",
]

SCOPES = GMAIL_SCOPES + CALENDAR_SCOPES


def get_google_credentials():
    creds = None
    token_json = os.getenv("GOOGLE_TOKEN_JSON")

    if token_json:
        creds = Credentials.from_authorized_user_info(
            json.loads(token_json),
            SCOPES,
        )
    elif TOKEN_FILE.is_file():
        creds = Credentials.from_authorized_user_file(
            TOKEN_FILE,
            SCOPES,
        )

    if creds and creds.valid:
        return creds

    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())

        if not token_json:
            TOKEN_FILE.write_text(creds.to_json())

        return creds

    # Browser-based OAuth is only for local development.
    if os.getenv("RENDER"):
        raise RuntimeError(
            "Google credentials are missing or invalid. "
            "Set GOOGLE_TOKEN_JSON in Render environment variables."
        )

    if not CREDENTIALS_FILE.is_file():
        raise FileNotFoundError(
            f"Google credentials file not found: {CREDENTIALS_FILE}"
        )

    flow = InstalledAppFlow.from_client_secrets_file(
        CREDENTIALS_FILE,
        SCOPES,
    )

    creds = flow.run_local_server(port=0)
    TOKEN_FILE.write_text(creds.to_json())

    return creds


def get_gmail_service():
    creds = get_google_credentials()
    return build("gmail", "v1", credentials=creds)


def get_calendar_service():
    creds = get_google_credentials()
    return build("calendar", "v3", credentials=creds)
