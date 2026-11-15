from django.contrib.auth.models import Permission
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from modules.organizations.models import CompanyMembership, MembershipEvent, PassengerGroupMembership
from tests.helpers import create_company, create_operational_point, create_passenger, create_route_group, create_user


class MembershipReadOnlyAdminTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = create_user('membership-admin@example.com', is_staff=True, is_superuser=True)
        cls.staff = create_user('membership-staff@example.com', is_staff=True)
        cls.company = create_company('membership-admin-company@example.com')
        cls.passenger = create_passenger('membership-admin-passenger@example.com')
        cls.membership = CompanyMembership.objects.create(
            company=cls.company, passenger=cls.passenger, requested_by=cls.passenger.user
        )
        cls.event = MembershipEvent.objects.create(
            membership=cls.membership, action=MembershipEvent.Action.REQUESTED, actor=cls.passenger.user
        )
        cls.point = create_operational_point(cls.company)
        cls.group = create_route_group(cls.company)
        group_passenger = create_passenger('admin-group-passenger@example.com')
        now = timezone.now()
        group_membership = CompanyMembership.objects.create(
            company=cls.company,
            passenger=group_passenger,
            requested_by=group_passenger.user,
            status=CompanyMembership.Status.ACTIVE,
            created_at=now,
            reviewed_at=now,
            reviewed_by=cls.company.user,
        )
        cls.participation = PassengerGroupMembership.objects.create(
            membership=group_membership,
            route_group=cls.group,
            transport_point=cls.point,
            assigned_by=cls.company.user,
        )

    def structural_objects(self):
        return self.membership, self.event, self.point, self.participation

    def admin_url(self, obj, action):
        args = [obj.pk] if action in ('change', 'delete') else []
        return reverse(f'admin:organizations_{obj._meta.model_name}_{action}', args=args)

    def test_superuser_can_read_structural_models(self):
        self.client.force_login(self.admin)
        for obj in self.structural_objects():
            for action in ('changelist', 'change'):
                with self.subTest(model=type(obj).__name__, action=action):
                    response = self.client.get(self.admin_url(obj, action))
                    self.assertEqual(response.status_code, 200)
                    self.assertFalse(response.context['has_add_permission'])
                    if action == 'change':
                        self.assertFalse(response.context['has_change_permission'])
                        self.assertFalse(response.context['has_delete_permission'])

    def test_add_change_delete_are_forbidden_even_for_superuser(self):
        self.client.force_login(self.admin)
        for obj in self.structural_objects():
            for action in ('add', 'change', 'delete'):
                with self.subTest(model=type(obj).__name__, action=action):
                    response = self.client.post(self.admin_url(obj, action), {'status': 'active', 'post': 'yes'})
                    self.assertEqual(response.status_code, 403)
        self.membership.refresh_from_db()
        self.event.refresh_from_db()
        self.assertEqual(self.membership.status, CompanyMembership.Status.PENDING)
        self.assertEqual(self.event.action, MembershipEvent.Action.REQUESTED)
        self.assertEqual(CompanyMembership.objects.count(), 2)
        self.assertEqual(MembershipEvent.objects.count(), 1)
        self.point.refresh_from_db()
        self.participation.refresh_from_db()
        self.assertEqual(self.point.street, 'Rua Fictícia')
        self.assertIsNone(self.participation.ended_at)

    def test_bulk_delete_action_is_unavailable(self):
        self.client.force_login(self.admin)
        for obj in self.structural_objects():
            with self.subTest(model=type(obj).__name__):
                response = self.client.post(
                    self.admin_url(obj, 'changelist'), {'action': 'delete_selected', '_selected_action': [obj.pk]}
                )
                self.assertEqual(response.status_code, 200)
                self.assertTrue(type(obj).objects.filter(pk=obj.pk).exists())

    def test_staff_without_model_permissions_cannot_read(self):
        self.client.force_login(self.staff)
        for obj in self.structural_objects():
            for action in ('changelist', 'change'):
                with self.subTest(model=type(obj).__name__, action=action):
                    self.assertEqual(self.client.get(self.admin_url(obj, action)).status_code, 403)

    def test_staff_with_view_permission_can_read_but_not_write(self):
        for obj in self.structural_objects():
            permission = Permission.objects.get(
                content_type__app_label='organizations',
                codename=f'view_{obj._meta.model_name}',
            )
            self.staff.user_permissions.add(permission)
        self.client.force_login(self.staff)
        for obj in self.structural_objects():
            with self.subTest(model=type(obj).__name__):
                url = self.admin_url(obj, 'change')
                self.assertEqual(self.client.get(url).status_code, 200)
                self.assertEqual(self.client.post(url, {'post': 'yes'}).status_code, 403)

    def test_legacy_group_admin_does_not_offer_or_write_destination(self):
        self.client.force_login(self.admin)
        url = reverse('admin:organizations_companyroutegroup_change', args=[self.group.pk])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertNotIn('destination', response.context['adminform'].form.fields)
        response = self.client.post(
            url,
            {'name': 'Grupo atualizado', 'common_cep': '89010-000', 'destination': self.point.pk, '_save': 'Salvar'},
        )
        self.assertEqual(response.status_code, 302)
        self.group.refresh_from_db()
        self.assertIsNone(self.group.destination_id)

    def test_company_user_cannot_access_admin_models(self):
        self.client.force_login(self.company.user)
        for obj in self.structural_objects():
            with self.subTest(model=type(obj).__name__):
                self.assertEqual(self.client.get(self.admin_url(obj, 'changelist')).status_code, 302)
