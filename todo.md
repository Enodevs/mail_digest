## Fixes & Improvements

- [✅] **Missing dep in pyproject.toml** — `requests` is used but not declared as a dependency (only pulled transitively via `tiktoken`)
- [✅] **Inconsistent limit defaults** — `fetch_unread_emails(limit=5)` vs `main()` calls it with `limit=6`
- [✅] **Missing return type hints** — add `-> list[...]`, `-> dict`, `-> None` on all functions
- [✅] **Slow sequential processing** — emails are analyzed one-by-one with a 1.5s sleep; could use `concurrent.futures` or `asyncio`
- [✅] **No retry on Telegram failure** — if the API call fails, the digest is silently dropped
- [✅] **Broad exception catches** — `except Exception` in fetch/analyze/send swallows errors; be more specific
- [✅] **Hardcoded IMAP host** — `"imap.gmail.com"` is hardcoded; should be configurable
- [✅] **Rough HTML body truncation** — `(msg.html or "")[:4000]` may capture garbage HTML markup instead of readable text
- [✅] **No `.env.example`** — no template for new users to know what vars to set
- [✅] **No logging module** — uses console output only; can't set log levels or route to files
