# cases/crawler/nlp_matcher.py
# ─────────────────────────────────────────────────────────────
# NLP matching: find the best existing Requirement in the library
# for a given piece of text extracted by the crawler.
#
# WHY NLP matching?
#   The same concept can be phrased many ways:
#     "Date of birth" / "Date of Birth (DD/MM/YYYY)" / "DOB" / "Birth Date"
#   Without matching, the crawler would create duplicate requirements.
#   The matcher suggests the closest existing requirement so the admin
#   can accept the link (reuse) or create a new one.
#
# ── Replacing the NLP Engine ─────────────────────────────────
#
# CURRENT IMPLEMENTATION: difflib.SequenceMatcher (built-in, no packages needed)
#   - Works well for near-identical strings
#   - Poor on semantic similarity ("passport expiry" vs "passport expiration date")
#   - Sufficient for a first pass with admin review
#
# UPGRADE A — sentence-transformers (best quality, local model):
#   pip install sentence-transformers
#   model = SentenceTransformer('all-MiniLM-L6-v2')  # small, fast, good
#   embeddings = model.encode(texts)
#   similarity = cosine_similarity([query_vec], embeddings)
#   → See _match_with_sentence_transformers() below for the full implementation stub
#
# UPGRADE B — spaCy (medium quality, adds linguistic features):
#   pip install spacy && python -m spacy download en_core_web_md
#   doc1 = nlp(text1); doc2 = nlp(text2); score = doc1.similarity(doc2)
#   → See _match_with_spacy() below
#
# UPGRADE C — Claude API (highest quality, requires API key):
#   Send the extracted text + library requirement names to Claude and ask it to
#   pick the best match or say "no match". Useful for complex eligibility sentences.
#   → See _match_with_claude() below for the integration stub
#
# UPGRADE D — Custom local LLM (Ollama, LlamaCpp):
#   Same pattern as Claude API but using a local model.
#   Replace _call_claude_api() with _call_local_llm().
#
# SWITCH ENGINE: change NLP_ENGINE constant below.
# ─────────────────────────────────────────────────────────────

import difflib


# CUSTOMIZE: set to 'difflib' (default), 'sentence_transformers', 'spacy', 'claude',
#            or 'custom_agent' to use your own NLP webhook (see CUSTOM_AGENT.md).
NLP_ENGINE = 'difflib'

# The minimum score (0.0–1.0) to consider a match "good enough" to suggest.
# Below this threshold → matched_requirement = None (admin creates from scratch).
# CUSTOMIZE: lower = more aggressive matching (more false positives);
#            higher = more conservative (more "no match" results).
MIN_CONFIDENCE = 0.60


def find_best_match(query_text: str, requirement_queryset) -> dict:
    """
    Find the best matching Requirement from the library for the given text.

    Args:
        query_text:            the raw text from the crawler (field name, sentence, etc.)
        requirement_queryset:  a Django queryset of Requirement objects to search against
                               (typically: Requirement.objects.filter(is_active=True))

    Returns:
        {
          'requirement': <Requirement object or None>,  # best match, or None if below threshold
          'confidence':  float,                         # 0.0–1.0 similarity score
          'engine':      str,                           # which engine was used
        }

    EXPAND: cache requirement embeddings to avoid recomputing on every call.
            Store embeddings in a Redis cache or a local numpy file.
    """
    if not query_text or not requirement_queryset.exists():
        return {'requirement': None, 'confidence': 0.0, 'engine': NLP_ENGINE}

    if NLP_ENGINE == 'sentence_transformers':
        return _match_with_sentence_transformers(query_text, requirement_queryset)
    elif NLP_ENGINE == 'spacy':
        return _match_with_spacy(query_text, requirement_queryset)
    elif NLP_ENGINE == 'claude':
        return _match_with_claude(query_text, requirement_queryset)
    elif NLP_ENGINE == 'custom_agent':
        # Delegate to your custom agent via CUSTOM_AGENT_NLP_URL in settings.py.
        # Falls back to difflib if the agent is unreachable.
        return _match_with_custom_agent(query_text, requirement_queryset)
    else:
        return _match_with_difflib(query_text, requirement_queryset)


# ── ENGINE A: difflib (DEFAULT — no install needed) ──────────
def _match_with_difflib(query_text: str, requirement_queryset) -> dict:
    """
    Use Python's built-in difflib.SequenceMatcher for string similarity.
    Fast and dependency-free. Works well when text is nearly identical.
    Weak on semantic similarity.

    REPLACE WITH: _match_with_sentence_transformers() for semantic matching.
    """
    query_lower = query_text.lower().strip()

    best_score = 0.0
    best_req   = None

    for req in requirement_queryset:
        # Compare against both name and description for better coverage
        candidates = [req.name]
        if hasattr(req, 'description') and req.description:
            candidates.append(req.description[:200])

        for candidate in candidates:
            ratio = difflib.SequenceMatcher(
                None,
                query_lower,
                candidate.lower().strip(),
            ).ratio()

            if ratio > best_score:
                best_score = ratio
                best_req   = req

    # Apply minimum confidence threshold
    if best_score < MIN_CONFIDENCE:
        best_req = None

    return {
        'requirement': best_req,
        'confidence':  round(best_score, 3),
        'engine':      'difflib',
    }


# ── ENGINE B: sentence-transformers (UPGRADE for semantic matching) ──
def _match_with_sentence_transformers(query_text: str, requirement_queryset) -> dict:
    """
    Use sentence-transformers for semantic embedding-based matching.
    This understands that "DOB" and "Date of Birth" are the same concept.

    Install:
        pip install sentence-transformers

    Recommended models (trade-off: size vs quality):
        'all-MiniLM-L6-v2'       — small (80MB), fast, good quality (recommended start)
        'all-mpnet-base-v2'       — medium (420MB), best quality
        'paraphrase-multilingual' — add this if you need French/English matching

    EXPAND: persist the model in memory across requests using Django's AppConfig.ready()
            to avoid reloading the model on each AJAX call (it's slow to load).
    """
    try:
        from sentence_transformers import SentenceTransformer, util  # noqa: F401
        import numpy as np

        # CUSTOMIZE: change model name here. First run downloads it (~80MB for MiniLM).
        MODEL_NAME = 'all-MiniLM-L6-v2'
        model = SentenceTransformer(MODEL_NAME)

        requirements = list(requirement_queryset)
        if not requirements:
            return {'requirement': None, 'confidence': 0.0, 'engine': 'sentence_transformers'}

        req_texts    = [req.name for req in requirements]
        query_embed  = model.encode(query_text, convert_to_tensor=True)
        corpus_embed = model.encode(req_texts, convert_to_tensor=True)

        # Cosine similarity between query and all requirements
        scores = util.cos_sim(query_embed, corpus_embed)[0].cpu().numpy()
        best_idx   = int(np.argmax(scores))
        best_score = float(scores[best_idx])
        best_req   = requirements[best_idx] if best_score >= MIN_CONFIDENCE else None

        return {
            'requirement': best_req,
            'confidence':  round(best_score, 3),
            'engine':      'sentence_transformers',
        }
    except ImportError:
        # Fall back to difflib if sentence-transformers is not installed
        return _match_with_difflib(query_text, requirement_queryset)


# ── ENGINE C: spaCy (UPGRADE for linguistic similarity) ──────
def _match_with_spacy(query_text: str, requirement_queryset) -> dict:
    """
    Use spaCy for word-vector similarity matching.

    Install:
        pip install spacy
        python -m spacy download en_core_web_md

    Models: en_core_web_sm (no vectors), en_core_web_md (300d vectors),
            en_core_web_lg (same but larger vocab).
    Use en_core_web_md for best balance.

    EXPAND: add French model (fr_core_news_md) for bilingual IRCC pages.
    """
    try:
        import spacy

        # CUSTOMIZE: change to 'en_core_web_lg' for larger vocabulary
        MODEL_NAME = 'en_core_web_md'
        nlp = spacy.load(MODEL_NAME)

        query_doc  = nlp(query_text)
        best_score = 0.0
        best_req   = None

        for req in requirement_queryset:
            req_doc = nlp(req.name)
            score   = query_doc.similarity(req_doc)
            if score > best_score:
                best_score = score
                best_req   = req

        if best_score < MIN_CONFIDENCE:
            best_req = None

        return {
            'requirement': best_req,
            'confidence':  round(best_score, 3),
            'engine':      'spacy',
        }
    except (ImportError, OSError):
        return _match_with_difflib(query_text, requirement_queryset)


# ── ENGINE D: Claude API (HIGHEST QUALITY) ───────────────────
def _match_with_claude(query_text: str, requirement_queryset) -> dict:
    """
    Ask Claude to pick the best matching requirement.
    Understands context, bilingual text, abbreviations, and legal phrasing.

    Install:
        pip install anthropic

    Set API key:
        In settings.py: ANTHROPIC_API_KEY = 'sk-ant-...'
        Or via environment variable: ANTHROPIC_API_KEY

    Model: claude-haiku-4-5-20251001 (fastest + cheapest; good for classification)
    CUSTOMIZE: change to claude-sonnet-4-6 for better accuracy on complex eligibility text.

    EXPAND: batch multiple queries in a single API call to reduce cost.
    EXPAND: add caching (Redis/memcached) on (query_text, library_hash) to avoid
            re-calling the API for the same crawl text.
    """
    try:
        import anthropic
        from django.conf import settings

        api_key = getattr(settings, 'ANTHROPIC_API_KEY', None)
        if not api_key:
            # No key configured — fall back silently
            return _match_with_difflib(query_text, requirement_queryset)

        requirements = list(requirement_queryset)
        if not requirements:
            return {'requirement': None, 'confidence': 0.0, 'engine': 'claude'}

        # Build a numbered list for Claude to choose from
        numbered = '\n'.join(f'{i+1}. {req.name}' for i, req in enumerate(requirements))

        prompt = (
            f'You are matching government immigration form fields to a requirement library.\n\n'
            f'Extracted text from form/page:\n"{query_text}"\n\n'
            f'Existing library requirements:\n{numbered}\n\n'
            f'Reply with ONLY the number of the best matching requirement, '
            f'or "0" if none match well enough (confidence < 60%).\n'
            f'Reply format: <number> <confidence 0-100>\n'
            f'Example: "3 87" means requirement 3 with 87% confidence.'
        )

        client   = anthropic.Anthropic(api_key=api_key)
        message  = client.messages.create(
            # CUSTOMIZE: change model here
            model='claude-haiku-4-5-20251001',
            max_tokens=20,
            messages=[{'role': 'user', 'content': prompt}],
        )
        response = message.content[0].text.strip()

        # Parse "3 87" format
        parts = response.split()
        if len(parts) >= 2 and parts[0].isdigit():
            idx        = int(parts[0]) - 1
            confidence = int(parts[1]) / 100.0 if parts[1].isdigit() else 0.0
            if 0 <= idx < len(requirements) and confidence >= MIN_CONFIDENCE:
                return {
                    'requirement': requirements[idx],
                    'confidence':  round(confidence, 3),
                    'engine':      'claude',
                }

        return {'requirement': None, 'confidence': 0.0, 'engine': 'claude'}

    except Exception:
        return _match_with_difflib(query_text, requirement_queryset)


# ── ENGINE E: Custom agent webhook (NLP_ENGINE = 'custom_agent') ──
def _match_with_custom_agent(query_text: str, requirement_queryset) -> dict:
    """
    POST to your custom NLP agent via CUSTOM_AGENT_NLP_URL in settings.py.

    WHY a webhook engine:
      Your agent can use any NLP model — a local LLM (Ollama, LlamaCpp),
      a cloud LLM (Claude, GPT-4), or a fine-tuned sentence classifier.
      Django doesn't need to know the model — it just sends text + candidates
      and gets back the best match ID and a confidence score.

    In settings.py:
        CUSTOM_AGENT_NLP_URL = 'http://localhost:8001/nlp/match/'

    Payload your agent receives:
        {
          "query": "Date of Birth (DD/MM/YYYY)",
          "requirements": [
            {"id": 12, "name": "Date of Birth"},
            {"id": 7,  "name": "Passport Number"},
            ...
          ]
        }

    Response your agent must return:
        {"requirement_id": 12, "confidence": 0.97}   # match found
        {"requirement_id": null, "confidence": 0.0}  # no match above threshold

    Falls back to difflib if:
      - CUSTOM_AGENT_NLP_URL is not set in settings.py
      - The agent is unreachable or returns unexpected JSON

    EXPAND: add 'name' + 'description' + 'type' to each requirement in the payload
            to give your agent more context for a better match.
    """
    from django.conf import settings
    from ._webhook import call_webhook

    webhook_url = getattr(settings, 'CUSTOM_AGENT_NLP_URL', None)
    if not webhook_url:
        # Setting not configured — fall back silently.
        return _match_with_difflib(query_text, requirement_queryset)

    requirements = list(requirement_queryset)
    if not requirements:
        return {'requirement': None, 'confidence': 0.0, 'engine': 'custom_agent'}

    payload = {
        'query': query_text,
        # Send id + name so the agent can identify the best match by id.
        # EXPAND: also send 'description' and 'type' for richer context.
        'requirements': [{'id': r.id, 'name': r.name} for r in requirements],
    }

    result = call_webhook(webhook_url, payload)

    if result and result.get('requirement_id') is not None:
        req_id     = result['requirement_id']
        confidence = float(result.get('confidence', 0.0))
        # Build a lookup map so we can find the Requirement object by id.
        id_map  = {r.id: r for r in requirements}
        matched = id_map.get(req_id)
        if matched and confidence >= MIN_CONFIDENCE:
            return {
                'requirement': matched,
                'confidence':  round(confidence, 3),
                'engine':      'custom_agent',
            }

    # Agent returned null / low confidence / unexpected shape — no match.
    return {'requirement': None, 'confidence': 0.0, 'engine': 'custom_agent'}


# ── ELIGIBILITY PARSER ────────────────────────────────────────
def parse_eligibility_sentence(sentence: str) -> dict:
    """
    Attempt to extract an operator + value from an eligibility sentence.

    Examples:
      "Must be at least 18 years old"   → {'operator': 'gte', 'value': '18'}
      "Must not have a criminal record"  → {'operator': 'eq',  'value': 'no'}
      "Valid passport required"          → {'operator': 'eq',  'value': 'yes'}
      "Education: minimum Bachelor's"   → {'operator': 'eq',  'value': "bachelor's"}

    Returns:
      {
        'operator': str,   # one of: gte, lte, eq, or '' if not parsed
        'value':    str,   # the threshold value, or '' if not parsed
      }

    WHY simple regex over NLP:
      Eligibility sentences follow predictable patterns on government pages.
      Regex is deterministic and explainable — the admin can verify the parse.
      For complex sentences (legal language), the admin edits the result manually.

    EXPAND: add more patterns as new government page formats are discovered.
    EXPAND: replace with Claude API call for complex legal eligibility language.

    UPGRADE WITH CLAUDE:
      prompt = f'Parse: "{sentence}" → operator (gte/lte/eq/contains) and value.'
      Use the same _call_claude_api() pattern from _match_with_claude().

    CUSTOM AGENT HOOK (CUSTOM_AGENT_ELIGIBILITY_URL):
      Set in settings.py to delegate parsing to your custom agent FIRST.
      The agent can use an LLM that understands complex legal phrasing.
      Falls back to regex below if the agent is unreachable or returns no operator.

      In settings.py:
          CUSTOM_AGENT_ELIGIBILITY_URL = 'http://localhost:8001/eligibility/parse/'

      Payload: {"sentence": "Must have arrived in Canada on or before Feb 28, 2025"}
      Response: {"operator": "on_or_before_date", "value": "2025-02-28"}
               or {"operator": "", "value": ""} if not parseable.

      Valid operators: on_or_before_date, before_date, on_or_after_date, after_date,
                       equals, not_equals, yes, no, contains.
                       (match the eligibility_operator choices in the model)

      See cases/crawler/CUSTOM_AGENT.md for a full integration guide.
    """
    # ── HOOK: custom agent eligibility parser ────────────────────────
    # Try the custom agent BEFORE the regex — an LLM handles legal phrasing
    # that regex cannot (e.g. "applicant must not have been convicted", "citizens only").
    from django.conf import settings
    from ._webhook import call_webhook

    elig_webhook_url = getattr(settings, 'CUSTOM_AGENT_ELIGIBILITY_URL', None)
    if elig_webhook_url:
        result = call_webhook(elig_webhook_url, {'sentence': sentence})
        if result and result.get('operator'):
            # Agent parsed successfully — use its result and skip the regex below.
            return {
                'operator': result['operator'],
                'value':    str(result.get('value', '')),
            }
        # Agent returned empty operator or None — fall through to regex.

    import re

    sentence_lower = sentence.lower().strip()

    # ── Numeric patterns ─────────────────────────────────────
    # "at least 18 years"  → gte, 18
    # "minimum 5 years"    → gte, 5
    # "at most 30 days"    → lte, 30
    # "maximum 12 months"  → lte, 12
    patterns = [
        (r'at\s+least\s+(\d+)',   'gte'),
        (r'minimum\s+(\d+)',      'gte'),
        (r'no\s+less\s+than\s+(\d+)', 'gte'),
        (r'at\s+most\s+(\d+)',    'lte'),
        (r'maximum\s+(\d+)',      'lte'),
        (r'no\s+more\s+than\s+(\d+)', 'lte'),
        (r'must\s+be\s+(\d+)\s+or\s+older', 'gte'),
        (r'must\s+be\s+(\d+)\s+or\s+younger', 'lte'),
    ]
    for pattern, operator in patterns:
        m = re.search(pattern, sentence_lower)
        if m:
            return {'operator': operator, 'value': m.group(1)}

    # ── Boolean patterns ─────────────────────────────────────
    # "must not have criminal"  → eq, no
    # "must have valid passport" → eq, yes
    if re.search(r'\b(must\s+not|no\s+criminal|no\s+record)\b', sentence_lower):
        return {'operator': 'eq', 'value': 'no'}
    if re.search(r'\b(must\s+have|required|valid\s+passport)\b', sentence_lower):
        return {'operator': 'eq', 'value': 'yes'}

    # No pattern matched — admin fills this in manually
    return {'operator': '', 'value': ''}
