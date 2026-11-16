from concurrent.futures import ThreadPoolExecutor
from datetime import time, timedelta
from threading import Barrier
from unittest import skipUnless

from django.db import close_old_connections, connection, connections

from modules.organizations.models import CompanyMembership, PassengerGroupMembership
from modules.transport.models import PassengerServiceAuthorization, SeatReservation, Vehicle
from modules.transport.services.calendar import generate_day
from modules.transport.services.common import DomainError
from modules.transport.services.demand import answer_day
from modules.transport.services.execution import start_travel
from modules.transport.services.jobs import claim_snapshot_job
from modules.transport.services.planning import calculate_travel
from modules.transport.services.requests import decide_request, request_change
from tests.helpers import create_passenger

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
                barrier.wait(timeout=10)
                try:
                    return ('ok', operation())
                except DomainError as exc:
                    return ('error', exc.code)
            finally:
                connections.close_all()

        with ThreadPoolExecutor(max_workers=len(operations)) as pool:
            futures = [pool.submit(run, operation) for operation in operations]
            return [future.result(timeout=20) for future in futures]

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
