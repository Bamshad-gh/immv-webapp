# cases/crawler/__init__.py
# ─────────────────────────────────────────────────────────────
# Crawler package for extracting requirements, eligibility conditions,
# and government forms from immigration program pages.
#
# Package structure:
#   scraper.py      — HTTP fetching and HTML/link extraction
#   pdf_parser.py   — Fillable PDF field extraction
#   nlp_matcher.py  — Match crawled text against the requirement library
#   pipeline.py     — Orchestrates scraper → parser → matcher → DB save
#
# Entry point (call this from views):
#   from cases.crawler.pipeline import crawl_category
#   result = crawl_category(category)   # → {'created': N, 'errors': [...]}
#
# EXPAND: add a Celery task in tasks.py to run crawl_category() asynchronously
#         so the HTTP crawl doesn't block the admin's request.
# EXPAND: add a scheduler (django-crontab or Celery beat) to auto-re-crawl
#         categories whose last_crawled_at is older than N days.
