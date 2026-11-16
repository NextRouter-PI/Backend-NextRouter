from concurrent.futures import ThreadPoolExecutor
from datetime import time, timedelta
from threading import Barrier
from unittest import skipUnless
from unittest.mock import patch

from django.db import close_old_connections, connection, connections

from modules.organizations.models import CompanyMembership, Driver, PassengerGroupMembership
from modules.transport.models import (
    Notification,
    PassengerServiceAuthorization,
    SeatReservation,
    TravelParticipation,
    Vehicle,
)
from modules.transport.services.calendar import generate_day
from modules.transport.services.common import DomainError
from modules.transport.services.demand import answer_day
from modules.transport.services.execution import start_travel
from modules.transport.services.invitations import invite_driver, respond_invitation
from modules.transport.services.jobs import claim_snapshot_job, process_snapshot_job
from modules.transport.services.planning import assign_vehicle, calculate_travel, publish_travel
from modules.transport.services.requests import apply_request, decide_request, request_change
from tests.helpers import create_passenger, create_user

from .service_helpers import ServiceTestCase


@skipUnless(connection.vendor == 'postgresql', 'Concorrência exige PostgreSQL; SQLite não comprova locks.')
class OperationalConcurrencyTests(ServiceTestCase):
    def race(self, *operations):
        barrier = Barrier(len(operations))

        def run(operation):
            close_old_connections()
            try:
                with connection.cursor() as cursor:
                    cursor.execute("SET lock_timeout = '5s'")
                    cursor.execute("SET statement_timeout = '10s'")
                    cursor.execute('SELECT pg_backend_pid()')
                    backend_pid = cursor.fetchone()[0]
                barrier.wait(timeout=10)
                try:
                    result = ('ok', operation())
                except DomainError as exc:
                    result = ('error', exc.code)
                return backend_pid, result
            finally:
                connections.close_all()

        with ThreadPoolExecutor(max_workers=len(operations)) as pool:
            futures = [pool.submit(run, operation) for operation in operations]
            results = [future.result(timeout=20) for future in futures]
        self.assertEqual(len({pid for pid, _ in results}), len(operations), 'A disputa reutilizou a mesma conexão.')
        return [result for _, result in results]

    def prepare_transfer(self):
        target = self.make_service('return', time(12))
        PassengerServiceAuthorization.objects.create(
            participation=self.group_member, service=target, direction='return'
        )
        generate_day(actor_id=self.company.user_id, group_id=self.group.pk, date=self.date)
        self.answer(outbound=False, returning=True)
        self.close()
        self.process_jobs()
        self.now += timedelta(minutes=30)
        request = request_change(
            actor_id=self.passenger.user_id,
            eligibility_id=self.eligibility.pk,
            leg='return',
            proposed_service_id=target.pk,
            expected_revision=1,
        )
        decide_request(actor_id=self.company.user_id, request_id=request.pk, approve=True)
        return request, target

    def assert_transfer_applied_once(self, request, target):
        request.refresh_from_db()
        request.response.refresh_from_db()
        self.assertEqual(request.application, 'applied')
        self.assertEqual(request.response.return_service_id, target.pk)
        self.assertEqual(request.response.revision, 2)
        self.assertEqual(request.seat_reservations.get().status, 'consumed')
        allocated = TravelParticipation.objects.get(eligibility=self.eligibility, leg='return', status='allocated')
        previous = self.travel(self.returning).participations.get(eligibility=self.eligibility)
        self.assertEqual(allocated.travel.service_id, target.pk)
        self.assertEqual(previous.status, 'withdrawn')
        self.assertEqual(allocated.events.filter(kind='allocated').count(), 1)
        self.assertEqual(previous.events.filter(kind='withdrawn').count(), 1)
        self.assertEqual(Notification.objects.filter(deduplication_key=f'request:{request.pk}:applied').count(), 2)
        for snapshot in request.route_snapshots.select_related('travel'):
            self.assertEqual(snapshot.travel.revision, snapshot.revision)
            self.assertEqual(snapshot.travel.current_snapshot_id, snapshot.pk)
            self.assertEqual(snapshot.travel.planning_status, 'ready')

    def prepare_invitation(self):
        travel = self.ready_travel()
        substitute = Driver.objects.create(user=create_user('concurrent-substitute@example.com'))
        membership = CompanyMembership.objects.create(
            company=self.company,
            driver=substitute,
            status='active',
            requested_by=substitute.user,
            created_at=self.now,
            reviewed_at=self.now,
            reviewed_by=self.company.user,
        )
        invitation = invite_driver(
            actor_id=self.company.user_id,
            travel_id=travel.pk,
            driver_membership_id=membership.pk,
            expires_at=self.now + timedelta(hours=1),
        )
        travel.refresh_from_db()
        return travel, invitation, substitute

    def test_two_generators_share_one_day_and_one_travel_per_service(self):
        date = self.date + timedelta(days=1)

        def generate():
            return generate_day(actor_id=self.company.user_id, group_id=self.group.pk, date=date).pk

        results = self.race(generate, generate)
        self.assertEqual(results[0], results[1])
        self.assertEqual(self.group.days.filter(date=date).get().travels.count(), 2)

    def test_two_workers_cannot_claim_same_attempt(self):
        self.answer()
        self.close()

        def claim():
            job = claim_snapshot_job(company_id=self.company.pk, lease_duration=timedelta(minutes=5), max_attempts=3)
            return job.pk if job else None

        results = self.race(claim, claim)
        self.assertTrue(all(result[0] == 'ok' for result in results))
        self.assertEqual(sum(result[1] is not None for result in results), 1)

    def test_start_and_recalculation_never_start_obsolete_publication(self):
        travel = self.ready_travel()
        self.publish(travel)
        results = self.race(
            lambda: (
                start_travel(actor_id=self.driver.user_id, travel_id=travel.pk, expected_revision=travel.revision).pk
            ),
            lambda: (
                calculate_travel(
                    actor_id=self.company.user_id, travel_id=travel.pk, expected_revision=travel.revision
                ).pk
            ),
        )
        self.assertEqual(sum(result[0] == 'ok' for result in results), 1)
        travel.refresh_from_db()
        if travel.status == 'in_progress':
            self.assertEqual(travel.revision, travel.published_revision)
            self.assertEqual(travel.current_snapshot_id, travel.published_snapshot_id)

    def test_two_approvals_dispute_last_reserved_seat_without_early_transfer(self):
        target = self.make_service('return', time(12))
        target.vehicle = Vehicle.objects.create(
            company=self.company, plate='JKL4G56', capacity=1, garage_point=self.garage
        )
        target.save(update_fields=['vehicle'])
        other = create_passenger('seat-competitor@example.com')
        membership = CompanyMembership.objects.create(
            company=self.company,
            passenger=other,
            status='active',
            requested_by=other.user,
            created_at=self.now,
            reviewed_at=self.now,
            reviewed_by=self.company.user,
        )
        group_member = PassengerGroupMembership.objects.create(
            membership=membership,
            route_group=self.group,
            transport_point=self.home,
            assigned_by=self.company.user,
            started_at=self.now,
        )
        PassengerServiceAuthorization.objects.create(
            participation=self.group_member, service=target, direction='return'
        )
        for service in (self.returning, target):
            PassengerServiceAuthorization.objects.create(
                participation=group_member, service=service, direction='return'
            )
        generate_day(actor_id=self.company.user_id, group_id=self.group.pk, date=self.date)
        other_eligibility = self.day.eligibilities.get(passenger=other)
        self.answer(outbound=False, returning=True)
        answer_day(
            actor_id=other.user_id,
            eligibility_id=other_eligibility.pk,
            outbound_service_id=None,
            return_service_id=self.returning.pk,
            expected_revision=0,
        )
        self.close()
        self.process_jobs()
        self.now += timedelta(minutes=30)
        proposals = [
            request_change(
                actor_id=actor,
                eligibility_id=eligibility,
                leg='return',
                proposed_service_id=target.pk,
                expected_revision=1,
            )
            for actor, eligibility in (
                (self.passenger.user_id, self.eligibility.pk),
                (other.user_id, other_eligibility.pk),
            )
        ]
        results = self.race(*[
            lambda proposal=proposal: (
                decide_request(actor_id=self.company.user_id, request_id=proposal.pk, approve=True).pk
            )
            for proposal in proposals
        ])
        self.assertEqual(sum(result[0] == 'ok' for result in results), 1)
        self.assertIn(('error', 'capacity_exceeded'), results)
        self.assertEqual(SeatReservation.objects.filter(status='held').count(), 1)
        self.assertEqual(self.travel(self.returning).participations.filter(status='allocated').count(), 2)

    def test_two_applications_transfer_once_and_deduplicate_events_and_notices(self):
        request, target = self.prepare_transfer()
        # Calcula a proposta sem aplicar, para disputar explicitamente a aplicação.
        with patch('modules.transport.services.jobs.apply_request'):
            self.process_jobs()
        self.assertEqual(self.travel(self.returning).participations.get().status, 'allocated')
        self.assertEqual(request.seat_reservations.get().status, 'held')

        def apply():
            return apply_request(actor_id=self.company.user_id, request_id=request.pk).pk

        self.assertEqual(self.race(apply, apply), [('ok', request.pk)] * 2)
        self.assert_transfer_applied_once(request, target)

    def test_two_workers_completing_proposal_apply_transfer_once(self):
        request, target = self.prepare_transfer()
        jobs = [
            claim_snapshot_job(company_id=self.company.pk, lease_duration=timedelta(minutes=5), max_attempts=1)
            for _ in range(2)
        ]
        self.assertEqual(len({job.pk for job in jobs}), 2)
        results = self.race(*[
            lambda job=job: process_snapshot_job(
                job_id=job.pk, claim_token=job.claim_token, max_attempts=1, retry_delay=timedelta(seconds=1)
            )
            for job in jobs
        ])
        self.assertEqual(results, [('ok', True)] * 2)
        self.assert_transfer_applied_once(request, target)
        for job in jobs:
            job.refresh_from_db()
            self.assertEqual(job.status, 'done')
            self.assertEqual(job.attempts, 1)

    def test_two_acceptances_designate_substitute_and_notify_only_once(self):
        travel, invitation, substitute = self.prepare_invitation()
        revision = travel.revision

        def accept():
            return respond_invitation(actor_id=substitute.user_id, invitation_id=invitation.pk, accept=True).pk

        self.assertEqual(self.race(accept, accept), [('ok', invitation.pk)] * 2)
        travel.refresh_from_db()
        invitation.refresh_from_db()
        self.assertEqual(invitation.status, 'accepted')
        self.assertEqual(travel.driver_id, substitute.pk)
        self.assertEqual(travel.revision, revision + 1)
        self.assertIsNone(travel.current_snapshot_id)
        self.assertEqual(
            Notification.objects.filter(deduplication_key=f'invitation:{invitation.pk}:accepted').count(), 1
        )

    def test_acceptance_and_refusal_cannot_both_decide_same_invitation(self):
        travel, invitation, substitute = self.prepare_invitation()
        results = self.race(*[
            lambda accept=accept: (
                respond_invitation(actor_id=substitute.user_id, invitation_id=invitation.pk, accept=accept).pk
            )
            for accept in (True, False)
        ])
        self.assertEqual(sorted(result[0] for result in results), ['error', 'ok'])
        self.assertIn(('error', 'invitation_expired'), results)
        invitation.refresh_from_db()
        travel.refresh_from_db()
        self.assertIn(invitation.status, ('accepted', 'declined'))
        self.assertEqual(travel.driver_id, substitute.pk if invitation.status == 'accepted' else None)
        self.assertEqual(
            Notification.objects.filter(
                resource_type='invitation', resource_id=str(invitation.pk), payload__status__in=['accepted', 'declined']
            ).count(),
            1,
        )

    def test_publication_and_vehicle_change_never_leave_stale_route_current(self):
        travel = self.ready_travel()
        revision, snapshot_id = travel.revision, travel.current_snapshot_id
        replacement = Vehicle.objects.create(
            company=self.company, plate='PQR6J78', capacity=2, garage_point=self.garage
        )
        results = self.race(
            lambda: publish_travel(actor_id=self.company.user_id, travel_id=travel.pk, expected_revision=revision).pk,
            lambda: assign_vehicle(actor_id=self.company.user_id, travel_id=travel.pk, vehicle_id=replacement.pk).pk,
        )
        self.assertEqual(results[1], ('ok', travel.pk))
        travel.refresh_from_db()
        self.assertEqual(travel.vehicle_id, replacement.pk)
        self.assertEqual(travel.revision, revision + 1)
        self.assertIsNone(travel.current_snapshot_id)
        self.assertEqual(travel.planning_status, 'draft')
        if results[0][0] == 'ok':
            self.assertEqual(travel.publications.get().snapshot_id, snapshot_id)
            self.assertEqual(travel.published_revision, revision)
        else:
            self.assertEqual(results[0], ('error', 'stale_revision'))
            self.assertFalse(travel.publications.exists())
        self.assert_domain(
            'publication_outdated',
            start_travel,
            actor_id=self.driver.user_id,
            travel_id=travel.pk,
            expected_revision=travel.revision,
        )
