import asyncio
import contextlib
import json
from datetime import timedelta

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer
from django.conf import settings
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from modules.accounts.models import UserSession
from modules.transport.broadcast import broadcast_location
from modules.transport.services.tracking import read_location, save_location


class TravelLocationConsumer(AsyncWebsocketConsumer):
    """Cookie + Origin no middleware; autorização revalidada antes de cada entrega."""

    async def connect(self):
        self.travel_id = self.scope['url_route']['kwargs']['travel_id']
        self.group_name = f'travel_{self.travel_id}'
        self.watchdog = None
        if not await self.session_active():
            await self.close(code=4001)
            return
        position = await self.position()
        if position is None:
            await self.close(code=4003)
            return
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()
        await self.send_json({'type': 'location', **position})
        self.watchdog = asyncio.create_task(self.watch_access())

    async def disconnect(self, close_code):
        if self.watchdog:
            self.watchdog.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self.watchdog
        if hasattr(self, 'group_name'):
            await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def send_json(self, data):
        await self.send(text_data=json.dumps(data))

    async def watch_access(self):
        while True:
            remaining = self.scope['access_exp'] - timezone.now().timestamp()
            await asyncio.sleep(max(0, min(settings.WS_REVALIDATION_SECONDS, remaining)))
            if not await self.session_active():
                await self.close(code=4001)
                return
            position = await self.position()
            if position is None:
                await self.close(code=4009)
                return
            # Informa desatualização mesmo sem novas coordenadas chegando.
            if position['stale']:
                await self.send_json({'type': 'location', **position})

    async def receive(self, text_data=None, bytes_data=None):
        if not await self.session_active() or await self.position() is None:
            await self.close(code=4003)
            return
        if bytes_data is not None or not text_data or len(text_data.encode('utf-8')) > 1024:
            await self.close(code=1009)
            return
        try:
            data = json.loads(text_data)
            if not isinstance(data, dict) or set(data) != {'latitude', 'longitude', 'recorded_at'}:
                raise ValueError
            if not isinstance(data['recorded_at'], str):
                raise ValueError
            recorded_at = parse_datetime(data['recorded_at'])
            await self.persist(data['latitude'], data['longitude'], recorded_at)
        except (ValueError, TypeError, KeyError, ValidationError) as exc:
            code = getattr(exc, 'code', None) or 'invalid_position'
            await self.send_json({'type': 'error', 'code': code, 'detail': 'Posição recusada.'})

    async def location_update(self, event):
        if not await self.session_active():
            await self.close(code=4001)
            return
        position = await self.position()
        if position is None:
            await self.close(code=4009)
            return
        # Releitura evita transmitir evento antigo ou dados a quem perdeu acesso.
        await self.send_json({'type': 'location', **position})

    async def travel_approaching(self, event):
        if not await self.session_active():
            await self.close(code=4001)
            return
        user_id = str(self.scope['user'].pk)
        if user_id != event['recipient_user_id'] and not await self.is_operational_viewer():
            return
        await self.send_json({
            'type': 'approaching',
            'participation_id': event['participation_id'],
            'distance_meters': event['distance_meters'],
        })

    async def travel_presence(self, event):
        if not await self.session_active():
            await self.close(code=4001)
            return
        user_id = str(self.scope['user'].pk)
        if user_id != event['recipient_user_id'] and not await self.is_operational_viewer():
            return
        await self.send_json({
            'type': 'presence',
            'participation_id': event['participation_id'],
            'status': event['status'],
        })

    async def travel_closed(self, event):
        await self.send_json({'type': 'closed'})
        await self.close(code=1000)

    @database_sync_to_async
    def is_operational_viewer(self):
        from modules.transport.access import operational_travels_for

        return operational_travels_for(self.scope['user']).filter(pk=self.travel_id).exists()

    @database_sync_to_async
    def session_active(self):
        user = self.scope.get('user')
        expiration = self.scope.get('access_exp')
        if not user or not user.is_authenticated or not expiration or timezone.now().timestamp() >= expiration:
            return False
        return UserSession.objects.filter(
            user_id=user.pk,
            user__is_active=True,
            access_jti=self.scope.get('access_jti'),
            is_active=True,
            expires_at__gt=timezone.now(),
        ).exists()

    @database_sync_to_async
    def position(self):
        try:
            return read_location(actor_id=self.scope['user'].pk, travel_id=self.travel_id)
        except ValidationError:
            return None

    @database_sync_to_async
    def persist(self, latitude, longitude, recorded_at):
        return save_location(
            actor_id=self.scope['user'].pk,
            travel_id=self.travel_id,
            latitude=latitude,
            longitude=longitude,
            recorded_at=recorded_at,
            max_future_skew=timedelta(),
            deliver=broadcast_location,
        )
