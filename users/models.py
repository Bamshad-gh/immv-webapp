from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import models

# users/models.py
# ─────────────────────────────────────────────────────────────
# What's in this file (in order):
#   1. UserManager      — custom manager for email-based login
#   2. User             — custom user model (email instead of username)
#   3. PersonalInfo     — abstract base, shared personal fields (no DB table)
#   4. Profile          — real user's personal info (inherits PersonalInfo)
#   5. ManagedProfile   — interior person, no login required (inherits PersonalInfo)
#   6. AdminProfile     — tracks what each staff member is allowed to do
#
# Signal lives in users/signals.py — auto-creates Profile on registration
# Signal is registered in users/apps.py via ready()
# ─────────────────────────────────────────────────────────────

from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import models


# ── 1. CUSTOM MANAGER ────────────────────────────────────────
# Needed because we removed username and login with email instead.
# Teaches Django how to create users and superusers without a username field.

class UserManager(BaseUserManager):

    def create_user(self, email, password=None, **extra_fields):
        # **extra_fields catches any extra data passed in (first_name, etc.)
        if not email:
            raise ValueError('Email is required')
        email = self.normalize_email(email)  # lowercase the domain part
        user  = self.model(email=email, **extra_fields)
        user.set_password(password)          # hash — never store plain text
        user.save()
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        # is_staff     = can access /admin panel
        # is_superuser = has all permissions automatically
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        return self.create_user(email, password, **extra_fields)


# ── 2. USER MODEL ─────────────────────────────────────────────
# Custom user model — always do this before the first migration.
# Adding it later requires deleting the DB and starting over.
# CUSTOMIZE: add any account-level fields here (not personal info — that goes in Profile)

class User(AbstractUser):
    username   = None  # removed — we use email instead
    email      = models.EmailField(unique=True)
    first_name = models.CharField(max_length=30, blank=True, null=True)
    last_name  = models.CharField(max_length=30, blank=True, null=True)
    phone      = models.CharField(max_length=20, blank=True, null=True)

    # User-level feature permissions — granted by admin on a per-user basis.
    # False by default: users cannot do these things until an admin explicitly allows it.
    # EXPAND: add more booleans here as new user-facing features need access control.
    can_create_group = models.BooleanField(default=False)

    objects = UserManager()  # attach our custom manager

    USERNAME_FIELD  = 'email'  # email is the login field
    REQUIRED_FIELDS = []       # only email + password required at creation

    def __str__(self):
        return self.email


# ── 3. PERSONAL INFO — Abstract Base ─────────────────────────
# abstract = True → Django creates NO table for this.
# It's a blueprint — Profile and ManagedProfile both inherit these fields.
# CUSTOMIZE: add, remove, or rename fields to match what your project collects.

class PersonalInfo(models.Model):
    first_name       = models.CharField(max_length=30, blank=True, null=True)
    last_name        = models.CharField(max_length=30, blank=True, null=True)
    date_of_birth    = models.DateField(blank=True, null=True)
    gender           = models.CharField(max_length=10, blank=True, null=True)
    country_of_birth = models.CharField(max_length=100, blank=True, null=True)
    city_of_birth    = models.CharField(max_length=100, blank=True, null=True)
    passport_number  = models.CharField(max_length=20, blank=True, null=True)
    passport_picture = models.ImageField(upload_to='passport_pictures/', blank=True, null=True)
    profile_picture  = models.ImageField(upload_to='profile_pictures/', blank=True, null=True)

    class Meta:
        abstract = True  # no DB table — just a blueprint

    def full_name(self):
        # safe helper — works even when first_name or last_name is None
        # usage in templates: {{ profile.full_name }}
        # usage in views:     managed.full_name()
        return f"{self.first_name or ''} {self.last_name or ''}".strip()

    def __str__(self):
        return self.full_name()


# ── 4. PROFILE — Real User's Personal Info ───────────────────
# One-to-one with User. Auto-created by signal in signals.py.
# Keeps User clean (auth only) — all personal data lives here.
# CUSTOMIZE: add domain-specific fields here (e.g., license_number, bio)

class Profile(PersonalInfo):
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='profile'  # access via: request.user.profile.full_name()
    )

    def __str__(self):
        return f'{self.first_name} {self.last_name}'


# ── 5. MANAGED PROFILE — Interior Person (No Login Required) ─
# A person managed by another user — e.g., a parent managing an elderly relative.
# The group leader creates this and fills requirements on their behalf.
# CUSTOMIZE: add a 'relationship' field if your domain tracks it (e.g., "mother")
# CUSTOMIZE: add a 'status' field if profiles go through a workflow

class ManagedProfile(PersonalInfo):
    # Who created and is responsible for this profile
    created_by = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='managed_profiles'  # user.managed_profiles.all()
    )

    # Optional: fill this if the person later creates their own account
    # null  = no account yet
    # filled = they now have their own login
    linked_user = models.OneToOneField(
        User,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='managed_account'
    )

    # String reference — avoids circular import between users and groups apps
    group = models.ForeignKey(
        'groups.Group',
        on_delete=models.CASCADE,
        null=True, blank=True,
        related_name='managed_profiles'
    )

    def __str__(self):
        return f'{self.first_name} {self.last_name} (managed by {self.created_by.email})'


# ── 6. ADMIN PROFILE — Granular Staff Permissions ────────────
# SuperAdmin controls exactly what each staff member can do.
# An admin can ONLY do what is explicitly True here.
# CUSTOMIZE: replace boolean fields with the capabilities your project needs.
# EXPAND: add more booleans as new admin features are built — no migration complexity.

class AdminProfile(models.Model):
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='admin_profile'  # access via: user.admin_profile.can_create_groups
    )

    # CUSTOMIZE: define the capabilities your admin panel needs
    can_create_groups   = models.BooleanField(default=False)
    can_assign_members  = models.BooleanField(default=False)
    can_view_all_cases  = models.BooleanField(default=False)
    can_create_users    = models.BooleanField(default=False)
    can_manage_roles    = models.BooleanField(default=False)
    can_manage_content = models.BooleanField(default=False)

    # Audit trail — who created this admin and when
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='created_admins'  # superadmin.created_admins.all()
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f'AdminProfile({self.user.email})'