"""Efeitos de transporte, nunca fonte de verdade para autorização ou decisão."""

import logging

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.db import transaction

logger = logging.getLogger(__name__)


def broadcast_location(travel_id, event):
    async_to_sync(get_channel_layer().group_send)(f'travel_{travel_id}', {'type': 'location.update'})


def broadcast_approaching(travel_id, recipient_user_id, participation_id, distance_meters):
    def deliver():
        try:
            async_to_sync(get_channel_layer().group_send)(
                f'travel_{travel_id}',
                {
                    'type': 'travel.approaching',
                    'recipient_user_id': str(recipient_user_id),
                    'participation_id': participation_id,
                    'distance_meters': distance_meters,
                },
            )
        except Exception:
            logger.warning('travel_approaching_delivery_failed travel_id=%s', travel_id)

    transaction.on_commit(deliver)


def broadcast_presence(travel_id, recipient_user_id, participation_id, status):
    def deliver():
        try:
            async_to_sync(get_channel_layer().group_send)(
                f'travel_{travel_id}',
                {
                    'type': 'travel.presence',
                    'recipient_user_id': str(recipient_user_id),
                    'participation_id': participation_id,
                    'status': status,
                },
            )
        except Exception:
            logger.warning('travel_presence_delivery_failed travel_id=%s', travel_id)

    transaction.on_commit(deliver)


def close_travel_after_commit(travel_id):
    def deliver():
        try:
            async_to_sync(get_channel_layer().group_send)(f'travel_{travel_id}', {'type': 'travel.closed'})
        except Exception:
            logger.warning('travel_close_delivery_failed travel_id=%s', travel_id)

    transaction.on_commit(deliver)
