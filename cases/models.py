from django.db import models


# -── SERVICE MODEL ───────────────────────────────────────────
class Service(models.Model):
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True, null=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.name

# -── CATEGORY MODEL ───────────────────────────────────────────
class Category(models.Model):
    service = models.ForeignKey(Service, on_delete=models.CASCADE, related_name='categories')
    parent = models.ForeignKey(
        'self',                          # points to same model (self-referencing)
        on_delete=models.SET_NULL,  # when parent deleted → children become top leve
        null=True, blank=True,           # top-level categories have no parent
        related_name='subcategories'     # lets you do: category.subcategories.all()
    )
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)
    
    def __str__(self):
        return self.name
    
# ── REQUIREMENT MODEL ───────────────────────────────────────  
class Requirement(models.Model):
    # You define the allowed options as a list of tuples
    # (value saved in DB, label shown in admin/forms)
    TYPE_CHOICES = [
    ('document', 'Document Upload'),
    ('question', 'Question'),
    ('text',     'Text Field'),
    ('number',   'Number'),
    ('date',     'Date'),
    ]
    # Then you tell the field to use those choices
    type = models.CharField(max_length=20, choices=TYPE_CHOICES)
    # Now Django only allows: 'document', 'question', 'text'
    # Anything else → validation error
    
    category = models.ForeignKey(Category, on_delete=models.CASCADE, related_name='requirements')
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)
    is_required = models.BooleanField(default=True)
    auto_field_form=models.CharField(max_length=100, blank=True, null=True) 
    
    def __str__(self):
        return self.name
# ── CASE MODEL ─────────────────────────────────────────────
class Case(models.Model):
    STATUS_CHOICES = [
        ('pending',   'Pending'),
        ('active',    'Active'),
        ('completed', 'Completed'),
        ('rejected',  'Rejected'),
    ]
    user = models.ForeignKey('users.User', on_delete=models.CASCADE, related_name='cases')
    # PROTECT instead of CASCADE — never accidentally delete user with active cases
    category = models.ForeignKey(Category, on_delete=models.CASCADE, related_name='cases')
    status   = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    notes    = models.TextField(blank=True, null=True)  # admin notes
    created_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f'Case #{self.id} - {self.user.email} - {self.category.name}'

# ── CASE ANSWER MODEL ─────────────────────────────────────  
class CaseAnswer(models.Model):
    case        = models.ForeignKey(Case, on_delete=models.CASCADE, related_name='answers')
    requirement = models.ForeignKey(Requirement, on_delete=models.CASCADE)
    
    # different answer fields for different requirement types
    answer_text   = models.TextField(blank=True, null=True)        # for text/question type
    answer_number = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)  # for number type
    answer_date   = models.DateField(blank=True, null=True)        # for date type
    answer_file   = models.FileField(upload_to='case_files/', blank=True, null=True)  # for document type
    
    is_auto_filled = models.BooleanField(default=False)  # True = pulled from profile automatically
    created_at     = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f'{self.case} - {self.requirement.name}'