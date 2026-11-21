"""Efeitos de transporte via Channels (grupos segmentados), nunca fonte de verdade para autorização."""

import logging

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.db import transaction

logger = logging.getLogger(__name__)


def travel_group(travel_id) -> str:
    return f'travel_{travel_id}'


def travel_ops_group(travel_id) -> str:
    return f'travel_{travel_id}_ops'


def travel_user_group(travel_id, user_id) -> str:
    return f'travel_{travel_id}_user_{user_id}'


def _schedule_group_send(groups: tuple[str, ...], payload: dict, log_event: str, *, travel_id) -> None:
    def deliver():
        layer = get_channel_layer()
        if layer is None:
            return
        send = async_to_sync(layer.group_send)
        for group in groups:
            try:
                send(group, payload)
            except Exception:
                logger.warning('%s travel_id=%s', log_event, travel_id)

    transaction.on_commit(deliver)


def broadcast_location(travel_id, event):
    _schedule_group_send(
        (travel_group(travel_id),),
        {'type': 'location.update'},
        'location_delivery_failed',
        travel_id=travel_id,
    )


def broadcast_approaching(travel_id, recipient_user_id, participation_id, distance_meters):
    payload = {
        'type': 'travel.approaching',
        'recipient_user_id': str(recipient_user_id),
        'participation_id': participation_id,
        'distance_meters': distance_meters,
    }
    _schedule_group_send(
        (travel_ops_group(travel_id), travel_user_group(travel_id, recipient_user_id)),
        payload,
        'travel_approaching_delivery_failed',
        travel_id=travel_id,
    )


def broadcast_presence(travel_id, recipient_user_id, participation_id, status):
    payload = {
        'type': 'travel.presence',
        'recipient_user_id': str(recipient_user_id),
        'participation_id': participation_id,
        'status': status,
    }
    _schedule_group_send(
        (travel_ops_group(travel_id), travel_user_group(travel_id, recipient_user_id)),
        payload,
        'travel_presence_delivery_failed',
        travel_id=travel_id,
    )


def close_travel_after_commit(travel_id):
    _schedule_group_send(
        (travel_group(travel_id),),
        {'type': 'travel.closed'},
        'travel_close_delivery_failed',
        travel_id=travel_id,
    )
