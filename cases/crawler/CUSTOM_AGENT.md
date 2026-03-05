# Custom Agent Integration Guide

This guide explains how to connect your own AI agent or browser automation tool
to the immigration crawler. Three independent hooks are available — you can
enable them one at a time, in any combination.

---

## Why a Custom Agent?

The built-in crawler uses Python's `urllib`, which government sites like
**canada.ca** block with a **403 Forbidden** error (bot protection).

The built-in NLP matcher uses `difflib` (string similarity), which misses
semantic matches ("DOB" ≠ "Date of Birth").

The built-in eligibility parser uses regex, which breaks on complex legal
phrasing ("applicants must not have been convicted of an indictable offence").

Your custom agent — running a real browser or a language model — solves all three.

---

## Settings Overview

Add any of these to your `config/settings.py`. All are optional and independent.

| Setting key | Hook it enables | Default |
|---|---|---|
| `FETCH_WEBHOOK_URL` | Page fetching (bypass 403) | Not set — uses urllib |
| `CUSTOM_AGENT_NLP_URL` | Requirement matching | Not set — uses difflib |
| `CUSTOM_AGENT_ELIGIBILITY_URL` | Eligibility parsing | Not set — uses regex |

Example `settings.py` block:

```python
# Custom agent hooks — comment out any you don't want to use.
FETCH_WEBHOOK_URL              = 'http://localhost:8001/fetch/'
CUSTOM_AGENT_NLP_URL           = 'http://localhost:8001/nlp/match/'
CUSTOM_AGENT_ELIGIBILITY_URL   = 'http://localhost:8001/eligibility/parse/'
```

---

## Hook 1 — Page Fetch (`FETCH_WEBHOOK_URL`)

**When it's called:** Every time the crawler fetches a government page.

**Payload Django sends to your agent:**
```json
{"url": "https://www.canada.ca/en/immigration-refugees-citizenship/..."}
```

**Response your agent must return:**
```json
{
  "ok": true,
  "html": "<html>...</html>",
  "final_url": "https://www.canada.ca/en/...",
  "error": ""
}
```
On failure: `{"ok": false, "html": "", "final_url": "...", "error": "reason"}`

**What your agent needs to do:**
- Use a real browser (Playwright, Puppeteer, Selenium) to load the page
- Return the full page HTML after JavaScript has rendered
- Follow redirects — `final_url` should be the actual URL after any redirects

**Timeout:** 30 seconds (set in `_webhook.py:call_webhook(timeout=30)`).
Increase if your browser is slow to start.

---

## Hook 2 — NLP Matching (`CUSTOM_AGENT_NLP_URL`)

**When it's called:** For each field name / text block extracted by the crawler,
to find the closest existing `Requirement` in the library.

**Also:** Change `NLP_ENGINE = 'custom_agent'` in `nlp_matcher.py` to always
use your agent for NLP matching (not just when the built-in returns no match).

**Payload Django sends:**
```json
{
  "query": "Date of Birth (DD/MM/YYYY)",
  "requirements": [
    {"id": 12, "name": "Date of Birth"},
    {"id": 7,  "name": "Passport Number"},
    {"id": 3,  "name": "Family Name"}
  ]
}
```

**Response your agent must return:**
```json
{"requirement_id": 12, "confidence": 0.97}
```
No match: `{"requirement_id": null, "confidence": 0.0}`

**Confidence threshold:** Results below `MIN_CONFIDENCE = 0.60` (set in `nlp_matcher.py`)
are treated as "no match" — admin creates a new requirement from scratch.

---

## Hook 3 — Eligibility Parsing (`CUSTOM_AGENT_ELIGIBILITY_URL`)

**When it's called:** For each sentence on a government page that looks like
an eligibility condition (e.g. "Must be at least 18 years old").

**Payload Django sends:**
```json
{"sentence": "Must have arrived in Canada on or before February 28, 2025"}
```

**Response your agent must return:**
```json
{"operator": "on_or_before_date", "value": "2025-02-28"}
```
Not parseable: `{"operator": "", "value": ""}`

**Valid operators** (must match `Requirement.eligibility_operator` choices):

| Operator | Meaning |
|---|---|
| `on_or_before_date` | Answer date ≤ value |
| `before_date` | Answer date < value |
| `on_or_after_date` | Answer date ≥ value |
| `after_date` | Answer date > value |
| `equals` | Answer == value |
| `not_equals` | Answer != value |
| `yes` | Boolean answer must be Yes |
| `no` | Boolean answer must be No |
| `contains` | Answer string contains value |

---

## Minimal FastAPI Agent (Copy-Paste)

Install: `pip install fastapi uvicorn playwright`
Run: `uvicorn agent:app --port 8001`

```python
# agent.py — minimal custom agent for all three hooks
from fastapi import FastAPI
from pydantic import BaseModel
from playwright.sync_api import sync_playwright
import difflib

app = FastAPI()


# ── Hook 1: Page fetch ────────────────────────────────────────
class FetchRequest(BaseModel):
    url: str

@app.post('/fetch/')
def fetch(req: FetchRequest):
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page    = browser.new_page()
            page.goto(req.url, timeout=30000, wait_until='networkidle')
            html      = page.content()
            final_url = page.url
            browser.close()
        return {'ok': True, 'html': html, 'final_url': final_url, 'error': ''}
    except Exception as e:
        return {'ok': False, 'html': '', 'final_url': req.url, 'error': str(e)}


# ── Hook 2: NLP match ─────────────────────────────────────────
class NlpRequest(BaseModel):
    query: str
    requirements: list[dict]   # [{"id": N, "name": "..."}]

@app.post('/nlp/match/')
def nlp_match(req: NlpRequest):
    if not req.requirements:
        return {'requirement_id': None, 'confidence': 0.0}

    best_id    = None
    best_score = 0.0
    query_l    = req.query.lower()

    for r in req.requirements:
        score = difflib.SequenceMatcher(None, query_l, r['name'].lower()).ratio()
        if score > best_score:
            best_score = score
            best_id    = r['id']

    # REPLACE: call your LLM here instead of difflib for semantic matching.
    # Example with ollama: import ollama; ollama.chat(model='llama3', messages=[...])

    if best_score < 0.6:
        return {'requirement_id': None, 'confidence': 0.0}
    return {'requirement_id': best_id, 'confidence': round(best_score, 3)}


# ── Hook 3: Eligibility parse ─────────────────────────────────
class EligibilityRequest(BaseModel):
    sentence: str

@app.post('/eligibility/parse/')
def eligibility_parse(req: EligibilityRequest):
    # REPLACE: call your LLM here.
    # This stub always returns "not parsed" — Django falls back to its regex.
    # Example prompt for any LLM:
    #   f"Parse this eligibility condition: '{req.sentence}'
    #     Return JSON: {\"operator\": \"gte\", \"value\": \"18\"}
    #     Valid operators: on_or_before_date, before_date, on_or_after_date, after_date,
    #                      equals, not_equals, yes, no, contains.
    #     Return {\"operator\": \"\", \"value\": \"\"} if not parseable."
    return {'operator': '', 'value': ''}
```

---

## LLM Agent with Claude API (Hook 2 + 3)

```python
import anthropic, json
from fastapi import FastAPI
from pydantic import BaseModel

app    = FastAPI()
client = anthropic.Anthropic()   # reads ANTHROPIC_API_KEY from environment

class NlpRequest(BaseModel):
    query: str
    requirements: list[dict]

@app.post('/nlp/match/')
def nlp_match(req: NlpRequest):
    numbered = '\n'.join(f"{i+1}. {r['name']}" for i, r in enumerate(req.requirements))
    prompt   = (
        f'Match this text to the closest requirement:\n"{req.query}"\n\n'
        f'Requirements:\n{numbered}\n\n'
        f'Reply with ONLY: <number> <confidence 0-100>\n'
        f'Reply "0 0" if nothing matches well (below 60%).'
    )
    msg   = client.messages.create(model='claude-haiku-4-5-20251001',
                                   max_tokens=10,
                                   messages=[{'role':'user','content':prompt}])
    parts = msg.content[0].text.strip().split()
    if len(parts) >= 2 and parts[0].isdigit() and parts[1].isdigit():
        idx  = int(parts[0]) - 1
        conf = int(parts[1]) / 100.0
        if 0 <= idx < len(req.requirements) and conf >= 0.6:
            return {'requirement_id': req.requirements[idx]['id'], 'confidence': conf}
    return {'requirement_id': None, 'confidence': 0.0}


class EligibilityRequest(BaseModel):
    sentence: str

@app.post('/eligibility/parse/')
def eligibility_parse(req: EligibilityRequest):
    prompt = (
        f'Parse this eligibility condition: "{req.sentence}"\n'
        f'Return ONLY valid JSON: {{"operator": "...", "value": "..."}}\n'
        f'Valid operators: on_or_before_date, before_date, on_or_after_date, after_date, '
        f'equals, not_equals, yes, no, contains.\n'
        f'Return {{"operator": "", "value": ""}} if not parseable.'
    )
    msg  = client.messages.create(model='claude-haiku-4-5-20251001',
                                  max_tokens=40,
                                  messages=[{'role':'user','content':prompt}])
    try:
        return json.loads(msg.content[0].text.strip())
    except Exception:
        return {'operator': '', 'value': ''}
```

---

## Testing Each Hook Independently

Use `curl` to test before connecting to Django:

```bash
# Hook 1 — page fetch
curl -X POST http://localhost:8001/fetch/ \
     -H "Content-Type: application/json" \
     -d '{"url":"https://www.canada.ca/en/immigration-refugees-citizenship/services/iran.html"}'

# Hook 2 — NLP match
curl -X POST http://localhost:8001/nlp/match/ \
     -H "Content-Type: application/json" \
     -d '{"query":"Date of Birth","requirements":[{"id":1,"name":"Date of Birth"},{"id":2,"name":"Passport Number"}]}'

# Hook 3 — eligibility parse
curl -X POST http://localhost:8001/eligibility/parse/ \
     -H "Content-Type: application/json" \
     -d '{"sentence":"Applicant must be at least 18 years old"}'
```

---

## Fallback Behaviour

If your agent is not running or returns unexpected data, Django **silently falls back**
to the built-in implementation — urllib, difflib, or regex. Nothing breaks.
Check `Django runserver` console output for crawler error details.
