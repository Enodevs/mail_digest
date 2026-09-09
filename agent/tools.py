from agent.auth import get_gmail_service
from lib.helpers import tool_extract_body


def search_emails(query: str, max_results: int):
    gmail_client = get_gmail_service()

    results = gmail_client.users().messages().list(userId="me", q=query, maxResults=max_results).execute()

    messages = results.get("messages", [])

    return [
        {"id": message["id"], "threadId": message["threadId"]} for message in messages
    ]

def read_email(message_id: str):
    gmail_client = get_gmail_service()

    message = (
        gmail_client.users()
        .messages()
        .get(
            userId="me",
            id=message_id,
            format="full",
        )
        .execute()
    )

    payload = message["payload"]
    headers = payload.get("headers", [])
    body = tool_extract_body(payload)

    from_header = next(
        header["value"] for header in headers if header["name"].lower() == "from"
    )

    to_header = next(
        header["value"] for header in headers if header["name"].lower() == "to"
    )

    subject_header = next(
        header["value"] for header in headers if header["name"].lower() == "subject"
    )

    date_header = next(
        header["value"] for header in headers if header["name"].lower() == "date"
    )

    return {
        "id": message["id"],
        "thread_id": message["threadId"],
        "from": from_header,
        "to": to_header,
        "subject": subject_header,
        "date": date_header,
        "body": body,
    }

def get_emails(query: str, max_results: int = 10):
    messages = search_emails(query, max_results)

    emails = []

    for msg in messages:
        mail = read_email(msg["id"])

        emails.append(mail)

    return emails

TOOL_FUNCTIONS = {
    "get_emails": get_emails,
}
