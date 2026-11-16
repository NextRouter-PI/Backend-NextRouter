from datetime import time, timedelta
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.utils import timezone

from modules.transport.models import DailyResponse, Notification, RouteOptimizationJob, ServiceDay, TravelParticipation
from modules.transport.services.calendar import generate_day, revise_day
from modules.transport.services.configuration import authorize_services, configure_policy, configure_service
from modules.transport.services.demand import answer_day, withdraw_leg
from modules.transport.services.execution import cancel_day, cancel_travel
from modules.transport.services.maintenance import process_due, read_notification
from modules.transport.services.planning import close_day

from .service_helpers import ServiceTestCase


class DailyServiceTests(ServiceTestCase):
    def test_generation_is_idempotent_and_freezes_dates_roster_and_vehicle(self):
        repeated = generate_day(actor_id=self.company.user_id, group_id=self.group.pk, date=self.date)
        self.assertEqual(repeated.pk, self.day.pk)
        self.assertEqual(repeated.revision, self.day.revision)
        self.assertEqual(repeated.travels.count(), 2)
        self.assertEqual(repeated.eligibilities.count(), 1)
        self.assertEqual(timezone.localtime(repeated.normal_deadline).hour, 22)
        self.assertEqual(self.travel().driver_id, self.driver.pk)
        self.assertEqual(self.travel().vehicle_id, self.vehicle.pk)

    def test_normal_answer_is_editable_and_negative_is_not_missing(self):
        self.assertFalse(DailyResponse.objects.exists())
        negative = self.answer(outbound=False)
        self.assertIsNotNone(negative.answered_at)
        positive = self.answer(returning=True)
        self.assertEqual(negative.pk, positive.pk)
        self.assertEqual(positive.revision, 2)
        self.assertEqual(positive.return_service_id, self.returning.pk)
        self.assertEqual(TravelParticipation.objects.count(), 0)

    def test_normal_deadline_equality_rejects_even_if_worker_has_not_run(self):
        self.now = self.day.normal_deadline
        self.assert_domain('response_window_closed', self.answer)
        self.assertFalse(DailyResponse.objects.exists())

    def test_opening_is_inclusive_and_before_opening_is_denied(self):
        self.now = self.day.opens_at - timedelta(microseconds=1)
        self.assert_domain('response_window_closed', self.answer)
        self.now = self.day.opens_at
        self.assertTrue(self.answer().outbound_service_id)

    def test_other_actor_or_unauthorized_service_cannot_answer(self):
        args = {
            'eligibility_id': self.eligibility.pk,
            'outbound_service_id': self.outbound.pk,
            'return_service_id': None,
            'expected_revision': 0,
        }
        self.assert_domain('permission_denied', answer_day, actor_id=self.other.user_id, **args)
        self.assert_domain(
            'service_not_authorized',
            answer_day,
            actor_id=self.passenger.user_id,
            **{**args, 'outbound_service_id': 999999},
        )

    def test_stale_answer_is_rejected(self):
        self.answer()
        self.assert_domain(
            'stale_revision',
            answer_day,
            actor_id=self.passenger.user_id,
            eligibility_id=self.eligibility.pk,
            outbound_service_id=None,
            return_service_id=None,
            expected_revision=0,
        )

    def test_close_is_idempotent_and_uses_only_valid_demand(self):
        self.answer()
        self.close()
        first_count = RouteOptimizationJob.objects.count()
        self.close()
        self.assertEqual(TravelParticipation.objects.count(), 1)
        self.assertEqual(RouteOptimizationJob.objects.count(), first_count)
        self.assertEqual(self.travel(self.returning).planning_status, 'blocked')

    def test_insufficient_capacity_rolls_back_all_allocations_and_jobs(self):
        from modules.organizations.models import PassengerGroupMembership
        from modules.transport.models import PassengerServiceAuthorization
        from tests.helpers import create_passenger

        second = create_passenger('second-demand@example.com')
        membership = self.membership.__class__.objects.create(
            company=self.company,
            passenger=second,
            status='active',
            requested_by=second.user,
            reviewed_by=self.company.user,
            created_at=self.now,
            reviewed_at=self.now,
        )
        group_member = PassengerGroupMembership.objects.create(
            membership=membership,
            route_group=self.group,
            transport_point=self.home,
            started_at=self.now,
            assigned_by=self.company.user,
        )
        PassengerServiceAuthorization.objects.create(
            participation=group_member, service=self.outbound, direction='outbound', is_habitual=True
        )
        generate_day(actor_id=self.company.user_id, group_id=self.group.pk, date=self.date)
        second_eligibility = self.day.eligibilities.get(passenger=second)
        answer_day(
            actor_id=second.user_id,
            eligibility_id=second_eligibility.pk,
            outbound_service_id=self.outbound.pk,
            return_service_id=None,
            expected_revision=0,
        )
        self.answer()
        self.vehicle.capacity = 1
        self.vehicle.save(update_fields=['capacity'])
        self.now = self.day.normal_deadline
        self.assert_domain('capacity_exceeded', close_day, actor_id=self.company.user_id, day_id=self.day.pk)
        self.assertFalse(TravelParticipation.objects.exists())
        self.assertFalse(RouteOptimizationJob.objects.exists())

    def test_regeneration_preserves_conflicting_answer_and_blocks_day(self):
        response = self.answer()
        authorize_services(
            actor_id=self.company.user_id, group_membership_id=self.group_member.pk, service_ids=[self.returning.pk]
        )
        response.refresh_from_db()
        self.day.refresh_from_db()
        self.assertEqual(response.outbound_service_id, self.outbound.pk)
        self.assertTrue(self.day.configuration_snapshot['issues'])
        self.now = self.day.normal_deadline
        self.assert_domain('day_conflicts', close_day, actor_id=self.company.user_id, day_id=self.day.pk)

    def test_one_publication_freezes_automatic_regeneration_of_whole_day(self):
        travel = self.ready_travel()
        self.publish(travel)
        self.day.refresh_from_db()
        frozen = self.day.configuration_snapshot
        configure_service(
            actor_id=self.company.user_id, group_id=self.group.pk, service_id=self.returning.pk, target_time=time(18)
        )
        self.day.refresh_from_db()
        self.assertEqual(self.day.configuration_snapshot, frozen)
        revised = revise_day(actor_id=self.company.user_id, day_id=self.day.pk, expected_revision=self.day.revision)
        self.assertGreater(revised.revision, self.day.revision)

    def test_policy_change_does_not_rewrite_effective_deadlines(self):
        configure_policy(actor_id=self.company.user_id, group_id=self.group.pk, normal_time=time(21))
        generate_day(actor_id=self.company.user_id, group_id=self.group.pk, date=self.date)
        self.day.refresh_from_db()
        self.assertEqual(timezone.localtime(self.day.normal_deadline).hour, 22)

    def test_cancel_tombstone_survives_regeneration_and_blocks_answers(self):
        cancel_day(actor_id=self.company.user_id, day_id=self.day.pk, reason='Cancelamento fictício')
        repeated = generate_day(actor_id=self.company.user_id, group_id=self.group.pk, date=self.date)
        self.assertIsNotNone(repeated.canceled_at)
        self.assert_domain('day_canceled', self.answer)
        self.assertFalse(self.day.travels.exclude(status='canceled').exists())

    def test_canceled_trip_is_not_recreated(self):
        travel = self.travel()
        cancel_travel(actor_id=self.company.user_id, travel_id=travel.pk)
        configure_service(
            actor_id=self.company.user_id, group_id=self.group.pk, service_id=self.outbound.pk, target_time=time(9)
        )
        travel.refresh_from_db()
        self.assertEqual(travel.status, 'canceled')
        self.assertEqual(self.day.travels.count(), 2)

    def test_date_can_be_canceled_before_any_travel_or_eligibility_is_generated(self):
        from modules.transport.services.execution import cancel_date

        date = self.date + timedelta(days=3)
        result = cancel_date(
            actor_id=self.company.user_id, group_id=self.group.pk, date=date, reason='Data fictícia cancelada'
        )
        self.assertFalse(result['day'].travels.exists())
        self.assertFalse(result['day'].eligibilities.exists())
        generated = generate_day(actor_id=self.company.user_id, group_id=self.group.pk, date=date)
        self.assertEqual(generated.pk, result['day'].pk)
        self.assertIsNotNone(generated.canceled_at)
        self.assertFalse(generated.travels.exists())

    def test_invalid_cancel_date_rolls_back_tombstone_creation(self):
        from modules.transport.services.execution import cancel_date

        date = self.date + timedelta(days=3)
        self.assert_domain(
            'reason_required', cancel_date, actor_id=self.company.user_id, group_id=self.group.pk, date=date, reason=''
        )
        self.assertFalse(ServiceDay.objects.filter(route_group=self.group, date=date).exists())

    def test_withdrawal_before_close_preserves_choice_and_excludes_allocation(self):
        response = self.answer()
        withdraw_leg(actor_id=self.passenger.user_id, eligibility_id=self.eligibility.pk, leg='outbound')
        self.close()
        response.refresh_from_db()
        self.assertIsNotNone(response.outbound_withdrawn_at)
        self.assertEqual(response.outbound_service_id, self.outbound.pk)
        self.assertFalse(TravelParticipation.objects.exists())

    def test_notifications_are_private_and_read_is_idempotent(self):
        travel = self.ready_travel()
        self.publish(travel)
        notification = Notification.objects.filter(recipient=self.passenger.user).first()
        self.assert_domain('not_found', read_notification, actor_id=self.other.user_id, notification_id=notification.pk)
        first = read_notification(actor_id=self.passenger.user_id, notification_id=notification.pk)
        self.now += timedelta(minutes=1)
        second = read_notification(actor_id=self.passenger.user_id, notification_id=notification.pk)
        self.assertEqual(first.read_at, second.read_at)
        self.assertEqual(set(notification.payload), {'status', 'revision'})

    def test_due_work_is_reentrant(self):
        self.answer()
        self.now = self.day.normal_deadline
        first = process_due(actor_id=self.company.user_id, company_id=self.company.pk, batch_size=10)
        second = process_due(actor_id=self.company.user_id, company_id=self.company.pk, batch_size=10)
        self.assertEqual(first[self.day.pk], 'closed')
        self.assertEqual(second, {})

    def test_invalid_durations_rejected_by_model_and_service(self):
        for duration in (timedelta(), timedelta(seconds=-1)):
            with self.assertRaises(ValidationError):
                configure_service(
                    actor_id=self.company.user_id,
                    group_id=self.group.pk,
                    service_id=self.outbound.pk,
                    planned_duration=duration,
                )

    def test_failed_publication_notice_rolls_back_publication(self):
        from modules.transport.models import TravelPublication
        from modules.transport.services.planning import publish_travel

        travel = self.ready_travel()
        with (
            patch.object(Notification.objects, 'get_or_create', side_effect=RuntimeError('Falha simulada')),
            self.assertRaises(RuntimeError),
        ):
            publish_travel(actor_id=self.company.user_id, travel_id=travel.pk, expected_revision=travel.revision)
        self.assertFalse(TravelPublication.objects.exists())
        travel.refresh_from_db()
        self.assertIsNone(travel.published_revision)
