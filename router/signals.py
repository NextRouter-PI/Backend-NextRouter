from django.db.models.signals import post_save
from django.dispatch import receiver

from authenticator.models import Driver, Passenger
from router.services import ensure_route_group_geocoded, sync_stop_for_user


@receiver(post_save, sender=Passenger)
def passenger_saved(sender, instance, **kwargs):
    if not instance.route_group_id:
        return

    ensure_route_group_geocoded(instance.route_group)
    sync_stop_for_user(instance.route_group, instance.user)


@receiver(post_save, sender=Driver)
def driver_saved(sender, instance, **kwargs):
    if not instance.route_group_id:
        return

    ensure_route_group_geocoded(instance.route_group)
    sync_stop_for_user(instance.route_group, instance.user, label=f'Motorista: {instance.user.name.title()}')
