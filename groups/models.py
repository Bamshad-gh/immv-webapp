from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import models

# ── ROLE — admin can add/edit roles per group type ────────────
class Role(models.Model):
    name       = models.CharField(max_length=50)
    group_type = models.CharField(max_length=20)
    # group_type matches Group.GROUP_TYPES choices
    # family roles: father, mother, son etc.
    # business roles: owner, manager, employee etc.
    # admin adds/edits roles from admin panel — no code changes needed

    def __str__(self):
        return f'{self.name} ({self.group_type})'

    class Meta:
        unique_together = ['name', 'group_type']
        # prevent duplicate role names within same group type

# ── GROUP ─────────────────────────────────────────────────────
class Group(models.Model):
    GROUP_TYPES = [
        ('family',   'Family'),
        ('business', 'Business'),
        ('friends',  'Friends'),
        ('other',    'Other'),
    ]
    name       = models.CharField(max_length=100)
    type       = models.CharField(max_length=20, choices=GROUP_TYPES)
    created_by = models.ForeignKey(
        'users.User',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='created_groups'
        # created_by.created_groups.all() = all groups this admin created
    )
    created_at = models.DateTimeField(auto_now_add=True)
    users      = models.ManyToManyField(
        'users.User',
        through='GroupMembership',  # use through table — stores role + permissions
        related_name='groups_joined'
        # user.groups_joined.all() = all groups this user is in
    )
    is_active = models.BooleanField(default=True)
    def __str__(self):
        return f'{self.name} ({self.type})'

# ── PERMISSION ──────────────────────────   
class GroupPermission(models.Model):
    name        = models.CharField(max_length=50)
    description = models.CharField(max_length=200, blank=True)

    def __str__(self):
        return self.name

# ── GROUP MEMBERSHIP — through table ──────────────────────────
# stores role + permissions for each user in each group
class GroupMembership(models.Model):
    user  = models.ForeignKey(
        'users.User',
        on_delete=models.CASCADE,
        related_name='memberships'
        # user.memberships.all() = all group memberships for this user
    )
    group = models.ForeignKey(
        Group,
        on_delete=models.CASCADE,
        related_name='memberships'
        # group.memberships.all() = all members of this group
    )
    role  = models.ForeignKey(
        Role,
        on_delete=models.SET_NULL,
        null=True, blank=True
        # role deleted → membership stays, role becomes null
    )

    # permissions — admin or leader sets these per member
    permissions = models.ManyToManyField(GroupPermission, blank=True)
    # admin assigns permissions per membership
    # add new permission = add row in admin panel, no migration needed
    joined_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)
    # suspended member → is_active=False
    # check in views: membership.is_active before allowing access

    class Meta:
        unique_together = ['user', 'group']
        # one user can only have one membership row per group

    def __str__(self):
        return f'{self.user.email} — {self.group.name} ({self.role})'


# ── FAMILY INFO — extra info for family groups ─────────────────
class FamilyInfo(models.Model):
    group       = models.OneToOneField(
        Group,
        on_delete=models.CASCADE,
        related_name='family_info'
        # group.family_info → get family details
    )
    family_name = models.CharField(max_length=100)

    def __str__(self):
        return self.family_name


# ── BUSINESS INFO — extra info for business groups ─────────────
class BusinessInfo(models.Model):
    group           = models.OneToOneField(
        Group,
        on_delete=models.CASCADE,
        related_name='business_info'
        # group.business_info → get business details
    )
    company_name    = models.CharField(max_length=100)
    business_number = models.CharField(max_length=50)

    def __str__(self):
        return self.company_name