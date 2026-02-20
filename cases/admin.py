from django.contrib import admin
from .models import Service, Category, Requirement , Case , CaseAnswer
# Register your models here.

# TabularInline = shows related model as a table INSIDE parent model's edit page
class RequirementInline(admin.TabularInline):
    model  = Requirement  # which model to embed
    extra  = 3            # show 3 empty rows ready to fill
    fields = ['name', 'type', 'is_required', 'auto_field_form', 'is_active']
    
    

@admin.register(Category)  # decorator — registers User model to show in /admin panel
class CustomCategoryAdmin(admin.ModelAdmin):
    # columns shown in the list page at /admin/users/user/
    list_display = ['name', 'service', 'parent', 'description', 'is_active']
    # which fields the search box at top of list page searches in
    search_fields = ['name', 'service__name']
    # sidebar filter buttons on the right side of list page
    list_filter = ['is_active']
    
    inlines       = [RequirementInline]  # ← move here, not in Requirement admin

@admin.register(Service)  # decorator — registers User model to show in /admin panel
class CustomServiceAdmin(admin.ModelAdmin):
    # columns shown in the list page at /admin/users/user/
    list_display = ['name', 'description', 'is_active']
    # which fields the search box at top of list page searches in
    search_fields = ['name', 'description']
    # sidebar filter buttons on the right side of list page
    list_filter = ['is_active']

@admin.register(Requirement)  # decorator — registers User model to show in /admin panel
class CustomRequirementAdmin(admin.ModelAdmin):
    # columns shown in the list page at /admin/users/user/
    list_display = ['name', 'category', 'type', 'description', 'is_active']
    # which fields the search box at top of list page searches in
    search_fields = ['name', 'category__name']
    # sidebar filter buttons on the right side of list page
    list_filter = ['is_active','type']

@admin.register(Case)  # decorator — registers User model to show in /admin panel
class CustomCaseAdmin(admin.ModelAdmin):
    # columns shown in the list page at /admin/users/user/
    list_display = ['id', 'user', 'category', 'status', 'is_active', 'created_at']
    # which fields the search box at top of list page searches in
    search_fields = ['user__email', 'status']
    # sidebar filter buttons on the right side of list page
    list_filter = ['status']
    
@admin.register(CaseAnswer)
class CustomCaseAnswerAdmin(admin.ModelAdmin):
    list_display = ['id', 'case', 'requirement', 'answer_text', 'answer_file', 'created_at']
    search_fields = ['case__id', 'requirement__name', 'answer_text']
    list_filter = ['created_at']