import json

from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver

from images.models import Image

from webhooks.models import Webhook

from utils.webhooks import event


@receiver(post_save, sender=Image)
def on_image_update_webhook(sender, instance, created, **kwargs):
    event(
        Webhook.Event.ON_IMAGE_CREATE if created else Webhook.Event.ON_IMAGE_UPDATE,
        instance,
    )


@receiver(post_delete, sender=Image)
def on_image_delete_webhook(sender, instance, **kwargs):
    event(Webhook.Event.ON_IMAGE_DELETE, instance)
