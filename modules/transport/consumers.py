import json

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer
from django.db.models import Q
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from modules.transport.models.travel import Travel
from modules.transport.services import LocationRejected, save_travel_location


class TravelLocationConsumer(AsyncWebsocketConsumer):
    """
    Canal de acompanhamento em tempo real de uma viagem:

    wss://host/ws/travels/<travel_id>/location/ (cookie de acesso)

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

        if travel.status != Travel.Status.IN_PROGRESS:
            await self.close(code=4009)
            return

        if not await self._user_can_access(travel, user):
            await self.close(code=4003)
            return

        self.user = user

        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

        if travel.current_latitude is not None:
            await self.send(
                text_data=json.dumps({
                    'type': 'location',
                    'latitude': travel.current_latitude,
                    'longitude': travel.current_longitude,
                    'updated_at': travel.location_updated_at.isoformat() if travel.location_updated_at else None,
                })
            )

    async def disconnect(self, close_code):
        if hasattr(self, 'group_name'):
            await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def receive(self, text_data=None, bytes_data=None):
        if not await self._can_receive(self.travel_id, self.user, self.scope['access_jti'], self.scope['access_exp']):
            await self.close(code=4003)
            return
        try:
            data = json.loads(text_data)
            latitude = float(data['latitude'])
            longitude = float(data['longitude'])
            recorded_at = parse_datetime(data['recorded_at']) if 'recorded_at' in data else None
            if 'recorded_at' in data and recorded_at is None:
                raise ValueError('Horário inválido.')
        except (TypeError, ValueError, KeyError, json.JSONDecodeError):
            await self.send(text_data=json.dumps({'type': 'error', 'detail': 'Localização inválida.'}))
            return
        try:
            await self._save_location(self.travel_id, self.user.pk, latitude, longitude, recorded_at)
        except LocationRejected as exc:
            await self.send(text_data=json.dumps({'type': 'error', 'detail': str(exc)}))

    async def location_update(self, event):
        if not await self._can_receive(self.travel_id, self.user, self.scope['access_jti'], self.scope['access_exp']):
            await self.close(code=4009)
            return
        await self.send(
            text_data=json.dumps({
                'type': 'location',
                'latitude': event['latitude'],
                'longitude': event['longitude'],
                'updated_at': event['updated_at'],
            })
        )

    async def travel_closed(self, event):
        await self.send(text_data=json.dumps({'type': 'closed'}))
        await self.close(code=1000)

    @database_sync_to_async
    def _get_travel(self, travel_id):
        return (
            Travel.objects
            .select_related('company__user', 'driver__user', 'path__route_group')
            .filter(pk=travel_id)
            .first()
        )

    @database_sync_to_async
    def _user_can_access(self, travel, user):
        if (travel.driver.user_id == user.id and travel.driver.is_approved) or (
            travel.company.user_id == user.id and travel.company.is_approved
        ):
            return True
        return travel.path.route_group.passengers.filter(user=user, is_approved=True).exists()

    @database_sync_to_async
    def _can_receive(self, travel_id, user, access_jti, access_exp):
        from modules.accounts.models.user_session import UserSession

        if (
            timezone.now().timestamp() >= access_exp
            or not UserSession.objects.filter(user=user, access_jti=access_jti, is_active=True).exists()
        ):
            return False
        return (
            Travel.objects
            .filter(pk=travel_id, status=Travel.Status.IN_PROGRESS)
            .filter(
                Q(company__user=user, company__is_approved=True)
                | Q(driver__user=user, driver__is_approved=True)
                | Q(path__route_group__passengers__user=user, path__route_group__passengers__is_approved=True)
            )
            .exists()
        )

    @database_sync_to_async
    def _save_location(self, travel_id, user_id, latitude, longitude, recorded_at):
        return save_travel_location(travel_id, user_id, latitude, longitude, recorded_at)
