from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import User, Profile

@admin.register(User)
class CustomUserAdmin(UserAdmin):
    # columns shown in the list page
    list_display = ['email', 'first_name', 'last_name', 'is_active']
    
    # search box — which fields to search in
    search_fields = ['email', 'first_name']
    
    # sidebar filters
    list_filter = ['is_active', 'is_staff']
    
    # default sort order
    ordering = ['email']
    
    # fields shown when EDITING a user
    fieldsets = (
        (None,          {'fields': ('email', 'password')}),        # section title, fields
        ('Personal',    {'fields': ('first_name', 'last_name', 'phone')}),
        ('Permissions', {'fields': ('is_active', 'is_staff', 'is_superuser')}),
    )
    
    # fields shown when ADDING a new user
    add_fieldsets = (
        (None, {'fields': ('email', 'password1', 'password2')}),
    )


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display  = ['user__email', 'get_full_name', 'passport_number', 'country_of_birth']
    search_fields = ['user__email', 'passport_number']  # search by related field
    ordering      = ['user__email']
    
    # custom column — when you need data from related model
    def get_full_name(self, obj):
        return f'{obj.user.first_name} {obj.user.last_name}'  # obj = current profile
    get_full_name.short_description = 'Full Name'  # column header title