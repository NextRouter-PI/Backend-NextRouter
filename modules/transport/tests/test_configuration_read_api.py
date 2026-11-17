from rest_framework.test import APIClient

from modules.organizations.api.serializers.membership import GroupMembershipSerializer
from modules.organizations.models import PassengerGroupMembership
from modules.transport.api.serializers.configuration import ServiceSerializer
from modules.transport.models import RecurringService
from modules.transport.services.configuration import authorize_services, configure_stops

from .service_helpers import ServiceTestCase


class ConfigurationReadApiTests(ServiceTestCase):
    def setUp(self):
        super().setUp()
        self.client = APIClient()
        self.client.force_authenticate(self.company.user)

    def test_group_membership_reads_habitual_outbound_without_guessing_first_authorization(self):
        extra = self.make_service('outbound', self.returning.target_time)
        authorize_services(
            actor_id=self.company.user_id,
            group_membership_id=self.group_member.pk,
            service_ids=[self.outbound.pk, self.returning.pk, extra.pk],
            habitual_outbound_id=extra.pk,
        )
        url = f'/api/group-memberships/{self.group_member.pk}/'
        for user in (self.company.user, self.passenger.user):
            self.client.force_authenticate(user)
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.data['habitual_outbound_id'], extra.pk)
            self.assertCountEqual(response.data['service_ids'], [self.outbound.pk, self.returning.pk, extra.pk])
        self.client.force_authenticate(self.company.user)
        response = self.client.post(
            f'{url}authorize-services/',
            {'service_ids': [self.returning.pk], 'habitual_outbound_id': None},
            format='json',
        )
        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.data['habitual_outbound_id'])
        self.assertEqual(response.data['service_ids'], [self.returning.pk])

    def test_configured_point_ids_keep_order_and_action_returns_new_configuration(self):
        url = f'/api/recurring-services/{self.outbound.pk}/'
        self.assertEqual(self.client.get(url).data['point_ids'], [])
        for points in ([self.home.pk, self.garage.pk], [self.garage.pk, self.home.pk], []):
            response = self.client.post(f'{url}stops/', {'point_ids': points}, format='json')
            self.assertEqual(response.status_code, 200, response.data)
            self.assertEqual(response.data['point_ids'], points)
            self.assertEqual(self.client.get(url).data['point_ids'], points)

    def test_new_read_fields_do_not_bypass_scoping_or_add_generic_writes(self):
        url = f'/api/recurring-services/{self.outbound.pk}/'
        response = self.client.patch(url, {'point_ids': [self.home.pk]}, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertFalse(self.outbound.configured_stops.exists())
        for user in (self.other.user, self.passenger.user):
            self.client.force_authenticate(user)
            self.assertEqual(self.client.get(url).status_code, 404)
            self.assertEqual(self.client.get('/api/recurring-services/').data['results'], [])
        self.client.force_authenticate(self.other.user)
        url = f'/api/group-memberships/{self.group_member.pk}/'
        self.assertEqual(self.client.get(url).status_code, 404)
        self.assertEqual(self.client.get('/api/group-memberships/').data['results'], [])
        self.assertTrue(GroupMembershipSerializer().fields['habitual_outbound_id'].read_only)
        self.assertTrue(ServiceSerializer().fields['point_ids'].read_only)

    def test_serialization_reuses_prefetched_authorizations_and_stops(self):
        configure_stops(actor_id=self.company.user_id, service_id=self.outbound.pk, point_ids=[self.home.pk])
        members = list(
            PassengerGroupMembership.objects.filter(pk=self.group_member.pk).prefetch_related('service_authorizations')
        )
        services = list(RecurringService.objects.filter(route_group=self.group).prefetch_related('configured_stops'))
        with self.assertNumQueries(0):
            member = GroupMembershipSerializer(members, many=True).data[0]
            result = ServiceSerializer(services, many=True).data
        self.assertEqual(member['habitual_outbound_id'], self.outbound.pk)
        self.assertEqual(next(row for row in result if row['id'] == self.outbound.pk)['point_ids'], [self.home.pk])
