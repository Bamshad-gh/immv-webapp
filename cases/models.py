from django.db import models
from django.utils.text import slugify


# cases/models.py
# ─────────────────────────────────────────────────────────────
# What's in this file (in order):
#   1. Service          — top-level service (e.g., "Immigration", "Visa")
#   2. Category         — sub-categories under a service, supports nesting
#   3. Requirement      — individual fields/questions in a category
#   4. Case             — a user's application for a category
#   5. CaseAnswer       — answers to requirements for a specific case
#
# Case ownership — three scenarios, all handled by the same Case model:
#   Personal case:         user=Ali,  group=None,        managed_profile=None
#   Group case:            user=Ali,  group=HassanFamily, managed_profile=None
#   Managed profile case:  user=Ali,  group=HassanFamily, managed_profile=Mother
#
# 'user' is always set — it's who submitted/owns the case.
# 'group' and 'managed_profile' are optional context on top of that.
# ─────────────────────────────────────────────────────────────

# ── 1. SERVICE ────────────────────────────────────────────────
# Top-level grouping of categories.
# Example: Service="Immigration" → Categories=["Work Visa", "Study Permit"]
# EXPAND: add 'icon' or 'color' field for UI display.

class Service(models.Model):
    name        = models.CharField(max_length=100)
    slug        = models.SlugField(max_length=120, unique=True, blank=True)
    description = models.TextField(blank=True, null=True)
    is_active   = models.BooleanField(default=True)

    def save(self, *args, **kwargs):
        # Auto-generate slug from name on first save.
        # Appends a counter (-2, -3 …) if the slug is already taken.
        if not self.slug:
            base    = slugify(self.name)[:100]
            slug    = base
            counter = 2
            while Service.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                slug = f'{base}-{counter}'
                counter += 1
            self.slug = slug
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


# ── 2. CATEGORY ───────────────────────────────────────────────
# Sub-categories under a service. Supports nesting via self-referencing FK.
# Top-level categories have parent=None.
# Access children: category.subcategories.all()
# EXPAND: add 'order' IntegerField if you need custom display ordering.

class Category(models.Model):
    service = models.ForeignKey(
        Service,
        on_delete=models.CASCADE,
        related_name='categories'
    )
    parent = models.ForeignKey(
        'self',                         # self-referencing — points to same model
        on_delete=models.SET_NULL,      # parent deleted → children become top-level
        null=True, blank=True,
        related_name='subcategories'    # category.subcategories.all()
    )
    name        = models.CharField(max_length=100)
    slug        = models.SlugField(max_length=120, unique=True, blank=True)
    description = models.TextField(blank=True, null=True)
    created_at  = models.DateTimeField(auto_now_add=True)
    is_active   = models.BooleanField(default=True)

    def save(self, *args, **kwargs):
        # Auto-generate slug from name on first save. Duplicates get -2, -3 …
        if not self.slug:
            base    = slugify(self.name)[:100]
            slug    = base
            counter = 2
            while Category.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                slug = f'{base}-{counter}'
                counter += 1
            self.slug = slug
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


# ── 3. REQUIREMENT ────────────────────────────────────────────
# Individual fields/questions that belong to a category.
# RequirementForm in cases/forms.py reads these to build the dynamic form.
# EXPAND: add a new TYPE_CHOICE and a matching entry in forms.py field_map.

class Requirement(models.Model):
    TYPE_CHOICES = [
        ('document', 'Document Upload'),
        ('question', 'Question'),
        ('text',     'Text Field'),
        ('number',   'Number'),
        ('date',     'Date'),
        # EXPAND: add new types here + matching entry in cases/forms.py field_map
    ]

    type        = models.CharField(max_length=20, choices=TYPE_CHOICES)
    category    = models.ForeignKey(
        Category,
        on_delete=models.CASCADE,
        related_name='requirements'
    )
    name           = models.CharField(max_length=100)
    description    = models.TextField(blank=True, null=True)
    created_at     = models.DateTimeField(auto_now_add=True)
    is_active      = models.BooleanField(default=True)
    is_required    = models.BooleanField(default=True)
    auto_field_form = models.CharField(max_length=100, blank=True, null=True)

    def __str__(self):
        return self.name


# ── 4. CASE ───────────────────────────────────────────────────
# A user's application for a specific category.
#
# Three ownership scenarios — all use the same model:
#
#   Scenario 1 — Personal case (existing behavior, unchanged):
#     user=Ali, group=None, managed_profile=None
#     → Ali is applying for himself
#
#   Scenario 2 — Group case:
#     user=Ali, group=HassanFamily, managed_profile=None
#     → Ali submitted this case on behalf of the group
#
#   Scenario 3 — Managed profile case:
#     user=Ali, group=HassanFamily, managed_profile=Mother
#     → Ali submitted this case on behalf of his mother (who has no account)
#
# 'user' is ALWAYS set — it's who created/submitted the case.
# 'group' and 'managed_profile' are optional — they add context on who it's for.
#
# Why null=True on group and managed_profile?
#   So existing personal cases (group=None, managed_profile=None) still work.
#   No data migration needed — old rows just have null in the new columns.

class Case(models.Model):
    STATUS_CHOICES = [
        ('pending',   'Pending'),
        ('active',    'Active'),
        ('completed', 'Completed'),
        ('rejected',  'Rejected'),
    ]

    # Always set — who created/owns this case
    user = models.ForeignKey(
        'users.User',
        on_delete=models.CASCADE,
        related_name='cases'            # user.cases.all()
    )

    # Optional — set if this case belongs to a group
    # null = personal case | filled = group case
    group = models.ForeignKey(
        'groups.Group',                 # string ref — avoids circular import
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='cases'            # group.cases.all()
    )

    # Optional — set if this case is for a managed profile (interior person)
    # null = case is for the user themselves | filled = case is for managed person
    managed_profile = models.ForeignKey(
        'users.ManagedProfile',         # string ref — avoids circular import
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='cases'            # managed_profile.cases.all()
    )

    category   = models.ForeignKey(
        Category,
        on_delete=models.CASCADE,
        related_name='cases'
    )
    status     = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    notes      = models.TextField(blank=True, null=True)   # admin notes
    created_at = models.DateTimeField(auto_now_add=True)
    is_active  = models.BooleanField(default=True)

    def __str__(self):
        if self.managed_profile:
            return f'Case #{self.id} - {self.managed_profile.full_name()} (via {self.user.email})'
        if self.group:
            return f'Case #{self.id} - {self.group.name} (by {self.user.email})'
        return f'Case #{self.id} - {self.user.email} - {self.category.name}'

    def get_owner_display(self):
        """
        Returns a human-readable string of who this case is for.
        Useful in templates: {{ case.get_owner_display }}
        """
        if self.managed_profile:
            return self.managed_profile.full_name()
        if self.group:
            return self.group.name
        return self.user.email


# ── 5. CASE ANSWER ────────────────────────────────────────────
# Stores answers to requirements for a specific case.
# One row per requirement per case.
# Different columns for different answer types — only one is filled per row.
#
# EXPAND: add answer_boolean for yes/no requirement types.

class CaseAnswer(models.Model):
    case        = models.ForeignKey(Case, on_delete=models.CASCADE, related_name='answers')
    requirement = models.ForeignKey(Requirement, on_delete=models.CASCADE)

    # Only one of these is filled per row — depends on requirement.type
    answer_text   = models.TextField(blank=True, null=True)       # text / question
    answer_number = models.DecimalField(
        max_digits=10, decimal_places=2,
        blank=True, null=True
    )                                                              # number
    answer_date   = models.DateField(blank=True, null=True)       # date
    answer_file   = models.FileField(
        upload_to='case_files/',
        blank=True, null=True
    )                                                              # document

    is_auto_filled = models.BooleanField(default=False)  # True = pulled from profile automatically
    created_at     = models.DateTimeField(auto_now_add=True)
    
    edited_by_admin = models.BooleanField(default=False)  # True if an admin edited this answer in the admin panel
    notify_user     = models.BooleanField(default=False)  # True if admin edited answer and user should be notified (e.g., email notification)

    def __str__(self):
        return f'{self.case} - {self.requirement.name}'
class CaseRequirement(models.Model):
    """
    Tracks which requirements are active for a specific case.
    
    Why this model?
      By default a case inherits ALL requirements from its category.
      But admin can customize per case — add extra requirements or
      soft-delete ones that don't apply to this specific user.
    
    How it works:
      - When a case is created, CaseRequirement rows are auto-created
        for all requirements in the category (is_active=True by default)
      - Admin can set is_active=False to hide a requirement from this case
      - Admin can add extra requirements not in the category (is_extra=True)
      - RequirementForm in forms.py filters by active CaseRequirements
    
    EXPAND: add 'added_by' ForeignKey to track which admin customized it.
    """
    case        = models.ForeignKey(
        Case,
        on_delete=models.CASCADE,
        related_name='case_requirements'  # case.case_requirements.all()
    )
    requirement = models.ForeignKey(
        Requirement,
        on_delete=models.CASCADE,
    )
    is_active = models.BooleanField(default=True)
    # False = admin removed this requirement from this specific case
    
    is_extra  = models.BooleanField(default=False)
    # True = admin added this requirement manually (not from category defaults)

    class Meta:
        unique_together = ['case', 'requirement']

    def __str__(self):
        status = 'active' if self.is_active else 'removed'
        return f'{self.requirement.name} → Case #{self.case.id} ({status})'