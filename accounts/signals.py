from django.conf import settings
from django.db.models.signals import post_save
from django.dispatch import receiver

from accounts.models import Profile


@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def create_profile_and_cart(sender, instance, created, **kwargs):
    """Whenever a new User is created, give them an empty Profile and an
    empty Cart so the rest of the app can always assume both exist."""
    if not created:
        return

    Profile.objects.get_or_create(user=instance)

    # Imported here to avoid a circular import between accounts <-> store.
    from store.models import Cart

    Cart.objects.get_or_create(user=instance)
