from django.contrib import admin
from .models import (
    Case, CaseAnswer, CaseRequirement,
    Service, Category, Requirement,
    RequirementSection, RequirementChoice, CategoryRequirement,
)

@admin.register(Service)
class ServiceAdmin(admin.ModelAdmin):
    list_display = ['name', 'is_active']

@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display  = ['name', 'service', 'parent', 'is_active']
    list_filter   = ['service', 'is_active']

@admin.register(RequirementSection)
class RequirementSectionAdmin(admin.ModelAdmin):
    list_display = ['name', 'order', 'is_active']

@admin.register(Requirement)
class RequirementAdmin(admin.ModelAdmin):
    # 'category' removed — requirements now link via CategoryRequirement M2M
    list_display  = ['name', 'section', 'type', 'is_active']
    list_filter   = ['type', 'is_active', 'section']

@admin.register(RequirementChoice)
class RequirementChoiceAdmin(admin.ModelAdmin):
    list_display = ['requirement', 'label', 'value', 'order']

@admin.register(CategoryRequirement)
class CategoryRequirementAdmin(admin.ModelAdmin):
    list_display = ['requirement', 'category', 'order', 'is_required_override']

@admin.register(Case)
class CaseAdmin(admin.ModelAdmin):
    list_display  = ['id', 'user', 'category', 'status', 'created_at']
    list_filter   = ['status']

@admin.register(CaseRequirement)
class CaseRequirementAdmin(admin.ModelAdmin):
    list_display  = ['case', 'requirement', 'is_active', 'is_extra']
    list_filter   = ['is_active', 'is_extra']

@admin.register(CaseAnswer)
class CaseAnswerAdmin(admin.ModelAdmin):
    list_display  = ['case', 'requirement']