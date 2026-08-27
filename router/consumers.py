import json

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer
from django.utils import timezone

from router.models.travel import Travel


class TravelLocationConsumer(AsyncWebsocketConsumer):
    """
    Canal de acompanhamento em tempo real de uma viagem:

    ws://host/ws/travels/<travel_id>/location/?token=<jwt access token>

    - O motorista da viagem envia {"latitude": ..., "longitude": ...} e essa
      localização é salva e retransmitida para todos os conectados (empresa e
      passageiros da rota).
    - Passageiros/empresa só recebem atualizações, não podem enviar.
    """

    async def connect(self):
        self.travel_id = self.scope['url_route']['kwargs']['travel_id']
        self.group_name = f'travel_{self.travel_id}'
        user = self.scope.get('user')

        if not user or not user.is_authenticated:
            await self.close(code=4001)
            return

        travel = await self._get_travel(self.travel_id)
        if travel is None:
            await self.close(code=4004)
            return

        if not await self._user_can_access(travel, user):
            await self.close(code=4003)
            return

        self.user = user

        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

        if travel.current_latitude is not None:
            await self.send(text_data=json.dumps({
                'type': 'location',
                'latitude': travel.current_latitude,
                'longitude': travel.current_longitude,
                'updated_at': travel.location_updated_at.isoformat() if travel.location_updated_at else None,
            }))

    async def disconnect(self, close_code):
        if hasattr(self, 'group_name'):
            await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def receive(self, text_data=None, bytes_data=None):
        if not await self._is_driver(self.travel_id, self.user):
            return

        try:
            data = json.loads(text_data)
            latitude = float(data['latitude'])
            longitude = float(data['longitude'])
        except (TypeError, ValueError, KeyError, json.JSONDecodeError):
            return

        updated_at = timezone.now()
        await self._save_location(self.travel_id, latitude, longitude, updated_at)

        await self.channel_layer.group_send(self.group_name, {
            'type': 'location_update',
            'latitude': latitude,
            'longitude': longitude,
            'updated_at': updated_at.isoformat(),
        })

    async def location_update(self, event):
        await self.send(text_data=json.dumps({
            'type': 'location',
            'latitude': event['latitude'],
            'longitude': event['longitude'],
            'updated_at': event['updated_at'],
        }))

    @database_sync_to_async
    def _get_travel(self, travel_id):
        return (
            Travel.objects.select_related('company__user', 'driver__user', 'path__route_group')
            .filter(pk=travel_id)
            .first()
        )

    @database_sync_to_async
    def _user_can_access(self, travel, user):
        if user.is_staff or user.is_superuser:
            return True
        if travel.driver.user_id == user.id or travel.company.user_id == user.id:
            return True
        return travel.path.route_group.passengers.filter(user=user).exists()

    @database_sync_to_async
    def _is_driver(self, travel_id, user):
        return Travel.objects.filter(pk=travel_id, driver__user=user).exists()

    @database_sync_to_async
    def _save_location(self, travel_id, latitude, longitude, updated_at):
        Travel.objects.filter(pk=travel_id).update(
            current_latitude=latitude,
            current_longitude=longitude,
            location_updated_at=updated_at,
        )
