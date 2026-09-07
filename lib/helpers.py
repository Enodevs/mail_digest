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
