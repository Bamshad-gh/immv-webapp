from django.contrib import admin
from .models import Group, GroupMembership, GroupPermission, Role, FamilyInfo, BusinessInfo

@admin.register(Role)
class RoleAdmin(admin.ModelAdmin):
    list_display  = ['name', 'group_type']
    list_filter   = ['group_type']

@admin.register(GroupPermission)
class GroupPermissionAdmin(admin.ModelAdmin):
    list_display = ['name', 'description']

@admin.register(Group)
class GroupAdmin(admin.ModelAdmin):
    list_display  = ['name', 'type', 'created_by', 'created_at', 'is_active']
    list_filter   = ['type', 'is_active']

@admin.register(GroupMembership)
class GroupMembershipAdmin(admin.ModelAdmin):
    list_display  = ['user', 'group', 'role', 'is_active', 'joined_at']
    list_filter   = ['is_active']

@admin.register(FamilyInfo)
class FamilyInfoAdmin(admin.ModelAdmin):
    list_display = ['family_name', 'group']

@admin.register(BusinessInfo)
class BusinessInfoAdmin(admin.ModelAdmin):
    list_display = ['company_name', 'business_number', 'group']