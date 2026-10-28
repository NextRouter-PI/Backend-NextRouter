from django.utils import timezone
from rest_framework.test import APIClient

from modules.organizations.models import Driver
from modules.transport.models import CompanyRouteSchedule, Path, Travel, Vehicle
from modules.uploads.models import Document
from tests.helpers import BaseAPITestCase, create_company, create_passenger, create_route_group, create_user, pdf_file


class PrivacyTests(BaseAPITestCase):
    def test_profile_filters_do_not_expose_pending_or_other_company_members(self):
        company = create_company('company@example.com')
        group = create_route_group(company)
        other = create_company('other@example.com')
        other_group = create_route_group(other)
        unapproved_company = create_company('pending@example.com', approved=False)
        pending_student = create_passenger('pending-student@example.com', group, approved=False)
        student = create_passenger('student@example.com', group)
        outsider = create_passenger('outsider@example.com', other_group)
        driver = Driver.objects.create(user=create_user('driver@example.com'), route_group=group, is_approved=True)
        pending_driver = Driver.objects.create(user=create_user('pending-driver@example.com'), route_group=group)

        self.client.force_authenticate(unapproved_company.user)
        for url in ('/api/passengers/', '/api/drivers/'):
            self.assertEqual(self.client.get(url, {'route_group': group.pk}).data['results'], [])
        self.assertEqual(self.client.get(f'/api/passengers/{student.pk}/').status_code, 404)

        self.client.force_authenticate(other.user)
        self.assertEqual(self.client.get('/api/passengers/', {'route_group': group.pk}).data['results'], [])
        self.assertEqual(self.client.get('/api/drivers/', {'route_group': group.pk}).data['results'], [])

        self.client.force_authenticate(driver.user)
        visible = self.client.get('/api/passengers/', {'route_group': group.pk, 'is_approved': 'true'})
        self.assertEqual([row['id'] for row in visible.data['results']], [student.pk])
        self.assertEqual(self.client.get('/api/passengers/', {'is_approved': 'false'}).data['results'], [])
        self.assertEqual(self.client.get(f'/api/passengers/{pending_student.pk}/').status_code, 404)
        self.assertEqual(self.client.get(f'/api/passengers/{outsider.pk}/').status_code, 404)

        self.client.force_authenticate(student.user)
        self.assertEqual(
            [row['id'] for row in self.client.get('/api/drivers/', {'is_approved': 'true'}).data['results']],
            [driver.pk],
        )
        self.assertEqual(self.client.get(f'/api/drivers/{pending_driver.pk}/').status_code, 404)

        self.client.force_authenticate(pending_student.user)
        self.assertEqual(self.client.get('/api/drivers/', {'route_group': group.pk}).data['results'], [])
        self.assertEqual(self.client.get(f'/api/passengers/{pending_student.pk}/').status_code, 200)

        self.client.force_authenticate(company.user)
        self.assertEqual(
            [row['id'] for row in self.client.get('/api/passengers/', {'is_approved': 'false'}).data['results']],
            [pending_student.pk],
        )
        self.assertEqual(
            [row['id'] for row in self.client.get('/api/drivers/', {'is_approved': 'false'}).data['results']],
            [pending_driver.pk],
        )

    def test_travel_and_vehicle_filters_preserve_tenant_scope(self):
        company = create_company('company@example.com')
        group = create_route_group(company)
        driver = Driver.objects.create(user=create_user('driver@example.com'), route_group=group, is_approved=True)
        path = Path.objects.create(route_group=group, name='Trajeto')
        today = timezone.now()
        travel = Travel.objects.create(
            company=company, driver=driver, path=path, status=Travel.Status.FINISHED, started_at=today
        )
        Travel.objects.create(company=company, driver=driver, path=path)
        vehicle = Vehicle.objects.create(
            route_group=group, driver=driver, plate='AAA1234', status=Vehicle.Status.ACTIVE
        )
        Vehicle.objects.create(route_group=group, plate='BBB1234', status=Vehicle.Status.MAINTENANCE)
        other = create_company('other@example.com')
        other_group = create_route_group(other)
        other_driver = Driver.objects.create(user=create_user('other-driver@example.com'), route_group=other_group)
        other_path = Path.objects.create(route_group=other_group, name='Outro trajeto')
        other_travel = Travel.objects.create(
            company=other, driver=other_driver, path=other_path, status=Travel.Status.FINISHED, started_at=today
        )
        Vehicle.objects.create(route_group=other_group, plate='CCC1234', status=Vehicle.Status.ACTIVE)

        self.client.force_authenticate(company.user)
        response = self.client.get(
            '/api/travels/', {'status': 'finished', 'started_at__date': today.date().isoformat()}
        )
        self.assertEqual([row['id'] for row in response.data['results']], [travel.pk])
        self.assertEqual(self.client.get('/api/travels/', {'company': other.pk}).data['results'], [])
        self.assertEqual(self.client.get('/api/travels/', {'driver': other_driver.pk}).data['results'], [])
        response = self.client.get('/api/vehicles/', {'driver': driver.pk, 'status': 'active'})
        self.assertEqual([row['id'] for row in response.data['results']], [vehicle.pk])
        self.assertEqual(self.client.get('/api/vehicles/', {'route_group': other_group.pk}).data['results'], [])
        self.assertEqual(self.client.get(f'/api/travels/{other_travel.pk}/').status_code, 404)

    def test_public_company_details_hide_identity_and_documents(self):
        company = create_company('company@example.com')
        document = Document.objects.create(file=pdf_file())
        company.articles_of_association_document = document
        company.save(update_fields=['articles_of_association_document'])

        response = APIClient().get(f'/api/companies/{company.pk}/')
        self.assertEqual(response.status_code, 200)
        self.assertNotIn('user_data', response.data)
        self.assertNotIn('cnpj', response.data)
        self.assertNotIn('articles_of_association_document_data', response.data)

        self.client.force_authenticate(company.user)
        own = self.client.get(f'/api/companies/{company.pk}/')
        self.assertEqual(own.status_code, 200)
        self.assertEqual(own.data['cnpj'], company.cnpj)
        self.assertIn('articles_of_association_document_data', own.data)

    def test_other_company_cannot_read_passenger_identity(self):
        company = create_company('first@example.com')
        stranger = create_company('other@example.com')
        passenger = create_passenger('student@example.com', create_route_group(company))

        self.client.force_authenticate(stranger.user)
        self.assertEqual(self.client.get(f'/api/passengers/{passenger.pk}/').status_code, 404)

        self.client.force_authenticate(company.user)
        response = self.client.get(f'/api/passengers/{passenger.pk}/')
        self.assertEqual(response.status_code, 200)
        self.assertNotIn('cpf', response.data['user_data'])
        self.assertNotIn('birthday', response.data['user_data'])

    def test_passenger_cannot_read_driver_identity_or_license(self):
        company = create_company('company@example.com')
        group = create_route_group(company)
        passenger = create_passenger('student@example.com', group)
        driver = Driver.objects.create(user=create_user('driver@example.com'), route_group=group, is_approved=True)
        self.client.force_authenticate(passenger.user)

        response = self.client.get(f'/api/drivers/{driver.pk}/')
        self.assertEqual(response.status_code, 200)
        self.assertNotIn('cpf', response.data['user_data'])
        self.assertNotIn('cnh_data', response.data)

    def test_document_download_only_by_owner_or_admin(self):
        company = create_company('company@example.com')
        other = create_company('other@example.com')
        document = Document.objects.create(file=pdf_file())
        company.articles_of_association_document = document
        company.save(update_fields=['articles_of_association_document'])
        url = f'/api/uploads/documents/{document.attachment_key}/download/'

        self.assertEqual(APIClient().get(url).status_code, 401)
        self.client.force_authenticate(other.user)
        self.assertEqual(self.client.get(url).status_code, 404)
        self.client.force_authenticate(company.user)
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/pdf')

        self.client.force_authenticate(None)
        self.assertEqual(self.client.get(f'/media/{document.file.name}').status_code, 404)

    def test_pending_passenger_cannot_see_group_travel_or_driver(self):
        company = create_company('company@example.com')
        group = create_route_group(company)
        passenger = create_passenger('student@example.com', group, approved=False)
        driver = Driver.objects.create(user=create_user('driver@example.com'), route_group=group, is_approved=True)
        path = Path.objects.create(route_group=group, name='Trajeto', points=[])
        schedule = CompanyRouteSchedule.objects.create(route_group=group, go_hour='08:00', return_hour='16:00')
        travel = Travel.objects.create(company=company, path=path, driver=driver)
        self.client.force_authenticate(passenger.user)

        for url in (
            f'/api/drivers/{driver.pk}/',
            f'/api/paths/{path.pk}/',
            f'/api/route-schedules/{schedule.pk}/',
            f'/api/travels/{travel.pk}/',
        ):
            self.assertEqual(self.client.get(url).status_code, 404, url)

    def test_unapproved_company_cannot_manage_group(self):
        company = create_company('company@example.com', approved=False)
        group = create_route_group(company)
        passenger = create_passenger('student@example.com', group, approved=False)
        self.client.force_authenticate(company.user)

        self.assertEqual(self.client.patch(f'/api/passengers/{passenger.pk}/approve/').status_code, 404)
        self.assertEqual(
            self.client.patch(f'/api/company-route-groups/{group.pk}/', {'name': 'Outro'}).status_code, 403
        )

    def test_company_cannot_request_new_group_on_behalf_of_student(self):
        company = create_company('company@example.com')
        group = create_route_group(company)
        passenger = create_passenger('student@example.com', group)
        other = create_route_group(create_company('other@example.com'))
        self.client.force_authenticate(company.user)

        response = self.client.patch(f'/api/passengers/{passenger.pk}/request-route-group/', {'route_group': other.pk})
        self.assertEqual(response.status_code, 403)
        passenger.refresh_from_db()
        self.assertEqual(passenger.route_group, group)

    def test_unapproved_driver_cannot_start_travel(self):
        company = create_company('company@example.com')
        group = create_route_group(company)
        driver = Driver.objects.create(user=create_user('driver@example.com'), route_group=group, is_approved=False)
        path = Path.objects.create(route_group=group, name='Trajeto', points=[])
        travel = Travel.objects.create(company=company, path=path, driver=driver)
        self.client.force_authenticate(driver.user)

        self.assertEqual(self.client.patch(f'/api/travels/{travel.pk}/start/').status_code, 404)
        self.assertEqual(self.client.get(f'/api/travels/{travel.pk}/').status_code, 404)
