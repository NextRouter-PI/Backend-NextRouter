from datetime import timedelta

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.db.models.deletion import ProtectedError
from django.test import TestCase
from django.utils import timezone

from modules.organizations.models import CompanyMembership, Driver, PassengerGroupMembership
from tests.helpers import create_company, create_operational_point, create_passenger, create_route_group, create_user


class PassengerGroupMembershipTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.company = create_company('group-member-company@example.com')
        cls.other_company = create_company('group-member-other-company@example.com')
        cls.group = create_route_group(cls.company)
        cls.second_group = create_route_group(cls.company, 'Outro grupo')
        cls.other_group = create_route_group(cls.other_company)
        cls.point = create_operational_point(cls.company)
        cls.other_point = create_operational_point(cls.other_company)
        cls.passenger = create_passenger('group-member-passenger@example.com')
        cls.started_at = timezone.now() - timedelta(hours=1)
        cls.reviewed_at = cls.started_at - timedelta(hours=1)
        cls.membership = CompanyMembership.objects.create(
            company=cls.company,
            passenger=cls.passenger,
            requested_by=cls.passenger.user,
            created_at=cls.reviewed_at,
            status=CompanyMembership.Status.ACTIVE,
            reviewed_at=cls.reviewed_at,
            reviewed_by=cls.company.user,
        )

    def participation_data(self, **extra):
        return {
            'membership': self.membership,
            'route_group': self.group,
            'transport_point': self.point,
            'started_at': self.started_at,
            'assigned_by': self.company.user,
            **extra,
        }

    def test_valid_participation_preserves_author_and_point(self):
        participation = PassengerGroupMembership.objects.create(**self.participation_data())
        participation.full_clean()
        self.assertEqual(participation.assigned_by, self.company.user)
        self.assertEqual(participation.transport_point, self.point)
        self.assertIsNone(participation.ended_at)

    def test_transport_point_can_be_pending_during_configuration(self):
        participation = PassengerGroupMembership.objects.create(**self.participation_data(transport_point=None))
        participation.full_clean()
        self.assertIsNone(participation.transport_point_id)

    def test_second_open_group_for_same_cycle_is_rejected_by_database(self):
        PassengerGroupMembership.objects.create(**self.participation_data())
        for group in (self.group, self.second_group):
            with self.subTest(group=group.pk), self.assertRaises(IntegrityError), transaction.atomic():
                PassengerGroupMembership.objects.create(**self.participation_data(route_group=group))

    def test_group_change_preserves_old_participation_and_company_approval(self):
        previous = PassengerGroupMembership.objects.create(**self.participation_data())
        change_at = self.started_at + timedelta(minutes=30)
        PassengerGroupMembership.objects.filter(pk=previous.pk).update(ended_at=change_at, ended_by=self.company.user)
        current = PassengerGroupMembership.objects.create(
            **self.participation_data(route_group=self.second_group, started_at=change_at)
        )
        current.full_clean()
        previous.refresh_from_db()
        self.assertEqual(previous.route_group, self.group)
        self.assertEqual(previous.ended_at, change_at)
        self.assertEqual(previous.ended_by, self.company.user)
        self.membership.refresh_from_db()
        self.assertEqual(self.membership.status, CompanyMembership.Status.ACTIVE)
        self.assertEqual(self.membership.reviewed_at, self.reviewed_at)
        self.assertEqual(self.membership.passenger_group_memberships.count(), 2)

    def test_multiple_passengers_can_share_group_and_operational_point(self):
        PassengerGroupMembership.objects.create(**self.participation_data())
        passenger = create_passenger('group-member-second-passenger@example.com')
        membership = CompanyMembership.objects.create(
            company=self.company,
            passenger=passenger,
            requested_by=passenger.user,
            created_at=self.reviewed_at,
            status=CompanyMembership.Status.ACTIVE,
            reviewed_at=self.reviewed_at,
            reviewed_by=self.company.user,
        )
        participation = PassengerGroupMembership.objects.create(
            **self.participation_data(membership=membership, started_at=timezone.now())
        )
        participation.full_clean()
        self.assertEqual(self.point.passenger_memberships.count(), 2)

    def test_database_requires_end_time_and_author_together(self):
        for extra in ({'ended_at': self.started_at}, {'ended_by': self.company.user}):
            with self.subTest(fields=tuple(extra)), self.assertRaises(IntegrityError), transaction.atomic():
                PassengerGroupMembership.objects.create(**self.participation_data(**extra))

    def test_database_rejects_end_before_start(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            PassengerGroupMembership.objects.create(
                **self.participation_data(
                    ended_at=self.started_at - timedelta(seconds=1),
                    ended_by=self.company.user,
                )
            )

    def test_equal_start_end_times_are_allowed(self):
        participation = PassengerGroupMembership.objects.create(
            **self.participation_data(ended_at=self.started_at, ended_by=self.company.user)
        )
        participation.full_clean()

    def test_update_cannot_skip_end_constraints(self):
        participation = PassengerGroupMembership.objects.create(**self.participation_data())
        with self.assertRaises(IntegrityError), transaction.atomic():
            PassengerGroupMembership.objects.filter(pk=participation.pk).update(ended_at=self.started_at)

    def test_bulk_create_cannot_skip_open_group_uniqueness(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            PassengerGroupMembership.objects.bulk_create([
                PassengerGroupMembership(**self.participation_data()),
                PassengerGroupMembership(**self.participation_data(route_group=self.second_group)),
            ])

    def test_full_clean_rejects_group_or_point_from_another_company(self):
        for field, value in (('route_group', self.other_group), ('transport_point', self.other_point)):
            with self.subTest(field=field):
                participation = PassengerGroupMembership(**self.participation_data(**{field: value}))
                with self.assertRaises(ValidationError) as error:
                    participation.full_clean()
                self.assertIn(field, error.exception.message_dict)

    def test_full_clean_rejects_driver_membership(self):
        driver = Driver.objects.create(user=create_user('group-member-driver@example.com'))
        membership = CompanyMembership.objects.create(
            company=self.company,
            driver=driver,
            requested_by=driver.user,
            created_at=self.reviewed_at,
            status=CompanyMembership.Status.ACTIVE,
            reviewed_at=self.reviewed_at,
            reviewed_by=self.company.user,
        )
        participation = PassengerGroupMembership(**self.participation_data(membership=membership))
        with self.assertRaises(ValidationError) as error:
            participation.full_clean()
        self.assertIn('membership', error.exception.message_dict)

    def test_full_clean_rejects_membership_without_approval(self):
        for status in (
            CompanyMembership.Status.PENDING,
            CompanyMembership.Status.REJECTED,
            CompanyMembership.Status.WITHDRAWN,
        ):
            CompanyMembership.objects.filter(pk=self.membership.pk).update(
                status=status,
                reviewed_at=self.reviewed_at if status == CompanyMembership.Status.REJECTED else None,
                reviewed_by=self.company.user if status == CompanyMembership.Status.REJECTED else None,
                withdrawn_at=self.started_at if status == CompanyMembership.Status.WITHDRAWN else None,
                withdrawn_by=self.passenger.user if status == CompanyMembership.Status.WITHDRAWN else None,
            )
            with self.subTest(status=status), self.assertRaises(ValidationError) as error:
                PassengerGroupMembership(**self.participation_data()).full_clean()
            self.assertIn('membership', error.exception.message_dict)

    def test_full_clean_rejects_open_participation_in_ended_membership(self):
        CompanyMembership.objects.filter(pk=self.membership.pk).update(
            status=CompanyMembership.Status.ENDED, ended_at=self.started_at, ended_by=self.company.user
        )
        with self.assertRaises(ValidationError) as error:
            PassengerGroupMembership(**self.participation_data()).full_clean()
        self.assertIn('membership', error.exception.message_dict)

    def test_closed_participation_in_ended_membership_preserves_history(self):
        end_at = self.started_at + timedelta(minutes=10)
        CompanyMembership.objects.filter(pk=self.membership.pk).update(
            status=CompanyMembership.Status.ENDED, ended_at=end_at, ended_by=self.company.user
        )
        participation = PassengerGroupMembership.objects.create(
            **self.participation_data(ended_at=end_at, ended_by=self.company.user)
        )
        participation.full_clean()

    def test_full_clean_rejects_participation_outside_membership_period(self):
        participation = PassengerGroupMembership(
            **self.participation_data(started_at=self.reviewed_at - timedelta(seconds=1))
        )
        with self.assertRaises(ValidationError) as error:
            participation.full_clean()
        self.assertIn('started_at', error.exception.message_dict)
        CompanyMembership.objects.filter(pk=self.membership.pk).update(
            status=CompanyMembership.Status.ENDED, ended_at=self.started_at, ended_by=self.company.user
        )
        participation = PassengerGroupMembership(
            **self.participation_data(
                ended_at=self.started_at + timedelta(seconds=1),
                ended_by=self.company.user,
            )
        )
        with self.assertRaises(ValidationError) as error:
            participation.full_clean()
        self.assertIn('ended_at', error.exception.message_dict)

    def test_clean_rejects_naive_timestamps_without_comparison_errors(self):
        for field in ('started_at', 'ended_at'):
            participation = PassengerGroupMembership(
                **self.participation_data(
                    **{field: timezone.now().replace(tzinfo=None)},
                )
            )
            with self.subTest(field=field), self.assertRaises(ValidationError) as error:
                participation.clean()
            self.assertIn(field, error.exception.message_dict)

    def test_full_clean_handles_missing_or_malformed_related_ids(self):
        for field in ('membership', 'route_group', 'transport_point'):
            for value in (999999, 'invalid'):
                participation = PassengerGroupMembership(**self.participation_data())
                setattr(participation, f'{field}_id', value)
                with self.subTest(field=field, value=value), self.assertRaises(ValidationError) as error:
                    participation.full_clean()
                self.assertIn(field, error.exception.message_dict)

    def test_referenced_membership_group_point_and_authors_are_protected(self):
        author = create_user('group-member-author@example.com')
        participation = PassengerGroupMembership.objects.create(
            **self.participation_data(
                assigned_by=author,
                ended_at=self.started_at,
                ended_by=author,
            )
        )
        for target in (self.membership, self.group, self.point, author):
            with self.subTest(model=type(target).__name__), self.assertRaises(ProtectedError):
                target.delete()
        self.assertEqual(participation.assigned_by, author)

    def test_participation_does_not_change_identity_or_company_approval(self):
        user_id = self.passenger.user_id
        PassengerGroupMembership.objects.create(**self.participation_data(route_group=self.second_group))
        self.passenger.refresh_from_db()
        self.membership.refresh_from_db()
        self.assertEqual(self.passenger.user_id, user_id)
        self.assertEqual(self.membership.status, 'active')

    def test_string_representation_only_uses_ids(self):
        participation = PassengerGroupMembership.objects.create(**self.participation_data())
        self.assertEqual(str(participation), f'Participação #{participation.pk} — grupo #{self.group.pk}')
