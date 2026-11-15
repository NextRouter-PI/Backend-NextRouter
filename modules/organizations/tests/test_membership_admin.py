from django.test import TestCase
from django.urls import reverse

from modules.organizations.models import CompanyMembership, MembershipEvent
from tests.helpers import create_company, create_passenger, create_user


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

    def admin_url(self, obj, action):
        args = [obj.pk] if action in ('change', 'delete') else []
        return reverse(f'admin:organizations_{obj._meta.model_name}_{action}', args=args)

    def test_superuser_can_read_both_models(self):
        self.client.force_login(self.admin)
        for obj in (self.membership, self.event):
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
        for obj in (self.membership, self.event):
            for action in ('add', 'change', 'delete'):
                with self.subTest(model=type(obj).__name__, action=action):
                    response = self.client.post(self.admin_url(obj, action), {'status': 'active', 'post': 'yes'})
                    self.assertEqual(response.status_code, 403)
        self.membership.refresh_from_db()
        self.event.refresh_from_db()
        self.assertEqual(self.membership.status, CompanyMembership.Status.PENDING)
        self.assertEqual(self.event.action, MembershipEvent.Action.REQUESTED)
        self.assertEqual(CompanyMembership.objects.count(), 1)
        self.assertEqual(MembershipEvent.objects.count(), 1)

    def test_bulk_delete_action_is_unavailable(self):
        self.client.force_login(self.admin)
        for obj in (self.membership, self.event):
            with self.subTest(model=type(obj).__name__):
                response = self.client.post(
                    self.admin_url(obj, 'changelist'), {'action': 'delete_selected', '_selected_action': [obj.pk]}
                )
                self.assertEqual(response.status_code, 200)
                self.assertTrue(type(obj).objects.filter(pk=obj.pk).exists())

    def test_staff_without_model_permissions_cannot_read(self):
        self.client.force_login(self.staff)
        for obj in (self.membership, self.event):
            for action in ('changelist', 'change'):
                with self.subTest(model=type(obj).__name__, action=action):
                    self.assertEqual(self.client.get(self.admin_url(obj, action)).status_code, 403)

    def test_company_user_cannot_access_admin_models(self):
        self.client.force_login(self.company.user)
        for obj in (self.membership, self.event):
            with self.subTest(model=type(obj).__name__):
                self.assertEqual(self.client.get(self.admin_url(obj, 'changelist')).status_code, 302)
