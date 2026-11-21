from datetime import time, timedelta
from unittest.mock import patch

from modules.transport.models import DailyResponse, Notification, RouteOptimizationJob, TravelParticipation
from modules.transport.osrm import OSRMError
from modules.transport.services.calendar import generate_day
from modules.transport.services.demand import withdraw_leg
from modules.transport.services.maintenance import process_due
from modules.transport.services.requests import apply_request, decide_request, request_change, withdraw_request

from .service_helpers import ServiceTestCase


class RequestServiceTests(ServiceTestCase):
    def prepare_transfer(self, *, respond=True, outbound=False):
        self.midday = self.make_service('return', time(12))
        from modules.transport.models import PassengerServiceAuthorization

        PassengerServiceAuthorization.objects.create(
            participation=self.group_member, service=self.midday, direction='return'
        )
        generate_day(actor_id=self.company.user_id, group_id=self.group.pk, date=self.date)
        if respond:
            self.answer(outbound=outbound, returning=True)
        self.close()
        self.process_jobs()
        self.now += timedelta(minutes=30)
        response = DailyResponse.objects.filter(eligibility=self.eligibility).first()
        return request_change(
            actor_id=self.passenger.user_id,
            eligibility_id=self.eligibility.pk,
            leg='return',
            proposed_service_id=self.midday.pk,
            expected_revision=response.revision if response else 0,
        )

    def approve(self, request):
        return decide_request(actor_id=self.company.user_id, request_id=request.pk, approve=True)

    def test_approval_reserves_seat_without_changing_choice_or_previous_allocation(self):
        request = self.prepare_transfer()
        previous = TravelParticipation.objects.get(eligibility=self.eligibility, status='allocated')
        approved = self.approve(request)
        request.response.refresh_from_db()
        previous.refresh_from_db()
        self.assertEqual(approved.application, 'preparing')
        self.assertEqual(request.response.return_service_id, self.returning.pk)
        self.assertEqual(previous.status, 'allocated')
        self.assertEqual(approved.seat_reservations.get().status, 'held')
        self.assertEqual(approved.route_snapshots.count(), 2)
        self.assertEqual(
            TravelParticipation.objects.filter(eligibility=self.eligibility, status='allocated').count(), 1
        )

    def test_valid_calculation_applies_transfer_atomically_and_idempotently(self):
        request = self.prepare_transfer()
        self.approve(request)
        self.process_jobs()
        request.refresh_from_db()
        request.response.refresh_from_db()
        self.assertEqual(request.application, 'applied')
        self.assertEqual(request.response.return_service_id, self.midday.pk)
        self.assertEqual(request.seat_reservations.get().status, 'consumed')
        allocated = TravelParticipation.objects.get(eligibility=self.eligibility, status='allocated')
        self.assertEqual(allocated.travel.service_id, self.midday.pk)
        self.assertEqual(TravelParticipation.objects.get(travel__service=self.returning).status, 'withdrawn')
        before = Notification.objects.count()
        apply_request(actor_id=self.company.user_id, request_id=request.pk)
        self.assertEqual(Notification.objects.count(), before)
        for snapshot in request.route_snapshots.all():
            snapshot.full_clean()
        self.assertTrue(allocated.route_stops.exists())

    def test_calculation_failure_preserves_previous_and_releases_proposed_seat(self):
        request = self.prepare_transfer()
        self.approve(request)
        with patch('modules.transport.services.jobs.calculate_frozen', side_effect=OSRMError('Falha fictícia')):
            self.process_jobs()
        request.refresh_from_db()
        request.response.refresh_from_db()
        self.assertEqual(request.application, 'failed')
        self.assertEqual(request.response.return_service_id, self.returning.pk)
        self.assertEqual(request.seat_reservations.get().status, 'released')
        self.assertEqual(TravelParticipation.objects.get(status='allocated').travel.service_id, self.returning.pk)

    def test_include_nonrespondent_does_not_fabricate_negative_before_application(self):
        request = self.prepare_transfer(respond=False)
        self.assertIsNone(request.response.answered_at)
        self.assertIsNone(request.response.return_service_id)
        self.approve(request)
        request.response.refresh_from_db()
        self.assertIsNone(request.response.answered_at)
        self.process_jobs()
        request.response.refresh_from_db()
        self.assertIsNotNone(request.response.answered_at)
        self.assertEqual(request.response.return_service_id, self.midday.pk)

    def test_approval_at_extension_equality_is_denied_and_pending_expires(self):
        request = self.prepare_transfer()
        self.now = self.day.extension_deadline
        self.assert_domain('extension_closed', self.approve, request=request)
        process_due(actor_id=self.company.user_id, company_id=self.company.pk, batch_size=10)
        request.refresh_from_db()
        self.assertEqual(request.status, 'expired')
        self.assertEqual(request.response.return_service_id, self.returning.pk)

    def test_refusal_and_withdrawal_preserve_previous_choice(self):
        request = self.prepare_transfer()
        decide_request(actor_id=self.company.user_id, request_id=request.pk, approve=False, reason='Recusa fictícia')
        self.assertEqual(request.response.return_service_id, self.returning.pk)
        self.assertFalse(request.seat_reservations.exists())
        next_request = request_change(
            actor_id=self.passenger.user_id,
            eligibility_id=self.eligibility.pk,
            leg='return',
            proposed_service_id=self.midday.pk,
            expected_revision=request.response.revision,
        )
        withdraw_request(actor_id=self.passenger.user_id, request_id=next_request.pk)
        self.assert_domain('request_not_pending', self.approve, request=next_request)

    def test_only_own_company_decides(self):
        request = self.prepare_transfer()
        self.assert_domain(
            'permission_denied', decide_request, actor_id=self.other.user_id, request_id=request.pk, approve=True
        )
        self.assert_domain(
            'permission_denied', decide_request, actor_id=self.passenger.user_id, request_id=request.pk, approve=True
        )

    def test_capacity_includes_existing_reservations(self):
        request = self.prepare_transfer()
        from modules.transport.models import SeatReservation

        target = self.travel(self.midday)
        self.vehicle.capacity = 1
        self.vehicle.save(update_fields=['capacity'])
        self.approve(request)
        self.assertEqual(SeatReservation.objects.filter(travel=target, status='held').count(), 1)
        from modules.transport.services.planning import capacity

        self.assert_domain('capacity_exceeded', capacity, travel=target, additional=1)

    def test_withdrawal_invalidates_conflicting_proposal_and_obsolete_jobs(self):
        request = self.prepare_transfer()
        self.approve(request)
        withdraw_leg(actor_id=self.passenger.user_id, eligibility_id=self.eligibility.pk, leg='return')
        self.process_jobs()
        request.refresh_from_db()
        self.assertEqual(request.status, 'superseded')
        self.assertEqual(request.seat_reservations.get().status, 'released')
        self.assertFalse(TravelParticipation.objects.filter(status='allocated').exists())
        self.assertFalse(
            RouteOptimizationJob.objects.filter(snapshot__change_request=request, status='pending').exists()
        )

    def test_application_revalidates_capacity_and_keeps_previous_on_conflict(self):
        request = self.prepare_transfer()
        self.approve(request)
        # Mudança de disponibilidade entre decisão e cálculo, sem copiar alocações novas.
        self.vehicle.status = 'maintenance'
        self.vehicle.save(update_fields=['status'])
        self.process_jobs()
        request.refresh_from_db()
        self.assertEqual(request.application, 'failed')
        self.assertEqual(TravelParticipation.objects.get(status='allocated').travel.service_id, self.returning.pk)

    def test_notification_failure_rolls_back_approval_reservation_and_jobs(self):
        request = self.prepare_transfer()
        count = RouteOptimizationJob.objects.count()
        with (
            patch('modules.transport.services.requests.lifecycle.notify', side_effect=RuntimeError('Falha fictícia')),
            self.assertRaises(RuntimeError),
        ):
            self.approve(request)
        request.refresh_from_db()
        self.assertEqual(request.status, 'pending')
        self.assertFalse(request.seat_reservations.exists())
        self.assertEqual(RouteOptimizationJob.objects.count(), count)

    def test_nonrespondent_can_withdraw_approved_inclusion_without_fabricating_answer(self):
        request = self.prepare_transfer(respond=False)
        self.approve(request)
        withdraw_leg(actor_id=self.passenger.user_id, eligibility_id=self.eligibility.pk, leg='return')
        self.process_jobs()
        request.refresh_from_db()
        request.response.refresh_from_db()
        self.assertEqual(request.status, 'superseded')
        self.assertIsNone(request.response.answered_at)
        self.assertFalse(TravelParticipation.objects.exists())

    def test_withdrawal_of_other_leg_does_not_invalidate_return_request(self):
        request = self.prepare_transfer(outbound=True)
        self.approve(request)
        withdraw_leg(actor_id=self.passenger.user_id, eligibility_id=self.eligibility.pk, leg='outbound')
        self.process_jobs()
        request.refresh_from_db()
        self.assertEqual(request.application, 'applied')

    def test_reinclusion_after_withdrawal_requires_fresh_approved_request(self):
        previous = self.prepare_transfer()
        withdraw_leg(actor_id=self.passenger.user_id, eligibility_id=self.eligibility.pk, leg='return')
        previous.response.refresh_from_db()
        request = request_change(
            actor_id=self.passenger.user_id,
            eligibility_id=self.eligibility.pk,
            leg='return',
            proposed_service_id=self.midday.pk,
            expected_revision=previous.response.revision,
        )
        self.approve(request)
        self.process_jobs()
        request.refresh_from_db()
        request.response.refresh_from_db()
        self.assertEqual(request.application, 'applied')
        self.assertIsNone(request.response.return_withdrawn_at)

    def test_normal_job_cannot_unlock_publication_while_proposal_is_pending(self):
        from modules.transport.services.jobs import claim_snapshot_job, process_snapshot_job
        from modules.transport.services.planning import calculate_travel, publish_travel

        request = self.prepare_transfer()
        source = self.travel(self.returning)
        calculate_travel(actor_id=self.company.user_id, travel_id=source.pk, expected_revision=source.revision)
        self.approve(request)
        job = claim_snapshot_job(company_id=self.company.pk, lease_duration=timedelta(minutes=5), max_attempts=1)
        self.assertIsNone(job.snapshot.change_request_id)
        process_snapshot_job(
            job_id=job.pk, claim_token=job.claim_token, max_attempts=1, retry_delay=timedelta(seconds=1)
        )
        source.refresh_from_db()
        self.assertEqual(source.planning_status, 'preparing')
        self.assert_domain(
            'planning_not_ready',
            publish_travel,
            actor_id=self.company.user_id,
            travel_id=source.pk,
            expected_revision=source.revision,
        )
