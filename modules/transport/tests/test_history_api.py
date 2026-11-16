from unittest.mock import patch
from uuid import uuid4

from rest_framework.test import APIClient

from modules.organizations.services.memberships import end_membership
from modules.transport.models import LostItem
from modules.transport.services.execution import finish_travel, record_participation, start_travel
from modules.transport.services.history import report_lost_item, transition_lost_item

from .service_helpers import ServiceTestCase


class HistoryApiTests(ServiceTestCase):
    def setUp(self):
        super().setUp()
        self.client = APIClient()
        self.trip = self.ready_travel()
        self.publish(self.trip)
        start_travel(actor_id=self.driver.user_id, travel_id=self.trip.pk, expected_revision=self.trip.revision)
        self.participant = self.trip.participations.get()

    def finish(self, *, boarded=True):
        for kind in ('boarded', 'dropped_off') if boarded else ('no_show',):
            record_participation(
                actor_id=self.driver.user_id, participation_id=self.participant.pk, kind=kind, operation_id=uuid4()
            )
        finish_travel(actor_id=self.driver.user_id, travel_id=self.trip.pk)

    def test_rating_requires_finished_trip_and_real_drop_off_not_intention(self):
        self.client.force_authenticate(self.passenger.user)
        data = {'travel_id': self.trip.pk, 'score': 5, 'comment': 'Avaliação fictícia'}
        self.assertEqual(self.client.post('/api/driver-ratings/', data, format='json').status_code, 400)
        self.finish()
        response = self.client.post('/api/driver-ratings/', data, format='json')
        self.assertEqual(response.status_code, 201, response.data)
        again = self.client.post('/api/driver-ratings/', data, format='json')
        self.assertEqual(again.data['id'], response.data['id'])
        self.client.force_authenticate(self.driver.user)
        self.assertEqual(self.client.post('/api/driver-ratings/', data, format='json').status_code, 403)

    def test_no_show_cannot_rate_or_report_and_ended_membership_cannot_read(self):
        self.finish(boarded=False)
        self.client.force_authenticate(self.passenger.user)
        self.assertEqual(
            self.client.post('/api/driver-ratings/', {'travel_id': self.trip.pk, 'score': 5}).status_code, 403
        )
        self.assertEqual(
            self.client.post(
                '/api/lost-items/',
                {'travel_id': self.trip.pk, 'item_description': 'Caderno', 'operation_id': str(uuid4())},
            ).status_code,
            403,
        )
        end_membership(actor_id=self.passenger.user_id, membership_id=self.membership.pk)
        self.assertEqual(self.client.get('/api/driver-ratings/').data['results'], [])

    def test_lost_item_custody_is_company_only_forward_and_audited_idempotently(self):
        self.finish()
        self.client.force_authenticate(self.passenger.user)
        operation_id = str(uuid4())
        data = {'travel_id': self.trip.pk, 'item_description': 'Caderno fictício', 'operation_id': operation_id}
        first = self.client.post('/api/lost-items/', data, format='json')
        self.assertEqual(first.status_code, 201, first.data)
        again = self.client.post('/api/lost-items/', data, format='json')
        self.assertEqual(first.data['id'], again.data['id'])
        url = f'/api/lost-items/{first.data["id"]}/transition/'
        found = {'target_status': 'found', 'operation_id': str(uuid4())}
        self.assertEqual(self.client.post(url, found, format='json').status_code, 403)
        self.client.force_authenticate(self.driver.user)
        self.assertEqual(self.client.post(url, found, format='json').status_code, 403)
        self.client.force_authenticate(self.other.user)
        self.assertEqual(self.client.post(url, found, format='json').status_code, 404)
        self.client.force_authenticate(self.company.user)
        for _ in range(2):
            self.assertEqual(self.client.post(url, found, format='json').status_code, 200)
        returned = {'target_status': 'returned', 'operation_id': str(uuid4())}
        response = self.client.post(url, returned, format='json')
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual([event['status'] for event in response.data['events']], ['reported', 'found', 'returned'])
        self.assertEqual(
            self.client.post(url, {'target_status': 'found', 'operation_id': str(uuid4())}, format='json').status_code,
            409,
        )
        self.assertEqual(self.client.delete(f'/api/lost-items/{first.data["id"]}/').status_code, 405)

    def test_audit_failure_rolls_back_custody_change(self):
        self.finish()
        item = report_lost_item(
            actor_id=self.driver.user_id,
            travel_id=self.trip.pk,
            item_description='Objeto fictício',
            operation_id=uuid4(),
        )
        with (
            patch(
                'modules.transport.services.history.LostItemEvent.objects.create', side_effect=RuntimeError('fixture')
            ),
            self.assertRaises(RuntimeError),
        ):
            transition_lost_item(
                actor_id=self.company.user_id, item_id=item.pk, target_status='found', operation_id=uuid4()
            )
        self.assertEqual(LostItem.objects.get(pk=item.pk).status, 'reported')
        self.assertEqual(item.events.count(), 1)
