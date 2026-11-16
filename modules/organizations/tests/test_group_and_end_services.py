from datetime import timedelta
from unittest.mock import patch

from django.utils import timezone

from modules.organizations.models import CompanyMembership, Driver, MembershipEvent, PassengerGroupMembership
from modules.organizations.services.errors import MembershipError
from modules.organizations.services.groups import assign_passenger_group
from modules.organizations.services.memberships import end_membership, request_membership
from modules.transport.models import (
    DailyResponse,
    Notification,
    PassengerServiceAuthorization,
    RouteSnapshot,
    Travel,
    TravelParticipation,
)
from modules.transport.tests.helpers import DayModelTestCase
from tests.helpers import create_operational_point, create_route_group, create_user


class GroupAndEndServiceTests(DayModelTestCase):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.new_group = create_route_group(cls.company, 'Outro grupo')
        cls.staff = create_user('group-service-staff@example.com', is_staff=True, is_superuser=True)
        cls.driver = Driver.objects.create(user=create_user('group-service-driver@example.com'))
        cls.driver_membership = CompanyMembership.objects.create(
            company=cls.company,
            driver=cls.driver,
            requested_by=cls.driver.user,
            created_at=cls.now,
            status='active',
            reviewed_at=cls.now,
            reviewed_by=cls.company.user,
        )

    def assign(self, **extra):
        return assign_passenger_group(**{
            'actor_id': self.company.user_id,
            'membership_id': self.membership.pk,
            'route_group_id': self.new_group.pk,
            'transport_point_id': self.point.pk,
            **extra,
        })

    def end(self, **extra):
        return end_membership(**{
            'actor_id': self.passenger.user_id,
            'membership_id': self.membership.pk,
            **extra,
        })

    def assert_error(self, code, operation, **extra):
        with self.assertRaises(MembershipError) as caught:
            operation(**extra)
        self.assertEqual(caught.exception.code, code)

    def create_travel(self, *, active=False, participant_status='allocated'):
        travel = Travel.objects.create(
            company=self.company,
            service_day=self.day,
            service=self.service,
            driver=self.driver,
            vehicle=self.vehicle,
            planned_start=self.now + timedelta(hours=3),
            planned_end=self.now + timedelta(hours=4),
        )
        data = {'travel': travel, 'eligibility': self.eligibility, 'leg': 'outbound', 'allocated_at': self.now}
        fields = {'withdrawn': 'withdrawn_at', 'no_show': 'no_show_at', 'on_board': 'boarded_at'}
        if participant_status in fields:
            data[fields[participant_status]] = self.now
        if participant_status == 'dropped_off':
            data.update(boarded_at=self.now, dropped_off_at=self.now)
        TravelParticipation.objects.create(**data, status=participant_status)
        if active:
            snapshot = RouteSnapshot.objects.create(
                travel=travel,
                revision=1,
                base_revision=1,
                state='ready',
                geometry={'type': 'LineString', 'coordinates': [[-48.8, -26.3], [-48.7, -26.2]]},
                origin={'latitude': -26.3, 'longitude': -48.8},
                destination={'latitude': -26.2, 'longitude': -48.7},
                distance_meters=1000,
                duration_seconds=120,
                created_at=self.now,
                calculated_at=self.now,
            )
            travel.current_snapshot = snapshot
            travel.published_snapshot = snapshot
            travel.published_revision = 1
            travel.planning_status = 'ready'
            travel.status = 'in_progress'
            travel.started_at = self.now
            travel.save()
        return travel

    def test_switch_group_preserves_approval_identity_eligibility_and_response(self):
        response = DailyResponse.objects.create(eligibility=self.eligibility, outbound_service=self.service)
        initial = (self.passenger.pk, self.passenger.user_id)
        result = self.assign()
        result.full_clean()
        self.participation.refresh_from_db()
        self.membership.refresh_from_db()
        self.eligibility.refresh_from_db()
        response.refresh_from_db()
        self.passenger.refresh_from_db()
        self.assertEqual(result.route_group_id, self.new_group.pk)
        self.assertEqual(self.membership.status, 'active')
        self.assertEqual(self.membership.reviewed_at, self.now)
        self.assertEqual(self.participation.ended_by_id, self.company.user_id)
        self.assertEqual(self.participation.ended_at, result.started_at)
        self.assertEqual(self.eligibility.group_membership_id, self.participation.pk)
        self.assertEqual(response.outbound_service_id, self.service.pk)
        self.assertEqual((self.passenger.pk, self.passenger.user_id), initial)
        self.assertEqual(self.membership.passenger_group_memberships.filter(ended_at=None).count(), 1)
        self.assertFalse(result.service_authorizations.exists())
        notice = Notification.objects.get()
        notice.full_clean()
        self.assertEqual(notice.recipient_id, self.passenger.user_id)
        self.assertEqual(notice.payload, {'status': 'active'})

    def test_initial_assignment_allows_incomplete_point_and_is_idempotent(self):
        self.participation.ended_at = self.now
        self.participation.ended_by = self.company.user
        self.participation.save()
        first = self.assign(transport_point_id=None)
        second = self.assign(transport_point_id=None)
        self.assertEqual(first.pk, second.pk)
        self.assertIsNone(first.transport_point_id)
        self.assertEqual(Notification.objects.count(), 1)

    def test_point_change_versions_group_and_copies_only_human_authorizations(self):
        point = create_operational_point(self.company, name='Outro ponto')
        authorization = PassengerServiceAuthorization.objects.create(
            participation=self.participation, service=self.service, direction='outbound', is_habitual=True
        )
        result = self.assign(route_group_id=self.group.pk, transport_point_id=point.pk)
        self.participation.refresh_from_db()
        self.assertEqual(self.participation.transport_point_id, self.point.pk)
        self.assertEqual(result.transport_point_id, point.pk)
        copied = result.service_authorizations.get()
        copied.full_clean()
        self.assertEqual(copied.service_id, authorization.service_id)
        self.assertTrue(copied.is_habitual)
        self.assertNotEqual(copied.pk, authorization.pk)

    def test_point_change_revalidates_authorizations_before_copying(self):
        PassengerServiceAuthorization.objects.create(
            participation=self.participation, service=self.service, direction='return'
        )
        point = create_operational_point(self.company, name='Outro ponto')
        self.assert_error(
            'invalid_authorization', self.assign, route_group_id=self.group.pk, transport_point_id=point.pk
        )
        self.participation.refresh_from_db()
        self.assertIsNone(self.participation.ended_at)
        self.assertEqual(PassengerGroupMembership.objects.count(), 1)

    def test_foreign_group_or_point_is_not_found_in_company_scope(self):
        self.assert_error('not_found', self.assign, route_group_id=self.other_group.pk)
        self.assert_error('not_found', self.assign, transport_point_id=self.other_point.pk)
        self.participation.refresh_from_db()
        self.assertIsNone(self.participation.ended_at)
        self.assertFalse(Notification.objects.exists())

    def test_group_assignment_requires_company_owner_without_staff_bypass(self):
        for actor in (self.passenger.user, self.driver.user, self.other_company.user, self.staff):
            self.assert_error('permission_denied', self.assign, actor_id=actor.pk)

    def test_group_assignment_requires_active_passenger_membership(self):
        self.assert_error('invalid_passenger_membership', self.assign, membership_id=self.driver_membership.pk)
        self.end()
        self.assert_error('invalid_passenger_membership', self.assign)

    def test_group_assignment_requires_approved_company_and_active_holder(self):
        type(self.company).objects.filter(pk=self.company.pk).update(is_approved=False)
        self.assert_error('company_unavailable', self.assign)
        type(self.company).objects.filter(pk=self.company.pk).update(is_approved=True)
        type(self.passenger.user).objects.filter(pk=self.passenger.user_id).update(is_active=False)
        self.assert_error('profile_unavailable', self.assign)

    def test_group_idempotence_does_not_bypass_authorization(self):
        self.assign()
        self.assert_error('permission_denied', self.assign, actor_id=self.staff.pk)
        self.assertEqual(Notification.objects.count(), 1)

    def test_holder_ends_membership_and_group_atomically_without_deleting_history(self):
        response = DailyResponse.objects.create(eligibility=self.eligibility, outbound_service=self.service)
        result = self.end(reason='Encerramento fictício')
        result.full_clean()
        self.participation.refresh_from_db()
        self.participation.full_clean()
        self.assertEqual(result.status, 'ended')
        self.assertEqual(result.ended_by_id, self.passenger.user_id)
        self.assertEqual(self.participation.ended_at, result.ended_at)
        self.assertEqual(self.participation.ended_by_id, self.passenger.user_id)
        self.assertEqual(result.events.get().action, 'ended')
        self.assertEqual(result.events.get().reason, 'Encerramento fictício')
        self.assertEqual(Notification.objects.get().recipient_id, self.company.user_id)
        self.assertTrue(DailyResponse.objects.filter(pk=response.pk).exists())
        self.assertTrue(type(self.passenger).objects.filter(pk=self.passenger.pk).exists())
        new = request_membership(
            actor_id=self.passenger.user_id, company_id=self.other_company.pk, passenger_id=self.passenger.pk
        )
        self.assertNotEqual(new.pk, result.pk)
        self.assertEqual(new.status, 'pending')

    def test_company_can_end_driver_membership_without_deleting_profile(self):
        result = self.end(actor_id=self.company.user_id, membership_id=self.driver_membership.pk)
        result.full_clean()
        self.assertEqual(result.status, 'ended')
        self.assertEqual(result.ended_by_id, self.company.user_id)
        self.assertEqual(Notification.objects.get().recipient_id, self.driver.user_id)
        self.assertTrue(Driver.objects.filter(pk=self.driver.pk).exists())

    def test_end_is_idempotent_and_preserves_original_actor_reason_and_time(self):
        first = self.end(reason='Primeiro motivo')
        second = self.end(actor_id=self.company.user_id, reason='Outro motivo')
        self.assertEqual(first.ended_at, second.ended_at)
        self.assertEqual(second.ended_by_id, self.passenger.user_id)
        self.assertEqual(second.events.get().reason, 'Primeiro motivo')
        self.assertEqual(Notification.objects.count(), 1)
        self.assert_error('permission_denied', self.end, actor_id=self.staff.pk)

    def test_end_does_not_require_company_approval(self):
        type(self.company).objects.filter(pk=self.company.pk).update(is_approved=False)
        self.assertEqual(self.end().status, 'ended')

    def test_other_company_and_staff_cannot_end_membership(self):
        for actor in (self.other_company.user, self.staff, self.driver.user):
            self.assert_error('permission_denied', self.end, actor_id=actor.pk)
        self.membership.refresh_from_db()
        self.assertEqual(self.membership.status, 'active')

    def test_inactive_holder_cannot_end_membership(self):
        type(self.passenger.user).objects.filter(pk=self.passenger.user_id).update(is_active=False)
        self.assert_error('permission_denied', self.end)

    def test_pending_membership_is_not_ended(self):
        CompanyMembership.objects.filter(pk=self.membership.pk).update(
            status='pending', reviewed_at=None, reviewed_by=None
        )
        self.assert_error('membership_not_active', self.end)

    def test_future_passenger_allocation_blocks_end_and_group_switch(self):
        travel = self.create_travel()
        for operation in (self.end, self.assign):
            self.assert_error('future_allocation', operation)
        self.assert_error(
            'future_allocation', self.end, actor_id=self.driver.user_id, membership_id=self.driver_membership.pk
        )
        self.membership.refresh_from_db()
        self.participation.refresh_from_db()
        self.assertEqual(self.membership.status, 'active')
        self.assertIsNone(self.participation.ended_at)
        self.assertEqual(travel.participations.get().status, 'allocated')
        self.assertFalse(Notification.objects.exists())

    def test_today_allocation_blocks_even_after_planned_end(self):
        self.day.date = timezone.localdate(self.now)
        self.day.save(update_fields=['date'])
        travel = self.create_travel()
        Travel.objects.filter(pk=travel.pk).update(
            planned_start=self.now - timedelta(hours=2), planned_end=self.now - timedelta(hours=1)
        )
        with patch('modules.organizations.services.memberships.timezone.now', return_value=self.now):
            self.assert_error('future_allocation', self.end)

    def test_previous_date_with_future_planned_end_still_blocks_change(self):
        self.day.date = timezone.localdate(self.now) - timedelta(days=1)
        self.day.save(update_fields=['date'])
        self.create_travel()
        self.assert_error('future_allocation', self.end)

    def test_active_participation_blocks_end_and_switch_even_on_previous_date(self):
        self.day.date = self.tomorrow - timedelta(days=3)
        self.day.save(update_fields=['date'])
        self.create_travel(active=True, participant_status='on_board')
        self.assert_error('operation_in_progress', self.end)
        self.assert_error('operation_in_progress', self.assign)
        self.assert_error(
            'operation_in_progress', self.end, actor_id=self.driver.user_id, membership_id=self.driver_membership.pk
        )

    def test_allocated_not_yet_boarded_on_active_travel_also_blocks(self):
        self.create_travel(active=True)
        self.assert_error('operation_in_progress', self.end)

    def test_withdrawn_passenger_can_end_but_active_driver_cannot(self):
        self.create_travel(active=True, participant_status='withdrawn')
        self.assertEqual(self.end().status, 'ended')
        self.assert_error(
            'operation_in_progress', self.end, actor_id=self.driver.user_id, membership_id=self.driver_membership.pk
        )

    def test_no_show_or_dropped_off_passenger_is_not_operationally_active(self):
        travel = self.create_travel(active=True, participant_status='no_show')
        self.assertEqual(self.assign().route_group_id, self.new_group.pk)
        TravelParticipation.objects.filter(travel=travel).update(
            status='dropped_off', no_show_at=None, boarded_at=self.now, dropped_off_at=self.now
        )
        self.assertEqual(self.end().status, 'ended')

    def test_canceled_future_travel_does_not_block_end(self):
        travel = self.create_travel()
        travel.status = 'canceled'
        travel.save(update_fields=['status'])
        self.assertEqual(self.end().status, 'ended')

    def test_future_withdrawn_participant_does_not_block_group_switch(self):
        self.create_travel(participant_status='withdrawn')
        self.assertEqual(self.assign().route_group_id, self.new_group.pk)

    def test_clock_before_group_start_has_no_partial_effect(self):
        self.participation.started_at = self.now + timedelta(days=1)
        self.participation.save(update_fields=['started_at'])
        for operation in (self.end, self.assign):
            with patch('modules.organizations.services.memberships.timezone.now', return_value=self.now):
                self.assert_error('invalid_time', operation)
        self.participation.refresh_from_db()
        self.assertIsNone(self.participation.ended_at)
        self.assertFalse(Notification.objects.exists())

    def test_notice_failure_rolls_back_end_and_closed_group(self):
        for manager in (MembershipEvent.objects, Notification.objects):
            with (
                patch.object(manager, 'create', side_effect=RuntimeError('Falha simulada')),
                self.assertRaises(RuntimeError),
            ):
                self.end()
            self.membership.refresh_from_db()
            self.participation.refresh_from_db()
            self.assertEqual(self.membership.status, 'active')
            self.assertIsNone(self.participation.ended_at)
            self.assertFalse(MembershipEvent.objects.exists())

    def test_notice_failure_rolls_back_group_switch(self):
        with (
            patch.object(Notification.objects, 'create', side_effect=RuntimeError('Falha simulada')),
            self.assertRaises(RuntimeError),
        ):
            self.assign()
        self.participation.refresh_from_db()
        self.assertIsNone(self.participation.ended_at)
        self.assertEqual(PassengerGroupMembership.objects.count(), 1)
