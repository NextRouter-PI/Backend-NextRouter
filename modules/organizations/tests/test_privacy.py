from rest_framework.test import APIClient

from modules.organizations.models import Driver
from modules.transport.tests.service_helpers import ServiceTestCase
from modules.uploads.models import Document
from tests.helpers import create_passenger, create_user, pdf_file


class PrivacyTests(ServiceTestCase):
    def setUp(self):
        super().setUp()
        self.client = APIClient()

    def test_profile_filters_do_not_expose_pending_or_other_company_members(self):
        pending = create_passenger('pending-privacy@example.com')
        self.client.force_authenticate(self.other.user)
        self.assertEqual(self.client.get('/api/passengers/', {'id': self.passenger.pk}).data['results'], [])
        self.assertEqual(self.client.get('/api/drivers/', {'id': self.driver.pk}).data['results'], [])
        self.client.force_authenticate(self.company.user)
        result = self.client.get('/api/passengers/').data['results']
        self.assertEqual([row['id'] for row in result], [self.passenger.pk])
        self.assertNotIn('cpf', result[0]['user_data'])
        self.assertNotIn('latitude', result[0]['user_data'])
        self.assertEqual(self.client.get(f'/api/passengers/{pending.pk}/').status_code, 404)
        self.client.force_authenticate(self.driver.user)
        self.assertEqual(self.client.get('/api/passengers/').data['results'], [])

    def test_travel_and_vehicle_filters_preserve_tenant_scope(self):
        travel = self.ready_travel()
        self.client.force_authenticate(self.company.user)
        result = self.client.get(
            '/api/travels/', {'service_day__date': self.date.isoformat(), 'service': self.outbound.pk}
        )
        self.assertEqual([row['id'] for row in result.data['results']], [travel.pk])
        self.assertEqual(self.client.get('/api/travels/', {'company': self.other.pk}).data['results'], [])
        self.assertEqual(self.client.get('/api/vehicles/', {'company': self.other.pk}).data['results'], [])
        self.assertEqual(
            [row['id'] for row in self.client.get('/api/vehicles/', {'status': 'active'}).data['results']],
            [self.vehicle.pk],
        )
        self.client.force_authenticate(self.other.user)
        self.assertEqual(self.client.get(f'/api/travels/{travel.pk}/').status_code, 404)
        self.assertEqual(self.client.get(f'/api/vehicles/{self.vehicle.pk}/').status_code, 404)

    def test_public_company_details_hide_identity_and_documents(self):
        document = Document.objects.create(file=pdf_file())
        self.addCleanup(document.file.delete, save=False)
        self.company.articles_of_association_document = document
        self.company.save(update_fields=['articles_of_association_document'])
        response = APIClient().get(f'/api/companies/{self.company.pk}/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            set(response.data), {'id', 'trade_name', 'city', 'state', 'profile_picture_url', 'route_groups'}
        )
        self.client.force_authenticate(self.company.user)
        own = self.client.get('/api/companies/me/')
        self.assertEqual(own.status_code, 200)
        self.assertEqual(own.data['cnpj'], self.company.cnpj)
        self.assertIn('articles_of_association_document_data', own.data)

    def test_other_company_cannot_read_passenger_identity(self):
        self.client.force_authenticate(self.other.user)
        self.assertEqual(self.client.get(f'/api/passengers/{self.passenger.pk}/').status_code, 404)
        self.client.force_authenticate(self.company.user)
        response = self.client.get(f'/api/passengers/{self.passenger.pk}/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(set(response.data['user_data']), {'id', 'name'})

    def test_passenger_cannot_read_driver_identity_or_license(self):
        self.client.force_authenticate(self.passenger.user)
        self.assertEqual(self.client.get(f'/api/drivers/{self.driver.pk}/').status_code, 404)
        self.client.force_authenticate(self.company.user)
        response = self.client.get(f'/api/drivers/{self.driver.pk}/')
        self.assertEqual(response.status_code, 200)
        self.assertNotIn('cpf', response.data['user_data'])
        self.assertNotIn('cnh_data', response.data)

    def test_document_download_only_by_owner_or_admin(self):
        document = Document.objects.create(file=pdf_file())
        self.addCleanup(document.file.delete, save=False)
        self.company.articles_of_association_document = document
        self.company.save(update_fields=['articles_of_association_document'])
        url = f'/api/uploads/documents/{document.attachment_key}/download/'
        self.assertEqual(APIClient().get(url).status_code, 401)
        self.client.force_authenticate(self.other.user)
        self.assertEqual(self.client.get(url).status_code, 404)
        self.client.force_authenticate(self.company.user)
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/pdf')
        self.assertEqual(response['Cache-Control'], 'private, no-store')
        response.close()
        self.client.force_authenticate(None)
        self.assertEqual(self.client.get(f'/media/{document.file.name}').status_code, 404)

    def test_pending_passenger_cannot_see_group_travel_or_driver(self):
        pending = create_passenger('pending-trip-privacy@example.com')
        self.client.force_authenticate(pending.user)
        travel = self.travel()
        for url in (
            f'/api/drivers/{self.driver.pk}/',
            f'/api/company-route-groups/{self.group.pk}/',
            f'/api/travels/{travel.pk}/',
        ):
            self.assertEqual(self.client.get(url).status_code, 404, url)

    def test_unapproved_company_cannot_manage_group(self):
        self.company.is_approved = False
        self.company.save(update_fields=['is_approved'])
        self.client.force_authenticate(self.company.user)
        self.assertEqual(
            self.client.patch(f'/api/company-route-groups/{self.group.pk}/', {'name': 'Outro'}).status_code, 404
        )

    def test_legacy_group_request_and_approval_endpoints_are_removed(self):
        self.client.force_authenticate(self.company.user)
        for action in ('approve', 'reject', 'request-route-group'):
            self.assertEqual(self.client.post(f'/api/passengers/{self.passenger.pk}/{action}/').status_code, 404)

    def test_driver_without_membership_cannot_start_travel(self):
        outsider = Driver.objects.create(user=create_user('no-membership-privacy@example.com'))
        self.client.force_authenticate(outsider.user)
        travel = self.travel()
        response = self.client.post(f'/api/travels/{travel.pk}/start/', {'expected_revision': travel.revision})
        self.assertEqual(response.status_code, 404)
        self.assertEqual(self.client.get(f'/api/travels/{travel.pk}/').status_code, 404)
