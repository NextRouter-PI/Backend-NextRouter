import json
from datetime import timedelta
from uuid import uuid4

from django.contrib import admin
from django.contrib.admin.helpers import ACTION_CHECKBOX_NAME
from django.core.management import call_command
from rest_framework.test import APIClient

from modules.organizations.models import CompanyMembership, Driver
from modules.organizations.services.memberships import end_membership
from modules.transport.models import Notification, TravelParticipation
from tests.helpers import PASSWORD, create_passenger, create_user

from .service_helpers import ServiceTestCase


class DatedApiTests(ServiceTestCase):
    def setUp(self):
        super().setUp()
        self.client = APIClient()

    def as_user(self, user):
        self.client.force_authenticate(user)

    def post(self, url, data=None, expected=200):
        result = self.client.post(url, data or {}, format='json')
        self.assertEqual(result.status_code, expected, getattr(result, 'data', result.content))
        return result

    def test_membership_http_lifecycle_does_not_mutate_legacy_profile(self):
        passenger = create_passenger('new-api-member@example.com')
        self.as_user(passenger.user)
        result = self.post('/api/memberships/', {'company_id': self.company.pk, 'profile': 'passenger'}, expected=201)
        pk = result.data['id']
        self.post(f'/api/memberships/{pk}/approve/', expected=403)
        self.as_user(self.company.user)
        self.post(f'/api/memberships/{pk}/approve/')
        assigned = self.post(
            f'/api/memberships/{pk}/assign-group/',
            {
                'route_group_id': self.group.pk,
                'transport_point_id': self.home.pk,
            },
        )
        self.post(
            f'/api/group-memberships/{assigned.data["id"]}/authorize-services/',
            {
                'service_ids': [self.outbound.pk, self.returning.pk],
                'habitual_outbound_id': self.outbound.pk,
            },
        )
        self.as_user(passenger.user)
        self.post(f'/api/memberships/{pk}/end/')
        self.assertEqual(self.client.get('/api/eligibilities/').data['results'], [])

    def test_lists_and_filters_are_scoped_before_pagination_without_staff_bypass(self):
        travel = self.ready_travel()
        for user in (self.other.user, create_user('api-staff@example.com', is_staff=True, is_superuser=True)):
            self.as_user(user)
            for resource in ('travels', 'service-days', 'route-snapshots', 'optimization-jobs', 'operational-points'):
                result = self.client.get(f'/api/{resource}/', {'page_size': 100})
                self.assertEqual(result.status_code, 200, result.data)
                self.assertEqual(result.data['results'], [], resource)
            self.assertEqual(self.client.get(f'/api/travels/{travel.pk}/').status_code, 404)
            self.post(f'/api/travels/{travel.pk}/publish/', {'expected_revision': travel.revision}, expected=404)
        self.as_user(self.company.user)
        self.assertEqual(self.client.get('/api/travels/', {'company': self.other.pk}).data['results'], [])

    def test_protected_fields_and_generic_state_patch_are_rejected(self):
        self.as_user(self.company.user)
        self.post('/api/vehicles/', {'company': self.other.pk, 'plate': 'ZZZ1A99', 'capacity': 5}, expected=400)
        self.post(f'/api/service-days/{self.day.pk}/close/', {'normal_deadline': self.now.isoformat()}, expected=400)
        travel = self.travel()
        self.assertEqual(self.client.patch(f'/api/travels/{travel.pk}/', {'status': 'finished'}).status_code, 405)
        self.as_user(self.passenger.user)
        self.assertEqual(
            self.client.patch(f'/api/passengers/{self.passenger.pk}/', {'route_group': self.group.pk}).status_code, 400
        )

    def test_answer_deadline_and_stale_revision_are_checked_in_service(self):
        self.as_user(self.passenger.user)
        url = f'/api/eligibilities/{self.eligibility.pk}/answer/'
        data = {'outbound_service_id': self.outbound.pk, 'return_service_id': None, 'expected_revision': 0}
        self.post(url, data)
        self.assertEqual(self.post(url, data, expected=409).data['code'], 'stale_revision')
        self.now = self.day.normal_deadline
        data['expected_revision'] = 1
        self.assertEqual(self.post(url, data, expected=400).data['code'], 'response_window_closed')

    def test_business_mutation_requires_real_cookie_csrf(self):
        self.client = APIClient(enforce_csrf_checks=True)
        csrf = self.client.get('/api/csrf/').data['csrfToken']
        login = self.client.post(
            '/api/login/', {'email': self.passenger.user.email, 'password': PASSWORD}, HTTP_X_CSRFTOKEN=csrf
        )
        self.assertEqual(login.status_code, 200)
        data = {'outbound_service_id': self.outbound.pk, 'return_service_id': None, 'expected_revision': 0}
        url = f'/api/eligibilities/{self.eligibility.pk}/answer/'
        self.assertEqual(self.client.post(url, data, format='json').status_code, 403)
        response = self.client.post(url, data, format='json', HTTP_X_CSRFTOKEN=login.data['csrfToken'])
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response['Cache-Control'], 'private, no-store')

    def test_passenger_sees_only_own_participation_not_route_or_other_homes(self):
        travel = self.ready_travel()
        self.publish(travel)
        self.as_user(self.passenger.user)
        self.assertEqual(self.client.get(f'/api/travels/{travel.pk}/').status_code, 200)
        for resource in ('route-snapshots', 'route-stops', 'operational-points', 'recurring-services', 'vehicles'):
            result = self.client.get(f'/api/{resource}/')
            self.assertEqual(result.status_code, 200)
            self.assertEqual(result.data['results'], [], resource)
        payload = self.client.get('/api/travel-participations/').data['results']
        self.assertEqual(len(payload), 1)
        self.assertNotIn('cpf', json.dumps(payload))
        self.assertNotIn('latitude', json.dumps(payload))
        unallocated = create_passenger('unallocated-api@example.com')
        self.as_user(unallocated.user)
        self.assertEqual(self.client.get('/api/travels/').data['results'], [])

    def test_publish_start_presence_finish_http_uses_services_and_audit(self):
        travel = self.ready_travel()
        self.as_user(self.company.user)
        published = self.post(f'/api/travels/{travel.pk}/publish/', {'expected_revision': travel.revision})
        self.assertEqual(published.data['revision'], travel.revision)
        self.post(f'/api/travels/{travel.pk}/start/', {'expected_revision': travel.revision}, expected=403)
        self.as_user(self.driver.user)
        self.post(f'/api/travels/{travel.pk}/start/', {'expected_revision': travel.revision})
        participant = travel.participations.get()
        url = f'/api/travel-participations/{participant.pk}/record/'
        operation_id = str(uuid4())
        first = self.post(url, {'kind': 'boarded', 'operation_id': operation_id})
        second = self.post(url, {'kind': 'boarded', 'operation_id': operation_id})
        self.assertEqual(first.data['id'], second.data['id'])
        self.post(f'/api/travels/{travel.pk}/finish/', expected=400)
        self.post(url, {'kind': 'dropped_off', 'operation_id': str(uuid4())})
        self.post(f'/api/travels/{travel.pk}/finish/')
        self.assertEqual(self.client.get(f'/api/travels/{travel.pk}/location/').status_code, 400)

    def test_calculate_returns_accepted_and_worker_command_processes_snapshot(self):
        self.answer()
        self.now = self.day.normal_deadline
        self.as_user(self.company.user)
        self.post(f'/api/service-days/{self.day.pk}/close/')
        call_command(
            'process_route_jobs',
            once=True,
            company_id=self.company.pk,
            lease_seconds=30,
            max_attempts=1,
            retry_seconds=1,
        )
        travel = self.travel()
        self.assertEqual(travel.planning_status, 'ready')
        result = self.post(f'/api/travels/{travel.pk}/calculate/', {'expected_revision': travel.revision}, expected=202)
        self.assertEqual(result.data['state'], 'pending')

    def test_substitute_invitation_only_invited_driver_can_respond(self):
        travel = self.ready_travel()
        substitute = Driver.objects.create(user=create_user('api-substitute@example.com'))
        member = CompanyMembership.objects.create(
            company=self.company,
            driver=substitute,
            status='active',
            requested_by=substitute.user,
            created_at=self.now,
            reviewed_by=self.company.user,
            reviewed_at=self.now,
        )
        self.as_user(self.company.user)
        invited = self.post(
            f'/api/travels/{travel.pk}/invite-driver/',
            {
                'driver_membership_id': member.pk,
                'expires_at': (self.now + timedelta(hours=1)).isoformat(),
            },
        )
        pk = invited.data['id']
        self.as_user(self.driver.user)
        self.post(f'/api/driver-invitations/{pk}/respond/', {'accept': True}, expected=404)
        self.as_user(substitute.user)
        self.post(f'/api/driver-invitations/{pk}/respond/', {'accept': True})
        travel.refresh_from_db()
        self.assertEqual(travel.driver_id, substitute.pk)
        self.assertNotEqual(travel.planning_status, 'ready')

    def test_notifications_are_recipient_only_and_mark_read_is_idempotent(self):
        self.answer()
        self.close()
        self.process_jobs()
        self.publish(self.travel())
        self.as_user(self.passenger.user)
        notice = self.client.get('/api/notifications/').data['results'][0]
        first = self.post(f'/api/notifications/{notice["id"]}/read/')
        second = self.post(f'/api/notifications/{notice["id"]}/read/')
        self.assertEqual(first.data['read_at'], second.data['read_at'])
        self.as_user(self.other.user)
        self.post(f'/api/notifications/{notice["id"]}/read/', expected=404)

    def test_ended_membership_denies_historical_trips_without_deleting_them(self):
        travel = self.ready_travel()
        self.publish(travel)
        from modules.transport.services.execution import finish_travel, record_participation, start_travel

        start_travel(actor_id=self.driver.user_id, travel_id=travel.pk, expected_revision=travel.revision)
        participant = travel.participations.get()
        record_participation(
            actor_id=self.driver.user_id, participation_id=participant.pk, kind='no_show', operation_id=uuid4()
        )
        finish_travel(actor_id=self.driver.user_id, travel_id=travel.pk)
        end_membership(actor_id=self.passenger.user_id, membership_id=self.membership.pk)
        self.as_user(self.passenger.user)
        self.assertEqual(self.client.get(f'/api/travels/{travel.pk}/').status_code, 404)
        self.assertEqual(self.client.get('/api/participation-events/').data['results'], [])
        self.assertTrue(TravelParticipation.objects.filter(pk=participant.pk).exists())

    def test_public_discovery_filters_by_served_destination_without_points(self):
        result = self.client.get(
            '/api/companies/', {'city': self.common.city, 'state': self.common.state, 'destination': self.group.name}
        )
        self.assertEqual(result.status_code, 200)
        self.assertEqual([row['id'] for row in result.data['results']], [self.company.pk])
        self.assertEqual(set(result.data['results'][0]), {'id', 'trade_name', 'city', 'state'})
        self.assertEqual(self.client.get('/api/operational-points/').status_code, 401)

    def test_statistics_use_service_day_date_not_started_at_or_all_scheduled(self):
        self.ready_travel()
        self.as_user(self.company.user)
        result = self.client.get('/api/companies/me/stats/', {'date': self.date.isoformat()})
        self.assertEqual(result.status_code, 200, result.data)
        self.assertEqual(result.data['routes_today'], 2)
        result = self.client.get('/api/companies/me/stats/', {'date': (self.date + timedelta(days=1)).isoformat()})
        self.assertEqual(result.data['routes_today'], 0)

    def test_admin_actions_call_services_without_staff_impersonation_or_generic_changes(self):
        travel = self.ready_travel()
        staff = create_user('api-admin@example.com', is_staff=True, is_superuser=True)
        self.client.force_login(staff)
        self.client.force_authenticate(None)
        from modules.transport.models import Travel

        model_admin = admin.site._registry[Travel]
        self.assertFalse(model_admin.has_change_permission(type('Request', (), {'user': staff})(), travel))
        result = self.client.post(
            '/admin/router/travel/',
            {
                'action': 'execute_command',
                ACTION_CHECKBOX_NAME: str(travel.pk),
                'domain_command': 'publish',
                'arguments': json.dumps({'expected_revision': travel.revision}),
            },
        )
        self.assertEqual(result.status_code, 302)
        travel.refresh_from_db()
        self.assertIsNone(travel.published_revision)
        self.company.user.is_staff = True
        self.company.user.is_superuser = True
        self.company.user.save(update_fields=['is_staff', 'is_superuser'])
        self.client.force_login(self.company.user)
        result = self.client.post(
            '/admin/router/travel/',
            {
                'action': 'execute_command',
                ACTION_CHECKBOX_NAME: str(travel.pk),
                'domain_command': 'publish',
                'arguments': json.dumps({'expected_revision': travel.revision}),
            },
        )
        self.assertEqual(result.status_code, 302)
        travel.refresh_from_db()
        self.assertEqual(travel.published_revision, travel.revision)
        self.assertTrue(Notification.objects.filter(resource_type='travel', resource_id=str(travel.pk)).exists())
