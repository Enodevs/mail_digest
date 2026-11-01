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

    if TOKEN_FILE.is_file():
        creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)

    if creds and creds.valid:
        return creds

    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
        TOKEN_FILE.write_text(creds.to_json())
        return creds

    flow = InstalledAppFlow.from_client_secrets_file(
        CREDENTIALS_FILE,
        SCOPES,
    )

    creds = flow.run_local_server(port=0)

    TOKEN_FILE.write_text(creds.to_json())

    return creds

def get_gmail_service():
    creds = get_google_credentials()

    gmail_client = build(
        "gmail",
        "v1",
        credentials=creds
    )

    return gmail_client

def get_calendar_service():
    creds = get_google_credentials()

    calendar_client = build(
        "calendar",
        "v3",
        credentials=creds
    )

    return calendar_client
