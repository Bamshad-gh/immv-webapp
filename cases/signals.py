# cases/signals.py
# ─────────────────────────────────────────────────────────────
# Django signals for the cases app.
#
# WHY signals at all:
#   Some post-save side effects (e.g. notifications) belong here so they
#   run regardless of WHICH view created the Case — direct create(), admin
#   panel, group assignment, bulk assignment, etc.
#
# WHAT DOES NOT belong here:
#   CaseRequirement creation. Every path that creates a Case uses either:
#     - admin_panel/views.py _create_case()   → creates CaseRequirement rows
#     - admin_panel/views.py create_case()    → creates CaseRequirement rows
#   Both do this correctly via CategoryRequirement (Phase 1 M2M bridge).
#   Adding CaseRequirement logic here would duplicate that work and risk
#   double-creating rows if signal + view both run.
#
# NOTE ON HISTORY (Phase 1 migration):
#   Before Phase 1, Requirement had a direct FK to Category.
#   An old signal used `instance.category.requirements.all()` which
#   relied on that now-removed FK. That code is gone. Do NOT restore it.
#   The correct access path (post Phase 1) is:
#       CategoryRequirement.objects.filter(category=instance.category)
#   But again — this belongs in the view helper, not here.
#
# EXPAND: add a signal here for:
#   - Sending a notification to the user when their case status changes
#   - Logging case creation to an audit table
#   - Triggering eligibility re-check when a case answer is updated
# ─────────────────────────────────────────────────────────────

# No signals needed at this time.
# The file is kept so it can be connected in apps.py when signals are added.
#
# HOW TO ADD A SIGNAL:
#   from django.db.models.signals import post_save
#   from django.dispatch import receiver
#   from .models import Case
#
#   @receiver(post_save, sender=Case)
#   def on_case_created(sender, instance, created, **kwargs):
#       if not created:
#           return
#       # your logic here
