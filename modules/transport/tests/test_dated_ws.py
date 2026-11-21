from uuid import uuid4

from asgiref.sync import async_to_sync
from channels.db import database_sync_to_async
from channels.routing import URLRouter
from channels.security.websocket import OriginValidator
from channels.sessions import CookieMiddleware
from channels.testing import WebsocketCommunicator
from django.test import override_settings
from rest_framework.test import APIClient

from modules.accounts.models import UserSession
from modules.accounts.ws_auth import JWTAuthMiddleware
from modules.transport.routing import websocket_urlpatterns
from modules.transport.services.demand import withdraw_leg
from modules.transport.services.execution import finish_travel, record_participation, start_travel
from tests.helpers import PASSWORD

from .service_helpers import ServiceTestCase


@override_settings(WS_REVALIDATION_SECONDS=0.2)
class DatedWebSocketTests(ServiceTestCase):
    def setUp(self):
        super().setUp()
        self.trip = self.ready_travel()
        self.publish(self.trip)
        start_travel(actor_id=self.driver.user_id, travel_id=self.trip.pk, expected_revision=self.trip.revision)
        self.app = OriginValidator(
            CookieMiddleware(JWTAuthMiddleware(URLRouter(websocket_urlpatterns))),
            ['http://testserver'],
        )

    def headers(self, user, *, origin=b'http://testserver'):
        client = APIClient(enforce_csrf_checks=True)
        csrf = client.get('/api/csrf/').data['csrfToken']
        response = client.post('/api/login/', {'email': user.email, 'password': PASSWORD}, HTTP_X_CSRFTOKEN=csrf)
        self.assertEqual(response.status_code, 200)
        cookie = '; '.join(f'{name}={value.value}' for name, value in client.cookies.items())
        return [(b'origin', origin), (b'cookie', cookie.encode())]

    def socket(self, headers):
        return WebsocketCommunicator(self.app, f'/ws/travels/{self.trip.pk}/location/', headers=headers)

    def test_origin_cookie_only_and_allocation_are_required(self):
        allowed = self.headers(self.passenger.user)
        wrong_origin = [(b'origin', b'https://evil.example.com'), allowed[1]]
        foreign = self.headers(self.other.user)
        bearer = [(b'origin', b'http://testserver'), (b'authorization', b'Bearer not-accepted')]

        async def scenario():
            for headers in (wrong_origin, foreign, bearer):
                socket = self.socket(headers)
                self.assertFalse((await socket.connect())[0])
                await socket.disconnect()
            socket = self.socket(allowed)
            self.assertTrue((await socket.connect())[0])
            first = await socket.receive_json_from()
            self.assertTrue(first['stale'])
            self.assertIsNone(first['position'])
            await socket.disconnect()

        async_to_sync(scenario)()

    def test_driver_positions_revalidate_recipients_and_withdrawal_closes_access(self):
        driver_headers, passenger_headers = self.headers(self.driver.user), self.headers(self.passenger.user)

        async def scenario():
            driver, passenger = self.socket(driver_headers), self.socket(passenger_headers)
            self.assertTrue((await driver.connect())[0])
            self.assertTrue((await passenger.connect())[0])
            await driver.receive_json_from()
            await passenger.receive_json_from()
            await driver.send_json_to({'latitude': -26.3, 'longitude': -48.8, 'recorded_at': self.now.isoformat()})
            position = await passenger.receive_json_from()
            self.assertEqual(position['position']['latitude'], -26.3)
            self.assertFalse(position['stale'])
            await driver.receive_json_from()
            await database_sync_to_async(withdraw_leg)(
                actor_id=self.passenger.user_id, eligibility_id=self.eligibility.pk, leg='outbound'
            )
            output = await passenger.receive_output(timeout=2)
            self.assertEqual(output['type'], 'websocket.close')
            await passenger.disconnect()
            await driver.disconnect()

        async_to_sync(scenario)()

    def test_revocation_closes_idle_connection_without_waiting_for_gps(self):
        headers = self.headers(self.passenger.user)

        async def scenario():
            socket = self.socket(headers)
            self.assertTrue((await socket.connect())[0])
            await socket.receive_json_from()
            await database_sync_to_async(
                lambda: UserSession.objects.filter(user=self.passenger.user).update(is_active=False)
            )()
            output = await socket.receive_output(timeout=2)
            self.assertEqual(output['type'], 'websocket.close')
            self.assertEqual(output['code'], 4001)
            await socket.disconnect()

        async_to_sync(scenario)()

    def test_finish_closes_socket_and_binary_or_oversized_payloads_are_rejected(self):
        headers = self.headers(self.driver.user)

        async def scenario():
            socket = self.socket(headers)
            self.assertTrue((await socket.connect())[0])
            await socket.receive_json_from()
            await socket.send_to(bytes_data=b'invalid')
            self.assertEqual((await socket.receive_output())['code'], 1009)
            await socket.disconnect()
            socket = self.socket(headers)
            self.assertTrue((await socket.connect())[0])
            await socket.receive_json_from()
            participant = await database_sync_to_async(self.trip.participations.get)()
            await database_sync_to_async(record_participation)(
                actor_id=self.driver.user_id, participation_id=participant.pk, kind='no_show', operation_id=uuid4()
            )
            await database_sync_to_async(finish_travel)(actor_id=self.driver.user_id, travel_id=self.trip.pk)
            self.assertEqual((await socket.receive_json_from())['type'], 'closed')
            self.assertEqual((await socket.receive_output())['code'], 1000)
            await socket.disconnect()

        async_to_sync(scenario)()
