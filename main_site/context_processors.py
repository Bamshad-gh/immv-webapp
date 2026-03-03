# main_site/context_processors.py
# ─────────────────────────────────────────────────────────────
# Injects `site_settings` into every template automatically.
# Registered in config/settings.py → TEMPLATES → context_processors.
#
# Usage in any template (no view code needed):
#   {{ site_settings.company_name }}
#   {{ site_settings.hero_title }}
#
# EXPAND: add more global context variables here (e.g. unread_notifications count).
# ─────────────────────────────────────────────────────────────

from .models import SiteSettings


def site_settings(request):
    """Make `site_settings` available in every template, public and private."""
    return {'site_settings': SiteSettings.get()}
