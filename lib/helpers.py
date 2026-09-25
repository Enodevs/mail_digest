import base64
import re


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

def clean_up(txt) -> str:
    clean = re.sub(r"<[^>]+>", " ", txt)
    clean = re.sub(r"\s+", " ", clean).strip()
    return clean[:4000]

def extract_body(msg) -> str:
    text = msg.text
    if text:
        return text.strip()
    html = msg.html
    if html:
        return clean_up(html)
    return ""


def decode_body(data: str):
    return base64.urlsafe_b64decode(data).decode("utf-8")


def tool_extract_body(payload):
    if payload.get("body", {}).get("data"):
        return decode_body(payload["body"]["data"])

    for part in payload.get("parts", []):
        if part.get("mimeType") == "text/plain":
            data = part.get("body", {}).get("data")
            if data:
                return decode_body(data)

        if part.get("mimeType") == "text/html":
            data = part.get("body", {}).get("data")
            if data:
                data_decoded = decode_body(data)
                clean_data = clean_up(data_decoded)
                return clean_data

    return ""
