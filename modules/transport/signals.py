from django.db.models.signals import post_delete, post_save, pre_save
from django.dispatch import receiver

from modules.accounts.models import User
from modules.organizations.models import Passenger
from modules.transport.models.path import Path
from shared.address import ADDRESS_FIELDS


@receiver(pre_save, sender=Passenger)
def capture_previous_group(sender, instance, **kwargs):
    instance._previous_route_group_id = (
        sender.objects.filter(pk=instance.pk).values_list('route_group_id', flat=True).first() if instance.pk else None
    )


@receiver(post_save, sender=Passenger)
def passenger_changed(sender, instance, **kwargs):
    group_ids = {instance.route_group_id, getattr(instance, '_previous_route_group_id', None)} - {None}
    if group_ids:
        Path.objects.filter(route_group_id__in=group_ids).update(is_outdated=True)


@receiver(post_delete, sender=Passenger)
def passenger_removed(sender, instance, **kwargs):
    if instance.route_group_id:
        Path.objects.filter(route_group_id=instance.route_group_id).update(is_outdated=True)


@receiver(post_save, sender=User)
def passenger_address_changed(sender, instance, update_fields=None, created=False, **kwargs):
    if not created and (update_fields is None or set(update_fields) & set(ADDRESS_FIELDS)):
        Path.objects.filter(route_group__passengers__user=instance).update(is_outdated=True)
