from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import models

# ── CUSTOM MANAGER ────────────────────────────────────────────
# Needed when you remove username completely and use email instead
# Teaches Django how to create users without username

class UserManager(BaseUserManager):
    
    def create_user(self, email, password=None, **extra_fields):
        # **extra_fields catches any extra data passed in (first_name etc.)
        if not email:
            raise ValueError('Email is required')
        email = self.normalize_email(email)  # lowercase domain part of email
        user = self.model(email=email, **extra_fields)  # create user object
        user.set_password(password)  # hash password safely (never store plain text)
        user.save()
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        # is_staff = can access /admin panel
        # is_superuser = has all permissions
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        return self.create_user(email, password, **extra_fields)


# ── USER MODEL ────────────────────────────────────────────────
class User(AbstractUser):
    username   = None  # remove username — we use email instead
    email      = models.EmailField(unique=True)  # unique = no duplicate emails
    first_name = models.CharField(max_length=30, blank=True, null=True)
    last_name  = models.CharField(max_length=30, blank=True, null=True)
    phone      = models.CharField(max_length=20, blank=True, null=True)

    objects = UserManager()  # attach our custom manager to this model

    USERNAME_FIELD  = 'email'  # use email as the login field
    REQUIRED_FIELDS = []       # no extra required fields — email+password only

    def __str__(self):
        return self.email


# ── PROFILE MODEL ─────────────────────────────────────────────
# Separate from User — stores personal info, not login info
# One User → One Profile (OneToOneField)

class Profile(models.Model):
    user             = models.OneToOneField(User, on_delete=models.CASCADE)
    # on_delete=CASCADE means: if User is deleted → Profile is deleted too
    date_of_birth    = models.DateField(blank=True, null=True)
    gender           = models.CharField(max_length=10, blank=True, null=True)
    country_of_birth = models.CharField(max_length=100, blank=True, null=True)
    city_of_birth    = models.CharField(max_length=100, blank=True, null=True)
    passport_picture = models.ImageField(upload_to='passport_pictures/', blank=True, null=True)
    passport_number  = models.CharField(max_length=20, blank=True, null=True)
    profile_picture  = models.ImageField(upload_to='profile_pictures/', blank=True, null=True)

    def __str__(self):
        return f'{self.user.first_name} {self.user.last_name}'
    
# ── managed profile model ─────────────────────────────────────────────
class managed_Profile(models.Model):
    user             = models.OneToOneField(User, on_delete=models.CASCADE)
    managed_Profile_first_name = models.CharField(max_length=30, blank=True, null=True)
    managed_Profile_last_name  = models.CharField(max_length=30, blank=True, null=True)
    # on_delete=CASCADE means: if User is deleted → Profile is deleted too
    managed_Profile_date_of_birth    = models.DateField(blank=True, null=True)
    managed_Profile_gender           = models.CharField(max_length=10, blank=True, null=True)
    managed_Profile_country_of_birth = models.CharField(max_length=100, blank=True, null=True)
    managed_Profile_city_of_birth    = models.CharField(max_length=100, blank=True, null=True)
    managed_Profile_passport_picture = models.ImageField(upload_to='passport_pictures/', blank=True, null=True)
    managed_Profile_passport_number  = models.CharField(max_length=20, blank=True, null=True)
    managed_Profile_profile_picture  = models.ImageField(upload_to='profile_pictures/', blank=True, null=True)

    def __str__(self):
        return f'{self.managed_Profile_first_name} {self.managed_Profile_last_name}'