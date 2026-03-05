# cases/crawler/scraper.py
# ─────────────────────────────────────────────────────────────
# HTTP layer: fetch pages and find PDF links.
#
# WHY keep this separate from pipeline.py:
#   - Easy to swap the HTTP library (requests → httpx → playwright) without
#     touching the parsing or matching logic.
#   - Unit-testable in isolation with mock responses.
#
# REPLACE / UPGRADE:
#   Current implementation uses Python's built-in urllib (no extra packages).
#   OPTION A: pip install requests → replace _fetch_url() with requests.get()
#   OPTION B: pip install playwright → replace with browser automation for JS-heavy pages.
#             Use this if IRCC pages render eligibility info via JavaScript.
#   OPTION C: pip install httpx → async HTTP for better performance.
# ─────────────────────────────────────────────────────────────

import urllib.request
import urllib.error
import ssl
import re


# ── Constants ────────────────────────────────────────────────
# Default headers mimic a real browser to avoid bot blocks.
# CUSTOMIZE: update the User-Agent string if IRCC blocks requests.
DEFAULT_HEADERS = {
    'User-Agent': (
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
        'AppleWebKit/537.36 (KHTML, like Gecko) '
        'Chrome/120.0.0.0 Safari/537.36'
    ),
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.5',
}

# Maximum number of bytes to read from a PDF (prevents huge downloads).
# CUSTOMIZE: increase if government PDFs are larger than 10 MB.
MAX_PDF_BYTES = 10 * 1024 * 1024  # 10 MB

# Request timeout in seconds.
# CUSTOMIZE: increase if the government site is slow.
HTTP_TIMEOUT = 30


def fetch_page(url: str) -> dict:
    """
    Fetch an HTML page from the given URL.

    Returns a dict with:
      {
        'ok':         bool,   # True = success
        'html':       str,    # page HTML (empty on failure)
        'final_url':  str,    # URL after any redirects
        'error':      str,    # error message (empty on success)
      }

    WHY return a dict instead of raising exceptions:
      The caller (pipeline.py) needs to log errors per-category without crashing.
      Exceptions would bubble up and stop the entire pipeline — a failed page
      should just be logged as an error, not crash the crawl job.

    CUSTOM AGENT HOOK (FETCH_WEBHOOK_URL):
      Set in settings.py to route page fetches through a custom agent with a real
      browser (Playwright, Puppeteer, Selenium). This bypasses bot protection on
      government sites like canada.ca that block Python's urllib with a 403.

      In settings.py:
          FETCH_WEBHOOK_URL = 'http://localhost:8001/fetch/'

      Your agent receives:  {"url": "https://canada.ca/..."}
      Your agent returns:   {"ok": true, "html": "...", "final_url": "...", "error": ""}

      See cases/crawler/CUSTOM_AGENT.md for a complete integration guide.

    WHY two SSL contexts (verified + unverified fallback):
      Some government servers occasionally fail Python's SSL certificate verification
      due to intermediate CA mismatches or outdated Python CA bundles. We try the
      secure context first; if it raises SSLError we silently retry without verification.
      NOTE: unverified HTTPS is still encrypted — just not authenticated.

    UPGRADE TO REQUESTS (recommended for production):
      pip install requests
      import requests
      resp = requests.get(url, headers=DEFAULT_HEADERS, timeout=HTTP_TIMEOUT, allow_redirects=True)
      return {'ok': True, 'html': resp.text, 'final_url': resp.url, 'error': ''}

    UPGRADE TO PLAYWRIGHT (for JS-rendered pages):
      from playwright.sync_api import sync_playwright
      with sync_playwright() as p:
          browser = p.chromium.launch()
          page = browser.new_page()
          page.goto(url)
          html = page.content()
          browser.close()
      return {'ok': True, 'html': html, 'final_url': url, 'error': ''}
    """
    # ── HOOK: custom agent page fetch ────────────────────────────────
    # If FETCH_WEBHOOK_URL is set in settings.py, delegate to the custom agent.
    # WHY check this FIRST (before the urllib loop):
    #   The whole point of the webhook is to bypass urllib's limitations — if it's
    #   configured, we should always use it rather than letting urllib try and fail.
    # WHY fall through to urllib if webhook returns None:
    #   call_webhook() returns None on any error (timeout, agent not running, etc.).
    #   Falling through gives the admin a result (possibly a 403) rather than silence.
    from django.conf import settings
    from ._webhook import call_webhook

    webhook_url = getattr(settings, 'FETCH_WEBHOOK_URL', None)
    if webhook_url:
        result = call_webhook(webhook_url, {'url': url}, timeout=30)
        if result is not None:
            # Agent responded — normalise to the expected shape and return.
            # The agent MUST return the same keys: ok, html, final_url, error.
            return {
                'ok':        bool(result.get('ok', False)),
                'html':      result.get('html', ''),
                'final_url': result.get('final_url', url),
                'error':     result.get('error', ''),
            }
        # Agent is not responding — fall through to built-in urllib below.

    # ── Built-in urllib fetch ─────────────────────────────────────────
    # Build two SSL contexts: verified first (secure), unverified as fallback.
    # CUSTOMIZE: set VERIFY_SSL = False globally to always skip verification.
    ssl_contexts = [
        ssl.create_default_context(),           # secure: checks certificate chain
        _make_unverified_ssl_context(),         # fallback: encrypted but no cert check
    ]

    last_error = ''

    for ctx in ssl_contexts:
        try:
            # build_opener lets us pass a custom SSL context and follow redirects.
            # HTTPRedirectHandler is included by default but listed explicitly for clarity.
            opener = urllib.request.build_opener(
                urllib.request.HTTPSHandler(context=ctx),
                urllib.request.HTTPRedirectHandler(),
            )
            req = urllib.request.Request(url, headers=DEFAULT_HEADERS)
            with opener.open(req, timeout=HTTP_TIMEOUT) as response:
                # Read and decode — try UTF-8 first (most gov pages), fall back to latin-1.
                raw = response.read()
                try:
                    html = raw.decode('utf-8')
                except UnicodeDecodeError:
                    html = raw.decode('latin-1', errors='replace')
                return {
                    'ok':        True,
                    'html':      html,
                    'final_url': response.geturl(),
                    'error':     '',
                }
        except ssl.SSLError:
            # SSL verification failed — try again with the next (unverified) context.
            # WHY continue instead of returning: the unverified context may succeed.
            last_error = 'SSL certificate verification failed; retried without verification'
            continue
        except urllib.error.HTTPError as e:
            # HTTP-level error (403, 404, 500…) — don't retry with a different SSL context.
            error_msg = f'HTTP {e.code}: {e.reason}'
            # 403 means the site is actively blocking automated requests (bot protection).
            # Append an actionable hint so the admin knows the exact next step.
            if e.code == 403:
                error_msg += (
                    ' — site is blocking automated requests (bot protection). '
                    'Fix: set FETCH_WEBHOOK_URL in settings.py and connect a custom '
                    'agent with a real browser. See cases/crawler/CUSTOM_AGENT.md.'
                )
            return {'ok': False, 'html': '', 'final_url': url, 'error': error_msg}
        except urllib.error.URLError as e:
            return {'ok': False, 'html': '', 'final_url': url, 'error': f'URL error: {e.reason}'}
        except Exception as e:
            return {'ok': False, 'html': '', 'final_url': url, 'error': str(e)}

    # All contexts failed (only reachable if both raised SSLError)
    return {'ok': False, 'html': '', 'final_url': url, 'error': last_error}


def _make_unverified_ssl_context() -> ssl.SSLContext:
    """
    Create an SSL context that encrypts the connection but does NOT verify
    the server's certificate chain or hostname.

    WHY a helper function:
      Keeps the construction logic in one place — easier to find and change.
      The context is created fresh each call (not cached) because SSLContext
      objects are not thread-safe to share across requests.

    SECURITY NOTE:
      This context is only used as a fallback when the verified context fails.
      Unverified HTTPS protects against passive eavesdropping but NOT against
      a man-in-the-middle attack. Acceptable for government public pages where
      the risk is low and the data is public anyway.
    """
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode    = ssl.CERT_NONE
    return ctx


def fetch_pdf_bytes(pdf_url: str) -> dict:
    """
    Download a PDF file. Returns raw bytes up to MAX_PDF_BYTES.

    Returns a dict:
      {
        'ok':    bool,
        'data':  bytes,   # PDF content (empty bytes on failure)
        'error': str,
      }

    WHY cap at MAX_PDF_BYTES:
      Some government forms are bundled in large packages. We only want
      the fillable form fields, which are in the first part of the file.

    UPGRADE: use requests with streaming to handle large PDFs gracefully:
      import requests
      with requests.get(pdf_url, stream=True, timeout=HTTP_TIMEOUT) as r:
          data = b''.join(itertools.islice(r.iter_content(8192), MAX_PDF_BYTES // 8192))
    """
    try:
        req = urllib.request.Request(pdf_url, headers=DEFAULT_HEADERS)
        with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT) as response:
            data = response.read(MAX_PDF_BYTES)
        return {'ok': True, 'data': data, 'error': ''}
    except Exception as e:
        return {'ok': False, 'data': b'', 'error': str(e)}


def extract_pdf_links(html: str, base_url: str) -> list[dict]:
    """
    Find all PDF links on an HTML page.

    Returns a list of dicts:
      [
        {'url': 'https://...IMM5710E.pdf', 'link_text': 'Application for Work Permit'},
        ...
      ]

    The link_text is extracted from the <a> tag content — it's the human-readable
    label (e.g. "IMM 5710 – Application for Work Permit") which becomes the form's
    suggested name in the review queue.

    WHY regex instead of BeautifulSoup:
      Avoids a dependency. IRCC pages have predictable <a href="...pdf"> patterns.

    UPGRADE TO BEAUTIFULSOUP (more robust HTML parsing):
      pip install beautifulsoup4 lxml
      from bs4 import BeautifulSoup
      soup = BeautifulSoup(html, 'lxml')
      links = soup.find_all('a', href=re.compile(r'\.pdf', re.I))
      return [{'url': _resolve_url(link['href'], base_url), 'link_text': link.get_text(strip=True)} for link in links]
    """
    # Find all <a href="...pdf...">text</a> patterns (case-insensitive)
    # Capture group 1: href value, group 2: link text content (stripped of inner tags)
    pattern = re.compile(
        r'<a[^>]+href=["\']([^"\']*\.pdf[^"\']*)["\'][^>]*>(.*?)</a>',
        re.IGNORECASE | re.DOTALL,
    )

    results = []
    seen_urls = set()    # dedup — the same PDF may be linked multiple times

    for match in pattern.finditer(html):
        raw_href  = match.group(1).strip()
        link_text = re.sub(r'<[^>]+>', '', match.group(2)).strip()  # strip inner HTML tags

        # Resolve relative URLs (e.g. "/content/dam/ircc/forms/...")
        pdf_url = _resolve_url(raw_href, base_url)

        if pdf_url and pdf_url not in seen_urls:
            seen_urls.add(pdf_url)
            results.append({'url': pdf_url, 'link_text': link_text or pdf_url.split('/')[-1]})

    return results


def extract_page_text(html: str) -> str:
    """
    Strip HTML tags and return the visible text of the page.
    Used by nlp_matcher.py to extract eligibility sentences.

    WHY not use BeautifulSoup:
      Same reason as above — avoiding dependencies. The regex approach
      is good enough for extracting plain text from government pages.

    UPGRADE: replace with BeautifulSoup for more accurate text extraction:
      from bs4 import BeautifulSoup
      soup = BeautifulSoup(html, 'lxml')
      for script in soup(['script', 'style', 'nav', 'footer']): script.decompose()
      return soup.get_text(separator=' ', strip=True)
    """
    # Remove script and style blocks entirely
    html = re.sub(r'<(script|style)[^>]*>.*?</\1>', ' ', html, flags=re.DOTALL | re.IGNORECASE)
    # Remove all remaining tags
    text = re.sub(r'<[^>]+>', ' ', html)
    # Collapse whitespace
    text = re.sub(r'\s+', ' ', text)
    return text.strip()


def _resolve_url(href: str, base_url: str) -> str:
    """
    Resolve a potentially relative URL against the page's base URL.

    Examples:
      '/content/dam/ircc/forms/imm5710e.pdf' + 'https://canada.ca/en/immigration...'
      → 'https://canada.ca/content/dam/ircc/forms/imm5710e.pdf'

    UPGRADE: use urllib.parse.urljoin (already built-in — just add the import):
      from urllib.parse import urljoin
      return urljoin(base_url, href)
    """
    from urllib.parse import urljoin
    if not href:
        return ''
    return urljoin(base_url, href)
