"""Signals for the twf app."""

from django.contrib.auth import get_user_model
from django.db.models.signals import post_save
from django.dispatch import receiver
from twf.models import UserProfile

User = get_user_model()


@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    """Create a user profile when a user is created."""
    if created:
        UserProfile.objects.create(user=instance)


@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    """Save the user profile when the user is saved."""
    instance.profile.save()
