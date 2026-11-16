from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from unittest import skipUnless

from django.db import close_old_connections, connection, connections
from django.test import TransactionTestCase

from modules.organizations.models import CompanyMembership, MembershipEvent
from modules.organizations.services.errors import MembershipError
from modules.organizations.services.groups import assign_passenger_group
from modules.organizations.services.memberships import (
    approve_membership,
    end_membership,
    request_membership,
    withdraw_membership,
)
from modules.transport.models import Notification
from tests.helpers import create_company, create_passenger, create_route_group


@skipUnless(connection.vendor == 'postgresql', 'Exige PostgreSQL e conexões independentes; SQLite não comprova locks.')
class MembershipConcurrencyTests(TransactionTestCase):
    def setUp(self):
        self.company = create_company('concurrent-company@example.com')
        self.other_company = create_company('concurrent-other@example.com')
        self.passenger = create_passenger('concurrent-passenger@example.com')

    def race(self, *operations):
        barrier = Barrier(len(operations))

        def run(operation):
            close_old_connections()
            try:
                # Evita travar a suíte em caso de regressão na ordem dos locks.
                with connection.cursor() as cursor:
                    cursor.execute("SET lock_timeout = '5s'")
                    cursor.execute("SET statement_timeout = '10s'")
                    cursor.execute('SELECT pg_backend_pid()')
                    backend_pid = cursor.fetchone()[0]
                barrier.wait(timeout=10)
                try:
                    result = operation()
                    result = ('ok', result.pk, result.status)
                except MembershipError as exc:
                    result = ('error', exc.code)
                return backend_pid, result
            finally:
                connections.close_all()

        with ThreadPoolExecutor(max_workers=len(operations)) as pool:
            futures = [pool.submit(run, operation) for operation in operations]
            results = [future.result(timeout=20) for future in futures]
        self.assertEqual(len({pid for pid, _ in results}), len(operations), 'A disputa reutilizou a mesma conexão.')
        return [result for _, result in results]

    def request(self, company_id):
        return request_membership(
            actor_id=self.passenger.user_id, company_id=company_id, passenger_id=self.passenger.pk
        )

    def test_two_requests_to_different_companies_have_only_one_winner(self):
        results = self.race(lambda: self.request(self.company.pk), lambda: self.request(self.other_company.pk))
        self.assertEqual(sorted(result[0] for result in results), ['error', 'ok'])
        self.assertIn(('error', 'membership_open'), results)
        self.assertEqual(CompanyMembership.objects.count(), 1)
        self.assertEqual(MembershipEvent.objects.count(), 1)
        self.assertEqual(Notification.objects.count(), 1)

    def test_two_identical_requests_share_cycle_event_and_notice(self):
        results = self.race(lambda: self.request(self.company.pk), lambda: self.request(self.company.pk))
        self.assertEqual(results[0], results[1])
        self.assertEqual(results[0][0], 'ok')
        self.assertEqual(CompanyMembership.objects.count(), 1)
        self.assertEqual(MembershipEvent.objects.count(), 1)
        self.assertEqual(Notification.objects.count(), 1)

    def test_two_approvals_do_not_duplicate_decision(self):
        membership = self.request(self.company.pk)

        def approve():
            return approve_membership(actor_id=self.company.user_id, membership_id=membership.pk)

        results = self.race(approve, approve)
        self.assertEqual(results, [('ok', membership.pk, 'active')] * 2)
        self.assertEqual(membership.events.count(), 2)
        self.assertEqual(Notification.objects.count(), 2)

    def test_approval_and_withdrawal_cannot_both_apply(self):
        membership = self.request(self.company.pk)
        results = self.race(
            lambda: approve_membership(actor_id=self.company.user_id, membership_id=membership.pk),
            lambda: withdraw_membership(actor_id=self.passenger.user_id, membership_id=membership.pk),
        )
        self.assertEqual(sorted(result[0] for result in results), ['error', 'ok'])
        self.assertIn(('error', 'membership_not_pending'), results)
        membership.refresh_from_db()
        self.assertIn(membership.status, ['active', 'withdrawn'])
        self.assertEqual(membership.events.count(), 2)
        self.assertEqual(Notification.objects.count(), 2)

    def test_concurrent_group_assignments_leave_one_current_interval(self):
        membership = self.request(self.company.pk)
        approve_membership(actor_id=self.company.user_id, membership_id=membership.pk)
        groups = [create_route_group(self.company, name) for name in ('Grupo A', 'Grupo B')]

        def assign(group):
            # race() recebe um objeto com pk/status; a participação não tem status.
            assign_passenger_group(actor_id=self.company.user_id, membership_id=membership.pk, route_group_id=group.pk)
            return CompanyMembership.objects.get(pk=membership.pk)

        results = self.race(lambda: assign(groups[0]), lambda: assign(groups[1]))
        self.assertEqual([result[0] for result in results], ['ok', 'ok'])
        self.assertEqual(membership.passenger_group_memberships.count(), 2)
        self.assertEqual(membership.passenger_group_memberships.filter(ended_at=None).count(), 1)

    def test_group_assignment_cannot_leave_open_group_after_ending(self):
        membership = self.request(self.company.pk)
        approve_membership(actor_id=self.company.user_id, membership_id=membership.pk)
        group = create_route_group(self.company)

        def assign():
            assign_passenger_group(actor_id=self.company.user_id, membership_id=membership.pk, route_group_id=group.pk)
            return CompanyMembership.objects.get(pk=membership.pk)

        results = self.race(
            assign, lambda: end_membership(actor_id=self.passenger.user_id, membership_id=membership.pk)
        )
        membership.refresh_from_db()
        self.assertEqual(membership.status, 'ended')
        self.assertFalse(membership.passenger_group_memberships.filter(ended_at=None).exists())
        self.assertEqual(results[1][0], 'ok')
        if results[0][0] == 'error':
            self.assertEqual(results[0][1], 'invalid_passenger_membership')
