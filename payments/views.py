# payments/views.py
# ─────────────────────────────────────────────────────────────
# User-facing invoice views.
# Admin-facing invoice management lives in admin_panel/views.py.
#
# Views in this file:
#   1. invoice_list   — user sees all their invoices
#   2. invoice_detail — user sees one invoice with payment history
# ─────────────────────────────────────────────────────────────

from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required

from .models import Invoice


# ── 1. INVOICE LIST ───────────────────────────────────────────
# Shows all invoices for the current user, newest first.
# Invoice.Meta.ordering = ['-created_at'] handles the sort automatically.
#
# EXPAND: add pagination if users accumulate many invoices.

@login_required
def invoice_list(request):
    invoices = Invoice.objects.filter(user=request.user)
    return render(request, 'payments/invoice_list.html', {
        'invoices': invoices,
    })


# ── 2. INVOICE DETAIL ─────────────────────────────────────────
# Shows a single invoice and its full payment history.
# Security: user=request.user in get_object_or_404 prevents users
# from accessing another person's invoice by guessing the ID.
#
# EXPAND: add a "Download as PDF" button for record keeping.

@login_required
def invoice_detail(request, invoice_id):
    invoice  = get_object_or_404(Invoice, id=invoice_id, user=request.user)
    payments = invoice.payments.all()  # ordered by -marked_at via Payment.Meta

    return render(request, 'payments/invoice_detail.html', {
        'invoice':  invoice,
        'payments': payments,
    })
