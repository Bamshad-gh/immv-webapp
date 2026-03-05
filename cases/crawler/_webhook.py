# cases/crawler/_webhook.py
# ─────────────────────────────────────────────────────────────
# Shared webhook caller used by all custom agent hooks in the crawler.
#
# WHY a separate file (not inline in each caller):
#   Three separate hooks (page fetch, NLP match, eligibility parse) all need
#   the same "POST JSON → get JSON back, or return None on failure" pattern.
#   Centralising it here means:
#     - One place to change error handling / logging / retry logic
#     - Each hook is one readable line:  result = call_webhook(url, payload)
#     - Easy to mock in tests:  patch('cases.crawler._webhook.call_webhook')
#
# HOW IT WORKS:
#   Your custom agent runs a web server (FastAPI, Flask, Express, etc.) that:
#     1. Listens on a local port (e.g. http://localhost:8001)
#     2. Accepts POST requests with a JSON body
#     3. Returns a JSON response
#   You set the URL in settings.py (see CUSTOM_AGENT.md for all available keys).
#   call_webhook() posts the payload and returns the parsed response.
#   Any failure (timeout, wrong JSON, network error) returns None silently —
#   the caller always falls back to the built-in implementation.
#
# SECURITY NOTE:
#   This only makes requests to localhost/LAN addresses you configure yourself.
#   Never set FETCH_WEBHOOK_URL etc. to an untrusted external URL — the webhook
#   receives the full HTML of government pages which may contain sensitive data.
#
# EXPAND: add optional HMAC request signing so your agent can verify requests
#         came from Django (not an outside caller).
#         In settings.py: WEBHOOK_SECRET = 'your-secret'
#         Here: sign the payload with HMAC-SHA256 and send as X-Webhook-Signature header.
# ─────────────────────────────────────────────────────────────

import json
import ssl
import urllib.request


def call_webhook(url: str, payload: dict, timeout: int = 10) -> dict | None:
    """
    POST a JSON payload to url and return the parsed JSON response.
    Returns None on ANY failure — callers always fall back to built-in logic.

    Args:
        url:     Full URL of your agent endpoint, e.g. 'http://localhost:8001/fetch/'
        payload: Dict that will be JSON-serialised and sent as the request body.
        timeout: Seconds before giving up. Default 10 — long enough for LAN/local,
                 short enough not to block a web request for too long.
                 CUSTOMIZE: increase if your agent does heavy inference (e.g. LLM calls).

    Returns:
        Parsed JSON dict from the agent, or None if anything went wrong.

    WHY return None instead of raising:
        Every hook that calls this function has a built-in fallback. Raising would
        force every caller to wrap in try/except — returning None lets them use:
            result = call_webhook(url, payload)
            if result:
                ... use result ...
            # else: fall through to built-in (already the next line)

    WHY urllib instead of requests:
        urllib is in Python's standard library — no extra package needed.
        This keeps _webhook.py dependency-free.
        UPGRADE: replace with `import requests; resp = requests.post(url, json=payload, timeout=timeout)`
                 if you want automatic retry, session pooling, or better error messages.

    EXPAND: add retry logic for transient failures:
        for attempt in range(3):
            result = _try_once(url, payload, timeout)
            if result is not None: return result
            time.sleep(0.5 * attempt)
        return None
    """
    try:
        # Serialise payload to JSON bytes — Content-Type header tells the agent
        # to parse it as JSON (not form data).
        data = json.dumps(payload).encode('utf-8')

        req = urllib.request.Request(
            url,
            data    = data,
            headers = {'Content-Type': 'application/json'},
            method  = 'POST',
        )

        # Use a verified SSL context for https:// webhook URLs.
        # For http:// (local agent), SSL is not used — the context is ignored.
        # CUSTOMIZE: if your agent uses a self-signed certificate, create an
        # unverified context: ctx.check_hostname = False; ctx.verify_mode = ssl.CERT_NONE
        ctx = ssl.create_default_context()

        with urllib.request.urlopen(req, timeout=timeout, context=ctx) as response:
            raw = response.read()

        # Parse JSON — returns dict on success, raises ValueError on bad JSON.
        return json.loads(raw)

    except Exception:
        # Silent failure — the caller falls back to built-in.
        # WHY not log here: this is called during AJAX requests; noisy logs would
        # fill the console every time the agent is down.
        # EXPAND: uncomment the line below to add debug logging.
        # import logging; logging.getLogger(__name__).debug('Webhook call failed: %s', url, exc_info=True)
        return None
