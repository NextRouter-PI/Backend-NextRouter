import uuid
from datetime import timedelta
from unittest.mock import patch

from django.contrib import admin
from django.test import RequestFactory
from rest_framework.test import APIClient

from modules.organizations.models import Company, CompanyMembership, Driver
from modules.transport.models import ParticipationEvent
from modules.transport.services.demand import withdraw_leg
from modules.transport.services.execution import (
    cancel_day,
    correct_participation,
    finish_travel,
    handle_stop,
    record_participation,
    start_travel,
)
from modules.transport.services.governance import deactivate_account, review_company
from modules.transport.services.invitations import invite_driver, report_unavailability, respond_invitation
from modules.transport.services.maintenance import process_due
from modules.transport.services.planning import calculate_travel
from tests.helpers import create_user

from .service_helpers import ServiceTestCase


class ExecutionServiceTests(ServiceTestCase):
    def start(self, travel):
        travel.refresh_from_db()
        return start_travel(actor_id=self.driver.user_id, travel_id=travel.pk, expected_revision=travel.revision)

    def running(self):
        travel = self.ready_travel()
        self.publish(travel)
        return self.start(travel)

    def test_start_requires_current_publication_and_designated_driver(self):
        travel = self.ready_travel()
        self.assert_domain('publication_outdated', self.start, travel=travel)
        self.publish(travel)
        self.assert_domain(
            'permission_denied',
            start_travel,
            actor_id=self.other.user_id,
            travel_id=travel.pk,
            expected_revision=travel.revision,
        )
        self.assertEqual(self.start(travel).status, 'in_progress')

    def test_start_finish_and_presence_events_are_auditable_and_idempotent(self):
        travel = self.running()
        self.assertEqual(self.start(travel).started_at, travel.started_at)
        participant = travel.participations.get()
        self.assert_domain('pending_participants', finish_travel, actor_id=self.driver.user_id, travel_id=travel.pk)
        boarding_id = uuid.uuid4()
        boarding = record_participation(
            actor_id=self.driver.user_id, participation_id=participant.pk, kind='boarded', operation_id=boarding_id
        )
        repeated = record_participation(
            actor_id=self.driver.user_id, participation_id=participant.pk, kind='boarded', operation_id=boarding_id
        )
        self.assertEqual(boarding.pk, repeated.pk)
        self.assert_domain('passengers_on_board', finish_travel, actor_id=self.driver.user_id, travel_id=travel.pk)
        record_participation(
            actor_id=self.driver.user_id, participation_id=participant.pk, kind='dropped_off', operation_id=uuid.uuid4()
        )
        result = finish_travel(actor_id=self.driver.user_id, travel_id=travel.pk)
        self.assertEqual(result.status, 'finished')
        self.assertIsNone(result.current_latitude)
        self.assertEqual(
            result.finished_at, finish_travel(actor_id=self.driver.user_id, travel_id=travel.pk).finished_at
        )

    def test_no_show_is_distinct_from_boarding_and_allows_finish(self):
        travel = self.running()
        participant = travel.participations.get()
        record_participation(
            actor_id=self.driver.user_id, participation_id=participant.pk, kind='no_show', operation_id=uuid.uuid4()
        )
        participant.refresh_from_db()
        self.assertIsNone(participant.boarded_at)
        self.assertEqual(finish_travel(actor_id=self.driver.user_id, travel_id=travel.pk).status, 'finished')

    def test_same_passenger_cannot_be_boarded_in_two_travels_at_once(self):
        from modules.transport.models import Vehicle
        from modules.transport.services.calendar import generate_day

        driver = Driver.objects.create(user=create_user('second-operation-driver@example.com'))
        membership = CompanyMembership.objects.create(
            company=self.company,
            driver=driver,
            status='active',
            requested_by=driver.user,
            reviewed_by=self.company.user,
            created_at=self.now,
            reviewed_at=self.now,
        )
        self.returning.driver_membership = membership
        self.returning.vehicle = Vehicle.objects.create(
            company=self.company, plate='MNO5H67', capacity=2, garage_point=self.garage
        )
        self.returning.save(update_fields=['driver_membership', 'vehicle'])
        generate_day(actor_id=self.company.user_id, group_id=self.group.pk, date=self.date)
        self.answer(returning=True)
        self.close()
        self.process_jobs()
        outbound, returning = self.travel(), self.travel(self.returning)
        self.publish(outbound)
        self.publish(returning)
        self.start(outbound)
        start_travel(actor_id=driver.user_id, travel_id=returning.pk, expected_revision=returning.revision)
        record_participation(
            actor_id=self.driver.user_id,
            participation_id=outbound.participations.get().pk,
            kind='boarded',
            operation_id=uuid.uuid4(),
        )
        self.assert_domain(
            'already_on_board',
            record_participation,
            actor_id=driver.user_id,
            participation_id=returning.participations.get().pk,
            kind='boarded',
            operation_id=uuid.uuid4(),
        )

    def test_withdrawal_after_start_does_not_rewrite_active_snapshot(self):
        travel = self.running()
        snapshot_id, revision = travel.current_snapshot_id, travel.revision
        withdraw_leg(actor_id=self.passenger.user_id, eligibility_id=self.eligibility.pk, leg='outbound')
        travel.refresh_from_db()
        self.assertEqual((travel.current_snapshot_id, travel.revision), (snapshot_id, revision))
        self.assertEqual(travel.status, 'in_progress')
        self.assertEqual(travel.participations.get().status, 'withdrawn')
        finish_travel(actor_id=self.driver.user_id, travel_id=travel.pk)

    def test_withdrawal_after_boarding_is_denied(self):
        travel = self.running()
        participant = travel.participations.get()
        record_participation(
            actor_id=self.driver.user_id, participation_id=participant.pk, kind='boarded', operation_id=uuid.uuid4()
        )
        self.assert_domain(
            'already_boarded',
            withdraw_leg,
            actor_id=self.passenger.user_id,
            eligibility_id=self.eligibility.pk,
            leg='outbound',
        )

    def test_only_company_can_correct_and_original_event_remains(self):
        travel = self.running()
        participant = travel.participations.get()
        event = record_participation(
            actor_id=self.driver.user_id, participation_id=participant.pk, kind='boarded', operation_id=uuid.uuid4()
        )
        args = {
            'participation_id': participant.pk,
            'corrects_event_id': event.pk,
            'target_status': 'no_show',
            'reason': 'Marcação equivocada fictícia',
            'operation_id': uuid.uuid4(),
        }
        self.assert_domain('permission_denied', correct_participation, actor_id=self.driver.user_id, **args)
        correction = correct_participation(actor_id=self.company.user_id, **args)
        self.assertEqual(correction.pk, correct_participation(actor_id=self.company.user_id, **args).pk)
        self.assertTrue(ParticipationEvent.objects.filter(pk=event.pk, kind='boarded').exists())
        participant.refresh_from_db()
        self.assertEqual(participant.status, 'no_show')
        self.assertIsNone(participant.boarded_at)
        finish_travel(actor_id=self.driver.user_id, travel_id=travel.pk)

    def test_correction_requires_reason_and_current_event(self):
        travel = self.running()
        participant = travel.participations.get()
        allocation = participant.events.get(kind='allocated')
        boarding = record_participation(
            actor_id=self.driver.user_id, participation_id=participant.pk, kind='boarded', operation_id=uuid.uuid4()
        )
        args = {
            'actor_id': self.company.user_id,
            'participation_id': participant.pk,
            'corrects_event_id': boarding.pk,
            'target_status': 'no_show',
            'operation_id': uuid.uuid4(),
        }
        self.assert_domain('reason_required', correct_participation, **args, reason='')
        self.assert_domain(
            'stale_event',
            correct_participation,
            **{**args, 'corrects_event_id': allocation.pk},
            reason='Correção fictícia',
        )

    def test_cancel_day_preserves_started_trip_and_cancels_only_pending(self):
        travel = self.running()
        result = cancel_day(actor_id=self.company.user_id, day_id=self.day.pk, reason='Cancelamento parcial fictício')
        self.assertTrue(result['partial'])
        self.assertEqual(result['preserved_travel_ids'], [travel.pk])
        travel.refresh_from_db()
        self.assertEqual(travel.status, 'in_progress')
        self.assertEqual(self.travel(self.returning).status, 'canceled')
        withdraw_leg(actor_id=self.passenger.user_id, eligibility_id=self.eligibility.pk, leg='outbound')
        finish_travel(actor_id=self.driver.user_id, travel_id=travel.pk)

    def test_normal_recalculation_cannot_mutate_running_trip(self):
        travel = self.running()
        self.assert_domain(
            'travel_not_scheduled',
            calculate_travel,
            actor_id=self.company.user_id,
            travel_id=travel.pk,
            expected_revision=travel.revision,
        )

    def test_publication_revalidates_aggregate_capacity(self):
        travel = self.ready_travel()
        self.vehicle.status = 'maintenance'
        self.vehicle.save(update_fields=['status'])
        self.assert_domain('vehicle_unavailable', self.publish, travel=travel)

    def test_stop_order_and_individual_events_are_not_gps(self):
        travel = self.running()
        first, last = list(travel.current_snapshot.stops.order_by('position'))
        self.assert_domain('stop_out_of_order', handle_stop, actor_id=self.driver.user_id, stop_id=last.pk)
        self.assert_domain('pending_participants', handle_stop, actor_id=self.driver.user_id, stop_id=first.pk)
        participant = travel.participations.get()
        record_participation(
            actor_id=self.driver.user_id, participation_id=participant.pk, kind='boarded', operation_id=uuid.uuid4()
        )
        handle_stop(actor_id=self.driver.user_id, stop_id=first.pk)
        record_participation(
            actor_id=self.driver.user_id, participation_id=participant.pk, kind='dropped_off', operation_id=uuid.uuid4()
        )
        self.assertEqual(handle_stop(actor_id=self.driver.user_id, stop_id=last.pk).state, 'completed')

    def test_operation_blocks_company_disapproval_and_account_deactivation(self):
        self.running()
        moderator = create_user('operation-moderator@example.com', is_staff=True)
        self.assert_domain(
            'operation_in_progress', review_company, actor_id=moderator.pk, company_id=self.company.pk, approve=False
        )
        for user_id in (self.passenger.user_id, self.driver.user_id, self.company.user_id):
            self.assert_domain('operation_in_progress', deactivate_account, actor_id=user_id, user_id=user_id)
        self.company.refresh_from_db()
        self.assertTrue(self.company.is_approved)

    def test_http_deactivation_uses_same_guard(self):
        self.running()
        client = APIClient()
        moderator = create_user('deactivation-moderator@example.com', is_staff=True)
        client.force_authenticate(moderator)
        response = client.delete(f'/api/users/{self.passenger.user_id}/')
        self.assertEqual(response.status_code, 400)
        self.passenger.user.refresh_from_db()
        self.assertTrue(self.passenger.user.is_active)

    def test_admin_company_review_uses_same_guard(self):
        self.running()
        moderator = create_user('review-moderator@example.com', is_staff=True, is_superuser=True)
        request = RequestFactory().post('/admin/')
        request.user = moderator
        model_admin = admin.site._registry[Company]
        with patch.object(model_admin, 'message_user') as message:
            model_admin.reject_companies(request, Company.objects.filter(pk=self.company.pk))
        self.assertTrue(message.called)
        self.company.refresh_from_db()
        self.assertTrue(self.company.is_approved)


class InvitationServiceTests(ServiceTestCase):
    def substitute(self):
        driver = Driver.objects.create(user=create_user('substitute-operation@example.com'))
        return CompanyMembership.objects.create(
            company=self.company,
            driver=driver,
            status='active',
            requested_by=driver.user,
            created_at=self.now,
            reviewed_by=self.company.user,
            reviewed_at=self.now,
        )

    def test_substitute_requires_explicit_acceptance_and_recalculation(self):
        travel = self.ready_travel()
        replacement = self.substitute()
        report_unavailability(actor_id=self.driver.user_id, travel_id=travel.pk, operation_id=uuid.uuid4())
        invitation = invite_driver(
            actor_id=self.company.user_id,
            travel_id=travel.pk,
            driver_membership_id=replacement.pk,
            expires_at=self.now + timedelta(hours=1),
        )
        travel.refresh_from_db()
        self.assertIsNone(travel.driver_id)
        respond_invitation(actor_id=replacement.driver.user_id, invitation_id=invitation.pk, accept=True)
        travel.refresh_from_db()
        self.assertEqual(travel.driver_id, replacement.driver_id)
        self.assertEqual(travel.planning_status, 'draft')
        calculate_travel(actor_id=self.company.user_id, travel_id=travel.pk, expected_revision=travel.revision)
        self.process_jobs()
        self.publish(travel)
        travel.refresh_from_db()
        self.assertEqual(
            start_travel(
                actor_id=replacement.driver.user_id, travel_id=travel.pk, expected_revision=travel.revision
            ).status,
            'in_progress',
        )

    def test_expired_or_replaced_invitation_never_means_acceptance(self):
        replacement = self.substitute()
        travel = self.travel()
        first = invite_driver(
            actor_id=self.company.user_id,
            travel_id=travel.pk,
            driver_membership_id=replacement.pk,
            expires_at=self.now + timedelta(hours=1),
        )
        second = invite_driver(
            actor_id=self.company.user_id,
            travel_id=travel.pk,
            driver_membership_id=replacement.pk,
            expires_at=self.now + timedelta(hours=2),
        )
        self.assert_domain(
            'invitation_not_current',
            respond_invitation,
            actor_id=replacement.driver.user_id,
            invitation_id=first.pk,
            accept=True,
        )
        self.now += timedelta(hours=2)
        self.assert_domain(
            'invitation_expired',
            respond_invitation,
            actor_id=replacement.driver.user_id,
            invitation_id=second.pk,
            accept=True,
        )
        process_due(actor_id=self.company.user_id, company_id=self.company.pk, batch_size=10)
        second.refresh_from_db()
        self.assertEqual(second.status, 'expired')
        self.assertIsNone(self.travel().driver_id)

    def test_other_driver_cannot_accept_invitation(self):
        replacement = self.substitute()
        invitation = invite_driver(
            actor_id=self.company.user_id,
            travel_id=self.travel().pk,
            driver_membership_id=replacement.pk,
            expires_at=self.now + timedelta(hours=1),
        )
        self.assert_domain(
            'permission_denied',
            respond_invitation,
            actor_id=self.driver.user_id,
            invitation_id=invitation.pk,
            accept=True,
        )
