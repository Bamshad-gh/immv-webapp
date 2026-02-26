from django.contrib import admin
from .models import Case, CaseAnswer, CaseRequirement, Service, Category, Requirement

@admin.register(Service)
class ServiceAdmin(admin.ModelAdmin):
    list_display = ['name', 'is_active']

@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display  = ['name', 'service', 'parent', 'is_active']
    list_filter   = ['service', 'is_active']

@admin.register(Requirement)
class RequirementAdmin(admin.ModelAdmin):
    list_display  = ['name', 'category', 'type', 'is_active']
    list_filter   = ['type', 'is_active']

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