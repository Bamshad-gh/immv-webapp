from django.db.models.signals import post_save  # the signal we want to listen for
from django.dispatch import receiver             # decorator that connects function to signal
from .models import User, Profile                # models from same app (. = current folder)

# ── SIGNAL 1: Auto-create empty Profile when new User is created ──
@receiver(post_save, sender=User)   # listen for post_save on User model
def create_user_profile(sender, instance, created, **kwargs):
    """
    Fires automatically every time a User object is saved.
    We only want to create a Profile when it's a NEW user (created=True)
    not every time the user updates their info (created=False)
    """
    if created:                                  # True = brand new user
        Profile.objects.create(user=instance)   # create empty profile linked to this user
        print(f"✓ Profile auto-created for {instance.email}")  # for debugging

# ── SIGNAL 2: Keep Profile in sync when User is updated ───────────
@receiver(post_save, sender=User)
def save_user_profile(sender, instance, created, **kwargs):
    """
    Fires when an existing user is updated.
    Makes sure profile is also saved when user is saved.
    """
    if not created:                  # False = existing user being updated
        try:
            instance.profile.save()  # save the related profile too
        except Profile.DoesNotExist:
            # Safety check: if profile doesn't exist for some reason, create it
            Profile.objects.create(user=instance)