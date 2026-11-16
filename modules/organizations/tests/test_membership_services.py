from datetime import UTC, datetime, timedelta
from unittest.mock import patch

from django.test import TestCase

from modules.accounts.models import User
from modules.organizations.models import Company, CompanyMembership, Driver, MembershipEvent
from modules.organizations.services.errors import MembershipError
from modules.organizations.services.memberships import (
    approve_membership,
    reject_membership,
    request_membership,
    withdraw_membership,
)
from modules.transport.models import Notification
from tests.helpers import create_company, create_passenger, create_route_group, create_user


class MembershipServiceTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.company = create_company('service-company@example.com')
        cls.other_company = create_company('service-other@example.com')
        cls.group = create_route_group(cls.company)
        cls.passenger = create_passenger('service-passenger@example.com', cls.group)
        cls.driver = Driver.objects.create(user=create_user('service-driver@example.com'))
        cls.staff = create_user('service-staff@example.com', is_staff=True, is_superuser=True)
        cls.now = datetime(2026, 11, 16, 1, tzinfo=UTC)

    def request(self, profile=None, company=None, actor=None):
        profile = profile or self.passenger
        return request_membership(
            actor_id=(actor or profile.user).pk,
            company_id=(company or self.company).pk,
            **{'passenger_id' if profile == self.passenger else 'driver_id': profile.pk},
        )

    def assert_error(self, code, operation, **kwargs):
        with self.assertRaises(MembershipError) as caught:
            operation(**kwargs)
        self.assertEqual(caught.exception.code, code)

    def test_request_and_approval_for_both_profiles_without_group(self):
        for profile in (self.passenger, self.driver):
            with (
                self.subTest(profile=type(profile).__name__),
                patch('modules.organizations.services.memberships.timezone.now', return_value=self.now),
            ):
                membership = self.request(profile)
                membership.full_clean()
                result = approve_membership(actor_id=self.company.user_id, membership_id=membership.pk)
                result.full_clean()
                self.assertEqual(result.status, 'active')
                self.assertEqual(result.requested_by_id, profile.user_id)
                self.assertEqual(result.reviewed_by_id, self.company.user_id)
                self.assertEqual(result.reviewed_at, self.now)
                self.assertFalse(result.passenger_group_memberships.exists())
                self.assertEqual(list(result.events.values_list('action', flat=True)), ['requested', 'approved'])
                self.assertEqual(result.events.last().actor_id, self.company.user_id)
                notices = Notification.objects.filter(resource_id=str(result.pk))
                self.assertEqual(notices.count(), 2)
                for notice in notices:
                    notice.full_clean()
                    self.assertEqual(set(notice.payload), {'status'})
                self.assertEqual(notices.get(payload={'status': 'pending'}).recipient_id, self.company.user_id)
                self.assertEqual(notices.get(payload={'status': 'active'}).recipient_id, profile.user_id)

    def test_pending_request_repetition_does_not_duplicate_effects(self):
        first = self.request()
        second = self.request()
        self.assertEqual(second.pk, first.pk)
        self.assertEqual(CompanyMembership.objects.count(), 1)
        self.assertEqual(MembershipEvent.objects.count(), 1)
        self.assertEqual(Notification.objects.count(), 1)

    def test_active_or_other_pending_blocks_new_request_and_preserves_legacy(self):
        for profile in (self.passenger, self.driver):
            initial = (profile.route_group_id, profile.is_approved, profile.is_rejected)
            membership = self.request(profile)
            self.assert_error('membership_open', self.request, profile=profile, company=self.other_company)
            approve_membership(actor_id=self.company.user_id, membership_id=membership.pk)
            for company in (self.company, self.other_company):
                self.assert_error('membership_open', self.request, profile=profile, company=company)
            profile.refresh_from_db()
            self.assertEqual((profile.route_group_id, profile.is_approved, profile.is_rejected), initial)
            membership.refresh_from_db()
            self.assertEqual(membership.status, 'active')
            self.assertEqual(membership.company_id, self.company.pk)

    def test_only_holder_can_request_including_no_staff_bypass(self):
        for actor in (self.company.user, self.other_company.user, self.staff, self.driver.user):
            self.assert_error('permission_denied', self.request, actor=actor)
        self.assertFalse(CompanyMembership.objects.exists())
        self.assertFalse(Notification.objects.exists())

    def test_profile_selection_and_missing_resources(self):
        base = {'actor_id': self.passenger.user_id, 'company_id': self.company.pk}
        self.assert_error('invalid_profile', request_membership, **base)
        self.assert_error(
            'invalid_profile', request_membership, **base, passenger_id=self.passenger.pk, driver_id=self.driver.pk
        )
        self.assert_error('not_found', request_membership, **base, passenger_id=999999)
        self.assert_error('not_found', approve_membership, actor_id=self.company.user_id, membership_id=999999)
        self.assert_error('not_found', self.request, company=Company(pk=999999))

    def test_inactive_actor_and_unapproved_company_are_reobtained(self):
        User.objects.filter(pk=self.passenger.user_id).update(is_active=False)
        self.assert_error('permission_denied', self.request)
        User.objects.filter(pk=self.passenger.user_id).update(is_active=True)
        Company.objects.filter(pk=self.company.pk).update(is_approved=False)
        self.assert_error('company_unavailable', self.request)
        self.assertFalse(CompanyMembership.objects.exists())

    def test_inactive_company_owner_cannot_receive_new_request(self):
        User.objects.filter(pk=self.company.user_id).update(is_active=False)
        self.assert_error('company_unavailable', self.request)

    def test_only_own_company_decides_and_only_holder_withdraws(self):
        membership = self.request()
        for operation in (approve_membership, reject_membership):
            for actor in (self.passenger.user, self.driver.user, self.other_company.user, self.staff):
                self.assert_error('permission_denied', operation, actor_id=actor.pk, membership_id=membership.pk)
        for actor in (self.company.user, self.other_company.user, self.staff):
            self.assert_error('permission_denied', withdraw_membership, actor_id=actor.pk, membership_id=membership.pk)
        membership.refresh_from_db()
        self.assertEqual(membership.status, 'pending')
        self.assertEqual(membership.events.count(), 1)
        self.assertEqual(Notification.objects.count(), 1)

    def test_repeated_decision_is_idempotent_opposite_decision_conflicts(self):
        for profile, operation, opposite in (
            (self.passenger, approve_membership, reject_membership),
            (self.driver, reject_membership, approve_membership),
        ):
            membership = self.request(profile)
            args = {'actor_id': self.company.user_id, 'membership_id': membership.pk}
            first = operation(**args, reason=' Decisão fictícia ')
            second = operation(**args, reason='Não reescreve o motivo')
            self.assertEqual(first.reviewed_at, second.reviewed_at)
            self.assertEqual(second.events.last().reason, 'Decisão fictícia')
            self.assertEqual(second.events.count(), 2)
            self.assertEqual(Notification.objects.filter(resource_id=str(membership.pk)).count(), 2)
            self.assert_error('membership_not_pending', opposite, **args)
            self.assert_error(
                'membership_not_pending', withdraw_membership, actor_id=profile.user_id, membership_id=membership.pk
            )

    def test_withdrawal_prevents_late_approval_and_allows_new_cycle(self):
        for profile in (self.passenger, self.driver):
            membership = self.request(profile)
            args = {'actor_id': profile.user_id, 'membership_id': membership.pk}
            first = withdraw_membership(**args, reason='Retirada fictícia')
            second = withdraw_membership(**args)
            second.full_clean()
            self.assertEqual(first.withdrawn_at, second.withdrawn_at)
            self.assertEqual(second.events.count(), 2)
            self.assertEqual(second.events.last().reason, 'Retirada fictícia')
            self.assertEqual(second.events.last().actor_id, profile.user_id)
            self.assert_error(
                'membership_not_pending', approve_membership, actor_id=self.company.user_id, membership_id=membership.pk
            )
            new = self.request(profile, self.other_company)
            self.assertNotEqual(new.pk, membership.pk)
            membership.refresh_from_db()
            self.assertEqual(membership.status, 'withdrawn')
            self.assertEqual(membership.company_id, self.company.pk)

    def test_rejection_allows_new_cycle_same_company_without_rewriting_history(self):
        old = self.request()
        reject_membership(actor_id=self.company.user_id, membership_id=old.pk)
        new = self.request()
        self.assertNotEqual(new.pk, old.pk)
        old.refresh_from_db()
        self.assertEqual(old.status, 'rejected')
        self.assertEqual(old.events.count(), 2)

    def test_withdrawal_does_not_require_company_approval(self):
        membership = self.request()
        Company.objects.filter(pk=self.company.pk).update(is_approved=False)
        self.assert_error(
            'company_unavailable', approve_membership, actor_id=self.company.user_id, membership_id=membership.pk
        )
        result = withdraw_membership(actor_id=self.passenger.user_id, membership_id=membership.pk)
        self.assertEqual(result.status, 'withdrawn')

    def test_approval_revalidates_holder_activity(self):
        membership = self.request()
        User.objects.filter(pk=self.passenger.user_id).update(is_active=False)
        self.assert_error(
            'profile_unavailable', approve_membership, actor_id=self.company.user_id, membership_id=membership.pk
        )
        membership.refresh_from_db()
        self.assertEqual(membership.status, 'pending')

    def test_authorization_is_checked_before_returning_idempotent_result(self):
        membership = self.request()
        approve_membership(actor_id=self.company.user_id, membership_id=membership.pk)
        self.assert_error('permission_denied', approve_membership, actor_id=self.staff.pk, membership_id=membership.pk)
        User.objects.filter(pk=self.company.user_id).update(is_active=False)
        self.assert_error(
            'permission_denied', approve_membership, actor_id=self.company.user_id, membership_id=membership.pk
        )

    def test_invalid_reason_has_no_effect(self):
        membership = self.request()
        for operation, actor in (
            (approve_membership, self.company.user),
            (reject_membership, self.company.user),
            (withdraw_membership, self.passenger.user),
        ):
            for reason in ('x' * 501, None, {}):
                self.assert_error(
                    'invalid_reason', operation, actor_id=actor.pk, membership_id=membership.pk, reason=reason
                )
        self.assertEqual(MembershipEvent.objects.count(), 1)

    def test_clock_before_request_is_domain_error_and_leaves_pending(self):
        with patch('modules.organizations.services.memberships.timezone.now', return_value=self.now):
            membership = self.request()
        for operation, actor in (
            (approve_membership, self.company.user),
            (reject_membership, self.company.user),
            (withdraw_membership, self.passenger.user),
        ):
            with patch(
                'modules.organizations.services.memberships.timezone.now', return_value=self.now - timedelta(seconds=1)
            ):
                self.assert_error('invalid_time', operation, actor_id=actor.pk, membership_id=membership.pk)
        membership.refresh_from_db()
        self.assertEqual(membership.status, 'pending')

    def test_notification_failure_rolls_back_creation_and_audit(self):
        with (
            patch.object(Notification.objects, 'create', side_effect=RuntimeError('Falha simulada')),
            self.assertRaises(RuntimeError),
        ):
            self.request()
        self.assertFalse(CompanyMembership.objects.exists())
        self.assertFalse(MembershipEvent.objects.exists())

    def test_effect_failures_roll_back_every_transition(self):
        membership = self.request()
        for operation, actor in (
            (approve_membership, self.company.user),
            (reject_membership, self.company.user),
            (withdraw_membership, self.passenger.user),
        ):
            for manager in (MembershipEvent.objects, Notification.objects):
                with (
                    patch.object(manager, 'create', side_effect=RuntimeError('Falha simulada')),
                    self.assertRaises(RuntimeError),
                ):
                    operation(actor_id=actor.pk, membership_id=membership.pk)
                membership.refresh_from_db()
                self.assertEqual(membership.status, 'pending')
                self.assertIsNone(membership.reviewed_at)
                self.assertIsNone(membership.withdrawn_at)
                self.assertEqual(membership.events.count(), 1)
                self.assertEqual(Notification.objects.count(), 1)
