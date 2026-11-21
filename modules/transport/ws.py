import asyncio
import contextlib
import json
from datetime import timedelta
from math import isfinite
from time import monotonic

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer
from django.conf import settings
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from pydantic import BaseModel, ConfigDict, StrictFloat, StrictInt, StrictStr, field_validator
from pydantic import ValidationError as PydanticValidationError

from modules.accounts.models import UserSession
from modules.transport.broadcast import (
    broadcast_location,
    travel_group,
    travel_ops_group,
    travel_user_group,
)
from modules.transport.services.tracking import read_location, save_location


class LocationFrame(BaseModel):
    model_config = ConfigDict(extra='forbid')

    latitude: StrictFloat | StrictInt
    longitude: StrictFloat | StrictInt
    recorded_at: StrictStr

    @field_validator('latitude')
    @classmethod
    def _validate_lat(cls, value: float | int) -> float:
        if not -90 <= value <= 90:
            raise ValueError('Latitude inválida.')
        numeric = float(value)
        if not isfinite(numeric):
            raise ValueError('Latitude inválida.')
        return numeric

    @field_validator('longitude')
    @classmethod
    def _validate_lon(cls, value: float | int) -> float:
        if not -180 <= value <= 180:
            raise ValueError('Longitude inválida.')
        numeric = float(value)
        if not isfinite(numeric):
            raise ValueError('Longitude inválida.')
        return numeric


class TravelLocationConsumer(AsyncWebsocketConsumer):
    """Cookie + Origin no middleware; grupos segmentados e autorização revalidada antes de cada entrega."""

    async def connect(self):
        self.travel_id = self.scope['url_route']['kwargs']['travel_id']
        self.group_name = travel_group(self.travel_id)
        self.subscribed_groups: list[str] = []
        self.watchdog = None
        self._last_gps_monotonic: float | None = None
        if not await self.session_active():
            await self.close(code=4001)
            return
        position = await self.position()
        if position is None:
            await self.close(code=4003)
            return

        groups = [self.group_name]
        if await self.is_operational_viewer():
            groups.append(travel_ops_group(self.travel_id))
        else:
            groups.append(travel_user_group(self.travel_id, self.scope['user'].pk))
        for group in groups:
            await self.channel_layer.group_add(group, self.channel_name)
            self.subscribed_groups.append(group)

        await self.accept()
        await self.send_json({'type': 'location', **position})
        self.watchdog = asyncio.create_task(self.watch_access())

    async def disconnect(self, close_code):
        if self.watchdog:
            self.watchdog.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self.watchdog
        for group in getattr(self, 'subscribed_groups', ()):
            await self.channel_layer.group_discard(group, self.channel_name)

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
        if bytes_data is not None or not text_data or len(text_data.encode('utf-8')) > 1024:
            await self.close(code=1009)
            return
        try:
            frame = LocationFrame.model_validate_json(text_data)
            recorded_at = parse_datetime(frame.recorded_at)
            if recorded_at is None:
                raise ValueError('recorded_at inválido')
            now_mono = monotonic()
            if (
                self._last_gps_monotonic is not None
                and now_mono - self._last_gps_monotonic < settings.LOCATION_MIN_INTERVAL_SECONDS
            ):
                await self.send_json({
                    'type': 'error',
                    'code': 'position_rate_limited',
                    'detail': 'Posição recusada.',
                })
                return
            if not await self.session_active() or await self.position() is None:
                await self.close(code=4003)
                return
            await self.persist(frame.latitude, frame.longitude, recorded_at)
            self._last_gps_monotonic = now_mono
        except (ValueError, TypeError, KeyError, PydanticValidationError, ValidationError) as exc:
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
        return UserSession.objects.for_access_jti(self.scope.get('access_jti'), user_id=user.pk).exists()

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
