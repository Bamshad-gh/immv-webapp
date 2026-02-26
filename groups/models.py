# groups/models.py

from django.db import models
from django.conf import settings  # use this instead of importing User directly

# groups/models.py
# ─────────────────────────────────────────────────────────────
# What's in this file (in order):
#   1. Role             — roles per group type (admin manages from panel)
#   2. Group            — main group entity
#   3. GroupPermission  — custom permissions per member (admin manages from panel)
#   4. GroupMembership  — through table: user + group + role + permissions
#   5. FamilyInfo       — extra fields for family groups
#   6. BusinessInfo     — extra fields for business groups
#
# EXPAND: add a new XxxInfo model for each new group type that needs extra fields
# ─────────────────────────────────────────────────────────────
# ── 1. ROLE ───────────────────────────────────────────────────
# Roles are managed from the admin panel — no code changes needed to add new ones.
# Scoped to group type so family roles don't appear in business groups and vice versa.
# EXPAND: add an 'icon' or 'color' field if your UI needs visual role badges.

class Role(models.Model):
    name       = models.CharField(max_length=50)
    group_type = models.CharField(max_length=20)
    # group_type matches Group.GROUP_TYPES choices
    # family roles:   father, mother, son, daughter, guardian
    # business roles: owner, manager, employee, contractor

    def __str__(self):
        return f'{self.name} ({self.group_type})'

    class Meta:
        unique_together = ['name', 'group_type']
        # prevent duplicate role names within same group type


# ── 2. GROUP ──────────────────────────────────────────────────
# Main group entity. Users join via GroupMembership (through table).
# CUSTOMIZE: change GROUP_TYPES to match your domain.
# EXPAND: add 'description' or 'cover_image' for richer group profiles.

class Group(models.Model):
    GROUP_TYPES = [
        ('family',   'Family'),
        ('business', 'Business'),
        ('friends',  'Friends'),
        ('other',    'Other'),
    ]
    name = models.CharField(max_length=100)
    type = models.CharField(max_length=20, choices=GROUP_TYPES)

    # SET_NULL — group survives if creator account is deleted
    created_by = models.ForeignKey(
        'users.User',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='created_groups'   # user.created_groups.all()
    )
    created_at = models.DateTimeField(auto_now_add=True)

    # M2M through table — stores role + permissions on the relationship
    users = models.ManyToManyField(
        'users.User',
        through='GroupMembership',
        related_name='groups_joined'    # user.groups_joined.all()
    )

    is_active = models.BooleanField(default=True)  # soft delete

    def __str__(self):
        return f'{self.name} ({self.type})'


# ── 3. GROUP PERMISSION ───────────────────────────────────────
# Permissions are DB rows — add new ones from admin panel, no migration needed.
# EXPAND: add a 'category' field to group permissions in the admin UI.
# Example permissions: can_fill_cases, can_view_members, can_manage_members

class GroupPermission(models.Model):
    name        = models.CharField(max_length=50)
    description = models.CharField(max_length=200, blank=True)

    def __str__(self):
        return self.name


# ── 4. GROUP MEMBERSHIP — Through Table ───────────────────────
# Sits between User and Group — stores role, permissions, join date, active status.
# Two ways to access:
#   user.memberships.all()   → Membership objects (has role + permissions)
#   user.groups_joined.all() → Group objects directly (no role info)
# EXPAND: add 'invited_by' ForeignKey to track who added this member.

class GroupMembership(models.Model):
    user = models.ForeignKey(
        'users.User',
        on_delete=models.CASCADE,
        related_name='memberships'      # user.memberships.all()
    )
    group = models.ForeignKey(
        Group,
        on_delete=models.CASCADE,
        related_name='memberships'      # group.memberships.all()
    )
    role = models.ForeignKey(
        Role,
        on_delete=models.SET_NULL,
        null=True, blank=True           # role deleted → membership stays, role becomes null
    )

    # Admin or group leader assigns these per member
    # Add new permission = add a row in admin panel, no migration needed
    permissions = models.ManyToManyField(GroupPermission, blank=True)

    joined_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)
    # is_active=False = suspended member — blocked in views without removing from group

    class Meta:
        unique_together = ['user', 'group']  # one membership row per user per group

    # ── Permission helpers ────────────────────────────────────
    # Call these in views and templates instead of raw .filter() every time.
    # EXPAND: add a helper for every new GroupPermission you create.

    def has_permission(self, permission_name: str) -> bool:
        """Base check — used by all helpers below."""
        return self.permissions.filter(name=permission_name).exists()

    def can_fill_cases(self) -> bool:
        return self.has_permission('can_fill_cases')

    def can_view_members(self) -> bool:
        return self.has_permission('can_view_members')

    def can_manage_members(self) -> bool:
        return self.has_permission('can_manage_members')

    # EXPAND: add helpers for your own permissions
    # def can_export_data(self) -> bool:
    #     return self.has_permission('can_export_data')

    def __str__(self):
        return f'{self.user.email} — {self.group.name} ({self.role})'


# ── 5. FAMILY INFO ────────────────────────────────────────────
# Extra fields specific to family groups.
# Access via: group.family_info.family_name

class FamilyInfo(models.Model):
    group = models.OneToOneField(
        Group,
        on_delete=models.CASCADE,
        related_name='family_info'
    )
    family_name = models.CharField(max_length=100)

    def __str__(self):
        return self.family_name


# ── 6. BUSINESS INFO ──────────────────────────────────────────
# Extra fields specific to business groups.
# Access via: group.business_info.company_name
# EXPAND: add tax_number, industry, website as needed.

class BusinessInfo(models.Model):
    group = models.OneToOneField(
        Group,
        on_delete=models.CASCADE,
        related_name='business_info'
    )
    company_name    = models.CharField(max_length=100)
    business_number = models.CharField(max_length=50)

    def __str__(self):
        return self.company_name