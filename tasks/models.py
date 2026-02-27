from django.db import models

# Create your models here.
# Task system — two types:
#   admin→user  : ask user to do something (fill requirement, upload file)
#   admin→admin : assign work to a team member (review case, check user)
#
# Both types share the same Task model — task_type field tells which.
# assigned_to_user XOR assigned_to_admin is always set (never both, never neither).
#
# Notification model — lightweight per-user inbox.
# Created automatically when a task is assigned.
#
# MULTI-TENANCY NOTE:
#   When adding multi-tenancy, add company FK to Task and Notification.
#   All querysets will need .filter(company=request.company).
#   No other model changes needed.
#
# EXPAND:
#   Add 'priority' field: low/medium/high
#   Add 'attachment' FileField for task instructions
#   Add 'comment' related model for back-and-forth on a task
# ─────────────────────────────────────────────────────────────

from django.db import models
from django.utils import timezone


class Task(models.Model):

    TYPE_CHOICES = [
        ('user',  'Admin → User'),   # admin assigns task to a regular user
        ('admin', 'Admin → Admin'),  # admin assigns task to another admin
    ]

    STATUS_CHOICES = [
        ('pending',     'Pending'),      # created, not started
        ('in_progress', 'In Progress'),  # assignee has acknowledged
        ('completed',   'Completed'),    # marked done
        ('cancelled',   'Cancelled'),    # admin cancelled it
    ]

    # Who created this task — always an admin user
    created_by = models.ForeignKey(
        'users.User',
        on_delete=models.SET_NULL,
        null=True,
        related_name='created_tasks',
    )

    # For admin→user tasks: the regular user this is assigned to
    # Null for admin→admin tasks
    assigned_to_user = models.ForeignKey(
        'users.User',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='assigned_tasks',
    )

    # For admin→admin tasks: the admin this is assigned to
    # Null for admin→user tasks
    assigned_to_admin = models.ForeignKey(
        'users.AdminProfile',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='admin_tasks',
    )

    task_type   = models.CharField(max_length=10, choices=TYPE_CHOICES)
    title       = models.CharField(max_length=200)
    description = models.TextField(blank=True, null=True)
    due_date    = models.DateField(null=True, blank=True)

    status = models.CharField(
        max_length=15,
        choices=STATUS_CHOICES,
        default='pending',
    )

    # Optional context links — help assignee understand what task is about
    # EXPAND: add related_group FK for group-level tasks
    related_case = models.ForeignKey(
        'cases.Case',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='tasks',
    )
    related_requirement = models.ForeignKey(
        'cases.Requirement',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='tasks',
    )

    created_at   = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f'Task #{self.id}: {self.title}'

    def mark_complete(self):
        """
        Marks task done and records timestamp.
        Always use this instead of setting status manually
        so completed_at stays in sync.
        """
        self.status       = 'completed'
        self.completed_at = timezone.now()
        self.save()

    def is_overdue(self):
        """
        True if task has a past due date and is not done/cancelled.
        Use in templates: {% if task.is_overdue %}
        """
        if not self.due_date:
            return False
        return (
            self.due_date < timezone.now().date()
            and self.status not in ('completed', 'cancelled')
        )

    class Meta:
        ordering = ['-created_at']


class Notification(models.Model):
    """
    Lightweight per-user notification inbox entry.

    Created automatically by the view when:
      - A user is assigned a new task
      - An admin is assigned a new task
    EXPAND: add notification_type choices for different alert kinds
            (task_assigned, payment_added, case_updated, message)
    EXPAND: add email_sent BooleanField to track email delivery
    """

    user = models.ForeignKey(
        'users.User',
        on_delete=models.CASCADE,
        related_name='notifications',
    )

    # The task that triggered this notification — optional
    task = models.ForeignKey(
        Task,
        on_delete=models.CASCADE,
        null=True, blank=True,
        related_name='notifications',
    )

    message    = models.CharField(max_length=300)
    is_read    = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f'Notification → {self.user.email}: {self.message}'

    class Meta:
        ordering = ['-created_at']
        
# ── Notification helper functions ─────────────────────────────
# Add these at the bottom of tasks/models.py
# These are called from views to create notifications consistently.

def notify_task_assigned(task):
    # Notify the assigned person
    recipient = task.assigned_to_user or (
        task.assigned_to_admin.user if task.assigned_to_admin else None
    )
    if recipient:
        Notification.objects.create(
            user    = recipient,
            task    = task,
            message = f'New task assigned to you: {task.title}',
        )

def notify_task_completed(task):
    # Notify the creator that assignee completed the task
    if task.created_by:
        Notification.objects.create(
            user    = task.created_by,
            task    = task,
            message = f'Task completed: {task.title}',
        )

def notify_invoice_created(invoice):
    Notification.objects.create(
        user    = invoice.user,
        task    = None,
        message = f'New invoice "{invoice.title}" — Amount due: ${invoice.amount}',
    )

def notify_payment_recorded(invoice, payment):
    Notification.objects.create(
        user    = invoice.user,
        task    = None,
        message = (
            f'Payment of ${payment.amount} recorded on "{invoice.title}". '
            f'Remaining balance: ${invoice.balance_due()}'  # ← balance_due not balance
        ),
    )

def notify_case_updated(case, message):
    Notification.objects.create(
        user    = case.user,
        task    = None,
        message = message,
    )