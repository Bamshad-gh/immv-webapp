# cases/crawler/pipeline.py
# ─────────────────────────────────────────────────────────────
# Main orchestration layer: ties scraper → pdf_parser → nlp_matcher → DB save.
#
# Entry point:
#   from cases.crawler.pipeline import crawl_category
#   result = crawl_category(category)
#
# What it does:
#   1. Fetch the category's source_url page (HTML)
#   2. Extract visible text → find eligibility-like sentences
#   3. Find all PDF links on the page → download + extract form fields
#   4. For each item found: run NLP matching against the requirement library
#   5. Create CrawlerSuggestion rows (status='pending') for admin review
#   6. Update category.last_crawled_at
#
# Returns:
#   {
#     'ok':           bool,
#     'created':      int,   # number of CrawlerSuggestion rows created
#     'skipped':      int,   # items not created (duplicates)
#     'warnings':     list,  # non-fatal issues (e.g. PDF parse failed)
#     'error':        str,   # fatal error message (empty on success)
#   }
#
# EXPAND: run this as a Celery task for async execution.
#   @shared_task
#   def crawl_category_task(category_id):
#       from cases.models import Category
#       from cases.crawler.pipeline import crawl_category
#       cat = Category.objects.get(id=category_id)
#       return crawl_category(cat)
#
# EXPAND: add a 'dry_run=True' parameter to preview what would be created
#         without writing to the DB — useful for testing new pages.
# ─────────────────────────────────────────────────────────────

import re
from django.utils import timezone


# ── Eligibility sentence patterns ────────────────────────────
# Sentences containing these keywords are treated as eligibility conditions.
# CUSTOMIZE: add/remove patterns based on IRCC page language conventions.
ELIGIBILITY_KEYWORDS = [
    'must be', 'must have', 'must not', 'eligible if', 'eligibility',
    'requirement', 'at least', 'minimum', 'maximum', 'at most',
    'no less than', 'no more than', 'required to', 'need to have',
    'criminal', 'valid passport', 'language test', 'education',
    'work experience', 'years of', 'months of', 'age of',
]

# IMM form code pattern: "IMM" followed by 4 digits and optional letter(s).
# Example: IMM5710, IMM5257E, IMM0008
# CUSTOMIZE: extend if Canada.ca uses other form naming conventions.
IMM_CODE_PATTERN = re.compile(r'\bIMM\s*(\d{3,5}[A-Z]*)\b', re.IGNORECASE)


def crawl_category(category) -> dict:
    """
    Full crawl pipeline for a single category.

    Steps:
      1. Validate source_url is set
      2. Fetch HTML
      3. Extract PDF links → download + parse form fields
      4. Extract eligibility sentences from page text
      5. Deduplicate against existing suggestions
      6. Create CrawlerSuggestion rows
      7. Update category.last_crawled_at

    Designed to be idempotent: re-running the same URL creates suggestions
    only for items NOT already in the review queue (status='pending').

    EXPAND: add a 'force=True' flag to re-create suggestions even if
            duplicates exist (useful when re-crawling after a major page change).
    """
    from cases.models import CrawlerSuggestion, Requirement

    result = {'ok': False, 'created': 0, 'skipped': 0, 'warnings': [], 'error': ''}

    # ── Step 1: validate ─────────────────────────────────────
    if not category.source_url:
        result['error'] = 'No source_url set on this category.'
        return result

    # ── Step 2: fetch the page ────────────────────────────────
    from .scraper import fetch_page, extract_pdf_links, extract_page_text
    fetch_result = fetch_page(category.source_url)
    if not fetch_result['ok']:
        result['error'] = f"Fetch failed: {fetch_result['error']}"
        return result

    html       = fetch_result['html']
    final_url  = fetch_result['final_url']
    page_text  = extract_page_text(html)

    # The requirement library — all active requirements for NLP matching
    library_qs = Requirement.objects.filter(is_active=True)

    # ── Step 3: process PDF links ─────────────────────────────
    pdf_links = extract_pdf_links(html, final_url)
    for pdf_link in pdf_links:
        _process_pdf_link(
            pdf_link     = pdf_link,
            category     = category,
            library_qs   = library_qs,
            result       = result,
        )

    # ── Step 4: extract eligibility sentences ─────────────────
    sentences = _extract_eligibility_sentences(page_text)
    for sentence in sentences:
        _process_eligibility_sentence(
            sentence   = sentence,
            category   = category,
            library_qs = library_qs,
            result     = result,
        )

    # ── Step 5: update last_crawled_at ────────────────────────
    category.last_crawled_at = timezone.now()
    category.save(update_fields=['last_crawled_at'])

    result['ok'] = True
    return result


# ── STEP 3 HELPER: process a PDF link ────────────────────────
def _process_pdf_link(pdf_link: dict, category, library_qs, result: dict):
    """
    Download a PDF, extract its form fields, and create CrawlerSuggestion rows.

    Creates one suggestion of type='form' for the PDF itself, then one
    suggestion of type='requirement' per extracted form field.

    WHY separate suggestion per field (not one suggestion per form):
      Each field becomes an individual requirement in the library.
      The admin reviews fields one-by-one and either links to an existing
      requirement or creates a new one.
    """
    from cases.models import CrawlerSuggestion
    from .scraper import fetch_pdf_bytes
    from .pdf_parser import extract_pdf_fields
    from .nlp_matcher import find_best_match

    pdf_url   = pdf_link['url']
    link_text = pdf_link['link_text']

    # Detect form code from URL or link text (IMM5710, IMM5257, etc.)
    imm_match = IMM_CODE_PATTERN.search(pdf_url) or IMM_CODE_PATTERN.search(link_text)
    form_code = ('IMM' + imm_match.group(1).upper()) if imm_match else ''
    form_name = link_text or form_code or pdf_url.split('/')[-1]

    # Create one 'form' suggestion for the PDF itself
    suggestion_key = f'form|{pdf_url}'
    if not _suggestion_exists(category, suggestion_key):
        CrawlerSuggestion.objects.create(
            category         = category,
            suggestion_type  = 'form',
            raw_text         = suggestion_key,
            suggested_name   = form_name[:255],
            suggested_url    = pdf_url[:500],
        )
        result['created'] += 1
    else:
        result['skipped'] += 1

    # Download and parse the PDF
    pdf_result = fetch_pdf_bytes(pdf_url)
    if not pdf_result['ok']:
        result['warnings'].append(f"PDF download failed: {pdf_url} — {pdf_result['error']}")
        return

    fields = extract_pdf_fields(pdf_result['data'])
    if not fields:
        result['warnings'].append(f"No fields extracted from: {pdf_url}")
        return

    # Create one 'requirement' suggestion per form field
    for field in fields:
        label      = field['label'] or field['field_id']
        # Deduplicate: skip info/signature fields — they're not requirements
        if field['field_type'] in ('signature',):
            continue

        suggestion_key = f'req|{pdf_url}|{field["field_id"]}'
        if _suggestion_exists(category, suggestion_key):
            result['skipped'] += 1
            continue

        # NLP match against the library
        match = find_best_match(label, library_qs)

        CrawlerSuggestion.objects.create(
            category            = category,
            suggestion_type     = 'requirement',
            raw_text            = suggestion_key,
            suggested_name      = label[:255],
            suggested_type      = _map_field_type(field['field_type']),
            matched_requirement = match['requirement'],
            match_confidence    = match['confidence'],
        )
        result['created'] += 1


# ── STEP 4 HELPER: process eligibility sentence ───────────────
def _process_eligibility_sentence(sentence: str, category, library_qs, result: dict):
    """
    Create a 'eligibility' CrawlerSuggestion for one sentence.

    Also tries to parse the operator/value from the sentence so the admin
    has a pre-filled starting point when setting up the eligibility gate.
    """
    from cases.models import CrawlerSuggestion
    from .nlp_matcher import find_best_match, parse_eligibility_sentence

    suggestion_key = f'elig|{sentence[:200]}'
    if _suggestion_exists(category, suggestion_key):
        result['skipped'] += 1
        return

    # NLP match: does this sentence correspond to an existing requirement?
    match  = find_best_match(sentence, library_qs)
    parsed = parse_eligibility_sentence(sentence)

    CrawlerSuggestion.objects.create(
        category             = category,
        suggestion_type      = 'eligibility',
        raw_text             = suggestion_key,
        suggested_name       = sentence[:255],
        matched_requirement  = match['requirement'],
        match_confidence     = match['confidence'],
        eligibility_operator = parsed['operator'],
        eligibility_value    = parsed['value'],
    )
    result['created'] += 1


# ── HELPERS ───────────────────────────────────────────────────

def _extract_eligibility_sentences(text: str) -> list[str]:
    """
    Split the page text into sentences and return only the ones that
    contain eligibility-related keywords.

    WHY sentence splitting (not just keyword search):
      We want the full sentence as context for NLP matching and admin review.
      A keyword match with surrounding words gives much better parse quality
      than just the keyword itself.

    EXPAND: use spaCy's sentence segmentation for more accurate splits:
      import spacy
      nlp = spacy.load('en_core_web_sm')
      doc = nlp(text)
      return [sent.text for sent in doc.sents if _is_eligibility(sent.text)]
    """
    # Simple sentence splitter: split on '. ' or '; ' or '\n'
    raw_sentences = re.split(r'(?<=[.!?;])\s+|\n+', text)

    eligibility = []
    seen        = set()

    for sentence in raw_sentences:
        sentence = sentence.strip()
        if len(sentence) < 15 or len(sentence) > 300:
            # Too short (noise) or too long (a paragraph, not a sentence)
            continue

        lower = sentence.lower()
        if any(kw in lower for kw in ELIGIBILITY_KEYWORDS):
            # Deduplicate (same sentence may appear multiple times on the page)
            norm = re.sub(r'\s+', ' ', lower)
            if norm not in seen:
                seen.add(norm)
                eligibility.append(sentence)

    # Cap at 50 sentences to prevent spamming the review queue on dense pages.
    # CUSTOMIZE: increase if pages legitimately have more than 50 eligibility conditions.
    return eligibility[:50]


def _suggestion_exists(category, raw_text: str) -> bool:
    """
    Check if a pending suggestion with this raw_text already exists for this category.
    Prevents duplicate suggestions when the same URL is re-crawled.

    WHY only check 'pending': accepted/rejected suggestions should not block
    re-crawling — if the page changes, the admin may need a fresh pending suggestion.
    """
    from cases.models import CrawlerSuggestion
    return CrawlerSuggestion.objects.filter(
        category = category,
        raw_text = raw_text,
        status   = 'pending',
    ).exists()


def _map_field_type(pdf_field_type: str) -> str:
    """
    Map a PDF field type to a Requirement type string.
    These are the valid type choices on the Requirement model.

    EXPAND: add more mappings as new PDF field types are discovered.
    """
    mapping = {
        'text':     'text',
        'checkbox': 'boolean',
        'radio':    'boolean',
        'dropdown': 'select',
        'signature':'file',     # treat signature as a file upload
    }
    return mapping.get(pdf_field_type, 'text')
