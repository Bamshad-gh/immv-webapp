from django.db import models

# Create your models here.
# Invoice — what a user owes in total.
# Payment — a single recorded payment against an invoice.
#
# One invoice can have many payments (supports partial payments).
# Invoice.status is recomputed after every payment via update_status().
#
# Double payment protection (two layers):
#   1. Payment.reference is unique — same reference cannot be submitted twice.
#   2. Views use select_for_update() + transaction.atomic() to lock the
#      invoice row during the transaction, preventing race conditions
#      when two admins submit at the exact same millisecond.
#
# MULTI-TENANCY NOTE:
#   Add company FK to Invoice when multi-tenancy is added.
#   Payment inherits company through Invoice — no extra field needed.
#
# EXPAND:
#   Add currency field per invoice for multi-currency support
#   Add Invoice.tax_amount for tax line items
#   Add Payment.payment_method CharField for external method tracking
# ─────────────────────────────────────────────────────────────

from django.db import models
from django.core.validators import MinValueValidator
import uuid


class Invoice(models.Model):

    STATUS_CHOICES = [
        ('unpaid',    'Unpaid'),
        ('partial',   'Partially Paid'),
        ('paid',      'Paid'),
        ('cancelled', 'Cancelled'),
    ]

    # Who this invoice is for
    user = models.ForeignKey(
        'users.User',
        on_delete=models.CASCADE,
        related_name='invoices',
    )

    # Admin who created this invoice
    created_by = models.ForeignKey(
        'users.User',
        on_delete=models.SET_NULL,
        null=True,
        related_name='created_invoices',
    )

    title       = models.CharField(max_length=200)
    description = models.TextField(blank=True, null=True)

    # Total amount owed — must be positive
    amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(0.01)],
    )

    # EXPAND: replace with per-invoice field for multi-currency
    currency = models.CharField(max_length=3, default='CAD')

    status = models.CharField(
        max_length=10,
        choices=STATUS_CHOICES,
        default='unpaid',
    )

    due_date   = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # Optional link to a case — gives context to the invoice
    related_case = models.ForeignKey(
        'cases.Case',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='invoices',
    )

    def total_paid(self):
        """
        Sum of all payments recorded against this invoice.
        Returns Decimal, or 0 if no payments yet.
        """
        result = self.payments.aggregate(
            total=models.Sum('amount')
        )['total']
        return result or 0

    def balance_due(self):
        """
        Remaining amount owed: total invoice - total paid.
        Always >= 0.
        """
        return self.amount - self.total_paid()

    def update_status(self):
        """
        Recomputes and saves status based on current payments.
        ALWAYS call this after recording a payment.
        Does nothing if invoice is cancelled.

        Why a method and not auto-computed?
          Writing to DB should be explicit — this makes it clear
          when status gets updated and who calls it.
        """
        if self.status == 'cancelled':
            return

        paid = self.total_paid()
        if paid <= 0:
            self.status = 'unpaid'
        elif paid < self.amount:
            self.status = 'partial'
        else:
            self.status = 'paid'
        self.save()

    def is_overdue(self):
        """
        True if unpaid/partial and past due date.
        Use in templates: {% if invoice.is_overdue %}
        """
        from django.utils import timezone
        if not self.due_date:
            return False
        return (
            self.due_date < timezone.now().date()
            and self.status in ('unpaid', 'partial')
        )

    def __str__(self):
        return f'Invoice #{self.id} — {self.user.email} — {self.amount} {self.currency}'

    class Meta:
        ordering = ['-created_at']


class Payment(models.Model):
    """
    A single payment recorded against an invoice.

    DOUBLE PAYMENT PROTECTION:
      reference field is unique — identical references are rejected at DB level.
      The view wraps payment creation in transaction.atomic() + select_for_update()
      so concurrent submissions are serialized — the second one will see the
      updated total and reject if it would overpay.

    reference is auto-generated as UUID4 if admin leaves it blank.
    Admin can provide a manual reference (e.g. bank transfer ID, cheque number)
    which also serves as the duplicate check key.
    """

    invoice = models.ForeignKey(
        Invoice,
        on_delete=models.CASCADE,
        related_name='payments',
    )

    # Admin who recorded this payment
    marked_by = models.ForeignKey(
        'users.User',
        on_delete=models.SET_NULL,
        null=True,
        related_name='recorded_payments',
    )

    amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(0.01)],
    )

    # Unique per payment — prevents double recording
    # Auto-generated as UUID4 if not provided by admin
    reference = models.CharField(
        max_length=100,
        unique=True,
        blank=True,
    )

    notes     = models.TextField(blank=True, null=True)
    marked_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        if not self.reference:
            self.reference = str(uuid.uuid4())
        super().save(*args, **kwargs)

    def __str__(self):
        return f'Payment #{self.id} — {self.amount} on Invoice #{self.invoice_id}'

    class Meta:
        ordering = ['-marked_at']