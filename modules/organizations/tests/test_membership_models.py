from datetime import timedelta

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.db.models.deletion import ProtectedError
from django.test import TestCase
from django.utils import timezone

from modules.organizations.models import CompanyMembership, Driver, MembershipEvent
from tests.helpers import create_company, create_passenger, create_route_group, create_user


class CompanyMembershipModelTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.company = create_company('membership-company@example.com')
        cls.other_company = create_company('membership-other@example.com')
        cls.group = create_route_group(cls.company)
        cls.passenger = create_passenger('membership-passenger@example.com')
        cls.driver = Driver.objects.create(user=create_user('membership-driver@example.com'))
        cls.created_at = timezone.now() - timedelta(days=1)

    def membership_data(self, *, profile=None, status=CompanyMembership.Status.PENDING, company=None):
        profile = profile or self.passenger
        data = {
            'company': company or self.company,
            'passenger' if profile == self.passenger else 'driver': profile,
            'requested_by': profile.user,
            'created_at': self.created_at,
            'status': status,
        }
        if status in (
            CompanyMembership.Status.ACTIVE,
            CompanyMembership.Status.REJECTED,
            CompanyMembership.Status.ENDED,
        ):
            data.update(reviewed_by=data['company'].user, reviewed_at=self.created_at + timedelta(hours=1))
        if status == CompanyMembership.Status.WITHDRAWN:
            data.update(withdrawn_by=profile.user, withdrawn_at=self.created_at + timedelta(hours=1))
        if status == CompanyMembership.Status.ENDED:
            data.update(ended_by=profile.user, ended_at=self.created_at + timedelta(hours=2))
        return data

    def assert_invalid_creation(self, data):
        # O savepoint preserva a transação do TestCase após a negação pelo banco.
        with self.assertRaises(IntegrityError), transaction.atomic():
            CompanyMembership.objects.create(**data)

    def test_all_states_support_either_profile(self):
        for profile in (self.passenger, self.driver):
            for status in CompanyMembership.Status:
                with self.subTest(profile=type(profile).__name__, status=status):
                    membership = CompanyMembership.objects.create(
                        **self.membership_data(profile=profile, status=status)
                    )
                    membership.full_clean()
                    self.assertEqual(membership.status, status)
                    self.assertEqual(membership.company, self.company)
                    membership.delete()

    def test_exactly_one_profile_is_required_by_database(self):
        no_profile = self.membership_data()
        no_profile.pop('passenger')
        self.assert_invalid_creation(no_profile)
        self.assert_invalid_creation({**self.membership_data(), 'driver': self.driver})

    def test_one_pending_or_active_cycle_per_profile_across_companies(self):
        open_states = (CompanyMembership.Status.PENDING, CompanyMembership.Status.ACTIVE)
        for profile in (self.passenger, self.driver):
            for existing_state in open_states:
                for proposed_state in open_states:
                    for company in (self.company, self.other_company):
                        with self.subTest(
                            profile=type(profile).__name__,
                            existing=existing_state,
                            proposed=proposed_state,
                            company=company.pk,
                        ):
                            membership = CompanyMembership.objects.create(
                                **self.membership_data(profile=profile, status=existing_state)
                            )
                            self.assert_invalid_creation(
                                self.membership_data(profile=profile, status=proposed_state, company=company)
                            )
                            membership.delete()

    def test_terminal_cycles_preserve_history_without_blocking_new_request(self):
        for profile in (self.passenger, self.driver):
            for status in (
                CompanyMembership.Status.REJECTED,
                CompanyMembership.Status.WITHDRAWN,
                CompanyMembership.Status.ENDED,
            ):
                CompanyMembership.objects.create(**self.membership_data(profile=profile, status=status))
            pending = CompanyMembership.objects.create(**self.membership_data(profile=profile))
            self.assertEqual(pending.status, CompanyMembership.Status.PENDING)
        self.assertEqual(CompanyMembership.objects.count(), 8)

    def test_different_profiles_can_request_same_company(self):
        for profile in (self.passenger, self.driver):
            CompanyMembership.objects.create(**self.membership_data(profile=profile))
        self.assertEqual(self.company.memberships.count(), 2)

    def test_unknown_status_is_rejected_by_database(self):
        self.assert_invalid_creation({**self.membership_data(), 'status': 'invalid'})

    def test_review_fields_must_match_status_even_without_full_clean(self):
        for status in CompanyMembership.Status:
            data = self.membership_data(status=status)
            if status in (CompanyMembership.Status.PENDING, CompanyMembership.Status.WITHDRAWN):
                changes = (
                    {'reviewed_at': self.created_at},
                    {'reviewed_by': self.company.user},
                    {'reviewed_at': self.created_at, 'reviewed_by': self.company.user},
                )
            else:
                changes = ({'reviewed_at': None}, {'reviewed_by': None})
            for change in changes:
                with self.subTest(status=status, fields=tuple(change)):
                    self.assert_invalid_creation({**data, **change})

    def test_withdrawal_fields_must_match_status(self):
        for status in CompanyMembership.Status:
            data = self.membership_data(status=status)
            if status == CompanyMembership.Status.WITHDRAWN:
                changes = ({'withdrawn_at': None}, {'withdrawn_by': None})
            else:
                changes = (
                    {'withdrawn_at': self.created_at},
                    {'withdrawn_by': self.passenger.user},
                    {'withdrawn_at': self.created_at, 'withdrawn_by': self.passenger.user},
                )
            for change in changes:
                with self.subTest(status=status, fields=tuple(change)):
                    self.assert_invalid_creation({**data, **change})

    def test_end_fields_must_match_status(self):
        for status in CompanyMembership.Status:
            data = self.membership_data(status=status)
            if status == CompanyMembership.Status.ENDED:
                changes = ({'ended_at': None}, {'ended_by': None})
            else:
                changes = (
                    {'ended_at': self.created_at},
                    {'ended_by': self.company.user},
                    {'ended_at': self.created_at, 'ended_by': self.company.user},
                )
            for change in changes:
                with self.subTest(status=status, fields=tuple(change)):
                    self.assert_invalid_creation({**data, **change})

    def test_timestamps_cannot_precede_previous_stage(self):
        cases = (
            (CompanyMembership.Status.ACTIVE, 'reviewed_at', self.created_at - timedelta(seconds=1)),
            (CompanyMembership.Status.REJECTED, 'reviewed_at', self.created_at - timedelta(seconds=1)),
            (CompanyMembership.Status.WITHDRAWN, 'withdrawn_at', self.created_at - timedelta(seconds=1)),
            (CompanyMembership.Status.ENDED, 'ended_at', self.created_at),
        )
        for status, field, value in cases:
            with self.subTest(status=status, field=field):
                self.assert_invalid_creation({**self.membership_data(status=status), field: value})

    def test_equal_timestamps_are_allowed(self):
        data = self.membership_data(status=CompanyMembership.Status.ENDED)
        data.update(reviewed_at=self.created_at, ended_at=self.created_at)
        membership = CompanyMembership.objects.create(**data)
        self.assertEqual(membership.created_at, membership.ended_at)

    def test_bulk_create_cannot_skip_profile_constraint(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            CompanyMembership.objects.bulk_create([
                CompanyMembership(**self.membership_data(), driver=self.driver),
            ])

    def test_queryset_update_cannot_skip_state_constraints(self):
        membership = CompanyMembership.objects.create(**self.membership_data())
        with self.assertRaises(IntegrityError), transaction.atomic():
            CompanyMembership.objects.filter(pk=membership.pk).update(status=CompanyMembership.Status.ACTIVE)
        membership.refresh_from_db()
        self.assertEqual(membership.status, CompanyMembership.Status.PENDING)

    def test_queryset_update_cannot_skip_open_cycle_uniqueness(self):
        CompanyMembership.objects.create(**self.membership_data())
        terminal = CompanyMembership.objects.create(**self.membership_data(status=CompanyMembership.Status.REJECTED))
        with self.assertRaises(IntegrityError), transaction.atomic():
            CompanyMembership.objects.filter(pk=terminal.pk).update(
                status=CompanyMembership.Status.PENDING, reviewed_at=None, reviewed_by=None
            )

    def test_full_clean_reports_constraint_violation(self):
        membership = CompanyMembership(**self.membership_data(), driver=self.driver)
        with self.assertRaises(ValidationError):
            membership.full_clean()

    def test_referenced_company_profile_and_authors_are_protected(self):
        membership = CompanyMembership.objects.create(**self.membership_data(status=CompanyMembership.Status.ENDED))
        for target in (self.company, self.passenger, membership.requested_by, membership.reviewed_by):
            with self.subTest(model=type(target).__name__), self.assertRaises(ProtectedError):
                target.delete()

    def test_membership_does_not_change_identity_or_fabricate_events_through_save(self):
        self.assertFalse(CompanyMembership.objects.exists())
        user_id = self.passenger.user_id
        CompanyMembership.objects.create(**self.membership_data(status=CompanyMembership.Status.REJECTED))
        self.passenger.refresh_from_db()
        self.assertEqual(self.passenger.user_id, user_id)
        self.assertNotIn('route_group', {field.name for field in self.passenger._meta.fields})
        self.assertFalse(MembershipEvent.objects.exists())


class MembershipEventModelTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.company = create_company('event-company@example.com')
        cls.passenger = create_passenger('event-passenger@example.com')
        cls.membership = CompanyMembership.objects.create(
            company=cls.company, passenger=cls.passenger, requested_by=cls.passenger.user
        )

    def event_data(self, **extra):
        return {
            'membership': self.membership,
            'action': MembershipEvent.Action.REQUESTED,
            'actor': self.passenger.user,
            **extra,
        }

    def test_event_preserves_actor_time_and_reason(self):
        now = timezone.now()
        event = MembershipEvent.objects.create(**self.event_data(occurred_at=now, reason='Solicitação de vínculo.'))
        event.full_clean()
        self.assertEqual(event.actor, self.passenger.user)
        self.assertEqual(event.occurred_at, now)
        self.assertEqual(event.reason, 'Solicitação de vínculo.')

    def test_same_action_cannot_be_recorded_twice_per_cycle(self):
        for action in MembershipEvent.Action:
            with self.subTest(action=action):
                MembershipEvent.objects.create(**self.event_data(action=action))
                with self.assertRaises(IntegrityError), transaction.atomic():
                    MembershipEvent.objects.create(**self.event_data(action=action))

    def test_same_action_can_exist_in_different_cycles(self):
        other_passenger = create_passenger('event-other-passenger@example.com')
        other = CompanyMembership.objects.create(
            company=self.company, passenger=other_passenger, requested_by=other_passenger.user
        )
        for membership in (self.membership, other):
            MembershipEvent.objects.create(**self.event_data(membership=membership))
        self.assertEqual(MembershipEvent.objects.count(), 2)

    def test_bulk_create_rejects_unknown_action(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            MembershipEvent.objects.bulk_create([MembershipEvent(**self.event_data(action='invalid'))])

    def test_queryset_update_rejects_unknown_action(self):
        event = MembershipEvent.objects.create(**self.event_data())
        with self.assertRaises(IntegrityError), transaction.atomic():
            MembershipEvent.objects.filter(pk=event.pk).update(action='invalid')

    def test_membership_and_actor_cannot_be_deleted_with_events(self):
        MembershipEvent.objects.create(**self.event_data())
        for target in (self.membership, self.passenger.user):
            with self.subTest(model=type(target).__name__), self.assertRaises(ProtectedError):
                target.delete()
