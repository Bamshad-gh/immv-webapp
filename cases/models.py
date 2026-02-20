from django.db import models

class Service(models.Model):
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True, null=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.name

# Create your models here.
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
    
class Requirement(models.Model):
    # You define the allowed options as a list of tuples
    # (value saved in DB, label shown in admin/forms)
    TYPE_CHOICES = [
    ('document', 'Document Upload'),  # saves 'document' in DB, shows 'Document Upload' in admin
    ('question', 'Question'),
    ('text',     'Text Field'),
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